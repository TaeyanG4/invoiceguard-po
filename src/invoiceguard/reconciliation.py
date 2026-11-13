"""Deterministic invoice <-> independent PO reconciliation (docs/04 sections 3-5).

Reason codes are exactly the enum of schemas/findings.schema.json. The invoice values are never
changed to match the PO; findings only describe differences for a human reviewer.
"""
from __future__ import annotations

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .normalization import FieldResult, normalize_invoice

TOLERANCE = Decimal("0.01")
CENT = Decimal("0.01")
MAX_ROWS = 12
SOURCES = ("oracle_fixture", "live_model", "human_review")

BLOCKER_CODES = frozenset({
    "MISSING_CRITICAL_FIELD", "AMBIGUOUS_NUMBER", "AMBIGUOUS_QUANTITY", "UNSUPPORTED_CURRENCY",
    "CURRENCY_MISMATCH", "UNIT_MISMATCH", "DUPLICATE_SKU", "UNSUPPORTED_DOCUMENT",
    "UNSUPPORTED_ROW_COUNT", "NO_PO",
})
WARNING_CODES = frozenset({
    "UNKNOWN_SKU", "PO_LINE_NOT_FOUND", "QTY_DIFF", "UNIT_PRICE_DIFF", "LINE_ARITHMETIC_MISMATCH",
    "TOTAL_ARITHMETIC_MISMATCH", "TOTAL_CHECK_NOT_EVALUABLE", "DUPLICATE_DOCUMENT",
})
TRANSACTION_DIFF_CODES = frozenset({"QTY_DIFF", "UNIT_PRICE_DIFF", "UNKNOWN_SKU", "PO_LINE_NOT_FOUND"})

MESSAGES = {
    "MISSING_CRITICAL_FIELD": "필수 값을 읽지 못했습니다. 원문을 보고 값을 보완한 뒤 다시 검증하세요.",
    "AMBIGUOUS_NUMBER": "숫자 형식을 지원 범위에서 해석할 수 없습니다. 원문을 확인하고 값을 명시하세요.",
    "AMBIGUOUS_QUANTITY": "수량 표기가 모호하거나 지원 범위 밖입니다. 원문을 확인하고 EA 기준 수량을 명시하세요.",
    "UNSUPPORTED_CURRENCY": "통화가 USD로 명시되지 않았습니다. 자동 환산하지 않습니다.",
    "CURRENCY_MISMATCH": "인보이스 통화와 발주서 통화가 다릅니다. 자동 환산하지 않습니다.",
    "UNIT_MISMATCH": "단위가 EA가 아닙니다. 단위를 환산하지 않습니다.",
    "DUPLICATE_SKU": "같은 품번이 여러 행에 있습니다. 자동으로 합치지 않습니다.",
    "UNSUPPORTED_DOCUMENT": "지원하는 인보이스 문서가 아닙니다.",
    "UNSUPPORTED_ROW_COUNT": "품목 행 수가 지원 범위(1–12) 밖입니다.",
    "NO_PO": "비교할 발주서가 연결되지 않았습니다.",
    "UNKNOWN_SKU": "발주서에 없는 품번입니다. 잘못된 발주서인지 실제 추가 품목인지 확인하세요.",
    "PO_LINE_NOT_FOUND": "발주서 행이 인보이스에 없습니다. 누락인지 부분선적인지 확인하세요.",
    "QTY_DIFF": "인보이스의 표시 수량이 발주 수량과 다릅니다. 읽기 오류인지 실제 거래 변경인지 원문과 계약을 확인하세요.",
    "UNIT_PRICE_DIFF": "인보이스의 표시 단가가 발주 단가와 다릅니다. 읽기 오류인지 실제 거래 변경인지 원문과 계약을 확인하세요.",
    "LINE_ARITHMETIC_MISMATCH": "수량×단가와 표시 금액이 0.01 넘게 다릅니다. 원문값은 자동 수정하지 않습니다.",
    "TOTAL_ARITHMETIC_MISMATCH": "행 금액 합계와 표시 총액이 0.01 넘게 다릅니다.",
    "TOTAL_CHECK_NOT_EVALUABLE": "총액 검산을 수행하지 못했습니다. 사유를 확인하세요.",
    "DUPLICATE_DOCUMENT": "같은 파일(sha256)로 만든 기존 건이 있습니다.",
}


