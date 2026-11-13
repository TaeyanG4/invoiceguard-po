"""Conservative parsing of TRADE_RAW invoice fields (docs/04 section 2).

The raw model output is never modified. Each field yields a FieldResult with
status parsed|missing|ambiguous|unsupported. Values are Decimal-backed strings;
no float is ever used. Nothing is inferred from the purchase order.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

PARSED, MISSING, AMBIGUOUS, UNSUPPORTED = "parsed", "missing", "ambiguous", "unsupported"

# en-US number: optional sign, exact 3-digit grouping or plain digits, optional fraction.
_EN_US_NUMBER = re.compile(r"^(?P<sign>-)?(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d+))?$")
_EUROPEAN_HINT = re.compile(r"^-?\d{1,3}(?:\.\d{3})+(?:,\d+)?$|^-?\d+,\d{1,2}$")
_CURRENCY_PREFIX = re.compile(r"^(?:USD|US\$|\$)\s?", re.IGNORECASE)
_QUANTITY_INT = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)$")

MONEY_MAX_DP = 2
UNIT_PRICE_MAX_DP = 4


@dataclass(frozen=True)
class FieldResult:
    raw: str | None
    normalized: str | None
    status: str
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == PARSED

    @property
    def decimal(self) -> Decimal | None:
        return Decimal(self.normalized) if self.ok and self.normalized is not None else None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blank(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def _type_guard(raw: Any) -> FieldResult | None:
    if raw is None:
        return FieldResult(None, None, MISSING, "null")
    if not isinstance(raw, str):
        return FieldResult(repr(raw), None, UNSUPPORTED, f"non_string_{type(raw).__name__}")
    if raw.strip() == "":
        return FieldResult(raw, None, MISSING, "empty")
    return None


def normalize_sku(raw: Any) -> FieldResult:
    """Trim only. Case and leading zeros preserved; never int-converted or fuzzy matched."""
    guard = _type_guard(raw)
    if guard:
        return guard
    return FieldResult(raw, raw.strip(), PARSED)


def parse_number(raw: Any, max_dp: int, allow_negative: bool = False) -> FieldResult:
    guard = _type_guard(raw)
    if guard:
        return guard
    text = raw.strip()
    reason = None
    stripped = _CURRENCY_PREFIX.sub("", text, count=1)
    if stripped != text:
        reason = "currency_prefix_ignored"
        text = stripped.strip()
    match = _EN_US_NUMBER.match(text)
    if not match:
        if _EUROPEAN_HINT.match(text):
            return FieldResult(raw, None, UNSUPPORTED, "non_en_us_number_format")
        return FieldResult(raw, None, AMBIGUOUS, "unparseable_number")
    frac = match.group("frac") or ""
    if len(frac) > max_dp:
        return FieldResult(raw, None, UNSUPPORTED, f"more_than_{max_dp}_decimal_places")
    if match.group("sign") and not allow_negative:
        return FieldResult(raw, None, UNSUPPORTED, "negative_not_supported")
    digits = match.group("int").replace(",", "")
    try:
        value = Decimal(f'{match.group("sign") or ""}{digits}.{frac or "0"}')
    except InvalidOperation:  # pragma: no cover - regex guarantees digits
        return FieldResult(raw, None, AMBIGUOUS, "unparseable_number")
    normalized = f"{value:.{max(len(frac), 0)}f}" if frac else str(int(value))
    return FieldResult(raw, normalized, PARSED, reason)


def parse_money(raw: Any) -> FieldResult:
    return parse_number(raw, MONEY_MAX_DP)


def parse_unit_price(raw: Any) -> FieldResult:
    return parse_number(raw, UNIT_PRICE_MAX_DP)


def parse_quantity(raw: Any) -> FieldResult:
    """Positive integers only. '2 cartons / 100 pcs', decimals, 0, negatives -> review."""
    guard = _type_guard(raw)
    if guard:
        return guard
    text = raw.strip()
    if not _QUANTITY_INT.match(text):
        return FieldResult(raw, None, AMBIGUOUS, "not_a_plain_positive_integer")
    value = int(text.replace(",", ""))
    if value <= 0:
        return FieldResult(raw, None, UNSUPPORTED, "non_positive_quantity")
    return FieldResult(raw, str(value), PARSED)


def normalize_unit(raw: Any) -> FieldResult:
    guard = _type_guard(raw)
    if guard:
        return guard
    if raw.strip().upper() == "EA":
        return FieldResult(raw, "EA", PARSED)
    return FieldResult(raw, None, UNSUPPORTED, "unit_not_EA_no_conversion")


def normalize_currency(raw: Any) -> FieldResult:
    guard = _type_guard(raw)
    if guard:
        return guard
    text = raw.strip()
    if text.upper() in {"USD", "US$"}:
        return FieldResult(raw, "USD", PARSED)
    if text == "$":
        return FieldResult(raw, None, AMBIGUOUS, "bare_dollar_sign_is_ambiguous")
    return FieldResult(raw, None, UNSUPPORTED, "currency_not_supported_in_p0")


ROW_FIELDS = {
    "sku": ("sku_raw", normalize_sku),
    "description": ("description_raw", None),
    "quantity": ("quantity_raw", parse_quantity),
    "unit": ("unit_raw", normalize_unit),
    "unit_price": ("unit_price_raw", parse_unit_price),
    "line_total": ("line_total_raw", parse_money),
}
DOC_FIELDS = {
    "currency": ("currency_raw", normalize_currency),
    "subtotal": ("subtotal_raw", parse_money),
    "tax": ("tax_raw", parse_money),
    "discount": ("discount_raw", parse_money),
    "total": ("total_raw", parse_money),
}


def normalize_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    """Return a separate normalization structure; the raw invoice dict is not mutated.

    Keys absent from the model response are expanded to null and listed in
    ``missing_in_response`` (docs/04 section 1).
    """
    missing_in_response: list[str] = []
    doc: dict[str, Any] = {}
    for name, (key, fn) in DOC_FIELDS.items():
        if key not in invoice:
            missing_in_response.append(key)
        doc[name] = fn(invoice.get(key))
    rows = []
    for item in invoice.get("items") or []:
        row: dict[str, Any] = {"row_index": item.get("row_index")}
        for name, (key, fn) in ROW_FIELDS.items():
            if key not in item:
                missing_in_response.append(f"items[{item.get('row_index')}].{key}")
            value = item.get(key)
            row[name] = fn(value) if fn else FieldResult(value, value.strip() if isinstance(value, str) else None,
                                                         PARSED if isinstance(value, str) and value.strip() else MISSING)
        rows.append(row)
    return {"document": doc, "rows": rows, "missing_in_response": missing_in_response}


def normalization_to_json(norm: dict[str, Any]) -> dict[str, Any]:
    return {
        "document": {k: v.as_dict() for k, v in norm["document"].items()},
        "rows": [{k: (v.as_dict() if isinstance(v, FieldResult) else v) for k, v in row.items()} for row in norm["rows"]],
        "missing_in_response": list(norm["missing_in_response"]),
    }
