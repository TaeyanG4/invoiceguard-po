"""Read-only local admin dashboard server (Korean UI) with a data browser.

Usage: python -m invoiceguard.dashboard_server [--port 8765] [--run-tests]

* Binds to 127.0.0.1 only (no option to expose it) and answers GET/HEAD only.
* Serves a static single-page app (vanilla HTML/CSS/JS from ``dashboard_static/``, no CDN, no network
  fetch beyond its own JSON endpoints) plus JSON/PNG endpoints:

    /api/status                              reports, gates, approval, manifests summaries, tests,
                                             raw key/values of reports/model/local_smoke*.json (if any)
    /api/public/rows?pool=&standard_role=&mini_role=&template=&quality=&eligible=&q=&offset=&limit=
    /api/public/doc/<base_id>?quality=clean   PUBLIC_CANONICAL gold items + per-field visibility + manifest
    /api/public/image/<base_id>/<quality>     PNG, extracted once from the pinned parquet and cached
    /api/trade/rows?split=&template=&scenario_type=&mini_role=&injection=&q=&offset=&limit=
    /api/trade/doc/<doc_id>                   TRADE_RAW gold, PO, oracle findings, manifest, hash checks
    /api/trade/image/<doc_id>                 PNG
    /api/cord/rows?split=&eligible=&overlap=&has_sub=&masked=&q=&offset=&limit=
    /api/cord/doc/<id>                        CORD_RAW gold + every recorded run's prediction for that document,
                                              scored slot by slot with the pre-registered evaluator (docs/20)
    /api/cord/image/<id>                      PNG (CORD v2 photo, CC BY 4.0)
    /static/favicon.svg (also /favicon.ico)   the dashboard icon

* Every ID is matched with a strict full-match regex AND must exist in the committed manifest; the
  client never supplies a file path. Anything else is 400/404.
* It shows what the records say. Gold labels and POs are evaluation data, never model inputs; missing
  evidence is reported as not_run / unknown, never fabricated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

import pyarrow.parquet as pq
import yaml

from . import dashboard as snap
from .cord_eval import TASK as CORD_TASK, _masked_keys, loose_norm, score_document, slots, strict_norm
from .evaluation import parse_for_eval
from .public_data import QUALITIES, canonical_items, shard_paths
from .reconciliation import reconcile

REPO = snap.REPO
STATIC_DIR = Path(__file__).with_name("dashboard_static")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

PUBLIC_ID = r"synth_\d{4}_[0-9a-f]{8}\.png"
TRADE_ID = r"tr_[0-9a-f]{12}"
QUALITY = "|".join(QUALITIES)
CORD_ID = r"cord_(?:train|dev|test)_\d{4}"
PUBLIC_ID_RE = re.compile(PUBLIC_ID)
TRADE_ID_RE = re.compile(TRADE_ID)
CORD_ID_RE = re.compile(CORD_ID)
MAX_RAW_CHARS = 20_000  # a model answer is at most 1,536 tokens; anything longer is cut with a marker

STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/favicon.ico": ("favicon.svg", "image/svg+xml"),  # browsers probe this path even with <link rel=icon>
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
MAX_LIMIT = 200
MAX_OFFSET = 1_000_000
NONE_VALUE = "none"  # filter value for a null role
MAX_SMOKE_FILES = 10
MAX_SMOKE_PAIRS = 400
MAX_RECORD_FILES = 20
MAX_RECORD_BYTES = 256 * 1024  # training/serving records are a few KB; anything larger is skipped, not truncated

VISIBILITY_KO = {
    "visible_exact": "보임·채점", "not_printed": "미인쇄", "printed_rounded": "반올림 인쇄",
    "truncated_by_renderer": "렌더러 잘림", "case_transformed": "대문자 변환", "source_empty": "원본 비어 있음",
    "visibility_unverified": "가시성 미검증",
}


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, code: str, detail: str | None = None):
        super().__init__(code)
        self.status, self.code, self.detail = status, code, detail


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


class DataStore:
    """Lazy, mtime-aware, read-only access to manifests and local data (plus the public image cache)."""

    def __init__(self, repo: Path = REPO):
        self.repo = repo
        self.trade_dir = repo / "data" / "processed" / "trade"
        self.cache_dir = repo / "data" / "processed" / "public" / "cache"
        self.cord_dir = repo / "data" / "processed" / "cord"
        self.pred_dir = repo / "artifacts" / "predictions"
        self._lock = threading.Lock()
        self._index_lock = threading.Lock()
        self._extract_lock = threading.Lock()  # one parquet row group in memory at a time
        self._jsonl: dict[Path, tuple[int, list[dict]]] = {}
        self._public_source: dict[tuple[str, str], dict] | None = None

    # ------------------------------------------------------------------ manifests
    def _load_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        mtime = path.stat().st_mtime_ns
        with self._lock:
            cached = self._jsonl.get(path)
            if cached and cached[0] == mtime:
                return cached[1]
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self._jsonl[path] = (mtime, rows)
            return rows

    def public_manifest(self) -> list[dict]:
        return self._load_jsonl(self.repo / "manifests" / "public_canonical_v1.jsonl")

    def trade_manifest(self) -> list[dict]:
        return self._load_jsonl(self.repo / "manifests" / "trade_raw_v1.jsonl")

    def public_row(self, base_id: str, quality: str) -> dict | None:
        return next((r for r in self.public_manifest() if r["base_id"] == base_id and r["quality"] == quality), None)

    def public_rows_for(self, base_id: str) -> list[dict]:
        rows = [r for r in self.public_manifest() if r["base_id"] == base_id]
        return sorted(rows, key=lambda r: QUALITIES.index(r["quality"]) if r["quality"] in QUALITIES else 99)

    def trade_row(self, doc_id: str) -> dict | None:
        return next((r for r in self.trade_manifest() if r["doc_id"] == doc_id), None)

    def cord_manifest(self) -> list[dict]:
        return self._load_jsonl(self.repo / "manifests" / "cord_v2.jsonl")

    def cord_row(self, rid: str) -> dict | None:
        return next((r for r in self.cord_manifest() if r["id"] == rid), None)

    def cord_available(self) -> bool:
        return (self.cord_dir / "images").is_dir() and (self.cord_dir / "gold").is_dir()

    def cord_runs(self) -> list[dict]:
        """Every recorded inference run that covered a cord:* set, in arm order (M0, M1 v1, M1-cord, others)."""
        runs = []
        for meta_path in sorted(self.pred_dir.glob("*/run_metadata.json")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            sets = [x for x in meta.get("sets") or [] if str(x).startswith("cord:")]
            if not sets:
                continue
            adapter = meta.get("adapter")
            runs.append({"run_id": meta.get("run_id") or meta_path.parent.name, "dir": meta_path.parent.name,
                         "label": cord_arm_label(adapter) + (" · 단가 프롬프트 (수정 4)" if (meta.get("fingerprint") or {}).get("prompt_variant") else ""),
                         "adapter": adapter, "sets": sets,
                         "adapter_sha256": (meta.get("fingerprint") or {}).get("adapter_sha256"),
                         "started": meta.get("started"), "finished": meta.get("finished"),
                         "wall_seconds": meta.get("wall_seconds"), "peak_vram_gb": meta.get("peak_vram_gb")})
        order = {label: i for i, label in enumerate(CORD_ARM_ORDER)}
        return sorted(runs, key=lambda r: (order.get(r["label"], 99), r["run_id"]))

    def cord_predictions(self, run_dir: str) -> dict[str, dict]:
        return {p["id"]: p for p in self._load_jsonl(self.pred_dir / run_dir / "predictions.jsonl") if "id" in p}

    # ------------------------------------------------------------------ availability
    def shards(self) -> list[Path]:
        return shard_paths(self.repo)

    def public_available(self) -> bool:
        return all(p.exists() for p in self.shards())

    def trade_available(self) -> bool:
        return all((self.trade_dir / d).is_dir() for d in ("images", "gold", "po"))

    def cache_path(self, base_id: str, quality: str) -> Path:
        # Both parts are validated (regex + manifest membership) before reaching here.
        return self.cache_dir / quality / base_id

    def cached_count(self) -> int:
        return sum(1 for q in QUALITIES if (self.cache_dir / q).is_dir() for _ in (self.cache_dir / q).glob("*.png"))

    # ------------------------------------------------------------------ public parquet access
    def public_source(self) -> dict[tuple[str, str], dict]:
        """(file_name, quality) -> {shard, row_group, row, template, line_items}; built once, no image bytes."""
        with self._index_lock:
            if self._public_source is None:
                if not self.public_available():
                    raise ApiError(HTTPStatus.NOT_FOUND, "local_public_data_missing")
                self._public_source = self._build_public_source()
            return self._public_source

    def _build_public_source(self) -> dict[tuple[str, str], dict]:
        index: dict[tuple[str, str], dict] = {}
        for path in self.shards():
            pf = pq.ParquetFile(path)
            for rg in range(pf.metadata.num_row_groups):
                table = pf.read_row_group(rg, columns=["file_name", "quality", "_template_used", "line_items"])
                cols = {name: table.column(name).to_pylist() for name in table.column_names}
                for i, (name, quality) in enumerate(zip(cols["file_name"], cols["quality"])):
                    index[(name, quality)] = {"shard": path, "row_group": rg, "row": i,
                                              "_template_used": cols["_template_used"][i],
                                              "line_items": cols["line_items"][i]}
        return index

    def public_image(self, base_id: str, quality: str, expected_sha256: str) -> Path:
        target = self.cache_path(base_id, quality)
        if target.exists():
            return target
        with self._extract_lock:
            if target.exists():
                return target
            loc = self.public_source().get((base_id, quality))
            if loc is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "row_not_in_parquet")
            pf = pq.ParquetFile(loc["shard"], buffer_size=1 << 20, pre_buffer=False)
            data = None
            for n, batch in enumerate(pf.iter_batches(batch_size=1, row_groups=[loc["row_group"]],
                                                       columns=["file_name", "quality", "image"])):
                if n == loc["row"]:
                    row = batch.to_pylist()[0]
                    if (row["file_name"], row["quality"]) != (base_id, quality):
                        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "parquet_index_mismatch")
                    data = (row["image"] or {}).get("bytes")
                    break
            if not data:
                raise ApiError(HTTPStatus.NOT_FOUND, "image_bytes_missing")
            if hashlib.sha256(data).hexdigest() != expected_sha256:
                raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "image_sha256_mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            return target


# ---------------------------------------------------------------------- query helpers
def _single(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name)
    if not values:
        return None
    if len(values) != 1:
        raise ApiError(HTTPStatus.BAD_REQUEST, "bad_param", name)
    return values[0]


def _int_param(params: dict[str, list[str]], name: str, default: int, low: int, high: int) -> int:
    raw = _single(params, name)
    if raw is None or raw == "":
        return default
    if not re.fullmatch(r"\d{1,7}", raw) or not low <= int(raw) <= high:
        raise ApiError(HTTPStatus.BAD_REQUEST, "bad_param", name)
    return int(raw)


def _facet_value(row: dict, key: str) -> str:
    value = row.get(key)
    if value is None:
        return NONE_VALUE
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _filter_rows(rows: list[dict], params: dict[str, list[str]], facets: dict[str, str],
                 search_key: str) -> dict[str, Any]:
    """Filter by exact facet values (validated against the known values), substring search, paging."""
    allowed = set(facets) | {"q", "offset", "limit"}
    unknown = set(params) - allowed
    if unknown:
        raise ApiError(HTTPStatus.BAD_REQUEST, "unknown_param", sorted(unknown)[0])
    facet_values = {param: sorted({_facet_value(r, key) for r in rows}) for param, key in facets.items()}
    selected = rows
    for param, key in facets.items():
        value = _single(params, param)
        if value is None or value == "":
            continue
        if value not in facet_values[param]:
            raise ApiError(HTTPStatus.BAD_REQUEST, "bad_param", param)
        selected = [r for r in selected if _facet_value(r, key) == value]
    query = _single(params, "q")
    if query:
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,40}", query):
            raise ApiError(HTTPStatus.BAD_REQUEST, "bad_param", "q")
        selected = [r for r in selected if query.lower() in str(r.get(search_key, "")).lower()]
    offset = _int_param(params, "offset", 0, 0, MAX_OFFSET)
    limit = _int_param(params, "limit", 50, 1, MAX_LIMIT)
    return {"total": len(selected), "offset": offset, "limit": limit,
            "facets": {p: [{"value": v, "count": sum(_facet_value(r, facets[p]) == v for r in rows)}
                           for v in vals] for p, vals in facet_values.items()},
            "page": selected[offset:offset + limit]}


PUBLIC_FACETS = {"pool": "pool", "standard_role": "standard_role", "mini_role": "mini_role",
                 "template": "template", "quality": "quality", "eligible": "train_eligible"}
TRADE_FACETS = {"split": "split", "template": "template", "scenario_type": "scenario_type",
                "mini_role": "mini_role", "injection": "has_injection_text"}
PUBLIC_LIST_KEYS = ("base_id", "quality", "template", "pool", "standard_role", "mini_role", "train_eligible",
                    "train_ineligible_reason", "n_items", "n_scored_fields", "n_masked_fields")
TRADE_LIST_KEYS = ("doc_id", "split", "template", "scenario_type", "expected_codes", "n_rows", "mini_role",
                   "standard_role", "has_injection_text", "render_check", "quality")
CORD_FACETS = {"split": "split", "eligible": "train_eligible", "overlap": "content_overlap", "has_sub": "has_sub",
               "masked": "has_masked"}
# arm labels by adapter folder (docs/20): base model, the adapter trained without CORD, the adapter trained with it
CORD_ARMS = {None: "M0", "m1_standard_v1": "M1 v1", "m1_cord_v1": "M1-cord",
             # exploratory dev-only runs (docs/20 amendments 2, 3, 5) — never CORD test
             "m1_cord_s20261114": "M1-cord seed 20261114", "m1_cord_s20261115": "M1-cord seed 20261115",
             "m1_cord_up_v1": "M1-cord 단가 가중 (수정 3)", "m1_cord_qkvo": "M1-cord q·k·v·o (수정 5)", "m1_cord_r16": "M1-cord r16 (수정 5)"}
CORD_ARM_ORDER = ("M0", "M1 v1", "M1-cord")
CORD_FIELD_ORDER = ("name", "count", "unit_price", "price")
CORD_DOC_ORDER = ("subtotal", "tax", "total")


def cord_arm_label(adapter: str | None) -> str:
    name = Path(adapter).name if adapter else None
    return CORD_ARMS.get(name, name or "M0")


def _cord_list_row(r: dict) -> dict:
    overlap = ("dup_excluded" if r.get("content_dup_of_heldout")
               else "seen_in_train" if r.get("content_seen_in_train") else "none")
    return {"id": r["id"], "split": r["split"], "cord_image_id": r.get("cord_image_id"), "n_items": r.get("n_items"),
            "n_sub_items": r.get("n_sub_items"), "train_eligible": bool(r.get("train_eligible")),
            "content_overlap": overlap, "has_sub": bool(r.get("n_sub_items")), "has_masked": bool(r.get("masked")),
            "n_masked": len(r.get("masked") or []), "width": r.get("width"), "height": r.get("height")}


# ---------------------------------------------------------------------- endpoint bodies
def _safe(errors: dict[str, str], name: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as exc:  # a report being edited concurrently must not take the whole page down
        errors[name] = f"{type(exc).__name__}: {exc}"
        return None


def _flatten(value: Any, prefix: str = "") -> list[list[str]]:
    if isinstance(value, dict):
        out: list[list[str]] = []
        for key, sub in value.items():
            out += _flatten(sub, f"{prefix}.{key}" if prefix else str(key))
        return out
    return [[prefix or "(value)", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)]]


def _read_record(path: Path) -> Any:
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError("skipped: file larger than the dashboard limit")
    return _read_json(path)


def _records(errors: dict[str, str], folder: Path, rel: str) -> dict[str, Any]:
    """Parsed JSON records of one reports/ folder (training runs, serving measurements), as written by the
    project's own scripts. Shown as recorded; oversize files are listed as skipped instead of being cut."""
    out: dict[str, Any] = {}
    for path in sorted(folder.glob("*.json"))[:MAX_RECORD_FILES]:
        content = _safe(errors, f"{rel}/{path.name}", lambda path=path: _read_record(path))
        if content is not None:
            out[path.name if rel.endswith("model") else path.stem] = content
    return out


