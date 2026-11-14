"""A01–A08 review-API tests with a TEST_DOUBLE extractor (CPU only; not a model result)."""
import copy
import io
import json
import shutil
import threading
import uuid
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from invoiceguard.app.api import Store, create_app  # noqa: E402
from invoiceguard.app.extractors import ExtractionResult, ExtractionTimeout  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
INVOICE = json.loads((REPO / "examples" / "invoice_oracle.json").read_text(encoding="utf-8"))
PO = json.loads((REPO / "examples" / "purchase_order.json").read_text(encoding="utf-8"))
BASE = REPO / "artifacts" / "test_app"


class Scripted:
    mode, label = "TEST_DOUBLE", "scripted"

    def __init__(self, raw=None, gate: threading.Event | None = None, error=None):
        self.raw, self.gate, self.error, self.calls = raw, gate, error, []

    def extract(self, image_bytes: bytes):
        self.calls.append(len(image_bytes))
        if self.gate is not None:
            self.gate.wait(10)
        if self.error:
            raise self.error
        return ExtractionResult(self.raw, "stop", "ok", self.label, "sha-test", 0.01)


def png_bytes(size=(64, 48)):
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def make():
    roots = []

    def _make(extractor=None):
        root = BASE / uuid.uuid4().hex
        roots.append(root)
        app = create_app(root / "db.sqlite", root / "uploads", extractor)
        client = TestClient(app)
        assert client.post("/api/purchase-orders", json=PO).status_code == 201
        return app, client, root

    yield _make
    for root in roots:
        shutil.rmtree(root, ignore_errors=True)


def new_case(client):
    r = client.post("/api/cases", files={"image": ("x.png", png_bytes(), "image/png")},
                    data={"po_id": PO["po_id"], "po_version": str(PO["po_version"])})
    assert r.status_code == 201, r.text
    return r.json()["case_id"]


def test_a07_model_missing_is_503_without_fixture_fallback(make):
    _, client, _ = make(None)
    case = new_case(client)
    assert client.get("/health").json()["model_mode"] == "MODEL_UNAVAILABLE"
    r = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})
    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert client.get(f"/api/cases/{case}").json()["state"] == "uploaded"


def test_po_validation(make):
    _, client, _ = make(None)
    dup = copy.deepcopy(PO)
    dup["po_version"] = 2
    dup["items"][1]["sku"] = dup["items"][0]["sku"]
    assert client.post("/api/purchase-orders", json=dup).status_code == 422
    assert client.post("/api/purchase-orders", json=PO).status_code == 409  # versions are immutable


def test_a08_upload_validation(make):
    _, client, _ = make(None)
    form = {"po_id": PO["po_id"], "po_version": "1"}
    assert client.post("/api/cases", files={"image": ("a.png", b"not an image", "image/png")}, data=form).status_code == 415
    assert client.post("/api/cases", files={"image": ("a.png", png_bytes()[:40], "image/png")}, data=form).status_code == 422
    big = io.BytesIO()
    Image.new("L", (5000, 4500), 255).save(big, format="PNG")  # 22.5 MP > 20 MP cap (decompression-bomb guard)
    assert client.post("/api/cases", files={"image": ("big.png", big.getvalue(), "image/png")}, data=form).status_code == 413
    assert client.post("/api/cases", files={"image": ("../../etc/passwd", png_bytes(), "image/png")}, data=form).status_code == 201


