"""Check teacher label drafts for the real GST invoices with the invoice's own arithmetic (no model involved).

For every drafted row: quantity x unit price vs line total (several GST layouts print the rate excl. or incl. tax, so a
row passes when the product matches the line total within 1 % or within the GST-adjusted total), and the sum of line
totals vs the printed grand total of the page. Rows and documents that fail go to manual reading. Nothing is corrected
automatically — this only routes work and records how much of a draft the arithmetic supports.

Usage: python scripts/realdocs/verify_labels.py reports/runpod2/teacher_raw.jsonl --out reports/realdocs/teacher_check.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def num(s) -> Decimal | None:
    if s is None:
        return None
    t = re.sub(r"[^\d.\-]", "", str(s).replace(",", ""))
    if t in ("", ".", "-"):
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def parse(raw: str | None) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def close(a: Decimal, b: Decimal, rel: Decimal = Decimal("0.01")) -> bool:
    return abs(a - b) <= max(Decimal("0.02"), rel * abs(b))


def check_row(it: dict) -> str:
    q, p, t = num(it.get("quantity_raw")), num(it.get("unit_price_raw")), num(it.get("line_total_raw"))
    if q is None or p is None or t is None:
        return "incomplete"
    prod = q * p
    if close(prod, t):
        return "ok"
    g = num(it.get("gst_rate_raw"))
    if g is not None and close(prod * (1 + g / 100), t, Decimal("0.015")):
        return "ok_gst"
    return "mismatch"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("teacher_jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    docs, summary = [], {"docs": 0, "parsed": 0, "rows": 0, "ok": 0, "ok_gst": 0, "mismatch": 0, "incomplete": 0,
                         "total_match": 0, "total_checked": 0}
    for line in Path(a.teacher_jsonl).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        summary["docs"] += 1
        obj = parse(rec.get("raw_response")) if rec.get("ok") else None
        entry = {"doc_id": rec["doc_id"], "status": "parsed" if obj else "unparsed", "finish_reason": rec.get("finish_reason"),
                 "rows": [], "total_check": None}
        if obj:
            summary["parsed"] += 1
            totals = []
            for it in obj.get("items") or []:
                st = check_row(it)
                summary["rows"] += 1
                summary[st] += 1
                entry["rows"].append({"row_index": it.get("row_index"), "check": st})
                if num(it.get("line_total_raw")) is not None:
                    totals.append(num(it.get("line_total_raw")))
            gt = num(obj.get("total_raw"))
            if gt is not None and totals:
                summary["total_checked"] += 1
                ok = close(sum(totals), gt, Decimal("0.005"))
                summary["total_match"] += ok
                entry["total_check"] = {"sum_rows": str(sum(totals)), "printed_total": str(gt), "match": ok}
            entry["supplier_name"] = obj.get("supplier_name")
            entry["n_items"] = len(obj.get("items") or [])
        docs.append(entry)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "docs": docs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
