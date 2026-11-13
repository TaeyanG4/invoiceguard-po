"""InvoiceOCR-Synth (public, SYNTHETIC English) loading and label conversion.

Only the four PUBLIC_CANONICAL target fields (description, quantity, unit_price, amount)
are converted. SKU / unit / raw printed formatting are NOT available and are never invented.
Parquet doubles are converted via label_to_decimal (round-trip repr, no arithmetic) and
cross-checked against ground_truth_released.json parsed with parse_float=Decimal.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import pyarrow.parquet as pq

from .canonical import LabelDataError, canonical_str, label_to_decimal

DATASET_ID = "alamgirqazi/invoice-ocr-synthetic"
DATASET_REVISION = "673ff85be462eb7f3715ec188a295dd17ca11115"
SHARD_SHA256 = {
    "data/train-00000-of-00002.parquet": "62b0432e30bc41baff495f0dfdfc64ffbccaaa39f1814e9528b7ed0d9f2085b3",
    "data/train-00001-of-00002.parquet": "7e48694c5acb676a7d9853c07cba82affb652463ccf14b1f97e678302a7d968b",
}
HOLDOUT_TEMPLATE = "freelancer_invoice"
QUALITIES = ("clean", "faded", "bad_scan")
TARGET_NUMERIC_FIELDS = ("quantity", "unit_price", "amount")

# Row metadata / provenance that must NOT define business content identity.
NON_CONTENT_FIELDS = frozenset({
    "file_name", "quality", "image", "_template_used", "_font_info", "labeled_at",
    "degradation_variants", "_synthetic", "mime_type",
})


def dataset_root(repo_root: Path) -> Path:
    return repo_root / "data" / "raw" / "invoice-ocr-synthetic" / DATASET_REVISION


def shard_paths(repo_root: Path) -> list[Path]:
    root = dataset_root(repo_root)
    return [root / rel for rel in sorted(SHARD_SHA256)]


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def iter_rows(paths: list[Path], with_images: bool = False, batch_size: int = 32) -> Iterator[dict[str, Any]]:
    """Yield parquet rows as python dicts. Image bytes only when requested."""
    for path in paths:
        pf = pq.ParquetFile(path)
        columns = [name for name in pf.schema_arrow.names if with_images or name != "image"]
        for batch in pf.iter_batches(batch_size=batch_size, columns=columns):
            for row in batch.to_pylist():
                row["_shard"] = path.name
                yield row


def nfkc_ws(text: str | None) -> str | None:
    """Description normalisation for EM: NFKC + whitespace collapse; case preserved."""
    if text is None:
        return None
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return canonical_str(value)
    if isinstance(value, float):
        return canonical_str(label_to_decimal(value))
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    raise TypeError(type(value).__name__)


def _numbers_to_decimal(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (float, int, Decimal)):
        return label_to_decimal(value)
    if isinstance(value, list):
        return [_numbers_to_decimal(v) for v in value]
    if isinstance(value, dict):
        return {k: _numbers_to_decimal(v) for k, v in value.items()}
    return value


def business_content_hash(record: dict[str, Any]) -> str:
    """Canonical hash of business content, ignoring file name, quality, font, template, image."""
    content = {k: _numbers_to_decimal(v) for k, v in record.items()
               if k not in NON_CONTENT_FIELDS and not k.startswith("_")}
    blob = json.dumps(content, sort_keys=True, ensure_ascii=False, default=_json_default)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def canonical_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert source line items into PUBLIC_CANONICAL gold items.

    Each numeric field gets a status: 'ok' (canonical string), 'source_null'
    (publisher-defined null; NOT verified as absent on the page), or 'data_error'.
    """
    items = []
    for index, item in enumerate(record.get("line_items") or [], start=1):
        gold: dict[str, Any] = {"row_index": index, "description": item.get("description"),
                                "field_status": {}}
        for field in TARGET_NUMERIC_FIELDS:
            value = item.get(field)
            if value is None:
                gold[field] = None
                gold["field_status"][field] = "source_null"
                continue
            try:
                gold[field] = canonical_str(label_to_decimal(value))
                gold["field_status"][field] = "ok"
            except LabelDataError as exc:
                gold[field] = None
                gold["field_status"][field] = f"data_error:{exc}"
        gold["field_status"]["description"] = "ok" if gold["description"] else "source_null"
        items.append(gold)
    return items


def line_items_target_hash(record: dict[str, Any]) -> str:
    """Hash of the extraction target only (normalised descriptions + canonical numbers)."""
    target = [[nfkc_ws(it["description"]), it["quantity"], it["unit_price"], it["amount"]]
              for it in canonical_items(record)]
    return hashlib.sha256(json.dumps(target, ensure_ascii=False).encode("utf-8")).hexdigest()


def load_released_ground_truth(repo_root: Path) -> list[dict[str, Any]]:
    path = dataset_root(repo_root) / "ground_truth_released.json"
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