def status_body(store: DataStore) -> dict[str, Any]:
    repo = store.repo
    errors: dict[str, str] = {}
    tasks, gates = _safe(errors, "task_board", lambda: snap.parse_task_board(
        (repo / "reports" / "TASK_BOARD.md").read_text(encoding="utf-8"))) or ([], [])
    config = _safe(errors, "config", lambda: yaml.safe_load((repo / "configs" / "project.yaml").read_text(encoding="utf-8")))
    smoke = []
    for path in sorted((repo / "reports" / "model").glob("local_smoke*.json"))[:MAX_SMOKE_FILES]:
        content = _safe(errors, f"reports/model/{path.name}", lambda path=path: _read_json(path))
        if content is not None:  # raw key/values only; the dashboard does not interpret them
            smoke.append({"path": f"reports/model/{path.name}", "pairs": _flatten(content)[:MAX_SMOKE_PAIRS]})
    evaluations, comparisons = [], []
    for path in sorted((repo / "reports" / "eval").glob("*.json")):
        content = _safe(errors, f"reports/eval/{path.name}", lambda path=path: _read_json(path))
        if not isinstance(content, dict):
            continue
        if "headline" in content and content.get("run_id"):
            sets = (content.get("run_metadata") or {}).get("sets") or []
            stage = "final" if any(x in ("public:iid_final", "public:ood_final", "trade:test") for x in sets) else (
                "dev" if any("dev" in x or x.startswith("stress:") for x in sets) else "train_diagnostic")
            meta = content.get("run_metadata") or {}
            evaluations.append({"file": f"reports/eval/{path.name}", "run_id": content["run_id"], "arm": content.get("arm"),
                                "stage": stage, "denominator_check": content.get("denominator_check"),
                                "adapter_sha256": (meta.get("fingerprint") or {}).get("adapter_sha256"),
                                "wall_seconds": meta.get("wall_seconds"),
                                "headline": content["headline"]})
        elif path.name.startswith("compare_") and not path.name.startswith("compare_cord_") and "sets" in content:
            comparisons.append({"file": f"reports/eval/{path.name}", "a": content.get("a"), "b": content.get("b"),
                                "sets": content["sets"]})
    return {
        "tasks": tasks, "gates": gates,
        "evaluations": evaluations, "comparisons": comparisons,
        "hardware": (config or {}).get("hardware"),
        "approval": _safe(errors, "approval", lambda: snap.parse_kv(snap._read(repo / "reports" / "RUNPOD_APPROVAL.md") or "")),
        "handoff": _safe(errors, "handoff", lambda: snap.parse_kv(snap._read(repo / "reports" / "SESSION_HANDOFF.md") or "")),
        "handoff_decision": _safe(errors, "handoff_decision", lambda: snap.parse_decision(snap._read(repo / "reports" / "SESSION_HANDOFF.md") or "")),
        "public_profile": _safe(errors, "public_profile", lambda: _read_json(repo / "reports" / "data" / "public_profile.json")),
        "public_manifest": _safe(errors, "public_manifest", lambda: _read_json(repo / "manifests" / "public_canonical_v1.summary.json")),
        "trade_manifest": _safe(errors, "trade_manifest", lambda: _read_json(repo / "manifests" / "trade_raw_v1.summary.json")),
        "results": _safe(errors, "results", lambda: _read_json(repo / "reports" / "RESULTS_TEMPLATE.json")),
        "junit": _safe(errors, "junit", lambda: snap.parse_junit(repo / "artifacts" / "dashboard" / "pytest_junit.xml")),
        "local_smoke": smoke,
        "cord": _safe(errors, "cord", lambda: cord_status(store, errors)),
        "model_reports": _records(errors, repo / "reports" / "model", "reports/model"),
        "serving": _records(errors, repo / "reports" / "serving", "reports/serving"),
        "local_data": {"public_parquet": store.public_available(), "trade_files": store.trade_available(),
                       "public_cached_images": store.cached_count()},
        "labels": {"status_ko": snap.STATUS_KO, "status_class": snap.STATUS_CLASS, "visibility_ko": VISIBILITY_KO},
        "errors": errors,
    }


