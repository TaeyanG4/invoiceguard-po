"""T02: leak-free PUBLIC_CANONICAL split + pre-registered standard/mini selections.

Usage: python -m invoiceguard.public_manifest            # build + check
       python -m invoiceguard.public_manifest --check    # verify an existing manifest only

The manifest has IDs, hashes, split, task and visibility status only; no label values,
no image bytes, no PO. The model input is (image, fixed task prompt) only.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

from .public_data import (
    DATASET_ID, DATASET_REVISION, HOLDOUT_TEMPLATE, QUALITIES, business_content_hash,
    iter_rows, line_items_target_hash, shard_paths,
)
from .public_visibility import RENDERER_COMMIT, SCORED, document_visibility, train_eligible
from .splits import assign_ratio, find_leaks, group_documents, stable_key

REPO = Path(__file__).resolve().parents[2]
SEED = 20261113
MANIFEST = REPO / "manifests" / "public_canonical_v1.jsonl"
SUMMARY = REPO / "manifests" / "public_canonical_v1.summary.json"
PROFILES = {
    "standard": {"train": 200, "dev": 20, "dev_stress": 8, "iid_final": 20, "ood_final": 20},
    "mini": {"train": 120, "dev": 10, "dev_stress": 4, "iid_final": 8, "ood_final": 8},
}
LEAK_KEYS = ["base_id", "group_id", "content_hash", "target_hash", "image_sha256"]


def _load_image_hashes() -> dict[tuple[str, str], str]:
    rows_path = REPO / "data" / "processed" / "public" / "rows.jsonl"
    if not rows_path.exists():
        raise SystemExit("run `python -m invoiceguard.public_profile` first (needs image hashes)")
    out = {}
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        meta = json.loads(line)
        out[(meta["file_name"], meta["quality"])] = meta["image_sha256"]
    return out


def build() -> list[dict]:
    image_sha = _load_image_hashes()
    records: dict[str, dict] = {}
    for row in iter_rows(shard_paths(REPO), with_images=False, batch_size=256):
        row.pop("_shard", None)
        records.setdefault(row["file_name"], row)

    docs = []
    for name, rec in records.items():
        docs.append({"base_id": name, "content_hash": business_content_hash(rec),
                     "target_hash": line_items_target_hash(rec),
                     # every quality variant's image hash links documents too
                     **{f"img_{q}": image_sha[(name, q)] for q in QUALITIES}})
    group_of = group_documents(docs, "base_id", ["content_hash", "target_hash"] + [f"img_{q}" for q in QUALITIES])

    groups: dict[str, list[str]] = collections.defaultdict(list)
    for name, gid in group_of.items():
        groups[gid].append(name)
    ood_groups = {g for g, names in groups.items() if any(records[n]["_template_used"] == HOLDOUT_TEMPLATE for n in names)}
    rest = [g for g in groups if g not in ood_groups]
    pool_of = assign_ratio(rest, SEED, ["train", "dev", "iid_test"], [0.75, 0.125, 0.125])
    pool_of.update({g: "ood_test" for g in ood_groups})

    # pre-registered selection order per pool (independent of any model output)
    eligible = {n: train_eligible(records[n]) for n in records}
    by_pool: dict[str, list[str]] = collections.defaultdict(list)
    for gid in sorted(groups, key=lambda g: stable_key(SEED, "select", g)):
        for name in sorted(groups[gid]):
            by_pool[pool_of[gid]].append(name)
    roles: dict[str, dict[str, list[str]]] = {}
    for profile, caps in PROFILES.items():
        train = [n for n in by_pool["train"] if eligible[n][0]][: caps["train"]]
        dev = by_pool["dev"][: caps["dev"]]
        roles[profile] = {"train": train, "dev": dev, "dev_stress": dev[: caps["dev_stress"]],
                          "iid_final": by_pool["iid_test"][: caps["iid_final"]],
                          "ood_final": by_pool["ood_test"][: caps["ood_final"]]}

    rows = []
    for name in sorted(records):
        rec = records[name]
        vis = document_visibility(rec)
        gid = group_of[name]
        pool = pool_of[gid]
        for quality in QUALITIES:
            membership = {}
            for profile, r in roles.items():
                role = None
                if quality == "clean" and name in r["train"]:
                    role = "train"
                elif name in r["dev"] and (quality == "clean" or name in r["dev_stress"]):
                    role = "dev" if quality == "clean" else "dev_stress"
                elif name in r["iid_final"]:
                    role = "iid_final"
                elif name in r["ood_final"]:
                    role = "ood_final"
                membership[profile] = role
            rows.append({
                "source": DATASET_ID, "revision": DATASET_REVISION, "origin": "synthetic_public",
                "task": "PUBLIC_CANONICAL", "base_id": name, "group_id": gid,
                "content_hash": business_content_hash(rec), "target_hash": line_items_target_hash(rec),
                "image_sha256": image_sha[(name, quality)], "template": rec["_template_used"],
                "quality": quality, "pool": pool, "standard_role": membership["standard"],
                "mini_role": membership["mini"], "train_eligible": eligible[name][0],
                "train_ineligible_reason": eligible[name][1], "n_items": len(vis),
                "n_scored_fields": sum(s == SCORED for row in vis for s in row.values()),
                "n_masked_fields": sum(s != SCORED for row in vis for s in row.values()),
                "visibility": vis, "renderer_commit": RENDERER_COMMIT,
                "label_status": "publisher_numeric_label_canonical_decimal; sku_not_available",
            })
    return rows


def check(rows: list[dict]) -> dict:
    result: dict = {}
    result["pool_leaks"] = find_leaks(rows, "pool", LEAK_KEYS)
    for profile in PROFILES:
        role_field = f"{profile}_role"
        bucket = lambda r: {"dev_stress": "dev"}.get(r[role_field], r[role_field])  # noqa: E731
        tagged = [dict(r, _bucket=bucket(r)) for r in rows if r[role_field]]
        result[f"{profile}_role_leaks"] = find_leaks(tagged, "_bucket", LEAK_KEYS)
    std = {(r["base_id"], r["quality"]): r["standard_role"] for r in rows}
    result["mini_nested_in_standard"] = all(
        r["mini_role"] is None or std[(r["base_id"], r["quality"])] == r["mini_role"] for r in rows)
    result["holdout_template_only_in_ood"] = all(
        (r["template"] == HOLDOUT_TEMPLATE) <= (r["pool"] == "ood_test") for r in rows)
    result["ood_pool_only_holdout_groups"] = all(
        r["pool"] != "ood_test" or r["template"] == HOLDOUT_TEMPLATE or any(
            x["group_id"] == r["group_id"] and x["template"] == HOLDOUT_TEMPLATE for x in rows) for r in rows)
    result["train_rows_all_eligible_clean"] = all(
        (r[f"{p}_role"] != "train") or (r["train_eligible"] and r["quality"] == "clean") for r in rows for p in PROFILES)
    result["final_has_all_three_qualities"] = all(
        sorted(r["quality"] for r in rows if r["base_id"] == b and r[f"{p}_role"] == role) == sorted(QUALITIES)
        for p in PROFILES for role in ("iid_final", "ood_final")
        for b in {r["base_id"] for r in rows if r[f"{p}_role"] == role})
    result["no_label_values_or_po_in_manifest"] = all(
        not ({"line_items", "quantity", "unit_price", "amount", "description", "po", "image"} & set(r)) for r in rows)
    result["pass"] = (not any(v for k, d in result.items() if k.endswith("leaks") for v in d.values())
                      and all(v for k, v in result.items() if isinstance(v, bool)))
    return result


def summarize(rows: list[dict], digest: str, checks: dict) -> dict:
    bases = {r["base_id"]: r for r in rows if r["quality"] == "clean"}
    out = {"manifest": str(MANIFEST.relative_to(REPO)).replace("\\", "/"), "sha256": digest, "seed": SEED,
           "dataset": DATASET_ID, "revision": DATASET_REVISION, "renderer_commit": RENDERER_COMMIT,
           "rows": len(rows), "base_documents": len(bases),
           "groups": len({r["group_id"] for r in rows}),
           "multi_document_groups": sum(1 for g, c in collections.Counter(r["group_id"] for r in bases.values()).items() if c > 1),
           "pool_base_docs": dict(collections.Counter(r["pool"] for r in bases.values())),
           "pool_templates": {p: dict(collections.Counter(r["template"] for r in bases.values() if r["pool"] == p))
                              for p in ("train", "dev", "iid_test", "ood_test")},
           "train_eligible_by_template": {t: f'{sum(r["train_eligible"] for r in bases.values() if r["template"] == t)}/'
                                             f'{sum(1 for r in bases.values() if r["template"] == t)}'
                                          for t in sorted({r["template"] for r in bases.values()})},
           "ineligible_reasons": dict(collections.Counter(
               r["train_ineligible_reason"].split(":")[0] + ":" + r["train_ineligible_reason"].split(":")[1]
               for r in bases.values() if r["train_ineligible_reason"] and ":" in r["train_ineligible_reason"])),
           "field_status_counts_all_bases": dict(collections.Counter(
               f"{f}:{s}" for r in bases.values() for row in r["visibility"] for f, s in row.items())),
           "profiles": {}, "checks": checks,
           "frozen": False,
           "freeze_note": "Membership pre-registered by seeded hash before any model output. Profile (standard|mini) "
                          "is chosen once after the training-only pilot (T03/T04) and then frozen."}
    for p in PROFILES:
        roles = collections.Counter(r[f"{p}_role"] for r in rows if r[f"{p}_role"])
        templ = {role: dict(collections.Counter(r["template"] for r in rows if r[f"{p}_role"] == role and r["quality"] == ("clean" if role != "dev_stress" else "faded")))
                 for role in ("train", "dev", "dev_stress", "iid_final", "ood_final")}
        out["profiles"][p] = {"image_rows_by_role": dict(roles), "base_templates_by_role": templ,
                              "scored_fields_by_role": {role: sum(r["n_scored_fields"] for r in rows if r[f"{p}_role"] == role) for role in templ},
                              "masked_fields_by_role": {role: sum(r["n_masked_fields"] for r in rows if r[f"{p}_role"] == role) for role in templ}}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines()]
    else:
        rows = build()
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    checks = check(rows)
    if not args.check:
        SUMMARY.write_text(json.dumps(summarize(rows, digest, checks), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sha256": digest, "pass": checks["pass"], "rows": len(rows)}, indent=1))
    return 0 if checks["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
