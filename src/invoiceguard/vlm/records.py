"""Training/eval records = (task, fixed prompt, image, gold answer JSON). Gold never enters the prompt."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..extraction_request import load_prompt
from ..public_data import canonical_items, iter_rows, shard_paths
from . import REPO

TRADE_KEYS = ("schema_version", "document_type", "invoice_number_raw", "currency_raw", "items",
              "subtotal_raw", "tax_raw", "discount_raw", "total_raw")
TRADE_ITEM_KEYS = ("row_index", "sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw")
PUBLIC_IMAGE_DIR = REPO / "data" / "processed" / "public" / "train_images"


def dump_answer(obj: dict) -> str:
    """Deterministic compact JSON target (keys in schema order, non-ASCII kept)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@dataclass
class Record:
    record_id: str
    task: str
    image_path: Path
    answer: str
    role: str

    def image(self) -> Image.Image:
        with Image.open(self.image_path) as img:
            return img.convert("RGB")

    def prompt(self) -> str:
        return load_prompt(self.task)[0]


def trade_answer(gold: dict) -> str:
    items = [{k: it[k] for k in TRADE_ITEM_KEYS} for it in gold["items"]]
    return dump_answer({k: (items if k == "items" else gold[k]) for k in TRADE_KEYS})


def public_answer(record: dict) -> str:
    items = [{"row_index": it["row_index"], "description": it["description"], "quantity": it["quantity"],
              "unit_price": it["unit_price"], "amount": it["amount"]} for it in canonical_items(record)]
    return dump_answer({"schema_version": "public-1.0", "items": items})


def _manifest(name: str) -> list[dict]:
    return [json.loads(line) for line in (REPO / "manifests" / name).read_text(encoding="utf-8").splitlines()]


def trade_records(role_field: str = "standard_role", role: str = "train", manifest: str = "trade_raw_v1.jsonl") -> list[Record]:
    out = []
    for row in _manifest(manifest):
        if row[role_field] != role:
            continue
        gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{row['doc_id']}.json").read_text(encoding="utf-8"))
        out.append(Record(row["doc_id"], "TRADE_RAW", REPO / "data" / "processed" / "trade" / "images" / f"{row['doc_id']}.png",
                          trade_answer(gold), role))
    return out


def public_records(role_field: str = "standard_role", role: str = "train") -> list[Record]:
    """Only train-eligible clean rows are used for training (all four fields visible_exact)."""
    wanted = {(r["base_id"], r["quality"]): r for r in _manifest("public_canonical_v1.jsonl") if r[role_field] == role}
    if role == "train":
        assert all(r["train_eligible"] and r["quality"] == "clean" for r in wanted.values())
    PUBLIC_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    missing = {k for k in wanted if not (PUBLIC_IMAGE_DIR / f"{k[0][:-4]}__{k[1]}.png").exists()}
    labels: dict[str, dict] = {}
    for row in iter_rows(shard_paths(REPO), with_images=bool(missing), batch_size=16):
        key = (row["file_name"], row["quality"])
        if key not in wanted:
            continue
        labels[row["file_name"]] = row
        if key in missing:
            (PUBLIC_IMAGE_DIR / f"{key[0][:-4]}__{key[1]}.png").write_bytes(row["image"]["bytes"])
    for (name, quality) in sorted(wanted):
        out.append(Record(f"{name[:-4]}__{quality}", "PUBLIC_CANONICAL", PUBLIC_IMAGE_DIR / f"{name[:-4]}__{quality}.png",
                          public_answer(labels[name]), role))
    return out


def image_bytes(record: Record) -> bytes:
    buf = io.BytesIO()
    record.image().save(buf, format="PNG")
    return buf.getvalue()


def cord_records(split: str, train_only_eligible: bool = True) -> list[Record]:
    """CORD v2 receipts (docs/20). split: train|dev|test. Training uses only train_eligible rows (no list-valued
    labels, no content duplicate of a dev/test answer); dev/test keep every document so denominators never shrink."""
    from ..cord import OUT_DIR, load_gold, manifest_rows

    rows = manifest_rows(split)
    if split == "train" and train_only_eligible:
        rows = [r for r in rows if r["train_eligible"]]
    return [Record(r["id"], "CORD_RAW", OUT_DIR / "images" / f"{r['id']}.png", dump_answer(load_gold(r["id"])), split)
            for r in rows]


def cord_unit_price_records() -> list[Record]:
    """docs/20 amendment 3 (exploratory, dev only): the train-eligible CORD receipts whose gold has at least one printed
    unit price, used as a second copy to up-weight them. On dev, M1-cord left 8 printed unit prices null on rows it did
    emit (usually when the unit price equals the line total, or printed with "@")."""
    from ..cord import load_gold

    return [r for r in cord_records("train")
            if any(it.get("unit_price") is not None for it in load_gold(r.record_id).get("items") or [])]
