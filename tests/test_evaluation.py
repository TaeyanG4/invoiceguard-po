"""E01–E05 evaluator tests with hand-written fictional responses (not model outputs)."""
import json
from collections import Counter
from pathlib import Path

from invoiceguard.evaluation import (
    aggregate, aggregate_trade, cluster_bootstrap, finding_keys, score_findings,
    score_public_document, score_trade_document, PUBLIC_FIELDS,
)
from invoiceguard.model_output import parse_response
from invoiceguard.reconciliation import reconcile

REPO = Path(__file__).resolve().parents[1]
GOLD = [{"row_index": 1, "description": "Sensor module", "quantity": "100", "unit_price": "2.5", "amount": "250"},
        {"row_index": 2, "description": "Signal cable", "quantity": "20", "unit_price": "5", "amount": "100"}]
VIS = [{f: "visible_exact" for f in PUBLIC_FIELDS} for _ in GOLD]


def pub(items):
    return json.dumps({"schema_version": "public-1.0", "items": items})


def test_b02_canonical_value_match_and_perfect_document():
    text = pub([{"row_index": 1, "description": "Sensor  module", "quantity": "100.00", "unit_price": "2.50", "amount": "250.0"},
                {"row_index": 2, "description": "Signal cable", "quantity": "20", "unit_price": "5.00", "amount": "100"}])
    score = score_public_document(GOLD, VIS, parse_response(text, "PUBLIC_CANONICAL"))
    assert score["doc_exact"] and score["row_exact"] == 2


def test_json_numbers_and_thousand_separators_are_wrong_not_fixed():
    text = pub([{"row_index": 1, "description": "Sensor module", "quantity": 100, "unit_price": "2.5", "amount": "250"},
                {"row_index": 2, "description": "Signal cable", "quantity": "20", "unit_price": "5", "amount": "1,00"}])
    parsed = parse_response(text, "PUBLIC_CANONICAL")
    assert parsed.status == "ok" and not parsed.schema_valid
    score = score_public_document(GOLD, VIS, parsed)
    assert score["fields"]["quantity"] == [1, 2] and score["fields"]["amount"] == [1, 2]
    assert not score["doc_exact"]


def test_e01_total_failure_keeps_denominator():
    ok_text = pub([dict(g) for g in GOLD])
    docs = [score_public_document(GOLD, VIS, parse_response(ok_text, "PUBLIC_CANONICAL")),
            score_public_document(GOLD, VIS, parse_response(None, "PUBLIC_CANONICAL", generation_status="timeout")),
            score_public_document(GOLD, VIS, parse_response('{"schema_version": "public-1.0", "items": [', "PUBLIC_CANONICAL"))]
    agg = aggregate(docs, PUBLIC_FIELDS)
    assert agg["attempted"] == 3
    assert agg["status_counts"] == {"ok": 1, "timeout": 1, "json_invalid": 1}
    assert agg["fields"]["amount"] == {"correct": 2, "scored": 6, "accuracy": round(2 / 6, 6)}
    assert agg["doc_exact"] == round(1 / 3, 6)


def test_truncated_generation_is_failure_even_if_parseable():
    text = pub([dict(g) for g in GOLD])
    assert parse_response(text, "PUBLIC_CANONICAL", finish_reason="length").status == "truncated"


def test_fence_repair_only_on_lenient_path():
    fenced = "```json\n" + pub([dict(g) for g in GOLD]) + "\n```"
    assert parse_response(fenced, "PUBLIC_CANONICAL").status == "json_invalid"
    lenient = parse_response(fenced, "PUBLIC_CANONICAL", lenient=True)
    assert lenient.status == "ok" and lenient.repair == "fence_strip"


def test_excess_and_missing_rows_no_reordering():
    swapped = pub([dict(GOLD[1], row_index=1), dict(GOLD[0], row_index=2)])
    score = score_public_document(GOLD, VIS, parse_response(swapped, "PUBLIC_CANONICAL"))
    assert score["row_exact"] == 0  # not silently re-aligned
    extra = pub([dict(g) for g in GOLD] + [{"row_index": 3, "description": None, "quantity": None, "unit_price": None, "amount": "0"}])
    score = score_public_document(GOLD, VIS, parse_response(extra, "PUBLIC_CANONICAL"))
    assert score["excess_rows"] == 1 and not score["doc_exact"] and score["row_exact"] == 2
    short = pub([dict(GOLD[0])])
    score = score_public_document(GOLD, VIS, parse_response(short, "PUBLIC_CANONICAL"))
    assert score["missing_rows"] == 1 and score["fields"]["description"] == [1, 2]


def test_masked_fields_not_scored_but_reported():
    vis = [dict(v) for v in VIS]
    vis[0]["unit_price"] = "not_printed"
    vis[1]["description"] = "case_transformed"
    text = pub([dict(GOLD[0], unit_price="999"), dict(GOLD[1], description="SIGNAL CABLE")])
    score = score_public_document(GOLD, vis, parse_response(text, "PUBLIC_CANONICAL"))
    assert score["doc_exact"]
    assert score["masked"] == {"unit_price:not_printed": 1, "description:case_transformed": 1}
    assert score["casefold_description"] == [1, 1]


