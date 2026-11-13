"""B01–B12 rule tests (docs/09) on the fictional fixtures in examples/ (oracle input, not model output)."""
import copy
import json
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest

from invoiceguard.normalization import parse_money, parse_quantity, parse_unit_price, normalize_sku
from invoiceguard.reconciliation import reconcile, validate_po

REPO = Path(__file__).resolve().parents[1]
EX = REPO / "examples"
FINDINGS_SCHEMA = json.loads((REPO / "schemas" / "findings.schema.json").read_text(encoding="utf-8"))
PO_SCHEMA = json.loads((REPO / "schemas" / "purchase_order.schema.json").read_text(encoding="utf-8"))
EXTRACTION_SCHEMA = json.loads((REPO / "schemas" / "extraction.schema.json").read_text(encoding="utf-8"))


def load(name):
    return json.loads((EX / name).read_text(encoding="utf-8"))


@pytest.fixture
def invoice():
    return load("invoice_oracle.json")


@pytest.fixture
def po():
    return load("purchase_order.json")


def codes(result):
    jsonschema.validate(result, FINDINGS_SCHEMA)  # every result must satisfy the findings contract
    return sorted(f["code"] for f in result["findings"])


def apply_patch(doc, patch):
    doc = copy.deepcopy(doc)
    for path, value in patch.items():
        if path.startswith("items["):
            index = int(path[len("items["):path.index("]")])
            doc["items"][index][path.split(".", 1)[1]] = value
        else:
            doc[path] = value
    return doc


def test_fixtures_satisfy_schemas(invoice, po):
    jsonschema.validate(invoice, EXTRACTION_SCHEMA)
    jsonschema.validate(po, PO_SCHEMA)
    assert validate_po(po) == []


def test_b03_base_fixture_matches_expected_findings_exactly(invoice, po):
    result = reconcile(invoice, po, source="oracle_fixture")
    assert result == load("expected_findings.json")
    assert "LINE_ARITHMETIC_MISMATCH" not in codes(result)


def test_b01_leading_zero_sku_is_a_different_sku(invoice, po):
    assert normalize_sku(" 000125 ").normalized == "000125"
    inv = apply_patch(invoice, {"items[0].sku_raw": "125"})
    assert codes(reconcile(inv, po, "oracle_fixture")) == ["PO_LINE_NOT_FOUND", "UNKNOWN_SKU"]


def test_b01_sku_match_is_case_sensitive(invoice, po):
    inv = apply_patch(invoice, {"items[1].sku_raw": "cab-002"})
    assert "UNKNOWN_SKU" in codes(reconcile(inv, po, "oracle_fixture"))


def test_b02_same_decimal_value(invoice, po):
    assert parse_unit_price("2.5000").decimal == parse_unit_price("2.50").decimal == Decimal("2.5")
    inv = apply_patch(invoice, {"items[0].unit_price_raw": "2.5000", "items[0].line_total_raw": "250.00",
                                "subtotal_raw": "350.00", "total_raw": "350.00"})
    result = reconcile(inv, po, "oracle_fixture")
    assert codes(result) == []
    assert result["case_status"] == "matched_candidate"
    assert result["reference_total_difference"] == "0.00"


def test_b04_quantity_difference(invoice, po):
    inv = apply_patch(invoice, {"items[0].quantity_raw": "90", "items[0].line_total_raw": "247.50",
                                "subtotal_raw": "347.50", "total_raw": "347.50"})
    assert codes(reconcile(inv, po, "oracle_fixture")) == ["QTY_DIFF", "UNIT_PRICE_DIFF"]


def test_b05_unknown_and_missing_po_line(invoice, po):
    inv = apply_patch(invoice, {"items[1].sku_raw": "XYZ-999"})
    result = reconcile(inv, po, "oracle_fixture")
    assert codes(result) == ["PO_LINE_NOT_FOUND", "UNIT_PRICE_DIFF", "UNKNOWN_SKU"]
    not_found = [f for f in result["findings"] if f["code"] == "PO_LINE_NOT_FOUND"][0]
    assert not_found["expected"] == "CAB-002" and not_found["row_index"] is None


def test_b06_duplicate_sku_is_blocker_and_not_merged(invoice, po):
    inv = apply_patch(invoice, {"items[1].sku_raw": "000125"})
    result = reconcile(inv, po, "oracle_fixture")
    c = codes(result)
    assert c.count("DUPLICATE_SKU") == 2
    assert "PO_LINE_NOT_FOUND" in c  # CAB-002 really is absent
    assert "QTY_DIFF" not in c and "UNIT_PRICE_DIFF" not in c  # duplicates are not compared/merged
    assert all(f["severity"] == "blocker" for f in result["findings"] if f["code"] == "DUPLICATE_SKU")


def test_b07_ambiguous_quantity_not_forced_to_100(invoice, po):
    assert parse_quantity("2 cartons / 100 pcs").status == "ambiguous"
    inv = apply_patch(invoice, {"items[0].quantity_raw": "2 cartons / 100 pcs"})
    result = reconcile(inv, po, "oracle_fixture")
    assert "AMBIGUOUS_QUANTITY" in codes(result)
    assert "QTY_DIFF" not in codes(result)
    assert inv["items"][0]["quantity_raw"] == "2 cartons / 100 pcs"  # raw preserved


