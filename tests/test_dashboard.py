import hashlib
import http.client
import json
import re
import shutil
import threading
from pathlib import Path

import pytest

from invoiceguard import dashboard_server as ds
from invoiceguard.dashboard import build_html, collect, parse_decision, parse_kv, parse_task_board
from invoiceguard.public_data import shard_paths

REPO = Path(__file__).resolve().parents[1]
TRADE_MANIFEST = REPO / "manifests" / "trade_raw_v1.jsonl"
PUBLIC_MANIFEST = REPO / "manifests" / "public_canonical_v1.jsonl"
TRADE_DATA = REPO / "data" / "processed" / "trade"
TEST_CACHE = REPO / "artifacts" / "test_dashboard_cache"  # git-ignored; never the system temp dir


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------- static snapshot (dashboard.py)
def test_task_board_parsed_from_real_report():
    tasks, gates = parse_task_board((REPO / "reports" / "TASK_BOARD.md").read_text(encoding="utf-8"))
    assert [t["id"] for t in tasks] == [f"T0{i}" for i in range(10)]
    assert [g["id"] for g in gates] == [f"G{i}" for i in range(8)]


def test_approval_form_defaults_to_not_approved():
    kv = parse_kv((REPO / "reports" / "RUNPOD_APPROVAL.md").read_text(encoding="utf-8"))
    assert kv["approved"] == "false" and kv["auto_top_up_authorized"] == "false"


def test_dashboard_escapes_untrusted_text_and_shows_not_run():
    data = collect(REPO / "artifacts" / "does-not-exist" / "junit.xml")
    data["tasks"][0]["evidence"] = "<script>alert(1)</script>"
    page = build_html(data)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "http://" not in page and "https://" not in page  # self-contained, no external fetches
    data["final_evals"] = {}
    assert build_html(data).count("미실행") >= 9  # without scoring files every model cell stays not_run


def test_snapshot_model_table_comes_from_final_scoring_files():
    data = collect(REPO / "artifacts" / "does-not-exist" / "junit.xml")
    for arm, run in data["final_evals"].items():
        assert run["run_id"].startswith(arm + "_final")
        cell = f"{run['headline']['trade:test']['fields_acc']:.3f}"
        assert cell in build_html(data)


def test_gate_status_suffix_is_normalised():
    _, gates = parse_task_board("| G3 x | partial: local only |\n| G0 y | pass (scope) |\n| G7 z | pass (local): backup ok |\n")
    assert [(g["status"], g["detail"]) for g in gates] == [("partial", "local only"), ("pass", "scope"), ("pass", "local: backup ok")]


def test_user_decision_paragraph_is_read_from_the_handoff():
    text = "- push: x\n\n## 사용자 결정 (2026-11-14, 종료 후)\nRunPod를 **쓰지 않기로** 결정.\n두 번째 줄.\n\n## 재개 시\n1. a\n"
    assert parse_decision(text) == "RunPod를 **쓰지 않기로** 결정. 두 번째 줄."
    assert parse_decision("- push: x\n") is None
    real = parse_decision((REPO / "reports" / "SESSION_HANDOFF.md").read_text(encoding="utf-8"))
    assert real and "RunPod" in real


