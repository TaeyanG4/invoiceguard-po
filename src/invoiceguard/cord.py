"""CORD v2 real receipt photos -> CORD_RAW gold + manifest (docs/20_DECISIONS_V6.md).

Gold values are the dataset's own printed strings; nothing is converted. A requested field whose CORD label is a list
(text split over several boxes) is NOT joined: it becomes null in the gold and is listed in `masked`, so the evaluator
skips it and training leaves that document out.

Usage (.venv-ml): python -I -m invoiceguard.cord build
  writes data/processed/cord/{images,gold}/ (git-ignored) and manifests/cord_v2.jsonl (ids and hashes only).
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CORD_REVISION = "7f0115a4b758a71d6473b8d085751692da2fef98"
RAW_DIR = REPO / "data" / "raw" / "cord-v2" / CORD_REVISION / "data"
OUT_DIR = REPO / "data" / "processed" / "cord"
MANIFEST = REPO / "manifests" / "cord_v2.jsonl"
SPLITS = {"train": "train", "validation": "dev", "test": "test"}
ITEM_FIELDS = (("name", "nm"), ("count", "cnt"), ("unit_price", "unitprice"), ("price", "price"))
DOC_FIELDS = (("subtotal", "sub_total", "subtotal_price"), ("tax", "sub_total", "tax_price"),
              ("total", "total", "total_price"))
SCHEMA_VERSION = "cord-raw-1.0"


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _value(src: dict, key: str, path: str, masked: list[str]) -> str | None:
    v = src.get(key)
    if isinstance(v, list):
        masked.append(path)
        return None
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(f"unexpected {type(v).__name__} at {path}")
    return v


def to_gold(gt_parse: dict) -> tuple[dict, list[str]]:
    """CORD gt_parse -> (CORD_RAW gold object, masked field paths)."""
    masked: list[str] = []
    items = []
    for i, m in enumerate(_as_list(gt_parse.get("menu")), start=1):
        if not isinstance(m, dict):
            raise ValueError(f"menu[{i}] is {type(m).__name__}")
        item: dict[str, Any] = {"row_index": i}
        for out_key, src_key in ITEM_FIELDS:
            item[out_key] = _value(m, src_key, f"items[{i}].{out_key}", masked)
        subs = []
        for j, s in enumerate(_as_list(m.get("sub")), start=1):
            if not isinstance(s, dict):
                raise ValueError(f"menu[{i}].sub[{j}] is {type(s).__name__}")
            subs.append({out_key: _value(s, src_key, f"items[{i}].sub_items[{j}].{out_key}", masked)
                         for out_key, src_key in ITEM_FIELDS})
        item["sub_items"] = subs
        items.append(item)
    gold: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "items": items}
    for out_key, section, src_key in DOC_FIELDS:
        sec = gt_parse.get(section)
        if isinstance(sec, list):  # a whole section split into several groups: treat its fields as multi-box
            sec = {k: [x.get(k) for x in sec if isinstance(x, dict)] for x in sec if isinstance(x, dict) for k in x}
        gold[out_key] = _value(sec or {}, src_key, out_key, masked)
    return gold, masked


def iter_split(split: str):
    """(image_id, png_bytes, gt_parse) for one CORD split, in file order."""
    import pyarrow.parquet as pq

    files = sorted(RAW_DIR.glob(f"{split}-*.parquet"))
    if not files:
        raise SystemExit(f"no CORD parquet for {split} in {RAW_DIR}; run scripts/realdocs/fetch_cord.py")
    for f in files:
        table = pq.read_table(f)
        for img, gt in zip(table.column("image").to_pylist(), table.column("ground_truth").to_pylist()):
            g = json.loads(gt)
            yield int(g["meta"]["image_id"]), img["bytes"], g["gt_parse"]


def record_id(split: str, image_id: int) -> str:
    return f"cord_{SPLITS[split]}_{image_id:04d}"


def build() -> dict:
    from PIL import Image

    (OUT_DIR / "images").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "gold").mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()
    for split in SPLITS:
        for image_id, data, parse in iter_split(split):
            rid = record_id(split, image_id)
            if rid in seen:
                raise SystemExit(f"duplicate id {rid}")
            seen.add(rid)
            gold, masked = to_gold(parse)
            with Image.open(io.BytesIO(data)) as im:
                fmt, (w, h), orient = im.format, im.size, im.getexif().get(274)
            if fmt != "PNG" or orient not in (None, 1):
                raise SystemExit(f"{rid}: unexpected image format {fmt} / EXIF orientation {orient}")
            (OUT_DIR / "images" / f"{rid}.png").write_bytes(data)
            (OUT_DIR / "gold" / f"{rid}.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1) + "\n",
                                                           encoding="utf-8", newline="\n")
            n_sub = sum(len(it["sub_items"]) for it in gold["items"])
            rows.append({"id": rid, "split": SPLITS[split], "cord_split": split, "cord_image_id": image_id,
                         "image_sha256": hashlib.sha256(data).hexdigest(), "width": w, "height": h,
                         "n_items": len(gold["items"]), "n_sub_items": n_sub, "masked": masked,
                         "train_eligible": SPLITS[split] == "train" and not masked,
                         "gold_sha256": hashlib.sha256(json.dumps(gold, ensure_ascii=False, sort_keys=True).encode()).hexdigest()})
    rows.sort(key=lambda r: r["id"])
    # Business-content duplicates (CLAUDE.md contract 3): CORD's official split has different photos with identical
    # labels across splits. Train copies of a dev/test answer are excluded from training; dev/test rows are flagged
    # so results are also reported on the content-unseen subset.
    heldout = {r["gold_sha256"] for r in rows if r["split"] != "train"}
    train_gold = {r["gold_sha256"] for r in rows if r["split"] == "train"}
    for r in rows:
        if r["split"] == "train":
            r["content_dup_of_heldout"] = r["gold_sha256"] in heldout
            r["train_eligible"] = r["train_eligible"] and not r["content_dup_of_heldout"]
        else:
            r["content_seen_in_train"] = r["gold_sha256"] in train_gold
    MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    summary = {split: {"docs": sum(r["split"] == split for r in rows),
                       "with_masked": sum(r["split"] == split and bool(r["masked"]) for r in rows),
                       "train_eligible": sum(r["split"] == split and r["train_eligible"] for r in rows),
                       "content_dup_excluded": sum(r["split"] == split and r.get("content_dup_of_heldout", False) for r in rows),
                       "content_seen_in_train": sum(r["split"] == split and r.get("content_seen_in_train", False) for r in rows),
                       "items": sum(r["n_items"] for r in rows if r["split"] == split),
                       "sub_items": sum(r["n_sub_items"] for r in rows if r["split"] == split)}
               for split in SPLITS.values()}
    return {"manifest": str(MANIFEST.relative_to(REPO)).replace("\\", "/"),
            "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "summary": summary}


def manifest_rows(split: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if split is None or r["split"] == split]


def load_gold(rid: str) -> dict:
    return json.loads((OUT_DIR / "gold" / f"{rid}.json").read_text(encoding="utf-8"))


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["build"])
    ap.parse_args()
    out = build()
    (REPO / "reports" / "realdocs").mkdir(parents=True, exist_ok=True)
    (REPO / "reports" / "realdocs" / "cord_build.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