def _finding(code: str, row_index: int | None, field: str, expected: str | None, observed: str | None,
             detail: str | None = None) -> dict[str, Any]:
    severity = "blocker" if code in BLOCKER_CODES else "warning"
    message = MESSAGES[code] + (f" ({detail})" if detail else "")
    return {"code": code, "severity": severity, "row_index": row_index, "field": field,
            "expected": expected, "observed": observed, "message": message}


def _raw(fr: FieldResult) -> str | None:
    return fr.raw


def validate_po(po: dict[str, Any]) -> list[str]:
    """Semantic PO checks beyond JSON Schema. Duplicate SKU -> reject (HTTP 422 at API)."""
    errors = []
    skus = [line.get("sku") for line in po.get("items") or []]
    for sku, count in Counter(skus).items():
        if count > 1:
            errors.append(f"duplicate_sku_in_po:{sku}")
    line_ids = [line.get("po_line_id") for line in po.get("items") or []]
    if len(set(line_ids)) != len(line_ids):
        errors.append("duplicate_po_line_id")
    return errors


def reconcile(invoice: dict[str, Any], po: dict[str, Any] | None, source: str,
              duplicate_of_case: str | None = None) -> dict[str, Any]:
    if source not in SOURCES:
        raise ValueError(f"unknown findings source {source!r}")
    norm = normalize_invoice(invoice)
    doc, rows = norm["document"], norm["rows"]
    findings: list[dict[str, Any]] = []

    if duplicate_of_case:
        findings.append(_finding("DUPLICATE_DOCUMENT", None, "document", duplicate_of_case, None))
    if invoice.get("document_type") != "invoice":
        findings.append(_finding("UNSUPPORTED_DOCUMENT", None, "document_type", "invoice", invoice.get("document_type")))
    if not 1 <= len(rows) <= MAX_ROWS:
        findings.append(_finding("UNSUPPORTED_ROW_COUNT", None, "items", f"1-{MAX_ROWS}", str(len(rows))))

    # ---- currency (document level)
    currency = doc["currency"]
    currency_ok = currency.ok
    if currency.status == "missing":
        findings.append(_finding("MISSING_CRITICAL_FIELD", None, "currency", None, None))
    elif not currency.ok:
        findings.append(_finding("UNSUPPORTED_CURRENCY", None, "currency", "USD", _raw(currency), currency.reason))
    elif po is not None and currency.normalized != po.get("currency"):
        currency_ok = False
        findings.append(_finding("CURRENCY_MISMATCH", None, "currency", po.get("currency"), _raw(currency)))

    # ---- per-row support / grammar checks
    row_ok: dict[int, dict[str, bool]] = {}
    for position, row in enumerate(rows, start=1):
        idx = row["row_index"] if isinstance(row["row_index"], int) else position
        ok = {}
        for field in ("sku", "quantity", "unit", "unit_price", "line_total"):
            fr: FieldResult = row[field]
            ok[field] = fr.ok
            if fr.status == "missing":
                findings.append(_finding("MISSING_CRITICAL_FIELD", idx, field, None, None))
            elif fr.ok:
                continue
            elif field == "quantity":
                findings.append(_finding("AMBIGUOUS_QUANTITY", idx, field, None, _raw(fr), fr.reason))
            elif field == "unit":
                findings.append(_finding("UNIT_MISMATCH", idx, field, "EA", _raw(fr), fr.reason))
            elif field in ("unit_price", "line_total"):
                findings.append(_finding("AMBIGUOUS_NUMBER", idx, field, None, _raw(fr), fr.reason))
            else:  # sku of non-string type
                findings.append(_finding("MISSING_CRITICAL_FIELD", idx, field, None, _raw(fr), fr.reason))
        row_ok[idx] = ok
        row["_idx"] = idx

    # ---- duplicate SKU inside the invoice (never merged)
    sku_counts = Counter(r["sku"].normalized for r in rows if r["sku"].ok)
    duplicate_skus = {s for s, c in sku_counts.items() if c > 1}
    for r in rows:
        if r["sku"].ok and r["sku"].normalized in duplicate_skus:
            findings.append(_finding("DUPLICATE_SKU", r["_idx"], "sku", None, _raw(r["sku"])))

    # ---- PO comparison
    if po is None:
        findings.append(_finding("NO_PO", None, "po", None, None))
    else:
        po_by_sku = {line["sku"]: line for line in po.get("items") or []}
        seen_po_skus: set[str] = set()
        for r in rows:
            idx, ok = r["_idx"], row_ok[r["_idx"]]
            if not ok["sku"]:
                continue
            sku = r["sku"].normalized
            line = po_by_sku.get(sku)
            if line is None:
                findings.append(_finding("UNKNOWN_SKU", idx, "sku", None, _raw(r["sku"])))
                continue
            seen_po_skus.add(sku)
            if sku in duplicate_skus or not ok["unit"]:
                continue  # not evaluable: no merge, no unit conversion
            if ok["quantity"] and r["quantity"].decimal != Decimal(line["quantity"]):
                findings.append(_finding("QTY_DIFF", idx, "quantity", line["quantity"], _raw(r["quantity"])))
            if ok["unit_price"] and currency_ok and r["unit_price"].decimal != Decimal(line["unit_price"]):
                findings.append(_finding("UNIT_PRICE_DIFF", idx, "unit_price", line["unit_price"], _raw(r["unit_price"])))
        for line in po.get("items") or []:
            if line["sku"] not in seen_po_skus:
                findings.append(_finding("PO_LINE_NOT_FOUND", None, "sku", line["sku"], None,
                                         f'po_line_id={line["po_line_id"]}'))

    # ---- line arithmetic (document-internal, cent ROUND_HALF_UP, tolerance 0.01)
    for r in rows:
        ok = row_ok[r["_idx"]]
        if ok["quantity"] and ok["unit_price"] and ok["line_total"]:
            expected = (r["quantity"].decimal * r["unit_price"].decimal).quantize(CENT, rounding=ROUND_HALF_UP)
            if abs(expected - r["line_total"].decimal) > TOLERANCE:
                findings.append(_finding("LINE_ARITHMETIC_MISMATCH", r["_idx"], "line_total", f"{expected:.2f}",
                                         _raw(r["line_total"])))

    # ---- total check: only when tax/discount are explicitly 0 and every row total is parsed
    reasons = []
    for name in ("tax", "discount"):
        fr = doc[name]
        if not fr.ok:
            reasons.append(f"{name}_{fr.status}")
        elif fr.decimal != 0:
            reasons.append(f"{name}_nonzero")
    if not doc["total"].ok:
        reasons.append(f"total_{doc['total'].status}")
    if not rows or not all(row_ok[r["_idx"]]["line_total"] for r in rows):
        reasons.append("row_total_not_parsed")
    if reasons:
        findings.append(_finding("TOTAL_CHECK_NOT_EVALUABLE", None, "total", None, _raw(doc["total"]),
                                 ",".join(reasons)))
    else:
        line_sum = sum((r["line_total"].decimal for r in rows), Decimal("0"))
        if abs(line_sum - doc["total"].decimal) > TOLERANCE:
            findings.append(_finding("TOTAL_ARITHMETIC_MISMATCH", None, "total", f"{line_sum:.2f}", _raw(doc["total"])))
        elif doc["subtotal"].ok and abs(line_sum - doc["subtotal"].decimal) > TOLERANCE:
            findings.append(_finding("TOTAL_ARITHMETIC_MISMATCH", None, "subtotal", f"{line_sum:.2f}", _raw(doc["subtotal"])))

    reference = None
    if po is not None and doc["total"].ok:
        po_total = sum((Decimal(l["quantity"]) * Decimal(l["unit_price"]) for l in po.get("items") or []), Decimal("0"))
        reference = f'{(doc["total"].decimal - po_total.quantize(CENT, rounding=ROUND_HALF_UP)):.2f}'

    return {"schema_version": "1.0", "source": source,
            "case_status": "needs_review" if findings else "matched_candidate",
            "findings": findings, "reference_total_difference": reference}


def has_blocker(result: dict[str, Any]) -> bool:
    return any(f["severity"] == "blocker" for f in result["findings"])
