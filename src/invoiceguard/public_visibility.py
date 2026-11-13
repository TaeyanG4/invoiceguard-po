"""Per-field visibility of PUBLIC_CANONICAL targets, derived from the source renderer.

Evidence (T01, 2026-11-14): Jinja templates of github.com/alamgirqazi/synthetic-invoice-gen at
commit 91082ede48d2c0b2e32d9c489ea35f34e9922a99 + manual inspection of 2 clean images per
template (reports/data/public_visual_audit.md).

Renderer facts used here (render_receipts.py casts quantity/unit_price/amount to float):
* unit_price and amount are printed with "%.2f" in every template that prints them.
* quantity is printed with str(float) except formal_corporate ("%.2f").
* event_ticket never prints unit_price and prints description|upper.
* pos_thermal prints unit_price only when unit_price != amount ("@ X each"), and prints
  description[:28].

Statuses
  visible_exact          printed value == label value (scored, trainable)
  not_printed            renderer verifiably does not print the field (masked; never invented)
  printed_rounded        "%.2f" printing changes the label value (masked)
  truncated_by_renderer  description cut by the template (masked)
  case_transformed       description printed upper-cased; case-sensitive EM masked
  source_empty           publisher label is null/empty (masked; not treated as verified absence)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .canonical import label_to_decimal

RENDERER_COMMIT = "91082ede48d2c0b2e32d9c489ea35f34e9922a99"
VERIFIED_TEMPLATES = frozenset({
    "event_ticket", "formal_corporate", "freelancer_invoice", "modern_minimal", "pos_thermal", "utility_bill",
})
TWO_DP_QUANTITY_TEMPLATES = frozenset({"formal_corporate"})
POS_DESCRIPTION_LIMIT = 28
SCORED = "visible_exact"


def _fits_two_dp(value: float) -> bool:
    return label_to_decimal(value) == Decimal(f"{value:.2f}")


def item_visibility(template: str, item: dict[str, Any]) -> dict[str, str]:
    if template not in VERIFIED_TEMPLATES:
        return {f: "visibility_unverified" for f in ("description", "quantity", "unit_price", "amount")}
    status: dict[str, str] = {}

    description = item.get("description")
    if not description:
        status["description"] = "source_empty"
    elif template == "event_ticket":
        status["description"] = "case_transformed"
    elif template == "pos_thermal" and len(description) > POS_DESCRIPTION_LIMIT:
        status["description"] = "truncated_by_renderer"
    else:
        status["description"] = SCORED

    quantity = item.get("quantity")
    if quantity is None:
        status["quantity"] = "source_empty"
    elif template in TWO_DP_QUANTITY_TEMPLATES and not _fits_two_dp(quantity):
        status["quantity"] = "printed_rounded"
    else:
        status["quantity"] = SCORED  # str(float) prints the round-trip repr == label_to_decimal

    unit_price, amount = item.get("unit_price"), item.get("amount")
    if unit_price is None:
        status["unit_price"] = "source_empty"
    elif template == "event_ticket":
        status["unit_price"] = "not_printed"
    elif template == "pos_thermal" and unit_price == amount:  # same float comparison as the template
        status["unit_price"] = "not_printed"
    elif not _fits_two_dp(unit_price):
        status["unit_price"] = "printed_rounded"
    else:
        status["unit_price"] = SCORED

    if amount is None:
        status["amount"] = "source_empty"
    elif not _fits_two_dp(amount):
        status["amount"] = "printed_rounded"
    else:
        status["amount"] = SCORED
    return status


def document_visibility(record: dict[str, Any]) -> list[dict[str, str]]:
    return [item_visibility(record["_template_used"], it) for it in (record.get("line_items") or [])]


def train_eligible(record: dict[str, Any]) -> tuple[bool, str | None]:
    """PUBLIC_CANONICAL training eligibility (docs/13): every row has all four fields visible_exact."""
    rows = document_visibility(record)
    if not rows:
        return False, "no_line_items"
    for row in rows:
        for field, status in row.items():
            if status != SCORED:
                return False, f"{field}:{status}"
    return True, None