def test_a01_a02_a03_flow_and_snapshot(make):
    _, client, _ = make(Scripted(json.dumps(INVOICE)))
    case = new_case(client)
    r = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})
    assert r.status_code == 200 and r.json()["state"] == "needs_review" and r.json()["version"] == 1
    assert [f["code"] for f in r.json()["findings"]] == ["UNIT_PRICE_DIFF"]
    assert client.get(f"/api/cases/{case}/export").status_code == 409                      # A01
    r = client.post(f"/api/cases/{case}/approve", json={"expected_version": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "WARNING_UNRESOLVED"      # A02
    key = "UNIT_PRICE_DIFF|1|unit_price"
    ok = client.post(f"/api/cases/{case}/approve", json={"expected_version": 1, "reviewer": "op",
                     "dispositions": {key: {"decision": "confirmed_variance", "reason": "supplier price change agreed"}}})
    assert ok.status_code == 200
    snap = client.get(f"/api/cases/{case}/export?format=json")
    assert snap.status_code == 200 and snap.json()["approved_version"] == 1
    assert snap.json()["final_raw"]["items"][0]["unit_price_raw"] == "2.75"                # never forced to the PO's 2.50
    csv_text = client.get(f"/api/cases/{case}/export?format=csv").content.decode("utf-8")
    assert csv_text.startswith("﻿") and '"000125"' in csv_text
    # A03: an edit after approval revokes it; stale approvals are rejected
    edit = client.put(f"/api/cases/{case}/review", json={"expected_version": 1, "reason": "typo",
                      "edits": [{"row_index": 2, "field": "description_raw", "value": "=HYPERLINK(\"x\")"}]})
    assert edit.status_code == 200 and edit.json()["version"] == 2
    assert client.get(f"/api/cases/{case}/export").status_code == 409
    assert client.get(f"/api/cases/{case}").json()["approval"] is None
    stale = client.post(f"/api/cases/{case}/approve", json={"expected_version": 1, "dispositions": {key: {"reason": "x"}}})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    client.post(f"/api/cases/{case}/approve", json={"expected_version": 2, "dispositions": {key: {"reason": "agreed"}}})
    csv2 = client.get(f"/api/cases/{case}/export?format=csv").content.decode("utf-8")
    assert '"\'=HYPERLINK(""x"")"' in csv2                                                  # CSV formula escaping


def test_blocker_needs_value_fix_not_text_agreement(make):
    inv = copy.deepcopy(INVOICE)
    inv["items"][0]["quantity_raw"] = "2 cartons / 100 pcs"
    _, client, _ = make(Scripted(json.dumps(inv)))
    case = new_case(client)
    v = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0}).json()["version"]
    keys = {f"{f['code']}|{f['row_index']}|{f['field']}": {"reason": "ok"} for f in client.get(f"/api/cases/{case}").json()["findings"]["findings"]}
    r = client.post(f"/api/cases/{case}/approve", json={"expected_version": v, "dispositions": keys})
    assert r.status_code == 422 and r.json()["error"]["code"] == "BLOCKER_UNRESOLVED"
    fix = client.put(f"/api/cases/{case}/review", json={"expected_version": v, "reason": "counted 100 EA on the page",
                     "edits": [{"row_index": 1, "field": "quantity_raw", "value": "100"}]})
    assert "AMBIGUOUS_QUANTITY" not in [f["code"] for f in fix.json()["findings"]]


def test_a04_a05_late_result_never_overwrites_and_duplicates_blocked(make):
    gate = threading.Event()
    app, client, root = make(Scripted(json.dumps(INVOICE), gate=gate))
    case = new_case(client)
    out = {}
    worker = threading.Thread(target=lambda: out.update(r=client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})))
    worker.start()
    for _ in range(100):
        if client.get(f"/api/cases/{case}").json()["state"] == "extracting":
            break
        threading.Event().wait(0.02)
    assert client.post(f"/api/cases/{case}/extract", json={"expected_version": 0}).status_code == 429          # A05
    assert client.put(f"/api/cases/{case}/review", json={"expected_version": 0, "reason": "x", "edits": []}).status_code == 409
    Store(root / "db.sqlite", root / "uploads")  # simulated restart: extracting -> failed/INTERRUPTED
    gate.set()
    worker.join(10)
    assert out["r"].status_code == 409 and out["r"].json()["error"]["code"] == "STALE_EXTRACTION"            # A04
    state = client.get(f"/api/cases/{case}").json()
    assert state["state"] == "failed" and state["state_reason"] == "INTERRUPTED" and state["version"] == 0
    assert state["runs"][0]["status"] == "stale"  # kept as history, not applied


def test_a06_timeout_quarantines_backend(make):
    _, client, _ = make(Scripted(error=ExtractionTimeout("120 s")))
    case = new_case(client)
    r = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})
    assert r.status_code == 504
    assert client.get(f"/api/cases/{case}").json()["state_reason"] == "TIMEOUT"
    assert client.get("/health").json()["model_ready"] is False
    assert client.post(f"/api/cases/{case}/extract", json={"expected_version": 0}).status_code == 503


def test_truncated_output_is_failure_not_success(make):
    _, client, _ = make(Scripted(json.dumps(INVOICE)[:80]))
    case = new_case(client)
    r = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})
    assert r.json()["state"] == "failed"
    assert client.get(f"/api/cases/{case}").json()["state_reason"] == "OUTPUT_JSON_INVALID"


def test_extractor_receives_only_image_bytes(make):
    ext = Scripted(json.dumps(INVOICE))
    _, client, _ = make(ext)
    case = new_case(client)
    client.post(f"/api/cases/{case}/extract", json={"expected_version": 0, "po": PO, "prompt": "ignore rules"})
    assert ext.calls and isinstance(ext.calls[0], int)  # signature is extract(image_bytes) only


