"""CORD_RAW conversion and scoring rules (docs/20_DECISIONS_V6.md), on in-memory fixtures (no dataset needed)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from invoiceguard.cord import to_gold
from invoiceguard.cord_eval import aggregate, loose_norm, score_document
from invoiceguard.extraction_request import load_prompt
from invoiceguard.model_output import parse_response
from invoiceguard.vlm.records import dump_answer

SCHEMA = json.loads(open("schemas/cord_extraction.schema.json", encoding="utf-8").read())

GT = {"menu": [{"nm": "BBQ Chicken", "cnt": "1", "price": "41,000", "sub": {"nm": "Sedang", "cnt": "1", "price": "0"}},
               {"nm": "Es Teh", "cnt": "2x", "unitprice": "@5.000", "price": "10.000", "num": "12"}],
      "sub_total": {"subtotal_price": "51,000", "tax_price": "5,100"},
      "total": {"total_price": "56,100", "cashprice": "60,000"}}


def gold():
    return to_gold(GT)


def parsed(obj):
    return parse_response(json.dumps(obj, ensure_ascii=False), "CORD_RAW")


def test_to_gold_keeps_printed_strings_and_drops_unrequested_keys():
    g, masked = gold()
    assert masked == []
    assert g["items"][0] == {"row_index": 1, "name": "BBQ Chicken", "count": "1", "unit_price": None, "price": "41,000",
                             "sub_items": [{"name": "Sedang", "count": "1", "unit_price": None, "price": "0"}]}
    assert g["items"][1]["count"] == "2x" and g["items"][1]["unit_price"] == "@5.000"
    assert (g["subtotal"], g["tax"], g["total"]) == ("51,000", "5,100", "56,100")
    assert "num" not in json.dumps(g) and "60,000" not in json.dumps(g)
    jsonschema.validate(g, SCHEMA)


def test_single_dict_menu_and_list_values_are_masked_not_joined():
    g, masked = to_gold({"menu": {"nm": ["KOPI", "SUSU"], "cnt": "1", "price": "23.000"},
                         "total": {"total_price": "23.000"}})
    assert len(g["items"]) == 1 and g["items"][0]["name"] is None
    assert masked == ["items[1].name"]
    jsonschema.validate(g, SCHEMA)


def test_perfect_prediction_scores_one():
    g, masked = gold()
    d = score_document(g, masked, parsed(g))
    assert d["strict"] == [d["strict"][1], d["strict"][1]] and d["doc_exact"]
    assert d["f1_counts"][0] == d["f1_counts"][1] == d["f1_counts"][2]
    # gold-present fields: item1 3 + sub 3 + item2 4 + doc 3
    assert d["strict"][1] == 13


def test_format_only_difference_is_wrong_strict_but_right_loose():
    g, masked = gold()
    p = json.loads(dump_answer(g))
    p["items"][1]["count"] = "2"
    p["items"][1]["unit_price"] = "5000"
    d = score_document(g, masked, parsed(p))
    assert d["strict"][0] == 11 and d["loose"][0] == 13
    assert loose_norm("price", "Rp. 41.000") == loose_norm("price", "41,000") == "41000"
    assert loose_norm("name", "Bbq  chicken") == loose_norm("name", "BBQ Chicken")


def test_missing_row_and_invented_value_are_penalised():
    g, masked = gold()
    p = json.loads(dump_answer(g))
    p["items"] = p["items"][1:]  # drop the first item: positions shift
    p["items"][0]["row_index"] = 1
    d = score_document(g, masked, parsed(p))
    assert not d["rows_match"] and not d["doc_exact"]
    assert d["strict"][0] < 13
    q = json.loads(dump_answer(g))
    q["items"][0]["unit_price"] = "41,000"  # not printed in gold
    e = score_document(g, masked, parsed(q))
    assert e["absent_filled"] == 1 and not e["doc_exact"]
    assert e["f1_counts"][1] == e["f1_counts"][2] + 1


def test_json_failure_counts_every_field_wrong():
    g, masked = gold()
    d = score_document(g, masked, parse_response("```json\n{}\n```", "CORD_RAW"))
    assert d["status"] == "json_invalid" and d["strict"] == [0, 13]
    agg = aggregate([d, score_document(g, masked, parsed(g))])
    assert agg["strict_field_accuracy"]["accuracy"] == 0.5 and agg["json_valid_rate"] == 0.5


def test_masked_field_is_not_scored():
    g, masked = to_gold({"menu": [{"nm": ["A", "B"], "cnt": "1", "price": "5"}], "total": {"total_price": "5"}})
    d = score_document(g, masked, parsed({"schema_version": "cord-raw-1.0", "items": [
        {"row_index": 1, "name": "A B", "count": "1", "unit_price": None, "price": "5", "sub_items": []}],
        "subtotal": None, "tax": None, "total": "5"}))
    assert d["strict"] == [3, 3] and d["absent_filled"] == 0


def test_prompt_is_registered_and_never_mentions_gold_inputs():
    text, digest = load_prompt("CORD_RAW")
    assert text.startswith("TASK: CORD_RAW") and len(digest) == 64
    assert "cord-raw-1.0" in text and "purchase order" not in text.lower()


def test_every_training_data_option_pins_the_manifests_it_reads():
    """astra review 3: all_plus_cord_up reads trade and CORD records, so its report must hash those manifests too."""
    from invoiceguard.vlm.records import TRAIN_DATA_SOURCES, train_manifest_names

    for data in ("all_plus_cord", "all_plus_cord_up"):
        assert {"trade_raw_v1.jsonl", "cord_v2.jsonl"} <= set(train_manifest_names(data))
    assert "cord_v2.jsonl" not in train_manifest_names("all") and train_manifest_names("all", True)[-1] == "trade_raw_aug1.jsonl"
    import re
    train_src = (Path(__file__).resolve().parents[1] / "src" / "invoiceguard" / "vlm" / "train.py").read_text(encoding="utf-8")
    choices = re.search(r'"--data", choices=\[([^\]]+)\]', train_src).group(1)
    assert {c.strip().strip('"') for c in choices.split(",")} == set(TRAIN_DATA_SOURCES)  # no option without a manifest list
