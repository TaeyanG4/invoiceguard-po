import json
from decimal import Decimal

import pytest

from invoiceguard.canonical import (
    LabelDataError,
    canonical_str,
    label_to_decimal,
    parse_canonical_prediction,
    values_equal,
)


def test_json_decimal_labels_are_exact():
    data = json.loads('{"q": 1.0, "p": 2.50, "a": 0.1}', parse_float=Decimal)
    assert canonical_str(label_to_decimal(data["q"])) == "1"
    assert canonical_str(label_to_decimal(data["p"])) == "2.5"
    assert canonical_str(label_to_decimal(data["a"])) == "0.1"


def test_parquet_float_uses_round_trip_repr_not_binary_expansion():
    # Decimal(0.1) would be 0.1000000000000000055511151231257827...; repr gives 0.1
    assert label_to_decimal(0.1) == Decimal("0.1")
    assert canonical_str(label_to_decimal(1200.5)) == "1200.5"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "2.5", None])
def test_bad_label_types_are_quarantined(bad):
    with pytest.raises(LabelDataError):
        label_to_decimal(bad)


@pytest.mark.parametrize(
    "value,expected",
    [(Decimal("100.00"), "100"), (Decimal("2.5000"), "2.5"), (Decimal("-0"), "0"),
     (Decimal("1E+2"), "100"), (Decimal("-3.10"), "-3.1"), (Decimal("0.05"), "0.05")],
)
def test_canonical_str(value, expected):
    assert canonical_str(value) == expected


def test_b02_numeric_value_match_not_raw_string():
    gold = Decimal("2.5")
    assert values_equal(gold, parse_canonical_prediction("2.50"))
    assert not values_equal(gold, parse_canonical_prediction("25.00"))


def test_thousands_separator_is_strict_format_error():
    parsed = parse_canonical_prediction("1,200.00")
    assert parsed.status == "format_error"
    assert not values_equal(Decimal("1200"), parsed)


def test_json_number_output_is_type_error_not_success():
    assert parse_canonical_prediction(2.5).status == "type_error"
    assert parse_canonical_prediction(100).status == "type_error"


def test_null_prediction_is_wrong_against_observed_label():
    parsed = parse_canonical_prediction(None)
    assert parsed.status == "null"
    assert not values_equal(Decimal("2.5"), parsed)


@pytest.mark.parametrize("text", ["$2.50", "2.5e3", " 2.5", "2.", ".5", "+2.5", "2,5"])
def test_non_canonical_strings_rejected(text):
    assert parse_canonical_prediction(text).status == "format_error"
