"""docs/20 amendment 6: the Korean-English mixed layout T07 is a dev-only stress set, CPU only (no images needed)."""
import json
from pathlib import Path

from invoiceguard.synth.scenarios import PRODUCTS
from invoiceguard.synth.t07 import KO, PLAN

REPO = Path(__file__).resolve().parents[1]


def _rows(name):
    return [json.loads(line) for line in (REPO / "manifests" / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_t07_is_a_separate_stress_set_that_never_overlaps_training_or_evaluation_documents():
    rows, base = _rows("trade_raw_t07.jsonl"), _rows("trade_raw_v1.jsonl")
    assert len(rows) == sum(n for _, n in PLAN) == 30
    assert {r["split"] for r in rows} == {r["standard_role"] for r in rows} == {"stress"}
    assert {r["template"] for r in rows} == {"T07"} and all(r["render_check"] == "pass" for r in rows)
    for key in ("family_id", "doc_id", "image_sha256", "gold_sha256"):
        assert not {r[key] for r in rows} & {b[key] for b in base}, key


def test_every_product_has_a_korean_name_for_the_bilingual_item_column():
    assert set(KO) == set(PRODUCTS) and all(any("가" <= ch <= "힣" for ch in KO[p]) for p in PRODUCTS)