def public_rows_body(store: DataStore, params: dict[str, list[str]]) -> dict[str, Any]:
    result = _filter_rows(store.public_manifest(), params, PUBLIC_FACETS, "base_id")
    result["page"] = [{k: r.get(k) for k in PUBLIC_LIST_KEYS} for r in result["page"]]
    return result


def public_doc_body(store: DataStore, base_id: str, params: dict[str, list[str]]) -> dict[str, Any]:
    rows = store.public_rows_for(base_id)
    if not rows:
        raise ApiError(HTTPStatus.NOT_FOUND, "unknown_id")
    if set(params) - {"quality"}:
        raise ApiError(HTTPStatus.BAD_REQUEST, "unknown_param")
    quality = _single(params, "quality") or rows[0]["quality"]
    row = next((r for r in rows if r["quality"] == quality), None)
    if row is None:
        raise ApiError(HTTPStatus.BAD_REQUEST, "bad_param", "quality")
    meta_keys = ("base_id", "template", "pool", "group_id", "content_hash", "target_hash", "train_eligible",
                 "train_ineligible_reason", "label_status", "origin", "source", "revision", "renderer_commit",
                 "task", "n_items", "n_scored_fields", "n_masked_fields")
    gold: dict[str, Any] = {"available": False, "reason": None, "items": [], "from_quality": quality}
    try:
        record = store.public_source().get((base_id, quality))
        if record is None:
            gold["reason"] = "row_not_in_parquet"
        else:
            visibility = row.get("visibility") or []
            items = canonical_items(record)
            for i, item in enumerate(items):
                item["visibility"] = visibility[i] if i < len(visibility) else None
            gold.update(available=True, items=items, template_in_parquet=record["_template_used"],
                        visibility_rows_match=len(visibility) == len(items))
    except ApiError as exc:
        gold["reason"] = exc.code
    return {
        "meta": {k: row.get(k) for k in meta_keys},
        "quality": quality,
        "qualities": [{"quality": r["quality"], "standard_role": r.get("standard_role"), "mini_role": r.get("mini_role"),
                       "image_sha256": r.get("image_sha256"),
                       "image_cached": store.cache_path(base_id, r["quality"]).exists()} for r in rows],
        "gold": gold,
        "public_parquet_available": store.public_available(),
    }