# ---------------------------------------------------------------------- server: bind + static page
def test_server_binds_loopback_only_by_default():
    server = ds.make_server(0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()
    for host in ("0.0.0.0", "", "::", "192.168.0.10"):
        with pytest.raises(ValueError):
            ds.make_server(0, host=host)
    launch = json.loads((REPO / ".claude" / "launch.json").read_text(encoding="utf-8"))
    cfg = next(c for c in launch["configurations"] if c["name"] == "admin-dashboard")
    assert "invoiceguard.dashboard_server" in cfg["runtimeArgs"] and cfg["port"] == 8765
    assert "0.0.0.0" not in json.dumps(cfg)


def test_static_page_has_no_external_urls_and_no_markup_sinks():
    for name in ("index.html", "app.js", "app.css", "theme.js"):
        text = (ds.STATIC_DIR / name).read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text and "//cdn" not in text, name
    for script in ("app.js", "theme.js"):
        js = (ds.STATIC_DIR / script).read_text(encoding="utf-8")
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert sink not in js, (script, sink)
    html = (ds.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert set(re.findall(r'(?:src|href)="([^"#]+)"', html)) == {"/static/app.css", "/static/app.js", "/static/theme.js",
                                                                "/static/favicon.svg"}
    for label in ("개요", "진행 단계·게이트", "공개 데이터", "자체 Invoice–PO", "분할·manifest", "모델·평가",
                  "서빙", "검수 API", "테스트", "클라우드·비용"):
        assert label in html
    js = (ds.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    for page in re.findall(r'data-page="(\w+)"', html):
        assert re.search(rf"\b{page}: page\w+", js), page  # every sidebar entry has a route


def test_favicon_is_a_plain_svg_without_scripts_or_links():
    svg = (ds.STATIC_DIR / "favicon.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "<script" not in svg and "href" not in svg and "foreignObject" not in svg
    assert re.findall(r"https?://[^\"]+", svg) == ["http://www.w3.org/2000/svg"]  # namespace only, nothing fetched


def test_local_smoke_values_are_flattened_raw_not_interpreted():
    pairs = ds._flatten({"kind": "x", "env": {"gpu": "<script>alert(1)</script>"}, "rows": [{"a": 1}], "pass": True})
    assert pairs == [["kind", "x"], ["env.gpu", "<script>alert(1)</script>"], ["rows", '[{"a": 1}]'], ["pass", "true"]]
    status = ds.status_body(ds.DataStore())
    assert isinstance(status["local_smoke"], list)
    assert all(f["path"].startswith("reports/model/local_smoke") for f in status["local_smoke"])


# ---------------------------------------------------------------------- server: live HTTP
@pytest.fixture(scope="module")
def server():
    store = ds.DataStore()
    store.cache_dir = TEST_CACHE
    shutil.rmtree(TEST_CACHE, ignore_errors=True)
    srv = ds.make_server(0, store=store)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    shutil.rmtree(TEST_CACHE, ignore_errors=True)


def _get(srv, path: str, method: str = "GET", host: str | None = None):
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host or f"127.0.0.1:{port}")
        conn.endheaders()
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def test_index_served_with_csp_and_status_is_json(server):
    status, headers, body = _get(server, "/")
    assert status == 200 and b"/static/app.js" in body
    assert "default-src 'none'" in headers["Content-Security-Policy"] and headers["X-Content-Type-Options"] == "nosniff"
    status, headers, body = _get(server, "/api/status")
    assert status == 200 and headers["Content-Type"].startswith("application/json")
    data = json.loads(body)
    assert [t["id"] for t in data["tasks"]] == [f"T0{i}" for i in range(10)]
    assert {"status_ko", "status_class", "visibility_ko"} <= set(data["labels"])


@pytest.mark.parametrize("path", [
    "/api/trade/doc/../../pyproject.toml",
    "/api/trade/image/..%2f..%2fpyproject.toml",
    "/api/trade/image/tr_24EE16EB748A",
    "/api/trade/doc/tr_000000000000",          # well-formed but not in the manifest
    "/api/public/image/synth_0000_8a064d3a.png/..%2f..%2fCLAUDE.md",
    "/api/public/image/synth_0000_8a064d3a.png/original",
    "/api/public/doc/synth_9999_00000000.png",
    "/api/public/doc/C:%5CWindows%5Cwin.ini",
    "/static/../pyproject.toml",
    "/static/app.js/../../CLAUDE.md",
    "/CLAUDE.md",
    "/manifests/trade_raw_v1.jsonl",
])
def test_path_traversal_and_unknown_ids_rejected(server, path):
    status, headers, body = _get(server, path)
    assert status == 404 and headers["Content-Type"].startswith("application/json")
    assert json.loads(body)["error"] in {"not_found", "unknown_id"}


@pytest.mark.parametrize("path", [
    "/api/public/rows?pool=..%2F..%2Fx",
    "/api/public/rows?path=C:/Windows/win.ini",
    "/api/public/rows?limit=100000",
    "/api/public/rows?q=%3Cscript%3E",
    "/api/trade/rows?split=train&split=test",
    "/api/trade/doc/tr_24ee16eb748a?file=../../x",
    "/api/public/doc/synth_0000_8a064d3a.png?quality=..%2Fx",
])
def test_bad_query_params_rejected(server, path):
    status, _, body = _get(server, path)
    assert status == 400 and json.loads(body)["error"] in {"bad_param", "unknown_param"}


def test_read_only_and_host_guard(server):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        assert _get(server, "/api/status", method=method)[0] == 405
    assert _get(server, "/api/status", host="evil.example")[0] == 400  # DNS-rebinding guard
    assert _get(server, "/api/status", host=f"localhost:{server.server_address[1]}")[0] == 200


def test_list_filters_match_manifest_counts(server):
    trade = _jsonl(TRADE_MANIFEST)
    status, _, body = _get(server, "/api/trade/rows?split=test&limit=5")
    data = json.loads(body)
    assert status == 200 and data["total"] == sum(r["split"] == "test" for r in trade) and len(data["page"]) == 5
    assert not {"gold", "po", "items"} & set(data["page"][0])
    public = _jsonl(PUBLIC_MANIFEST)
    status, _, body = _get(server, "/api/public/rows?template=pos_thermal&quality=clean&eligible=false")
    data = json.loads(body)
    expected = sum(r["template"] == "pos_thermal" and r["quality"] == "clean" and not r["train_eligible"] for r in public)
    assert status == 200 and data["total"] == expected
    assert all(not r["train_eligible"] and r["train_ineligible_reason"] for r in data["page"])


@pytest.mark.skipif(not (TRADE_DATA / "gold").is_dir(), reason="local trade data not generated")
def test_trade_doc_endpoint_returns_gold_po_findings_and_png(server):
    row = next(r for r in _jsonl(TRADE_MANIFEST) if r["expected_codes"])
    status, _, body = _get(server, f"/api/trade/doc/{row['doc_id']}")
    data = json.loads(body)
    assert status == 200 and data["meta"]["doc_id"] == row["doc_id"]
    assert data["gold"]["items"] and data["po"]["items"]
    assert data["integrity"] == {"gold": True, "po": True, "image": True}
    assert data["oracle"]["source"] == "oracle_fixture" and data["codes_match"] is True
    assert data["expected_codes"] == sorted(row["expected_codes"])
    status, headers, png = _get(server, f"/api/trade/image/{row['doc_id']}")
    assert status == 200 and headers["Content-Type"] == "image/png" and png.startswith(b"\x89PNG")
    assert hashlib.sha256(png).hexdigest() == row["image_sha256"]


@pytest.mark.skipif(not all(p.exists() for p in shard_paths(REPO)), reason="public parquet shards not downloaded")
def test_public_doc_and_image_endpoints(server):
    row = next(r for r in _jsonl(PUBLIC_MANIFEST) if r["n_masked_fields"] and r["quality"] == "bad_scan")
    status, _, body = _get(server, f"/api/public/doc/{row['base_id']}?quality=bad_scan")
    data = json.loads(body)
    assert status == 200 and data["quality"] == "bad_scan" and data["gold"]["available"]
    items = data["gold"]["items"]
    assert len(items) == row["n_items"] and [it["visibility"] for it in items] == row["visibility"]
    assert {q["quality"] for q in data["qualities"]} == {"clean", "faded", "bad_scan"}
    assert not any("sku" in key for it in items for key in it)  # PUBLIC_CANONICAL has no SKU labels
    cached = TEST_CACHE / "bad_scan" / row["base_id"]
    assert not cached.exists()
    status, headers, png = _get(server, f"/api/public/image/{row['base_id']}/bad_scan")
    assert status == 200 and headers["Content-Type"] == "image/png"
    assert hashlib.sha256(png).hexdigest() == row["image_sha256"] and cached.exists()
    assert _get(server, f"/api/public/image/{row['base_id']}/bad_scan")[2] == png  # served from cache



def test_theme_is_dark_by_default_with_a_light_toggle():
    html = (ds.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (ds.STATIC_DIR / "app.css").read_text(encoding="utf-8")
    js = (ds.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    theme = (ds.STATIC_DIR / "theme.js").read_text(encoding="utf-8")
    assert 'id="themetoggle"' in html and '<html lang="ko" data-theme="dark">' in html
    assert html.index("/static/theme.js") < html.index("/static/app.css")  # applied before first paint
    root = css[css.index(":root{"):css.index("}", css.index(":root{"))]
    assert "color-scheme:dark" in root and ':root[data-theme="light"]' in css  # dark tokens are the base
    assert "prefers-color-scheme" not in css  # the OS setting no longer picks the theme
    assert 'var theme = "dark"' in theme and '=== "light"' in theme  # only an explicit light choice changes it
    assert "localStorage" in js and "try {" in js and "try {" in theme  # remembered, but never required


def test_theme_script_and_favicon_are_served(server):
    status, headers, body = _get(server, "/static/theme.js")
    assert status == 200 and headers["Content-Type"].startswith("text/javascript") and b"ig-theme" in body
    for path in ("/static/favicon.svg", "/favicon.ico"):
        status, headers, body = _get(server, path)
        assert status == 200 and headers["Content-Type"] == "image/svg+xml" and body.startswith(b"<svg")


def test_status_carries_recorded_serving_and_training_runs(server):
    data = json.loads(_get(server, "/api/status")[2])
    assert set(data["serving"]) >= {"hf_peft_nf4_local", "hf_cancel_probe", "live_e2e_demo"}
    assert data["serving"]["hf_cancel_probe"]["timeout_cancel_test"]["http_status"] == 504
    train = data["model_reports"]["train_m1_standard_v1.json"]
    finals = {e["run_id"]: e for e in data["evaluations"] if e["stage"] == "final"}
    assert finals["m1_final_v1"]["adapter_sha256"] == train["adapter_files_sha256"]["adapter_model.safetensors"]
    assert all(g["status"] in data["labels"]["status_ko"] for g in data["gates"])
    assert data["handoff_decision"] and not data["errors"]
