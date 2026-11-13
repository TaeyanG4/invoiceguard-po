"""D05/D06 checks for the self-generated synthetic Invoice–PO data (fictional)."""
import dataclasses
import hashlib
import json
import random
from pathlib import Path

import pytest

from invoiceguard.extraction_request import build_request, load_prompt
from invoiceguard.reconciliation import reconcile
from invoiceguard.synth.build import SPLIT_TEMPLATES, mini_quota
from invoiceguard.synth.render import LAYOUTS, available_font_pairs, overlap_errors, render, verify_render
from invoiceguard.synth.scenarios import EXPECTED_CODES, SCENARIO_TYPES, build_family

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "manifests" / "trade_raw_v1.jsonl"
DATA = REPO / "data" / "processed" / "trade"


def test_family_generation_is_deterministic():
    a = build_family(random.Random("s|f1"), "f1", "price_change")
    b = build_family(random.Random("s|f1"), "f1", "price_change")
    assert a == b


@pytest.mark.parametrize("scenario", SCENARIO_TYPES)
def test_oracle_findings_match_scenario(scenario):
    for seed in range(15):
        fam = build_family(random.Random(f"t|{scenario}|{seed}"), "f", scenario)
        codes = sorted(f["code"] for f in reconcile(fam["gold"], fam["po"], "oracle_fixture")["findings"])
        assert codes == sorted(EXPECTED_CODES[scenario]), (scenario, seed, codes)


def test_po_is_never_modified_to_match_changed_invoice():
    fam = build_family(random.Random("t|pc"), "f", "price_change")
    po_prices = {l["sku"]: l["unit_price"] for l in fam["po"]["items"]}
    changed = [it for it in fam["gold"]["items"] if it["unit_price_raw"].replace(",", "") != po_prices[it["sku_raw"]]
               and float(it["unit_price_raw"].replace(",", "")) != float(po_prices[it["sku_raw"]])]
    assert len(changed) == 1


@pytest.mark.skipif(len(available_font_pairs()) < 3, reason="needs local system fonts")
@pytest.mark.parametrize("template", LAYOUTS)
def test_d05_render_equals_gold_no_overlap(template):
    for seed in range(4):
        for scenario in ("ambiguous_quantity", "duplicate_sku"):
            rng = random.Random(f"r|{template}|{seed}|{scenario}")
            fam = build_family(rng, "f", scenario)
            _, meta = render(fam, template, rng, available_font_pairs())
            assert verify_render(fam["gold"], meta["drawn"]) == []
            assert overlap_errors(meta["drawn"]) == []


def test_mini_quota_sums_and_keeps_every_type():
    counts = {"normal": 10, "price_change": 6, "quantity_change": 4, "unknown_sku": 1, "ambiguous_quantity": 1,
              "missing_po_line": 1, "duplicate_sku": 1}
    quota = mini_quota(counts, 12)
    assert sum(quota.values()) == 12 and all(q >= 1 for q in quota.values())


def test_d06_request_has_only_task_prompt_and_image():
    req = build_request("TRADE_RAW", b"\x89PNG fake")
    fields = {f.name for f in dataclasses.fields(req)}
    assert fields == {"task", "prompt", "prompt_sha256", "image_bytes", "image_sha256"}
    prompt, digest = load_prompt("TRADE_RAW")
    assert req.prompt == prompt and req.prompt_sha256 == digest
    assert "purchase order" in prompt.lower()  # the prompt states that no PO is given
    assert load_prompt("PUBLIC_CANONICAL")[1] != digest  # task prompts hashed separately
    with pytest.raises(ValueError):
        build_request("CHAT", b"x")


@pytest.mark.skipif(not MANIFEST.exists(), reason="trade manifest not built")
def test_d04_trade_manifest_families_do_not_cross_splits_and_layouts_held_out():
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines()]
    split_of = {}
    for r in rows:
        assert split_of.setdefault(r["family_id"], r["split"]) == r["split"]
    allowed = {"train": SPLIT_TEMPLATES["train"], "dev": SPLIT_TEMPLATES["validation"], "test": SPLIT_TEMPLATES["test"]}
    assert all(r["template"] in allowed[r["split"]] for r in rows)
    assert all(r["mini_role"] in (None, r["split"]) for r in rows)
    forbidden = {"po", "gold", "items", "unit_price", "quantity"}
    assert not forbidden & set(rows[0])


@pytest.mark.skipif(not (MANIFEST.exists() and DATA.exists()), reason="trade data not generated")
def test_trade_files_match_manifest_hashes():
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines()]
    for r in rows[:: max(1, len(rows) // 25)]:
        assert hashlib.sha256((DATA / "images" / f"{r['doc_id']}.png").read_bytes()).hexdigest() == r["image_sha256"]
        assert hashlib.sha256((DATA / "gold" / f"{r['doc_id']}.json").read_bytes()).hexdigest() == r["gold_sha256"]