def trade_rows_body(store: DataStore, params: dict[str, list[str]]) -> dict[str, Any]:
    result = _filter_rows(store.trade_manifest(), params, TRADE_FACETS, "doc_id")
    result["page"] = [{k: r.get(k) for k in TRADE_LIST_KEYS} for r in result["page"]]
    return result


def trade_doc_body(store: DataStore, doc_id: str, params: dict[str, list[str]]) -> dict[str, Any]:
    row = store.trade_row(doc_id)
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "unknown_id")
    if params:
        raise ApiError(HTTPStatus.BAD_REQUEST, "unknown_param")
    paths = {"gold": store.trade_dir / "gold" / f"{doc_id}.json", "po": store.trade_dir / "po" / f"{doc_id}.json",
             "image": store.trade_dir / "images" / f"{doc_id}.png"}
    integrity = {k: (_sha256(p) == row.get(f"{k}_sha256")) if p.exists() else None for k, p in paths.items()}
    gold = _read_json(paths["gold"])
    po = _read_json(paths["po"])
    oracle = reconcile(gold, po, "oracle_fixture") if gold is not None else None
    oracle_codes = sorted(f["code"] for f in oracle["findings"]) if oracle else None
    expected = sorted(row.get("expected_codes") or [])
    return {
        "meta": row, "gold": gold, "po": po, "oracle": oracle, "integrity": integrity,
        "expected_codes": expected, "oracle_codes": oracle_codes,
        "codes_match": None if oracle_codes is None else oracle_codes == expected,
    }


