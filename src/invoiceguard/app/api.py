"""Minimal review API (docs/07, docs/16): upload → extract → review/edit → approve → export snapshot.

Concurrency contract (docs/16):
* extract: short transaction checks expected_version and sets state=extracting + run_id; the model call runs
  OUTSIDE any transaction; completion re-checks (version, run_id, state) with compare-and-swap. A stale
  result is kept as history and never overwrites the current version.
* one inference at a time (semaphore=1) → 429 when busy; edits/approvals while extracting → 409.
* timeout → run=timeout, case=failed, backend quarantined (503) until its health check passes.
* every edit creates a new version and revokes approvals; export returns only the immutable approved snapshot.
* restart: cases left in `extracting` become failed/INTERRUPTED.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from ..model_output import parse_response
from ..normalization import normalization_to_json, normalize_invoice
from ..reconciliation import reconcile, validate_po
from .extractors import ExtractionTimeout, ModelUnavailable, UnavailableExtractor
from .uploads import UploadRejected, normalise_image

REPO = Path(__file__).resolve().parents[3]
PO_SCHEMA = json.loads((REPO / "schemas" / "purchase_order.schema.json").read_text(encoding="utf-8"))
ROW_FIELDS = {"sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw"}
DOC_FIELDS = {"invoice_number_raw", "currency_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw"}
CSV_COLUMNS = ["sku", "description", "quantity", "unit", "unit_price", "line_total", "currency", "review_note"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS purchase_orders (po_id TEXT, po_version INTEGER, json TEXT, created_at TEXT, PRIMARY KEY (po_id, po_version));
CREATE TABLE IF NOT EXISTS documents (document_id TEXT PRIMARY KEY, sha256 TEXT, width INTEGER, height INTEGER, created_at TEXT);
CREATE INDEX IF NOT EXISTS documents_sha ON documents (sha256);
CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, document_id TEXT, po_id TEXT, po_version INTEGER, state TEXT,
  state_reason TEXT, current_version INTEGER, active_run_id TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS extraction_runs (run_id TEXT PRIMARY KEY, case_id TEXT, started_version INTEGER, status TEXT,
  extractor_mode TEXT, model_label TEXT, prompt_sha256 TEXT, raw_response TEXT, finish_reason TEXT, latency_s REAL,
  error TEXT, created_at TEXT, finished_at TEXT);
CREATE TABLE IF NOT EXISTS case_versions (case_id TEXT, version INTEGER, source TEXT, run_id TEXT, current_json TEXT,
  normalization_json TEXT, findings_json TEXT, created_at TEXT, PRIMARY KEY (case_id, version));
CREATE TABLE IF NOT EXISTS review_events (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, version INTEGER, actor TEXT,
  patch_json TEXT, reason TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approvals (approval_id TEXT PRIMARY KEY, case_id TEXT, version INTEGER, reviewer TEXT,
  dispositions_json TEXT, snapshot_json TEXT, snapshot_sha256 TEXT, revoked INTEGER DEFAULT 0, created_at TEXT);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def finding_key(f: dict) -> str:
    """Stable id a reviewer's disposition is attached to. Row-less PO_LINE_NOT_FOUND can occur once per missing PO
    line, so its key carries the PO SKU — two missing lines need two separate reasons (astra review 2)."""
    key = f"{f['code']}|{f['row_index']}|{f['field']}"
    return f"{key}|{f['expected']}" if f["code"] == "PO_LINE_NOT_FOUND" and f["row_index"] is None else key


def apply_row_op(current: dict, edit: dict) -> None:
    """Reviewer adds a row the model missed or deletes a row it invented. Rows are renumbered 1..n in printed
    order afterwards, so later edits in the same request use the new numbering; findings are recomputed."""
    items = current.setdefault("items", [])
    if edit["op"] == "delete_row":
        idx = edit.get("row_index")
        if not any(r["row_index"] == idx for r in items):
            raise ApiError(422, "BAD_ROW", "없는 행입니다.")
        items[:] = [r for r in items if r["row_index"] != idx]
    else:
        values = edit.get("values") or {}
        after = edit.get("after_row_index", len(items))
        if not isinstance(values, dict) or set(values) - ROW_FIELDS:
            raise ApiError(422, "BAD_FIELD", "추가할 행의 필드가 올바르지 않습니다.")
        if any(v is not None and not isinstance(v, str) for v in values.values()):
            raise ApiError(422, "BAD_VALUE", "값은 문자열 또는 null이어야 합니다.")
        if not isinstance(after, int) or not 0 <= after <= len(items):
            raise ApiError(422, "BAD_ROW", "after_row_index가 범위를 벗어났습니다.")
        position = next((i + 1 for i, r in enumerate(items) if r["row_index"] == after), 0) if after else 0
        items.insert(position, {"row_index": None, **{f: values.get(f) for f in sorted(ROW_FIELDS)}})
    for i, r in enumerate(items, start=1):
        r["row_index"] = i


def csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


class Store:
    def __init__(self, db_path: Path, storage_dir: Path):
        self.db_path, self.storage_dir = db_path, storage_dir
        storage_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()  # serialises write transactions on the single SQLite file
        init = sqlite3.connect(db_path)
        try:
            init.executescript(SCHEMA)  # executescript commits implicitly, so it runs outside tx()
        finally:
            init.close()
        with self.tx() as db:
            # restart recovery: nothing can still be running in this new process
            db.execute("UPDATE extraction_runs SET status='interrupted', finished_at=? WHERE status='running'", (_now(),))
            db.execute("UPDATE cases SET state='failed', state_reason='INTERRUPTED', active_run_id=NULL, updated_at=? "
                       "WHERE state='extracting'", (_now(),))

    def tx(self):
        store = self

        class _Tx:
            def __enter__(self_inner):
                store.lock.acquire()
                self_inner.db = sqlite3.connect(store.db_path, isolation_level=None)
                self_inner.db.row_factory = sqlite3.Row
                self_inner.db.execute("BEGIN IMMEDIATE")
                return self_inner.db

            def __exit__(self_inner, exc_type, exc, tb):
                try:
                    self_inner.db.execute("ROLLBACK" if exc_type else "COMMIT")
                finally:
                    self_inner.db.close()
                    store.lock.release()
                return False

        return _Tx()


def create_app(db_path: Path, storage_dir: Path, extractor=None) -> FastAPI:
    app = FastAPI(title="InvoiceGuard-PO review API", docs_url=None, redoc_url=None, openapi_url=None)
    store = Store(db_path, storage_dir)
    app.state.store = store
    app.state.extractor = extractor or UnavailableExtractor()
    app.state.quarantined = False
    busy = threading.Semaphore(1)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message,
                                                                       "request_id": str(uuid.uuid4())}})

    def load_case(db, case_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise ApiError(404, "CASE_NOT_FOUND", "케이스가 없습니다.")
        return row

    def load_po(db, po_id: str, version: int) -> dict:
        row = db.execute("SELECT json FROM purchase_orders WHERE po_id=? AND po_version=?", (po_id, version)).fetchone()
        if row is None:
            raise ApiError(422, "NO_PO", "등록된 발주서 버전이 아닙니다.")
        return json.loads(row["json"])

    def current_version_row(db, case_id: str, version: int):
        return db.execute("SELECT * FROM case_versions WHERE case_id=? AND version=?", (case_id, version)).fetchone()

    def add_version(db, case: sqlite3.Row, source: str, run_id: str | None, current: dict | None, po: dict) -> tuple[int, dict | None]:
        version = case["current_version"] + 1
        findings, norm = None, None
        if current is not None:
            dup = db.execute("SELECT c.case_id FROM cases c JOIN documents d ON c.document_id=d.document_id "
                             "WHERE d.sha256=(SELECT sha256 FROM documents WHERE document_id=?) AND c.case_id<>? LIMIT 1",
                             (case["document_id"], case["case_id"])).fetchone()
            findings = reconcile(current, po, "human_review" if source == "review" else "live_model",
                                 duplicate_of_case=dup["case_id"] if dup else None)
            for f in findings["findings"]:  # the exact key /approve expects in `dispositions`
                f["key"] = finding_key(f)
            norm = normalization_to_json(normalize_invoice(current))
        db.execute("INSERT INTO case_versions VALUES (?,?,?,?,?,?,?,?)",
                   (case["case_id"], version, source, run_id, json.dumps(current) if current is not None else None,
                    json.dumps(norm) if norm else None, json.dumps(findings) if findings else None, _now()))
        db.execute("UPDATE approvals SET revoked=1 WHERE case_id=? AND revoked=0", (case["case_id"],))
        return version, findings

    def check_version(case: sqlite3.Row, expected: int) -> None:
        if case["current_version"] != expected:
            raise ApiError(409, "STALE_VERSION", "다른 변경이 먼저 저장되었습니다. 새로고침 후 다시 시도하세요.")
        if case["state"] == "extracting":
            raise ApiError(409, "EXTRACTION_IN_PROGRESS", "추출이 진행 중입니다.")

    @app.get("/health")
    def health():
        ext = app.state.extractor
        return {"app": "ok", "model_mode": ext.mode, "model_label": ext.label, "model_ready": backend_ready(),
                "quarantined": app.state.quarantined}

    @app.post("/api/purchase-orders", status_code=201)
    async def create_po(request: Request):
        try:
            po = await request.json()
            jsonschema.validate(po, PO_SCHEMA)
        except (ValueError, jsonschema.ValidationError) as exc:
            raise ApiError(422, "PO_SCHEMA", f"발주서 형식 오류: {str(exc)[:120]}")
        errors = validate_po(po)
        if errors:
            raise ApiError(422, "PO_INVALID", ", ".join(errors))
        with store.tx() as db:
            if db.execute("SELECT 1 FROM purchase_orders WHERE po_id=? AND po_version=?", (po["po_id"], po["po_version"])).fetchone():
                raise ApiError(409, "PO_VERSION_EXISTS", "같은 발주서 버전이 이미 있습니다. 새 버전으로 등록하세요.")
            db.execute("INSERT INTO purchase_orders VALUES (?,?,?,?)", (po["po_id"], po["po_version"], json.dumps(po), _now()))
        return {"po_id": po["po_id"], "po_version": po["po_version"]}

    @app.post("/api/cases", status_code=201)
    async def create_case(image: UploadFile = File(...), po_id: str = Form(...), po_version: int = Form(...)):
        data = await image.read(10 * 1024 * 1024 + 1)
        try:
            png, meta = normalise_image(data)
        except UploadRejected as exc:
            raise ApiError(exc.status, exc.code, str(exc))
        sha = hashlib.sha256(png).hexdigest()
        case_id, document_id = str(uuid.uuid4()), str(uuid.uuid4())
        with store.tx() as db:
            load_po(db, po_id, po_version)
            (store.storage_dir / f"{document_id}.png").write_bytes(png)  # server-generated key; client name ignored
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?)", (document_id, sha, meta["width"], meta["height"], _now()))
            db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (case_id, document_id, po_id, po_version, "uploaded", None, 0, None, _now(), _now()))
        return {"case_id": case_id, "version": 0, "state": "uploaded", "image_sha256": sha}

    def backend_ready() -> bool:
        """Quarantine is lifted only when the backend proves it is healthy again (e.g. GET /health on the model server)."""
        ext = app.state.extractor
        if ext.mode == "MODEL_UNAVAILABLE":
            return False
        if app.state.quarantined:
            probe = getattr(ext, "ready", None)
            if probe is not None and probe():
                app.state.quarantined = False
        return not app.state.quarantined

    @app.post("/api/cases/{case_id}/extract")
    def extract(case_id: str, body: dict = Body(...)):  # sync def: FastAPI runs it in a worker thread, the event loop stays free
        ext = app.state.extractor
        if not backend_ready():
            raise ApiError(503, "MODEL_UNAVAILABLE", "모델 서버를 사용할 수 없습니다. 예시 결과로 대체하지 않습니다.")
        if not busy.acquire(blocking=False):
            raise ApiError(429, "INFERENCE_BUSY", "다른 추출이 진행 중입니다. 잠시 후 다시 시도하세요.")
        run_id = str(uuid.uuid4())
        try:
            with store.tx() as db:  # short transaction: claim the case
                case = load_case(db, case_id)
                check_version(case, int(body.get("expected_version", -1)))
                if case["state"] == "approved":
                    raise ApiError(409, "ALREADY_APPROVED", "승인된 버전은 재추출 전에 수정·검토가 필요합니다.")
                db.execute("UPDATE cases SET state='extracting', active_run_id=?, updated_at=? WHERE case_id=?", (run_id, _now(), case_id))
                db.execute("INSERT INTO extraction_runs (run_id, case_id, started_version, status, extractor_mode, model_label, created_at) "
                           "VALUES (?,?,?,?,?,?,?)", (run_id, case_id, case["current_version"], "running", ext.mode, ext.label, _now()))
                image_bytes = (store.storage_dir / f"{case['document_id']}.png").read_bytes()
            status, result, error = "done", None, None
            try:
                result = ext.extract(image_bytes)  # no DB transaction held during inference
            except ExtractionTimeout as exc:
                status, error = "timeout", str(exc)[:200]
                app.state.quarantined = True
            except ModelUnavailable as exc:
                status, error = "unavailable", str(exc)[:200]
            except Exception as exc:  # noqa: BLE001 - any backend error must release the case, never leave it extracting
                status, error = "error", repr(exc)[:200]
            outcome_error = None  # raised only AFTER the history is committed (raising inside would roll it back)
            with store.tx() as db:  # compare-and-swap on completion
                case = load_case(db, case_id)
                fresh = case["state"] == "extracting" and case["active_run_id"] == run_id
                db.execute("UPDATE extraction_runs SET raw_response=?, finish_reason=?, latency_s=?, prompt_sha256=?, error=?, finished_at=? WHERE run_id=?",
                           (result.raw_response if result else None, result.finish_reason if result else None,
                            result.latency_s if result else None, result.prompt_sha256 if result else None, error, _now(), run_id))
                if not fresh:
                    db.execute("UPDATE extraction_runs SET status='stale' WHERE run_id=?", (run_id,))
                    outcome_error = ApiError(409, "STALE_EXTRACTION", "이 추출 결과는 더 최신 상태가 있어 이력으로만 저장했습니다.")
                elif status != "done":
                    db.execute("UPDATE extraction_runs SET status=? WHERE run_id=?", (status, run_id))
                    reason = {"timeout": "TIMEOUT", "unavailable": "MODEL_UNAVAILABLE"}.get(status, "BACKEND_ERROR")
                    db.execute("UPDATE cases SET state='failed', state_reason=?, active_run_id=NULL, updated_at=? WHERE case_id=?",
                               (reason, _now(), case_id))
                    outcome_error = ApiError({"timeout": 504, "unavailable": 503}.get(status, 502), reason,
                                             "추출에 실패했습니다. 명시적으로 재시도하세요.")
                else:  # fresh + model answered: apply in the SAME transaction as the CAS check
                    parsed = parse_response(result.raw_response, "TRADE_RAW", result.generation_status, result.finish_reason)
                    po = load_po(db, case["po_id"], case["po_version"])
                    if parsed.status != "ok" or not parsed.schema_valid or not parsed.row_index_valid:
                        version, _ = add_version(db, case, "extraction", run_id, None, po)
                        db.execute("UPDATE extraction_runs SET status='failed_output' WHERE run_id=?", (run_id,))
                        db.execute("UPDATE cases SET state='failed', state_reason=?, current_version=?, active_run_id=NULL, updated_at=? WHERE case_id=?",
                                   (f"OUTPUT_{parsed.status.upper()}" if parsed.status != "ok" else "OUTPUT_SCHEMA", version, _now(), case_id))
                        return {"case_id": case_id, "version": version, "state": "failed", "mode": ext.mode, "run_id": run_id}
                    version, findings = add_version(db, case, "extraction", run_id, parsed.obj, po)
                    state = findings["case_status"]
                    db.execute("UPDATE extraction_runs SET status='applied' WHERE run_id=?", (run_id,))
                    db.execute("UPDATE cases SET state=?, state_reason=NULL, current_version=?, active_run_id=NULL, updated_at=? WHERE case_id=?",
                               (state, version, _now(), case_id))
            if outcome_error is not None:  # history already committed
                raise outcome_error
            return {"case_id": case_id, "version": version, "state": state, "mode": ext.mode, "run_id": run_id,
                    "findings": findings["findings"]}
        finally:
            busy.release()

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        with store.tx() as db:
            case = load_case(db, case_id)
            ver = current_version_row(db, case_id, case["current_version"])
            runs = [dict(r) for r in db.execute("SELECT run_id, status, extractor_mode, model_label, prompt_sha256, latency_s, created_at "
                                                "FROM extraction_runs WHERE case_id=? ORDER BY created_at", (case_id,))]
            approval = db.execute("SELECT approval_id, version, reviewer, created_at FROM approvals WHERE case_id=? AND revoked=0", (case_id,)).fetchone()
        return {"case_id": case_id, "state": case["state"], "state_reason": case["state_reason"], "version": case["current_version"],
                "po": {"po_id": case["po_id"], "po_version": case["po_version"]},
                "current": json.loads(ver["current_json"]) if ver and ver["current_json"] else None,
                "findings": json.loads(ver["findings_json"]) if ver and ver["findings_json"] else None,
                "runs": runs, "approval": dict(approval) if approval else None}

    @app.get("/api/cases/{case_id}/image")
    def get_image(case_id: str):
        with store.tx() as db:
            case = load_case(db, case_id)
        return Response((store.storage_dir / f"{case['document_id']}.png").read_bytes(), media_type="image/png")

    @app.put("/api/cases/{case_id}/review")
    async def review(case_id: str, request: Request):
        body = await request.json()
        reason = (body.get("reason") or "").strip()
        if not reason:
            raise ApiError(422, "REASON_REQUIRED", "수정 사유가 필요합니다.")
        with store.tx() as db:
            case = load_case(db, case_id)
            check_version(case, int(body.get("expected_version", -1)))
            ver = current_version_row(db, case_id, case["current_version"])
            if ver is None or ver["current_json"] is None:
                raise ApiError(409, "NOTHING_TO_REVIEW", "검수할 추출 결과가 없습니다.")
            current = json.loads(ver["current_json"])
            for edit in body.get("edits", []):
                op = edit.get("op", "set")
                if op in ("add_row", "delete_row"):
                    apply_row_op(current, edit)
                    continue
                if op != "set":
                    raise ApiError(422, "BAD_OP", "op는 set, add_row, delete_row 중 하나입니다.")
                field, value = edit.get("field"), edit.get("value")
                if value is not None and not isinstance(value, str):
                    raise ApiError(422, "BAD_VALUE", "값은 문자열 또는 null이어야 합니다.")
                if field in DOC_FIELDS and edit.get("row_index") is None:
                    current[field] = value
                elif field in ROW_FIELDS:
                    rows = [r for r in current["items"] if r["row_index"] == edit.get("row_index")]
                    if not rows:
                        raise ApiError(422, "BAD_ROW", "없는 행입니다.")
                    rows[0][field] = value
                else:
                    raise ApiError(422, "BAD_FIELD", "수정할 수 없는 필드입니다.")
            po = load_po(db, case["po_id"], case["po_version"])
            version, findings = add_version(db, case, "review", None, current, po)
            db.execute("INSERT INTO review_events (case_id, version, actor, patch_json, reason, created_at) VALUES (?,?,?,?,?,?)",
                       (case_id, version, "local_operator", json.dumps(body.get("edits", [])), reason, _now()))
            db.execute("UPDATE cases SET state=?, state_reason=NULL, current_version=?, updated_at=? WHERE case_id=?",
                       (findings["case_status"], version, _now(), case_id))
        return {"case_id": case_id, "version": version, "state": findings["case_status"], "findings": findings["findings"]}

    @app.post("/api/cases/{case_id}/approve")
    async def approve(case_id: str, request: Request):
        body = await request.json()
        reviewer = (body.get("reviewer") or "local_operator").strip()
        dispositions = body.get("dispositions") or {}
        if not isinstance(dispositions, dict) or not all(isinstance(v, dict) for v in dispositions.values()):
            raise ApiError(422, "BAD_DISPOSITIONS", "dispositions는 {finding_key: {decision, reason}} 형식이어야 합니다.")
        with store.tx() as db:
            case = load_case(db, case_id)
            check_version(case, int(body.get("expected_version", -1)))
            if case["state"] not in ("needs_review", "matched_candidate"):
                raise ApiError(409, "NOT_APPROVABLE", "승인할 수 있는 상태가 아닙니다.")
            ver = current_version_row(db, case_id, case["current_version"])
            findings = json.loads(ver["findings_json"])
            blockers = [f for f in findings["findings"] if f["severity"] == "blocker"]
            if blockers:
                raise ApiError(422, "BLOCKER_UNRESOLVED", "값을 보완해야 하는 blocker가 남아 있습니다.")
            missing = [finding_key(f) for f in findings["findings"]
                       if not (dispositions.get(finding_key(f), {}).get("reason") or "").strip()]
            if missing:
                raise ApiError(422, "WARNING_UNRESOLVED", f"사유 없는 warning {len(missing)}건이 있습니다.")
            run = db.execute("SELECT run_id FROM case_versions WHERE case_id=? AND run_id IS NOT NULL ORDER BY version DESC LIMIT 1", (case_id,)).fetchone()
            current = json.loads(ver["current_json"])
            snapshot = {"schema_version": "1.0", "case_id": case_id, "approved_version": case["current_version"],
                        "model_run_id": run["run_id"] if run else None, "reviewer": reviewer, "approved_at": _now(),
                        "po_id": case["po_id"], "po_version": case["po_version"], "final_raw": current,
                        "normalized_values": json.loads(ver["normalization_json"]),
                        "acknowledged_findings": [{**f, "disposition": dispositions[finding_key(f)]} for f in findings["findings"]]}
            blob = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            approval_id = str(uuid.uuid4())
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?)",
                       (approval_id, case_id, case["current_version"], reviewer, json.dumps(dispositions), blob,
                        hashlib.sha256(blob.encode()).hexdigest(), 0, _now()))
            db.execute("UPDATE cases SET state='approved', updated_at=? WHERE case_id=?", (_now(), case_id))
        return {"case_id": case_id, "version": case["current_version"], "state": "approved", "approval_id": approval_id}

    @app.post("/api/cases/{case_id}/reject")
    async def reject(case_id: str, request: Request):
        body = await request.json()
        with store.tx() as db:
            case = load_case(db, case_id)
            check_version(case, int(body.get("expected_version", -1)))
            db.execute("UPDATE cases SET state='rejected', state_reason=?, updated_at=? WHERE case_id=?",
                       ((body.get("reason") or "")[:500], _now(), case_id))
        return {"case_id": case_id, "state": "rejected"}

    @app.get("/api/cases/{case_id}/export")
    def export(case_id: str, format: str = "json"):
        with store.tx() as db:
            case = load_case(db, case_id)
            appr = db.execute("SELECT * FROM approvals WHERE case_id=? AND revoked=0 AND version=?",
                              (case_id, case["current_version"])).fetchone()
        if case["state"] != "approved" or appr is None:
            raise ApiError(409, "APPROVAL_REQUIRED", "현재 버전의 사람 승인이 필요합니다.")
        snapshot = json.loads(appr["snapshot_json"])
        if format == "json":
            return Response(appr["snapshot_json"], media_type="application/json",
                            headers={"X-Snapshot-SHA256": appr["snapshot_sha256"]})
        if format != "csv":
            raise ApiError(422, "BAD_FORMAT", "json 또는 csv만 지원합니다.")
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        currency = snapshot["final_raw"].get("currency_raw")
        for item in snapshot["final_raw"]["items"]:
            writer.writerow([csv_safe(v) for v in (item.get("sku_raw"), item.get("description_raw"), item.get("quantity_raw"),
                                                   item.get("unit_raw"), item.get("unit_price_raw"), item.get("line_total_raw"),
                                                   currency, "")])
        return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"X-Snapshot-SHA256": appr["snapshot_sha256"]})

    return app
