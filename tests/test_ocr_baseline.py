"""B0 heuristics on hand-made OCR word boxes (no Tesseract/Docker needed; runs in CI)."""
import json

from invoiceguard.model_output import parse_response
from invoiceguard.ocr_baseline import (
    TRADE_NUMERIC, TRADE_VOCAB, Word, build_lines, canonical_number, find_header, predict_public, predict_trade,
)


def words_line(y, cells, h=20):
    """cells: [(x_left, text)], each text may contain spaces (one word per token, 8px apart)."""
    out = []
    for x, text in cells:
        for token in text.split():
            width = 11 * len(token)
            out.append(Word(token, x, y, width, h, 95.0))
            x += width + 8
    return out


HEADER = [(80, "Item #"), (230, "Description"), (700, "Qty"), (790, "Unit"), (960, "Unit Price"), (1100, "Amount")]


def test_longest_keyword_wins_unit_price_is_not_unit():
    lines = build_lines(words_line(400, HEADER))
    idx, cols = find_header(lines, TRADE_VOCAB, TRADE_NUMERIC, [{"quantity"}, {"unit_price"}, {"sku"}])
    assert idx == 0
    assert [c.name for c in cols] == ["sku", "description", "quantity", "unit", "unit_price", "line_total"]


def test_table_rows_with_wrapped_quantity_and_totals():
    words = (words_line(100, [(80, "SI-000731")]) + words_line(140, [(80, "Currency"), (300, "USD")])
             + words_line(400, HEADER)
             + words_line(460, [(80, "000125"), (230, "Sensor module"), (620, "283 cartons /"), (790, "EA"),
                                (1000, "2.75"), (1100, "1,556.50")])
             + words_line(490, [(683, "566 pcs")])
             + words_line(540, [(80, "CAB-002"), (230, "Signal cable 2m"), (735, "20"), (790, "EA"), (1000, "5.00"), (1110, "100.00")])
             + words_line(620, [(900, "Subtotal"), (1100, "1,656.50")])
             + words_line(660, [(900, "Discount"), (1120, "0.00")])
             + words_line(700, [(900, "Tax"), (1120, "0.00")])
             + words_line(740, [(900, "Total (USD)"), (1100, "1,656.50")]))
    obj = predict_trade(words)
    parsed = parse_response(json.dumps(obj), "TRADE_RAW")
    assert parsed.status == "ok" and parsed.schema_valid and parsed.row_index_valid
    first, second = obj["items"]
    assert first["sku_raw"] == "000125" and first["quantity_raw"] == "283 cartons / 566 pcs"
    assert first["unit_price_raw"] == "2.75" and first["line_total_raw"] == "1,556.50"
    assert second["description_raw"] == "Signal cable 2m" and second["quantity_raw"] == "20"
    assert obj["invoice_number_raw"] == "SI-000731" and obj["currency_raw"] == "USD"
    assert (obj["subtotal_raw"], obj["discount_raw"], obj["tax_raw"], obj["total_raw"]) == ("1,656.50", "0.00", "0.00", "1,656.50")


def test_two_line_list_pattern_without_header():
    words = (words_line(300, [(70, "80-1748"), (200, "- Spirit level vial")])
             + words_line(330, [(90, "Qty / Unit / Price / Amount"), (790, "432 EA @ 166.82 = 72,066.24")]))
    item = predict_trade(words)["items"][0]
    assert (item["sku_raw"], item["description_raw"]) == ("80-1748", "Spirit level vial")
    assert (item["quantity_raw"], item["unit_raw"], item["unit_price_raw"], item["line_total_raw"]) == ("432", "EA", "166.82", "72,066.24")


def test_public_ticket_rows_leave_unprinted_price_null():
    words = words_line(400, [(118, "None"), (410, "2.0 x GENERAL ADMISSION TICKET"), (1050, "£90.00")])
    obj = predict_public(words)
    assert obj["items"] == [{"row_index": 1, "description": "GENERAL ADMISSION TICKET", "quantity": "2",
                             "unit_price": None, "amount": "90"}]
    assert parse_response(json.dumps(obj), "PUBLIC_CANONICAL").schema_valid


def test_canonical_number_strips_currency_and_grouping():
    assert canonical_number("€1,200.50") == "1200.5"
    assert canonical_number("C$45.00") == "45"
    assert canonical_number("n/a") is None


def test_ocr_artifacts_are_named_by_unique_record_id():
    """Regression: stress variants share the clean image's file stem; OCR caches must key on record_id."""
    import inspect

    from invoiceguard import ocr_baseline

    src = inspect.getsource(ocr_baseline.run_ocr) + inspect.getsource(ocr_baseline.run_predict)
    assert "rec.record_id" in src and "image_path.stem" not in src