def cord_rows_body(store: DataStore, params: dict[str, list[str]]) -> dict[str, Any]:
    return _filter_rows([_cord_list_row(r) for r in store.cord_manifest()], params, CORD_FACETS, "id")


def _slot_label(key: tuple) -> tuple[str, str]:
    if key[0] == "item":
        return f"{key[1] + 1}", "item"
    if key[0] == "sub":
        return f"{key[1] + 1}.{key[2] + 1}", "sub"
    return "", "doc"


def _slot_order(key: tuple) -> tuple:
    if key[0] == "doc":
        return (10_000, 0, CORD_DOC_ORDER.index(key[1]) if key[1] in CORD_DOC_ORDER else 9)
    sub = key[2] + 1 if key[0] == "sub" else 0
    field = key[-1]
    return (key[1], sub, CORD_FIELD_ORDER.index(field) if field in CORD_FIELD_ORDER else 9)


def _cell_state(field: str, gold_value: Any, pred_value: Any, masked: bool) -> str:
    if masked:
        return "masked"
    if gold_value is None:
        return "filled" if pred_value is not None else "empty"
    if strict_norm(pred_value) == strict_norm(gold_value):
        return "ok"
    lp = loose_norm(field, pred_value)
    if lp is not None and lp == loose_norm(field, gold_value):
        return "format"
    return "wrong" if pred_value is not None else "missing"


