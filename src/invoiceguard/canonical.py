"""PUBLIC_CANONICAL numeric contract (docs/15 section A).

Ground-truth numbers are converted to Decimal without float arithmetic and serialised as
canonical decimal strings (no exponent, no thousands separators, no currency symbols,
trailing zeros removed). Predictions are parsed strictly: only JSON *strings* matching
``^-?[0-9]+(\\.[0-9]+)?$`` pass. A JSON number (float/int) output is a contract violation
and is NOT silently converted into a canonical success.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

CANONICAL_RE = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")


class LabelDataError(ValueError):
    """Source label is non-finite or of an unsupported type; quarantine, never coerce."""


def label_to_decimal(value: Any) -> Decimal:
    """Convert a source label value (JSON parsed with parse_float=Decimal, or parquet scalar).

    * Decimal / int -> exact.
    * float (parquet double) -> Decimal(repr(value)): shortest round-trip decimal
      serialisation of the stored binary value; no arithmetic is performed.
    * bool, str, None, non-finite -> LabelDataError (caller decides null semantics first).
    """
    if isinstance(value, bool):
        raise LabelDataError(f"boolean is not a numeric label: {value!r}")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise LabelDataError(f"non-finite float label: {value!r}")
        result = Decimal(repr(value))
    else:
        raise LabelDataError(f"unsupported label type {type(value).__name__}: {value!r}")
    if not result.is_finite():
        raise LabelDataError(f"non-finite decimal label: {value!r}")
    return result


def canonical_str(value: Decimal) -> str:
    """Decimal -> canonical decimal string. 2.50 -> '2.5', 100.0 -> '100', -0 -> '0'."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise LabelDataError(f"canonical_str needs a finite Decimal, got {value!r}")
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    assert CANONICAL_RE.match(text), text
    return text


@dataclass(frozen=True)
class ParsedNumber:
    status: str  # ok | null | format_error | type_error
    value: Decimal | None
    raw: Any


def parse_canonical_prediction(value: Any) -> ParsedNumber:
    """Strict parser for model output values in PUBLIC_CANONICAL.

    null -> status 'null' (counts as wrong/abstention against an observed label).
    JSON number -> 'type_error' (contract violation; not canonical success).
    String not matching the canonical regex (e.g. '1,200.00', '$2.50') -> 'format_error'.
    """
    if value is None:
        return ParsedNumber("null", None, value)
    if isinstance(value, bool) or not isinstance(value, str):
        return ParsedNumber("type_error", None, value)
    if not CANONICAL_RE.match(value):
        return ParsedNumber("format_error", None, value)
    try:
        return ParsedNumber("ok", Decimal(value), value)
    except InvalidOperation:  # pragma: no cover - regex already guarantees validity
        return ParsedNumber("format_error", None, value)


def values_equal(gold: Decimal, pred: ParsedNumber) -> bool:
    """Numeric value exact match: Decimal('2.5') == Decimal('2.50')."""
    return pred.status == "ok" and pred.value is not None and pred.value == gold