@pytest.mark.parametrize("raw", ["0", "-5", "100.5", "1,00", "100 pcs"])
def test_quantity_only_positive_integers(raw):
    assert not parse_quantity(raw).ok
    assert parse_quantity("1,000").normalized == "1000"


def test_b08_european_number_unsupported(invoice, po):
    assert parse_unit_price("1.234,50").status == "unsupported"
    assert parse_money("1,234").normalized == "1234"
    assert parse_money("1,234.50").normalized == "1234.50"
    assert not parse_money("12,34.50").ok
    assert not parse_money("2.755").ok  # money max 2 dp
    assert parse_unit_price("2.7550").ok  # unit price max 4 dp
    inv = apply_patch(invoice, {"items[0].unit_price_raw": "1.234,50"})
    assert "AMBIGUOUS_NUMBER" in codes(reconcile(inv, po, "oracle_fixture"))


@pytest.mark.parametrize("currency", ["$", "EUR", "€"])
def test_b09_non_usd_or_bare_dollar(invoice, po, currency):
    inv = apply_patch(invoice, {"currency_raw": currency})
    c = codes(reconcile(inv, po, "oracle_fixture"))
    assert "UNSUPPORTED_CURRENCY" in c
    assert "UNIT_PRICE_DIFF" not in c  # price comparison not evaluable without conversion


def test_b10_box_vs_ea(invoice, po):
    inv = apply_patch(invoice, {"items[0].unit_raw": "BOX"})
    c = codes(reconcile(inv, po, "oracle_fixture"))
    assert "UNIT_MISMATCH" in c and "UNIT_PRICE_DIFF" not in c and "QTY_DIFF" not in c


def test_b11_line_arithmetic_warning_without_auto_fix(invoice, po):
    inv = apply_patch(invoice, {"items[0].unit_price_raw": "2.50", "items[0].line_total_raw": "2500.00"})
    result = reconcile(inv, po, "oracle_fixture")
    assert "LINE_ARITHMETIC_MISMATCH" in codes(result)
    mismatch = [f for f in result["findings"] if f["code"] == "LINE_ARITHMETIC_MISMATCH"][0]
    assert mismatch["expected"] == "250.00" and mismatch["observed"] == "2500.00"
    assert inv["items"][0]["line_total_raw"] == "2500.00"


def test_total_arithmetic_mismatch(invoice, po):
    inv = apply_patch(invoice, {"total_raw": "380.00"})
    assert "TOTAL_ARITHMETIC_MISMATCH" in codes(reconcile(inv, po, "oracle_fixture"))


def test_nonzero_tax_makes_total_not_evaluable(invoice, po):
    inv = apply_patch(invoice, {"tax_raw": "10.00", "total_raw": "385.00"})
    c = codes(reconcile(inv, po, "oracle_fixture"))
    assert "TOTAL_CHECK_NOT_EVALUABLE" in c and "TOTAL_ARITHMETIC_MISMATCH" not in c


def test_b12_missing_critical_field(invoice, po):
    inv = apply_patch(invoice, {"items[0].quantity_raw": None})
    c = codes(reconcile(inv, po, "oracle_fixture"))
    assert "MISSING_CRITICAL_FIELD" in c and "QTY_DIFF" not in c


def test_missing_key_is_expanded_and_flagged(invoice, po):
    inv = copy.deepcopy(invoice)
    del inv["items"][0]["unit_raw"]
    assert "MISSING_CRITICAL_FIELD" in codes(reconcile(inv, po, "oracle_fixture"))


def test_no_po_and_unsupported_document(invoice):
    assert "NO_PO" in codes(reconcile(invoice, None, "oracle_fixture"))
    inv = apply_patch(invoice, {"document_type": "receipt"})
    assert "UNSUPPORTED_DOCUMENT" in codes(reconcile(inv, None, "oracle_fixture"))


def test_row_count_limits(invoice, po):
    inv = copy.deepcopy(invoice)
    inv["items"] = []
    assert "UNSUPPORTED_ROW_COUNT" in codes(reconcile(inv, po, "oracle_fixture"))


def test_po_duplicate_sku_rejected(po):
    bad = copy.deepcopy(po)
    bad["items"][1]["sku"] = "000125"
    assert validate_po(bad) == ["duplicate_sku_in_po:000125"]


def test_e03_unknown_reason_enum_fails_schema(invoice, po):
    result = reconcile(invoice, po, "oracle_fixture")
    result["findings"][0]["code"] = "QUANTITY_DIFF"  # forbidden alias
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, FINDINGS_SCHEMA)


def test_unknown_source_rejected(invoice, po):
    with pytest.raises(ValueError):
        reconcile(invoice, po, source="mock")


def test_reconcile_never_mutates_invoice(invoice, po):
    before = copy.deepcopy(invoice)
    reconcile(invoice, po, "live_model")
    assert invoice == before


@pytest.mark.parametrize("case", [c for c in load("test_cases.json")["cases"] if "invoice_patch" in c],
                         ids=lambda c: c["id"])
def test_examples_test_cases_spec(case, invoice, po):
    result = reconcile(apply_patch(invoice, case["invoice_patch"]), po, "oracle_fixture")
    for code in case["expect"]:
        assert code in codes(result)
