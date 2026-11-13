"""T02: build the self-generated TRADE_RAW Invoice–PO dataset and its frozen-candidate manifest.

Usage: python -m invoiceguard.synth.build [--out data/processed/trade]

* train T01–T03 / dev T04 / test T05–T06 (layout holdout), counts from configs/project.yaml.
* One scenario family = one PO transaction + one rendered invoice; families never cross splits.
* Gold JSON = exact strings drawn by the renderer. PO and gold are separate files; the model
  request is (image, fixed TRADE_RAW prompt) only.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
from pathlib import Path

import jsonschema
import yaml

from ..reconciliation import reconcile, validate_po
from ..splits import find_leaks, stable_key
from . import GENERATOR_VERSION
from .render import LAYOUTS, available_font_pairs, font_sha256, overlap_errors, render, verify_render
from .scenarios import SCENARIO_TYPES, build_family

REPO = Path(__file__).resolve().parents[3]
SEED = 20261113
SPLIT_TEMPLATES = {"train": ["T01", "T02", "T03"], "validation": ["T04"], "test": ["T05", "T06"]}
SPLIT_NAME = {"train": "train", "validation": "dev", "test": "test"}
MANIFEST = REPO / "manifests" / "trade_raw_v1.jsonl"
SUMMARY = REPO / "manifests" / "trade_raw_v1.summary.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mini_quota(counts: dict[str, int], k: int) -> dict[str, int]:
    """Largest-remainder allocation of k with at least one per present type (pre-registered)."""
    total = sum(counts.values())
    raw = {t: counts[t] * k / total for t in counts}
    quota = {t: int(raw[t]) for t in counts}
    for t in sorted(counts, key=lambda t: (-(raw[t] - quota[t]), SCENARIO_TYPES.index(t)))[: k - sum(quota.values())]:
        quota[t] += 1
    for t in SCENARIO_TYPES:
        if counts.get(t, 0) > 0 and quota[t] == 0:
            donor = max(quota, key=lambda x: (quota[x], -SCENARIO_TYPES.index(x)))
            quota[donor] -= 1
            quota[t] = 1
    return quota


def plan_families(cfg: dict) -> list[dict]:
    plan = []
    for split, templates in SPLIT_TEMPLATES.items():
        rng = random.Random(f"{SEED}|plan|{split}")
        pairs = []
        # each scenario type is spread round-robin over the split's templates (random offset per type),
        # so no type is tied to one layout; the combined list is then shuffled.
        for scenario, n in cfg["data"]["synthetic"]["type_counts"][split].items():
            offset = rng.randrange(len(templates))
            pairs += [(scenario, templates[(offset + j) % len(templates)]) for j in range(n)]
        assert len(pairs) == cfg["data"]["synthetic"]["counts"][split], split
        rng.shuffle(pairs)
        for i, (scenario, template) in enumerate(pairs):
            family_id = "fam_" + stable_key(SEED, "family", split, str(i))[:12]
            plan.append({"family_id": family_id, "split": SPLIT_NAME[split], "template": template,
                         "scenario_type": scenario})
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "data" / "processed" / "trade"))
    args = parser.parse_args()
    out = Path(args.out)
    for sub in ("images", "gold", "po"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((REPO / "configs" / "project.yaml").read_text(encoding="utf-8"))
    profiles = cfg["profiles"]
    extraction_schema = json.loads((REPO / "schemas" / "extraction.schema.json").read_text(encoding="utf-8"))
    po_schema = json.loads((REPO / "schemas" / "purchase_order.schema.json").read_text(encoding="utf-8"))
    fonts = available_font_pairs()
    if len(fonts) < 3:
        raise SystemExit("need at least 3 local font pairs to vary typography")
    font_hashes = {name: font_sha256(name) for pair in fonts for name in pair}

    rows, errors = [], []
    for item in plan_families(cfg):
        rng = random.Random(f"{SEED}|{item['family_id']}")
        fam = build_family(rng, item["family_id"], item["scenario_type"])
        image, meta = render(fam, item["template"], rng, fonts)
        doc_id = "tr_" + stable_key(SEED, "doc", item["family_id"])[:12]

        problems = verify_render(fam["gold"], meta["drawn"]) + overlap_errors(meta["drawn"])
        try:
            jsonschema.validate(fam["gold"], extraction_schema)
            jsonschema.validate(fam["po"], po_schema)
        except jsonschema.ValidationError as exc:
            problems.append(f"schema:{exc.message[:80]}")
        problems += [f"po:{e}" for e in validate_po(fam["po"])]
        oracle = reconcile(fam["gold"], fam["po"], "oracle_fixture")
        oracle_codes = sorted(f["code"] for f in oracle["findings"])
        if oracle_codes != sorted(fam["expected_codes"]):
            problems.append(f"oracle_mismatch:{oracle_codes}!={fam['expected_codes']}")
        if problems:
            errors.append({"doc_id": doc_id, "template": item["template"], "problems": problems[:5]})

        png = out / "images" / f"{doc_id}.png"
        image.save(png, format="PNG", optimize=True)
        gold_bytes = json.dumps(fam["gold"], ensure_ascii=False, indent=1).encode("utf-8")
        po_bytes = json.dumps(fam["po"], ensure_ascii=False, indent=1).encode("utf-8")
        (out / "gold" / f"{doc_id}.json").write_bytes(gold_bytes)
        (out / "po" / f"{doc_id}.json").write_bytes(po_bytes)
        rows.append({
            "doc_id": doc_id, "family_id": item["family_id"], "split": item["split"], "template": item["template"],
            "scenario_type": item["scenario_type"], "task": "TRADE_RAW", "origin": "synthetic_self_generated",
            "generator_version": GENERATOR_VERSION, "seed": SEED, "quality": "clean",
            "image_sha256": _sha(png.read_bytes()), "gold_sha256": _sha(gold_bytes), "po_sha256": _sha(po_bytes),
            "width": image.width, "height": image.height, "n_rows": len(fam["gold"]["items"]),
            "font_regular": meta["font_regular"], "font_bold": meta["font_bold"],
            "font_sha256": [font_hashes[meta["font_regular"]], font_hashes[meta["font_bold"]]],
            "has_injection_text": fam["context"]["injection_note"] is not None,
            "expected_codes": fam["expected_codes"], "transaction_diff": fam["transaction_diff"],
            "render_check": "pass" if not problems else "fail",
        })

    # pre-registered standard/mini membership (stratified by scenario type, seeded order)
    split_cap = {"train": ("trade_train",), "dev": ("trade_dev",), "test": ("trade_test",)}
    for row in rows:
        row["standard_role"] = row["split"]
        row["mini_role"] = None
    for split, (key,) in split_cap.items():
        members = [r for r in rows if r["split"] == split]
        counts = collections.Counter(r["scenario_type"] for r in members)
        quota = mini_quota(dict(counts), profiles["mini"][key])
        for scenario, q in quota.items():
            ordered = sorted((r for r in members if r["scenario_type"] == scenario),
                             key=lambda r: stable_key(SEED, "mini", r["family_id"]))
            for r in ordered[:q]:
                r["mini_role"] = split
        assert sum(r["mini_role"] == split for r in members) == profiles["mini"][key]
        assert len(members) == profiles["standard"][key]

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    digest = _sha(MANIFEST.read_bytes())

    leaks = find_leaks(rows, "split", ["family_id", "doc_id", "image_sha256", "gold_sha256", "po_sha256"])
    template_split_ok = all(r["template"] in SPLIT_TEMPLATES[{v: k for k, v in SPLIT_NAME.items()}[r["split"]]] for r in rows)
    contingency = {s: {t: dict(collections.Counter(r["template"] for r in rows if r["split"] == s and r["scenario_type"] == t))
                       for t in SCENARIO_TYPES} for s in ("train", "dev", "test")}
    # fault type must not determine template: every type with >=2 docs spans >=2 templates where possible
    type_template_ok = all(len(v) >= 2 for s in ("train", "test") for t, v in contingency[s].items()
                           if sum(v.values()) >= 2)
    checks = {
        "render_errors": errors, "split_leaks": leaks,
        "template_holdout_respected": template_split_ok,
        "fault_type_not_determining_template": type_template_ok,
        "all_render_checks_pass": not errors,
        "injection_text_docs": sum(r["has_injection_text"] for r in rows),
    }
    checks["pass"] = (not errors and not any(leaks.values()) and template_split_ok and type_template_ok)
    summary = {
        "manifest": "manifests/trade_raw_v1.jsonl", "sha256": digest, "seed": SEED, "generator_version": GENERATOR_VERSION,
        "documents": len(rows), "by_split": dict(collections.Counter(r["split"] for r in rows)),
        "mini_by_split": dict(collections.Counter(r["mini_role"] for r in rows if r["mini_role"])),
        "type_by_template": contingency,
        "fonts_used": dict(collections.Counter(r["font_regular"] for r in rows)),
        "rows_per_doc": dict(sorted(collections.Counter(r["n_rows"] for r in rows).items())),
        "image_size": dict(collections.Counter(f'{r["width"]}x{r["height"]}' for r in rows)),
        "checks": checks, "frozen": False,
        "note": "Synthetic, self-generated, fictional companies. PO/gold/scenario metadata are never model inputs.",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"documents": len(rows), "sha256": digest, "pass": checks["pass"],
                      "render_errors": len(errors)}, indent=1))
    if errors:
        print(json.dumps(errors[:5], indent=1))
    return 0 if checks["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