def test_e04_bootstrap_clusters_by_base_not_image():
    docs = [score_public_document(GOLD, VIS, parse_response(pub([dict(g) for g in GOLD]), "PUBLIC_CANONICAL"))] * 6
    result = cluster_bootstrap(docs, ["b1", "b1", "b1", "b2", "b2", "b2"], iterations=50)
    assert result["n_clusters"] == 2 and result["ci95"] == [1.0, 1.0]


def test_trade_raw_vs_numeric_and_leading_zero_sku():
    invoice = json.loads((REPO / "examples" / "invoice_oracle.json").read_text(encoding="utf-8"))
    pred = json.loads(json.dumps(invoice))
    pred["items"][0]["sku_raw"] = "125"            # leading zero lost -> SKU wrong
    pred["items"][0]["unit_price_raw"] = "2.750"   # raw EM wrong, numeric EM right
    score = score_trade_document(invoice, parse_response(json.dumps(pred), "TRADE_RAW"))
    assert score["fields"]["sku_raw"] == [1, 2]
    assert score["fields"]["unit_price_raw"] == [1, 2]
    assert score["numeric_fields"]["unit_price_raw"] == [2, 2]
    assert not score["doc_exact"]
    failed = score_trade_document(invoice, parse_response(None, "TRADE_RAW", generation_status="oom"))
    agg = aggregate_trade([score, failed])
    assert agg["attempted"] == 2 and agg["fields"]["total_raw"]["scored"] == 2 and agg["fields"]["total_raw"]["correct"] == 1


def test_ambiguous_gold_quantity_excluded_from_numeric_only():
    invoice = json.loads((REPO / "examples" / "invoice_oracle.json").read_text(encoding="utf-8"))
    invoice["items"][0]["quantity_raw"] = "2 cartons / 100 pcs"
    pred = json.loads(json.dumps(invoice))
    pred["items"][0]["quantity_raw"] = "100"  # forced number: raw EM wrong
    score = score_trade_document(invoice, parse_response(json.dumps(pred), "TRADE_RAW"))
    assert score["fields"]["quantity_raw"] == [1, 2]
    assert score["numeric_fields"]["quantity_raw"] == [1, 1]


def test_e05_precision_null_when_no_predictions_and_e02_sources_separate():
    invoice = json.loads((REPO / "examples" / "invoice_oracle.json").read_text(encoding="utf-8"))
    po = json.loads((REPO / "examples" / "purchase_order.json").read_text(encoding="utf-8"))
    oracle = reconcile(invoice, po, "oracle_fixture")
    exp = finding_keys(oracle, invoice)
    assert exp == Counter({("UNIT_PRICE_DIFF", "000125"): 1})
    empty = Counter()
    result = score_findings([exp], [empty], ["UNIT_PRICE_DIFF", "QTY_DIFF"], ["failed"], [True], [True])
    assert result["per_code"]["UNIT_PRICE_DIFF"] == {"tp": 0, "fp": 0, "fn": 1, "support": 1, "precision": None, "recall": 0.0}
    assert result["per_code"]["QTY_DIFF"]["recall"] is None
    assert result["candidates_with_actual_transaction_diff"] is None
    assert oracle["source"] == "oracle_fixture"


def test_metric_contract_v2_strict_vs_lenient_and_conditional():
    """Fenced output: strict counts it as a failure; lenient (fence strip only) and the conditional
    reading accuracy are reported separately with their own denominators."""
    from invoiceguard.evaluation import strict_and_lenient

    good = pub([dict(g) for g in GOLD])
    fenced = "```json\n" + good + "\n```"
    truncated = good[: len(good) // 2]
    items = [((GOLD, VIS), {"raw_response": good}),
             ((GOLD, VIS), {"raw_response": fenced}),
             ((GOLD, VIS), {"raw_response": truncated}),
             ((GOLD, VIS), {"raw_response": None, "generation_status": "timeout"})]
    result = strict_and_lenient(score_public_document, items, "PUBLIC_CANONICAL",
                                lambda docs: aggregate(docs, PUBLIC_FIELDS))
    strict, lenient = result["strict"], result["lenient_fence_strip"]
    assert strict["attempted"] == lenient["attempted"] == 4  # denominators never shrink
    assert strict["status_counts"] == {"ok": 1, "json_invalid": 2, "timeout": 1}
    assert lenient["status_counts"] == {"ok": 2, "json_invalid": 1, "timeout": 1}  # truncation NOT repaired
    assert lenient["repaired_documents"] == 1
    assert strict["conditional_on_json_parse_ok"]["documents"] == 1
    assert strict["conditional_on_json_parse_ok"]["accuracy"] == 1.0
    assert strict["all_scored_fields"]["accuracy"] == 0.25
