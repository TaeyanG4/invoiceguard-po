"""T01: full local profile of InvoiceOCR-Synth at a pinned revision.

Usage: python -m invoiceguard.public_profile [--audit-dir DIR]

Outputs
  data/processed/public/rows.jsonl      per-row metadata (no image bytes; git-ignored)
  reports/data/public_profile.json      aggregate profile + checks (small, committed)
  <audit-dir>/*.png + audit_gold.json   deterministic 2-clean-per-template audit sample
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import math
from decimal import Decimal
from pathlib import Path

from PIL import Image

from .canonical import canonical_str, label_to_decimal
from .public_data import (
    DATASET_ID, DATASET_REVISION, QUALITIES, SHARD_SHA256, business_content_hash,
    canonical_items, dataset_root, iter_rows, line_items_target_hash,
    load_released_ground_truth, sha256_file, shard_paths,
)

REPO = Path(__file__).resolve().parents[2]
SEED = "20261113"
Image.MAX_IMAGE_PIXELS = 20_000_000  # configs/project.yaml scope.max_decoded_pixels


def _stable_key(*parts: str) -> str:
    return hashlib.sha256("|".join((SEED,) + parts).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", default=str(REPO / "data" / "processed" / "public" / "audit"))
    parser.add_argument("--skip-shard-hash", action="store_true")
    args = parser.parse_args()

    root = dataset_root(REPO)
    shards = shard_paths(REPO)
    report: dict = {"dataset_id": DATASET_ID, "revision": DATASET_REVISION, "origin": "synthetic_public",
                    "license_tag": "cc-by-4.0", "checks": {}}

    # 1. shard integrity
    shard_info = {}
    for rel, expected in SHARD_SHA256.items():
        path = root / rel
        actual = None if args.skip_shard_hash else sha256_file(path)
        shard_info[rel] = {"bytes": path.stat().st_size, "sha256": actual,
                           "matches_hf_lfs_oid": None if actual is None else actual == expected}
    report["shards"] = shard_info

    # 2. stream every row with image bytes: decode + hash
    out_dir = REPO / "data" / "processed" / "public"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_meta = []
    records_by_file: dict[str, dict] = {}
    content_by_file: dict[str, set] = collections.defaultdict(set)
    qualities_by_file: dict[str, list] = collections.defaultdict(list)
    decode_failures = []
    numeric_issues = collections.Counter()
    field_types = collections.Counter()
    for row in iter_rows(shards, with_images=True, batch_size=16):
        image = row.pop("image") or {}
        raw = image.get("bytes")
        meta = {"file_name": row["file_name"], "quality": row["quality"], "shard": row["_shard"],
                "template": row["_template_used"], "image_sha256": None, "image_format": None,
                "width": None, "height": None, "decode_ok": False}
        if raw:
            meta["image_sha256"] = hashlib.sha256(raw).hexdigest()
            try:
                with Image.open(io.BytesIO(raw)) as img:
                    meta["image_format"] = img.format
                    meta["mode"] = img.mode
                    meta["width"], meta["height"] = img.size
                    img.load()
                meta["decode_ok"] = True
            except Exception as exc:  # noqa: BLE001 - record and continue
                decode_failures.append({"file_name": row["file_name"], "quality": row["quality"], "error": repr(exc)})
        row.pop("_shard", None)
        meta["content_hash"] = business_content_hash(row)
        meta["target_hash"] = line_items_target_hash(row)
        meta["n_items"] = len(row.get("line_items") or [])
        for it in row.get("line_items") or []:
            for field in ("quantity", "unit_price", "amount"):
                value = it.get(field)
                field_types[(field, type(value).__name__)] += 1
                if isinstance(value, float) and not math.isfinite(value):
                    numeric_issues[f"{field}_non_finite"] += 1
                elif isinstance(value, float) and value < 0:
                    numeric_issues[f"{field}_negative"] += 1
            q = it.get("quantity")
            if isinstance(q, float) and math.isfinite(q) and q != int(q):
                numeric_issues["quantity_non_integer"] += 1
            if all(isinstance(it.get(f), float) and math.isfinite(it.get(f)) for f in ("quantity", "unit_price", "amount")):
                product = label_to_decimal(it["quantity"]) * label_to_decimal(it["unit_price"])
                amount = label_to_decimal(it["amount"])
                if product != amount:
                    numeric_issues["q_x_p_ne_amount_exact"] += 1
                    if abs(product - amount) > Decimal("0.01"):
                        numeric_issues["q_x_p_ne_amount_gt_0.01"] += 1
            if not it.get("description"):
                numeric_issues["description_null_or_empty"] += 1
        rows_meta.append(meta)
        content_by_file[row["file_name"]].add(meta["content_hash"])
        qualities_by_file[row["file_name"]].append(row["quality"])
        records_by_file.setdefault(row["file_name"], row)

    with (out_dir / "rows.jsonl").open("w", encoding="utf-8") as handle:
        for meta in rows_meta:
            handle.write(json.dumps(meta, ensure_ascii=False) + "\n")

    # 3. counts and claims
    base_files = sorted(records_by_file)
    report["counts"] = {
        "rows_actual": len(rows_meta), "rows_claimed": 2814,
        "base_documents_actual": len(base_files), "base_documents_claimed": 938,
        "rows_per_quality": dict(collections.Counter(m["quality"] for m in rows_meta)),
        "templates_base_docs": dict(collections.Counter(r["_template_used"] for r in records_by_file.values())),
        "locale_base_docs": dict(collections.Counter(r.get("locale") for r in records_by_file.values())),
        "currency_base_docs": dict(collections.Counter(r.get("document_currency") for r in records_by_file.values())),
        "category_base_docs": dict(collections.Counter(r.get("document_category") for r in records_by_file.values())),
        "items_per_doc": dict(sorted(collections.Counter(len(r.get("line_items") or []) for r in records_by_file.values()).items())),
        "image_formats": dict(collections.Counter(m["image_format"] for m in rows_meta)),
        "image_sizes_top": dict(collections.Counter(f'{m["width"]}x{m["height"]}' for m in rows_meta).most_common(10)),
        "max_image_pixels": max((m["width"] or 0) * (m["height"] or 0) for m in rows_meta),
        "line_item_field_types": {f"{k[0]}:{k[1]}": v for k, v in sorted(field_types.items())},
        "line_item_numeric_issues": dict(numeric_issues),
    }
    tmpl_by_file = {f: r["_template_used"] for f, r in records_by_file.items()}

    # 4. checks
    checks = report["checks"]
    checks["all_images_decoded"] = {"pass": not decode_failures, "failures": decode_failures[:20],
                                    "n_failures": len(decode_failures)}
    incomplete = {f: q for f, q in qualities_by_file.items() if sorted(q) != sorted(QUALITIES)}
    checks["each_file_has_exactly_3_qualities"] = {"pass": not incomplete, "violations": dict(list(incomplete.items())[:20])}
    differing = [f for f, hashes in content_by_file.items() if len(hashes) != 1]
    checks["annotations_identical_across_qualities"] = {"pass": not differing, "violations": differing[:20]}

    released = load_released_ground_truth(REPO)
    released_by_file = {r["file_name"]: r for r in released}
    mismatch = []
    for name, record in records_by_file.items():
        gold_parquet = canonical_items(record)
        rel = released_by_file.get(name)
        if rel is None:
            mismatch.append({"file_name": name, "reason": "missing_in_released_json"})
            continue
        gold_json = canonical_items(rel)
        strip = lambda items: [{k: v for k, v in it.items() if k != "field_status"} for it in items]  # noqa: E731
        if strip(gold_parquet) != strip(gold_json):
            mismatch.append({"file_name": name, "reason": "canonical_items_differ"})
    checks["parquet_vs_released_json_canonical_items"] = {
        "pass": not mismatch and len(released_by_file) == len(records_by_file),
        "released_records": len(released_by_file), "mismatches": mismatch[:20], "n_mismatches": len(mismatch)}

    excluded = [line.split("\t")[0] for line in (root / "excluded_records.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    leaked_excluded = sorted(set(excluded) & set(base_files))
    checks["excluded_records_absent"] = {"pass": not leaked_excluded, "n_excluded_listed": len(excluded),
                                         "present_in_data": leaked_excluded}

    # duplicates across different file names
    def groups_by(key: str) -> list[list[str]]:
        mapping: dict[str, set] = collections.defaultdict(set)
        for m in rows_meta:
            if m[key]:
                mapping[m[key]].add(m["file_name"])
        return [sorted(v) for v in mapping.values() if len(v) > 1]

    image_dups = groups_by("image_sha256")
    content_dups = groups_by("content_hash")
    target_dups = groups_by("target_hash")
    report["duplicates_across_file_names"] = {
        "same_image_sha256_groups": len(image_dups), "same_image_examples": image_dups[:5],
        "same_business_content_groups": len(content_dups), "same_business_content_examples": content_dups[:5],
        "same_target_items_groups": len(target_dups),
        "same_target_items_files": sum(len(g) for g in target_dups),
        "same_target_items_examples": target_dups[:5],
        "same_target_items_cross_template_groups": sum(1 for g in target_dups if len({tmpl_by_file[f] for f in g}) > 1),
        "same_target_items_involving_holdout_template": sum(1 for g in target_dups if any(tmpl_by_file[f] == "freelancer_invoice" for f in g)),
    }
    report["sku_labels_available"] = False
    report["raw_print_format_labels_available"] = False
    report["note"] = ("Profile of public SYNTHETIC data at the pinned revision. Visibility of target columns in each "
                      "template is decided by the manual audit (reports/data/public_visual_audit.md), not by this script.")

    # 5. deterministic audit sample: 2 clean per template, plus faded/bad_scan of the first pick per template
    audit_dir = Path(args.audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    picks: dict[str, list[str]] = {}
    for template in sorted(set(tmpl_by_file.values())):
        names = sorted((f for f, t in tmpl_by_file.items() if t == template), key=lambda f: _stable_key("audit", f))
        picks[template] = names[:2]
    wanted = {(f, "clean") for names in picks.values() for f in names}
    wanted |= {(names[0], q) for names in picks.values() for q in ("faded", "bad_scan")}
    audit_gold = {}
    for row in iter_rows(shards, with_images=True, batch_size=16):
        key = (row["file_name"], row["quality"])
        if key not in wanted:
            continue
        stem = f'{row["_template_used"]}__{Path(row["file_name"]).stem}__{row["quality"]}'
        (audit_dir / f"{stem}.png").write_bytes(row["image"]["bytes"])
        if row["quality"] == "clean":
            audit_gold[stem] = {"file_name": row["file_name"], "template": row["_template_used"],
                                "currency": row.get("document_currency"), "items": canonical_items(row)}
    (audit_dir / "audit_gold.json").write_text(json.dumps(audit_gold, ensure_ascii=False, indent=1), encoding="utf-8")
    report["audit_sample"] = {"seed": SEED, "picks": picks, "dir": str(audit_dir.relative_to(REPO)).replace("\\", "/")}

    report_dir = REPO / "reports" / "data"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "public_profile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [name for name, c in checks.items() if not c["pass"]]
    print(json.dumps({"rows": len(rows_meta), "base_docs": len(base_files), "failed_checks": failed}, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