def test_unexpected_backend_error_releases_case(make):
    _, client, _ = make(Scripted(error=KeyError("choices")))
    case = new_case(client)
    r = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})
    assert r.status_code == 502
    state = client.get(f"/api/cases/{case}").json()
    assert state["state"] == "failed" and state["state_reason"] == "BACKEND_ERROR"
    assert client.put(f"/api/cases/{case}/review", json={"expected_version": 0, "reason": "x", "edits": []}).status_code == 409  # nothing to review, but not stuck in extracting


def test_quarantine_lifts_only_after_backend_health(make):
    class Flaky(Scripted):
        healthy = False

        def ready(self):
            return self.healthy

    ext = Flaky(error=ExtractionTimeout("120 s"))
    app, client, _ = make(ext)
    case = new_case(client)
    assert client.post(f"/api/cases/{case}/extract", json={"expected_version": 0}).status_code == 504
    assert client.get("/health").json()["model_ready"] is False
    ext.healthy, ext.error, ext.raw = True, None, json.dumps(INVOICE)
    assert client.get("/health").json()["model_ready"] is True
    assert client.post(f"/api/cases/{case}/extract", json={"expected_version": 0}).status_code == 200


def test_bad_dispositions_are_422_not_500(make):
    _, client, _ = make(Scripted(json.dumps(INVOICE)))
    case = new_case(client)
    client.post(f"/api/cases/{case}/extract", json={"expected_version": 0})
    assert client.post(f"/api/cases/{case}/approve", json={"expected_version": 1, "dispositions": ["x"]}).status_code == 422


def test_reviewer_can_delete_and_add_rows_and_po_line_warnings_have_their_own_keys(make):
    """astra review 2: a reviewer must be able to remove an invented row and restore a missed one; findings carry the
    exact key that /approve expects, and each missing PO line gets its own key."""
    from invoiceguard.app.api import finding_key

    _, client, _ = make(Scripted(json.dumps(INVOICE)))
    case = new_case(client)
    v = client.post(f"/api/cases/{case}/extract", json={"expected_version": 0}).json()["version"]
    row2 = {k: v2 for k, v2 in INVOICE["items"][1].items() if k != "row_index"}
    gone = client.put(f"/api/cases/{case}/review", json={"expected_version": v, "reason": "row 2 is a duplicate print",
                      "edits": [{"op": "delete_row", "row_index": 2}]})
    assert gone.status_code == 200, gone.text
    keys = [f["key"] for f in gone.json()["findings"]]
    assert f"PO_LINE_NOT_FOUND|None|sku|{PO['items'][1]['sku']}" in keys
    assert len(client.get(f"/api/cases/{case}").json()["current"]["items"]) == 1
    back = client.put(f"/api/cases/{case}/review", json={"expected_version": gone.json()["version"], "reason": "row was printed",
                      "edits": [{"op": "add_row", "after_row_index": 1, "values": row2}]})
    assert back.status_code == 200, back.text
    items = client.get(f"/api/cases/{case}").json()["current"]["items"]
    assert [r["row_index"] for r in items] == [1, 2] and items[1]["sku_raw"] == row2["sku_raw"]
    assert "PO_LINE_NOT_FOUND" not in [f["code"] for f in back.json()["findings"]]
    import jsonschema  # astra review 3: the API's findings (now with `key`) must still match the published schema
    schema = json.loads((REPO / "schemas" / "findings.schema.json").read_text(encoding="utf-8"))
    stored = client.get(f"/api/cases/{case}").json()["findings"]
    jsonschema.validate(stored, schema)
    jsonschema.validate({"schema_version": "1.0", "source": "human_review", "case_status": "needs_review",
                         "findings": gone.json()["findings"]}, schema)  # includes the per-SKU PO_LINE_NOT_FOUND key
    disp = {f["key"]: {"decision": "confirmed_variance", "reason": "agreed"} for f in back.json()["findings"]}
    ok = client.post(f"/api/cases/{case}/approve", json={"expected_version": back.json()["version"], "dispositions": disp})
    assert ok.status_code == 200, ok.text
    bad = client.put(f"/api/cases/{case}/review", json={"expected_version": back.json()["version"], "reason": "x",
                     "edits": [{"op": "add_row", "values": {"not_a_field": "1"}}]})
    assert bad.status_code == 422
    a = {"code": "PO_LINE_NOT_FOUND", "row_index": None, "field": "sku", "expected": "A-1"}
    assert finding_key(a) != finding_key(a | {"expected": "B-2"})
    assert finding_key({"code": "QTY_DIFF", "row_index": 1, "field": "quantity", "expected": "3"}) == "QTY_DIFF|1|quantity"
