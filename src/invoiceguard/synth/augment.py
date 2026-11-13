"""S5 fix (one change, dev-driven): extra TRAIN-only families targeting M1 dev failures.

Observed on dev (reports/eval/failures_m1_dev_v1.md): ambiguous quantities in a wrapped, narrow quantity cell
were turned into a number ("100 cartons / 2000 pcs" -> "500"), and the last row of 6-7-row documents was
dropped. Fix: 32 additional train families on TRAIN layouts only (T01-T03): 16 ambiguous_quantity and 16 normal
documents with 6-7 lines. Separate manifest; the frozen dev/test manifests are untouched.

Usage: python -m invoiceguard.synth.augment
"""
from __future__ import annotations

import hashlib
import json
import random

from ..reconciliation import reconcile
from ..splits import stable_key
from .build import REPO, SEED, _sha
from .render import available_font_pairs, overlap_errors, render, verify_render
from .scenarios import build_family

MANIFEST = REPO / "manifests" / "trade_raw_aug1.jsonl"
TEMPLATES = ["T01", "T02", "T03"]


def main() -> int:
    out = REPO / "data" / "processed" / "trade"
    fonts = available_font_pairs()
    plan = [("ambiguous_quantity", None)] * 16 + [("normal", 6)] * 8 + [("normal", 7)] * 8
    rows, errors = [], []
    for i, (scenario, n_lines) in enumerate(plan):
        family_id = "fam_aug1_" + stable_key(SEED, "aug1", str(i))[:10]
        rng = random.Random(f"{SEED}|{family_id}")
        fam = build_family(rng, family_id, scenario, n_lines=n_lines)
        template = TEMPLATES[i % 3]
        image, meta = render(fam, template, rng, fonts)
        problems = verify_render(fam["gold"], meta["drawn"]) + overlap_errors(meta["drawn"])
        codes = sorted(f["code"] for f in reconcile(fam["gold"], fam["po"], "oracle_fixture")["findings"])
        if codes != sorted(fam["expected_codes"]):
            problems.append(f"oracle:{codes}")
        if problems:
            errors.append({"family": family_id, "template": template, "problems": problems[:3]})
            continue
        doc_id = "tr_" + stable_key(SEED, "doc", family_id)[:12]
        image.save(out / "images" / f"{doc_id}.png", format="PNG", optimize=True)
        gold_bytes = json.dumps(fam["gold"], ensure_ascii=False, indent=1).encode("utf-8")
        po_bytes = json.dumps(fam["po"], ensure_ascii=False, indent=1).encode("utf-8")
        (out / "gold" / f"{doc_id}.json").write_bytes(gold_bytes)
        (out / "po" / f"{doc_id}.json").write_bytes(po_bytes)
        rows.append({"doc_id": doc_id, "family_id": family_id, "split": "train", "template": template,
                     "scenario_type": scenario, "task": "TRADE_RAW", "origin": "synthetic_self_generated_aug1",
                     "n_rows": len(fam["gold"]["items"]), "image_sha256": _sha((out / "images" / f"{doc_id}.png").read_bytes()),
                     "gold_sha256": _sha(gold_bytes), "po_sha256": _sha(po_bytes), "standard_role": "train", "mini_role": None,
                     "expected_codes": fam["expected_codes"], "transaction_diff": fam["transaction_diff"],
                     "augmentation": "S5 dev-driven fix: wrapped ambiguous quantities, 6-7 row documents"})
    MANIFEST.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(json.dumps({"rendered": len(rows), "errors": errors, "sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest()}, indent=1))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
