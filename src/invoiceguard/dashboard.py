"""Read-only admin/operations dashboard (Korean UI), generated from the project's own records.

Usage: python -m invoiceguard.dashboard [--run-tests] [--out artifacts/dashboard/index.html]

It renders what the reports, manifests and config say — nothing more. Missing evidence is
shown as not_run / blocked / unknown; it never fabricates GPU, billing or model results.
Self-contained HTML (no CDN, no network); every value is HTML-escaped.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
E = html.escape

STATUS_CLASS = {
    "passed_with_evidence": "ok", "pass": "ok", "completed": "ok",
    "in_progress": "run", "not_started": "idle", "not_run": "idle", "not_implemented": "idle",
    "blocked": "warn", "failed": "bad", "unknown": "warn",
}
STATUS_KO = {
    "passed_with_evidence": "증거 있음 통과", "pass": "통과", "in_progress": "진행 중", "not_started": "시작 전",
    "not_run": "미실행", "blocked": "차단", "failed": "실패", "not_implemented": "미구현", "unknown": "미확인",
}


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _json(path: Path) -> Any:
    text = _read(path)
    return json.loads(text) if text else None


def parse_task_board(text: str) -> tuple[list[dict], list[dict]]:
    tasks, gates = [], []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.fullmatch(r"T0\d", cells[0]) and len(cells) >= 5:
            tasks.append({"id": cells[0], "name": cells[1], "where": cells[2], "status": cells[3], "evidence": cells[4]})
        elif re.match(r"G\d ", cells[0]) and len(cells) >= 2:
            status = cells[1].split(" ")[0]
            gates.append({"id": cells[0][:2], "name": cells[0][3:], "status": status, "detail": cells[1][len(status):].strip(" ()")})
    return tasks, gates


def parse_kv(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = re.match(r"^- ([\w /]+?):\s*(.*)$", line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def run_tests(junit: Path) -> None:
    junit.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"], cwd=REPO, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_junit(path: Path) -> dict | None:
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    by_file: Counter = Counter()
    failed: Counter = Counter()
    for case in suite.iter("testcase"):
        name = case.get("classname", "").split(".")[-1] or "?"
        by_file[name] += 1
        if case.find("failure") is not None or case.find("error") is not None:
            failed[name] += 1
    return {"tests": int(suite.get("tests", 0)), "failures": int(suite.get("failures", 0)),
            "errors": int(suite.get("errors", 0)), "skipped": int(suite.get("skipped", 0)),
            "time": suite.get("time"), "timestamp": suite.get("timestamp"),
            "by_file": dict(sorted(by_file.items())), "failed_by_file": dict(failed),
            "mtime": dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}


# ----------------------------------------------------------------------------- html pieces
def pill(status: str) -> str:
    cls = STATUS_CLASS.get(status, "idle")
    return f'<span class="pill {cls}">{E(STATUS_KO.get(status, status))}</span>'


def bar_rows(counts: dict[str, int], total: int | None = None) -> str:
    total = total or max(1, sum(counts.values()))
    rows = []
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        pct = 100 * v / total
        rows.append(f'<div class="bar"><span class="bl">{E(str(k))}</span><span class="bt"><i style="width:{pct:.1f}%"></i></span>'
                    f'<span class="bv">{v}</span></div>')
    return "".join(rows)


def kv_table(pairs: list[tuple[str, str]]) -> str:
    return '<table class="kv">' + "".join(f"<tr><th>{E(k)}</th><td>{v}</td></tr>" for k, v in pairs) + "</table>"


def build_html(data: dict) -> str:
    tasks, gates = data["tasks"], data["gates"]
    done = sum(t["status"] == "passed_with_evidence" for t in tasks)
    cfg = data["config"]["hardware"]
    approval = data["approval"]
    handoff = data["handoff"]
    junit = data["junit"]
    pub, pubm, trade = data["public_profile"], data["public_manifest"], data["trade_manifest"]

    # --- KPI row
    kpis = [
        ("진행 단계", f"{done}/{len(tasks)}", "증거로 통과한 T단계"),
        ("인수 게이트", f"{sum(g['status'] == 'pass' for g in gates)}/{len(gates)}", "G0–G7 중 통과"),
        ("CPU 테스트", f"{junit['tests'] - junit['failures'] - junit['errors']}/{junit['tests']}" if junit else "—",
         f"pytest 통과 · {junit['mtime']}" if junit else "--run-tests로 실행"),
        ("클라우드 지출", "$0.00" if handoff.get("actual_spend_from_this_package", "").startswith("$0") else "미확인",
         "이 프로젝트가 만든 RunPod 리소스 없음" if "none_created" in handoff.get("active_pods_from_this_package", "") else "확인 필요"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="kl">{E(a)}</div><div class="kn">{E(b)}</div><div class="ks">{E(c)}</div></div>'
                       for a, b, c in kpis)

    task_rows = "".join(
        f"<tr><td class='mono'>{E(t['id'])}</td><td>{E(t['name'])}<div class='sub'>{E(t['evidence'])}</div></td>"
        f"<td>{E(t['where'])}</td><td>{pill(t['status'])}</td></tr>" for t in tasks)
    gate_rows = "".join(f"<li>{pill(g['status'])}<b class='mono'>{E(g['id'])}</b> {E(g['name'])}"
                        f"{'<div class=sub>' + E(g['detail']) + '</div>' if g['detail'] else ''}</li>" for g in gates)

    # --- budget (planned caps vs verified spend)
    gpu_cap, other_cap, reserve = cfg["gpu_compute_budget_usd"], cfg["storage_and_shutdown_budget_usd"], cfg["reserve_usd"]
    total = cfg["prepaid_balance_usd_user_reported"]
    budget = (f'<div class="stack"><i class="gpu" style="width:{100 * gpu_cap / total:.0f}%">GPU ${gpu_cap:g}</i>'
              f'<i class="oth" style="width:{100 * other_cap / total:.0f}%">기타 ${other_cap:g}</i>'
              f'<i class="res" style="width:{100 * reserve / total:.0f}%">여유 ${reserve:g}</i></div>'
              f'<div class="sub">계획 배분 (사용자 보고 잔액 약 ${total:g}, 계정 잔액 미검증). 계산기는 과금 차단 장치가 아님.</div>')
    approval_pairs = [
        ("이번 실행 승인", pill("pass") if approval.get("approved") == "true" else '<span class="pill warn">승인 없음</span>'),
        ("실제 잔액", E(approval.get("actual_balance_usd", "null")).replace("null", "미확인")),
        ("콘솔 GPU 단가", E(approval.get("gpu_rate_usd_per_hour", "null")).replace("null", "미확인")),
        ("이 프로젝트의 활성 Pod", E(handoff.get("active_pods_from_this_package", "unknown"))),
        ("계정 전체 과금 리소스", E(handoff.get("actual_account_active_resources", "unknown"))),
        ("FullSSH 파일 왕복", pill("pass") if approval.get("full_ssh_file_roundtrip_verified") == "true" else pill("not_run")),
        ("자동 충전 허용", E(approval.get("auto_top_up_authorized", "false"))),
    ]

    # --- data
    data_html = ""
    if pub:
        c = pub["counts"]
        data_html += (f"<h3>공개 InvoiceOCR-Synth <span class='tag'>합성·영어·SKU 정답 없음</span></h3>"
                      + kv_table([("revision", f"<span class='mono'>{E(pub['revision'][:12])}</span>"),
                                  ("행 / base", f"{c['rows_actual']:,} / {c['base_documents_actual']:,} (게시자 주장과 일치)"),
                                  ("자동 검사", " ".join(pill("pass" if v["pass"] else "failed") + f" <small>{E(k)}</small>"
                                                       for k, v in pub["checks"].items()))])
                      + "<div class='two'><div><div class='cap'>템플릿별 base 문서</div>" + bar_rows(c["templates_base_docs"]) + "</div>")
    if pubm:
        data_html += ("<div><div class='cap'>분할 pool (base)</div>" + bar_rows(pubm["pool_base_docs"])
                      + f"<div class='sub'>manifest <span class='mono'>{E(pubm['sha256'][:16])}…</span> · 누수 검사 "
                      + ("통과" if pubm["checks"]["pass"] else "실패") + "</div></div></div>")
        roles = pubm["profiles"]["standard"]["image_rows_by_role"]
        mini = pubm["profiles"]["mini"]["image_rows_by_role"]
        data_html += ("<table class='grid'><tr><th>역할</th><th>standard 이미지</th><th>mini 이미지</th><th>채점 필드(standard)</th><th>마스크 필드</th></tr>"
                      + "".join(f"<tr><td>{E(r)}</td><td>{roles.get(r, 0)}</td><td>{mini.get(r, 0)}</td>"
                                f"<td>{pubm['profiles']['standard']['scored_fields_by_role'].get(r, 0)}</td>"
                                f"<td>{pubm['profiles']['standard']['masked_fields_by_role'].get(r, 0)}</td></tr>"
                                for r in ("train", "dev", "dev_stress", "iid_final", "ood_final"))
                      + "</table><div class='sub'>프로필(standard/mini)은 훈련 전용 파일럿 후 한 번 선택·동결 — 현재 "
                      + ("동결됨" if pubm.get("frozen") else "미동결") + "</div>")
    if trade:
        types = list(next(iter(trade["type_by_template"].values())).keys())
        head = "".join(f"<th>{E(t)}</th>" for t in types)
        body = ""
        for split, by_type in trade["type_by_template"].items():
            templates = sorted({tpl for v in by_type.values() for tpl in v})
            for tpl in templates:
                body += f"<tr><td>{E(split)}</td><td class='mono'>{E(tpl)}</td>" + "".join(
                    f"<td>{by_type[t].get(tpl, 0) or '·'}</td>" for t in types) + "</tr>"
        data_html += (f"<h3>자체 영어 Invoice–PO <span class='tag'>합성·가상 회사</span></h3>"
                      + kv_table([("문서", f"{trade['documents']} (train/dev/test = "
                                         + " / ".join(str(trade['by_split'].get(s, 0)) for s in ('train', 'dev', 'test')) + ")"),
                                  ("렌더=정답 검사", pill("pass" if trade["checks"]["all_render_checks_pass"] else "failed")),
                                  ("family 누수 / 레이아웃 holdout", pill("pass" if trade["checks"]["pass"] else "failed")),
                                  ("manifest", f"<span class='mono'>{E(trade['sha256'][:16])}…</span>")])
                      + f"<table class='grid small'><tr><th>split</th><th>layout</th>{head}</tr>{body}</table>")

    # --- tests
    if junit:
        test_html = ("<div class='bars'>" + bar_rows(junit["by_file"]) + "</div>"
                     + f"<div class='sub'>실패 {junit['failures']} · 오류 {junit['errors']} · 건너뜀 {junit['skipped']} · {E(str(junit['time']))}s. "
                     "CPU 기능 테스트(application_cpu_test)이며 모델·GPU 결과가 아님.</div>")
    else:
        test_html = "<p class='sub'>테스트 결과 파일 없음 — <code>python -m invoiceguard.dashboard --run-tests</code></p>"

    # --- model results matrix
    results = data["results"] or {}
    matrix = "".join(f"<tr><td class='mono'>{m}</td>" + "".join(f"<td>{pill('not_run')}</td>" for _ in range(3)) + "</tr>"
                     for m in ("M0 base (NF4)", "M1 adapter (NF4)"))
    model_html = (f"<table class='grid'><tr><th>모델</th><th>public IID final</th><th>public OOD final</th><th>trade final</th></tr>{matrix}</table>"
                  f"<div class='sub'>결과 파일 상태: <b>{E(results.get('status', 'not_run'))}</b>. 실제 RunPod 추론 전에는 모든 수치가 비어 있음.</div>")

    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>InvoiceGuard 관리자</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--mute:#667085;--line:#e4e7ec;--acc:#2f5bd3;
--ok:#1f7a4d;--okb:#e3f4ea;--run:#2f5bd3;--runb:#e6edfc;--warn:#9a6200;--warnb:#fdf1d8;--bad:#b42318;--badb:#fde5e3;--idle:#5d6677;--idleb:#eef0f3}}
@media (prefers-color-scheme:dark){{:root{{--bg:#11141a;--card:#1a1f27;--ink:#e6e9ef;--mute:#98a2b3;--line:#2a313c;--acc:#7ea2ff;
--ok:#6fd39c;--okb:#173326;--run:#9db7ff;--runb:#1d2a4a;--warn:#f4c46b;--warnb:#3a2d12;--bad:#ff8a80;--badb:#3d1b19;--idle:#aab3c2;--idleb:#252b35}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Segoe UI","Malgun Gothic",system-ui,sans-serif}}
header{{padding:22px 28px 10px;max-width:1280px;margin:auto}}h1{{font-size:20px;margin:0}}.meta{{color:var(--mute);font-size:12.5px}}
.banner{{margin:12px 0 0;padding:10px 14px;border-radius:10px;background:var(--warnb);color:var(--warn);font-size:13px}}
main{{max-width:1280px;margin:auto;padding:8px 28px 40px;display:grid;gap:16px;grid-template-columns:repeat(12,1fr)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;grid-column:span 12;min-width:0}}
.half{{grid-column:span 6}}.third{{grid-column:span 4}}.wide{{grid-column:span 8}}
@media (max-width:900px){{.half,.third,.wide{{grid-column:span 12}}main{{padding:8px 16px 32px}}header{{padding:18px 16px 6px}}}}
h2{{font-size:15px;margin:0 0 12px}}h3{{font-size:14px;margin:18px 0 8px}}.tag{{font-weight:500;font-size:11.5px;color:var(--mute);border:1px solid var(--line);border-radius:99px;padding:1px 8px;margin-left:6px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;grid-column:span 12}}@media (max-width:900px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}.kl{{color:var(--mute);font-size:12px}}.kn{{font-size:26px;font-weight:650;margin:2px 0}}.ks{{color:var(--mute);font-size:12px}}
table{{border-collapse:collapse;width:100%}}.grid th,.grid td,.tasks th,.tasks td{{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}}
.grid th,.tasks th{{color:var(--mute);font-weight:600;font-size:12px}}.small td,.small th{{font-size:12px;padding:5px 6px}}
.kv th{{text-align:left;color:var(--mute);font-weight:500;padding:5px 12px 5px 0;white-space:nowrap;vertical-align:top;width:1%}}.kv td{{padding:5px 0}}
.sub{{color:var(--mute);font-size:12px;margin-top:3px}}.mono{{font-family:Consolas,ui-monospace,monospace}}.cap{{color:var(--mute);font-size:12px;margin:6px 0}}
.pill{{display:inline-block;font-size:11.5px;font-weight:600;border-radius:99px;padding:1px 9px;margin-right:6px;white-space:nowrap}}
.ok{{color:var(--ok);background:var(--okb)}}.run{{color:var(--run);background:var(--runb)}}.warn{{color:var(--warn);background:var(--warnb)}}.bad{{color:var(--bad);background:var(--badb)}}.idle{{color:var(--idle);background:var(--idleb)}}
.gates{{list-style:none;padding:0;margin:0;display:grid;gap:8px}}
.bar{{display:grid;grid-template-columns:minmax(90px,170px) 1fr 44px;gap:8px;align-items:center;margin:4px 0;font-size:12.5px}}.bl{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bt{{background:var(--idleb);border-radius:6px;height:10px;overflow:hidden}}.bt i{{display:block;height:100%;background:var(--acc);border-radius:6px}}.bv{{text-align:right;font-variant-numeric:tabular-nums}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}@media (max-width:700px){{.two{{grid-template-columns:1fr}}}}
.stack{{display:flex;height:30px;border-radius:8px;overflow:hidden;font-size:12px;font-weight:600}}.stack i{{font-style:normal;display:flex;align-items:center;justify-content:center;color:#fff}}
.gpu{{background:#2f5bd3}}.oth{{background:#7a5af8}}.res{{background:#8a94a6}}
code{{background:var(--idleb);padding:1px 5px;border-radius:5px}}
</style></head><body>
<header><h1>InvoiceGuard-PO · 관리자 대시보드</h1>
<div class="meta">생성 {E(generated)} · 읽기 전용 · 원본: reports/, manifests/, configs/project.yaml</div>
<div class="banner">이 화면은 기록된 증거만 보여줍니다. 실제 VLM 추론·QLoRA 학습·GPU 측정은 아직 실행하지 않았으며(not_run), 자체 Invoice–PO와 공개 데이터는 모두 합성 자료입니다.</div></header>
<main>
<div class="kpis">{kpi_html}</div>
<section class="card wide"><h2>진행 단계 T00–T09</h2><table class="tasks"><tr><th>ID</th><th>작업 · 증거</th><th>위치</th><th>상태</th></tr>{task_rows}</table></section>
<section class="card third"><h2>인수 게이트</h2><ul class="gates">{gate_rows}</ul></section>
<section class="card half"><h2>RunPod 예산·과금 상태</h2>{budget}{kv_table(approval_pairs)}</section>
<section class="card half"><h2>모델 평가 (M0 vs M1, 동일 manifest·NF4)</h2>{model_html}</section>
<section class="card"><h2>데이터·분할</h2>{data_html}</section>
<section class="card half"><h2>CPU 테스트</h2>{test_html}</section>
<section class="card half"><h2>검수 앱 (업로드→추출→수정·승인→export)</h2>{kv_table([("상태", pill("not_implemented") + " T06에서 구현"), ("검수 건 / 승인 / export", "— (앱 DB 없음)"), ("추론 큐·타임아웃 격리", pill("not_run")), ("모델 서버", '<span class="pill warn">연결 없음</span> fixture로 대체하지 않음')])}</section>
</main></body></html>"""


def collect(junit_path: Path) -> dict:
    board = _read(REPO / "reports" / "TASK_BOARD.md") or ""
    tasks, gates = parse_task_board(board)
    return {
        "tasks": tasks, "gates": gates,
        "config": yaml.safe_load((REPO / "configs" / "project.yaml").read_text(encoding="utf-8")),
        "approval": parse_kv(_read(REPO / "reports" / "RUNPOD_APPROVAL.md") or ""),
        "handoff": parse_kv(_read(REPO / "reports" / "SESSION_HANDOFF.md") or ""),
        "public_profile": _json(REPO / "reports" / "data" / "public_profile.json"),
        "public_manifest": _json(REPO / "manifests" / "public_canonical_v1.summary.json"),
        "trade_manifest": _json(REPO / "manifests" / "trade_raw_v1.summary.json"),
        "results": _json(REPO / "reports" / "RESULTS_TEMPLATE.json"),
        "junit": parse_junit(junit_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "artifacts" / "dashboard" / "index.html"))
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    junit = out.parent / "pytest_junit.xml"
    if args.run_tests:
        run_tests(junit)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(collect(junit)), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