def cord_doc_body(store: DataStore, rid: str, params: dict[str, list[str]]) -> dict[str, Any]:
    """Gold, and for every recorded run on this split: the fence-stripped answer scored slot by slot with the
    pre-registered evaluator (cord_eval.score_document). Nothing is re-generated; a missing answer stays missing."""
    row = store.cord_row(rid)
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "unknown_id")
    if params:
        raise ApiError(HTTPStatus.BAD_REQUEST, "unknown_param")
    image_path = store.cord_dir / "images" / f"{rid}.png"
    gold = _read_json(store.cord_dir / "gold" / f"{rid}.json")
    # gold_sha256 is the canonical dump the manifest builder hashed (cord.build), not the file bytes
    gold_hash = None if gold is None else hashlib.sha256(
        json.dumps(gold, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    integrity = {"gold": None if gold is None else gold_hash == row.get("gold_sha256"),
                 "image": _sha256(image_path) == row.get("image_sha256") if image_path.exists() else None}
    masked = row.get("masked") or []
    skip = _masked_keys(masked)
    gold_slots = {key: (field, value) for key, field, value in slots(gold)} if gold else {}
    runs, run_values = [], []
    for run in store.cord_runs():
        if f"cord:{row['split']}" not in run["sets"]:
            continue
        rec = store.cord_predictions(run["dir"]).get(rid)
        info = {k: run[k] for k in ("run_id", "label", "adapter", "sets")}
        if rec is None:
            runs.append(info | {"status": "missing", "score": None})
            run_values.append({})
            continue
        parsed = parse_for_eval(rec, CORD_TASK, lenient=True)
        strict_ok = parse_for_eval(rec, CORD_TASK, lenient=False).status == "ok"
        doc = score_document(gold, masked, parsed) if gold else None
        raw = rec.get("raw_response")
        if isinstance(raw, str) and len(raw) > MAX_RAW_CHARS:
            raw = raw[:MAX_RAW_CHARS] + f"\n[... {len(raw) - MAX_RAW_CHARS} chars not shown]"
        runs.append(info | {
            "status": parsed.status, "strict_json": strict_ok, "fence_stripped": parsed.status == "ok" and not strict_ok,
            "finish_reason": rec.get("finish_reason"), "generated_tokens": rec.get("generated_tokens"),
            "latency_s": rec.get("batch_latency_s"), "raw_response": raw,
            "score": None if doc is None else {k: doc[k] for k in ("strict", "loose", "absent_filled", "rows_match",
                                                                   "doc_exact", "gold_items", "pred_items")}})
        run_values.append({key: value for key, _, value in slots(parsed.obj if parsed.status == "ok" else None)})
    keys = set(gold_slots) | {k for values in run_values for k, v in values.items() if v is not None}
    table = []
    for key in sorted(keys, key=_slot_order):
        field, gval = gold_slots.get(key, (key[-1], None))
        idx, kind = _slot_label(key)
        table.append({"index": idx, "kind": kind, "field": field, "gold": gval, "in_gold": key in gold_slots,
                      "masked": key in skip,
                      "cells": [{"value": values.get(key), "state": _cell_state(field, gval, values.get(key), key in skip)}
                                for values in run_values]})
    return {"meta": row, "gold": gold, "integrity": integrity, "runs": runs, "slots": table,
            "local_data": store.cord_available()}


def cord_status(store: DataStore, errors: dict[str, str]) -> dict[str, Any]:
    """Everything the CORD pages show, read from the records the CORD scripts wrote (nothing is recomputed)."""
    repo = store.repo
    evals, comps = [], []
    for path in sorted((repo / "reports" / "eval").glob("cord_*.json")):
        content = _safe(errors, f"reports/eval/{path.name}", lambda path=path: _read_json(path))
        if not isinstance(content, dict):
            continue
        fp = content.get("fingerprint") or {}
        for spec, v in (content.get("sets") or {}).items():
            evals.append({"file": f"reports/eval/{path.name}", "run_id": content.get("run_id"), "set": spec,
                          "arm": fp.get("arm"), "adapter_sha256": fp.get("adapter_sha256"),
                          "wall_seconds": content.get("wall_seconds"), "peak_vram_gb": content.get("peak_vram_gb"),
                          "all": v.get("all"), "unseen": v.get("content_unseen"),
                          "strict_json": v.get("strict_json_no_repair_all"),
                          "fence_stripped_documents": v.get("fence_stripped_documents")})
    for path in sorted((repo / "reports" / "eval").glob("compare_cord_*.json")):
        content = _safe(errors, f"reports/eval/{path.name}", lambda path=path: _read_json(path))
        if isinstance(content, dict) and "sets" in content:
            comps.append({"file": f"reports/eval/{path.name}", "a": content.get("a"), "b": content.get("b"),
                          "sets": content["sets"]})
    runs = store.cord_runs()
    labels = {r["run_id"]: r["label"] for r in runs}
    for e in evals:
        e["label"] = labels.get(e["run_id"])
    for c in comps:
        c["a_label"], c["b_label"] = labels.get(c["a"]), labels.get(c["b"])
    fetch = _safe(errors, "cord_fetch", lambda: _read_json(repo / "reports" / "realdocs" / "cord_fetch.json"))
    build = _safe(errors, "cord_build", lambda: _read_json(repo / "reports" / "realdocs" / "cord_build.json"))
    return {
        "evaluations": evals, "comparisons": comps,
        "runs": [{k: v for k, v in r.items() if k != "dir"} for r in runs],
        "regression": _safe(errors, "cord_regression", lambda: _read_json(
            repo / "reports" / "eval" / "compare_m1cord_dev_v1__vs__m1_dev_v1.json")),
        "frozen": _safe(errors, "cord_frozen", lambda: _read_json(repo / "configs" / "frozen_cord_v1.json")),
        "build": build,
        "fetch": None if not fetch else {k: fetch.get(k) for k in (
            "repo", "revision", "license", "source", "approved_by_user", "fetched_at", "total_bytes", "total_seconds",
            "all_ok")} | {"files": len(fetch.get("files") or [])},
        "budget": _safe(errors, "cord_budget", lambda: _read_json(repo / "reports" / "realdocs" / "cord_budget.json")),
        "local_data": store.cord_available(),
    }


# ---------------------------------------------------------------------- HTTP layer
ROUTES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/api/status"), "status"),
    (re.compile(r"/api/public/rows"), "public_rows"),
    (re.compile(rf"/api/public/doc/({PUBLIC_ID})"), "public_doc"),
    (re.compile(rf"/api/public/image/({PUBLIC_ID})/({QUALITY})"), "public_image"),
    (re.compile(r"/api/trade/rows"), "trade_rows"),
    (re.compile(rf"/api/trade/doc/({TRADE_ID})"), "trade_doc"),
    (re.compile(rf"/api/trade/image/({TRADE_ID})"), "trade_image"),
    (re.compile(r"/api/cord/rows"), "cord_rows"),
    (re.compile(rf"/api/cord/doc/({CORD_ID})"), "cord_doc"),
    (re.compile(rf"/api/cord/image/({CORD_ID})"), "cord_image"),
]


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "InvoiceGuardDashboard/1"
    sys_version = ""
    store: DataStore  # set by make_server via a subclass attribute

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter, no headers or query bodies
        sys.stderr.write(f"[dashboard] {self.address_string()} {fmt % args}\n")

    # -- responses
    def _send(self, status: HTTPStatus, body: bytes, ctype: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, code: str, detail: str | None = None) -> None:
        self._json(status, {"error": code, "detail": detail})

    def _host_ok(self) -> bool:
        # DNS-rebinding guard: only accept the loopback names we are actually reachable under.
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    # -- methods
    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        try:
            if not self._host_ok():
                return self._error(HTTPStatus.BAD_REQUEST, "bad_host")
            parts = urlsplit(self.path)
            path = parts.path
            if path in STATIC_ROUTES:
                name, ctype = STATIC_ROUTES[path]
                return self._send(HTTPStatus.OK, (STATIC_DIR / name).read_bytes(), ctype)
            for pattern, name in ROUTES:
                match = pattern.fullmatch(path)
                if match:
                    try:
                        params = parse_qs(parts.query, keep_blank_values=False, max_num_fields=20)
                    except ValueError:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "bad_query") from None
                    return self._dispatch(name, match.groups(), params)
            return self._error(HTTPStatus.NOT_FOUND, "not_found")
        except ApiError as exc:
            return self._error(exc.status, exc.code, exc.detail)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return None
        except Exception as exc:
            traceback.print_exc()
            try:
                return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", type(exc).__name__)
            except OSError:
                return None

    def _method_not_allowed(self) -> None:
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "read_only")

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _method_not_allowed

    def _dispatch(self, name: str, groups: tuple[str, ...], params: dict[str, list[str]]) -> None:
        store = self.store
        if name == "status":
            return self._json(HTTPStatus.OK, status_body(store))
        if name == "public_rows":
            return self._json(HTTPStatus.OK, public_rows_body(store, params))
        if name == "public_doc":
            return self._json(HTTPStatus.OK, public_doc_body(store, groups[0], params))
        if name == "trade_rows":
            return self._json(HTTPStatus.OK, trade_rows_body(store, params))
        if name == "trade_doc":
            return self._json(HTTPStatus.OK, trade_doc_body(store, groups[0], params))
        if name == "cord_rows":
            return self._json(HTTPStatus.OK, cord_rows_body(store, params))
        if name == "cord_doc":
            return self._json(HTTPStatus.OK, cord_doc_body(store, groups[0], params))
        if params:
            raise ApiError(HTTPStatus.BAD_REQUEST, "unknown_param")
        if name == "public_image":
            base_id, quality = groups
            row = store.public_row(base_id, quality)
            if row is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "unknown_id")
            path = store.public_image(base_id, quality, row["image_sha256"])
            return self._send(HTTPStatus.OK, path.read_bytes(), "image/png", "private, max-age=86400")
        if name == "trade_image":
            if store.trade_row(groups[0]) is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "unknown_id")
            path = store.trade_dir / "images" / f"{groups[0]}.png"
            if not path.exists():
                raise ApiError(HTTPStatus.NOT_FOUND, "local_trade_data_missing")
            return self._send(HTTPStatus.OK, path.read_bytes(), "image/png", "private, max-age=86400")
        if name == "cord_image":
            row = store.cord_row(groups[0])
            if row is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "unknown_id")
            path = store.cord_dir / "images" / f"{groups[0]}.png"
            if not path.exists():
                raise ApiError(HTTPStatus.NOT_FOUND, "local_cord_data_missing")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != row.get("image_sha256"):
                raise ApiError(HTTPStatus.CONFLICT, "image_hash_mismatch")
            return self._send(HTTPStatus.OK, data, "image/png", "private, max-age=86400")
        raise ApiError(HTTPStatus.NOT_FOUND, "not_found")


def make_server(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, store: DataStore | None = None) -> ThreadingHTTPServer:
    """Create (not start) the server. Only the IPv4 loopback address is accepted."""
    if host != DEFAULT_HOST:
        raise ValueError("the admin dashboard binds to 127.0.0.1 only")
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"store": store or DataStore()})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local admin dashboard (127.0.0.1 only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--run-tests", action="store_true", help="run pytest once and record junit before serving")
    args = parser.parse_args(argv)
    if args.run_tests:
        snap.run_tests(REPO / "artifacts" / "dashboard" / "pytest_junit.xml")
    server = make_server(args.port)
    host, port = server.server_address[:2]
    print(f"InvoiceGuard admin dashboard (read-only): http://{host}:{port}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
