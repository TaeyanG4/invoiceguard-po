"""S5 failure analysis on DEV predictions (docs/06 "오류 개선"): classify real failures, never invent them.

Usage (.venv): python -m invoiceguard.failure_analysis artifacts/predictions/<run> [--max 10]
Writes reports/eval/failures_<run>.md and .json. Documents are taken in a fixed order (id sort), at most N.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .evaluation import parse_for_eval
from .public_data import nfkc_ws

REPO = Path(__file__).resolve().parents[2]
ROW_FIELDS = ("sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw")
DOC_FIELDS = ("invoice_number_raw", "currency_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw")


def _num(text):
    if not isinstance(text, str):
        return None
    t = re.sub(r"[^\d.\-]", "", text)
    try:
        return Decimal(t) if t else None
    except InvalidOperation:
        return None


def classify_field(field: str, gold, pred) -> str:
    if pred is None:
        return "missing_value"
    if not isinstance(pred, str):
        return "wrong_type"
    if field == "sku_raw" and gold.lstrip("0") == pred.lstrip("0") and gold != pred:
        return "sku_leading_zero_loss"
    if field == "description_raw":
        return "description_case_or_space" if nfkc_ws(gold).lower() == nfkc_ws(pred).lower() else "description_text"
    if field in ("quantity_raw", "unit_price_raw", "line_total_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw"):
        g, p = _num(gold), _num(pred)
        if g is not None and p is not None and g == p:
            return "number_format_only"  # same value, different print (e.g. grouping, trailing zeros)
        if gold and not re.fullmatch(r"[\d,.]+", gold.replace(" ", "")):
            return "ambiguous_quantity_text"
        return "number_value"
    if field == "unit_raw":
        return "unit_text"
    return f"{field}_text"


def analyse_trade(gold: dict, parsed) -> list[str]:
    if parsed.status != "ok":
        return [f"output:{parsed.status}"]
    causes = []
    if not parsed.schema_valid:
        causes.append("output:schema_invalid")
    items = parsed.obj.get("items") if isinstance(parsed.obj.get("items"), list) else []
    if len(items) < len(gold["items"]):
        causes.append("rows:missing")
    if len(items) > len(gold["items"]):
        causes.append("rows:excess")
    for g, p in zip(gold["items"], items):
        for f in ROW_FIELDS:
            gv, pv = g.get(f), (p.get(f) if isinstance(p, dict) else None)
            if (gv or None) != (pv.strip() if isinstance(pv, str) else pv):
                causes.append(f"{f}:{classify_field(f, gv, pv)}")
    for f in DOC_FIELDS:
        gv, pv = gold.get(f), parsed.obj.get(f)
        if (gv or None) != (pv.strip() if isinstance(pv, str) else pv):
            causes.append(f"{f}:{classify_field(f, gv, pv) if gv else 'unexpected_value'}")
    return causes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--max", type=int, default=10)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    preds = [json.loads(l) for l in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    failures, cause_counts = [], Counter()
    for p in sorted(preds, key=lambda r: r["id"]):
        if p["task"] != "TRADE_RAW":
            parsed = parse_for_eval(p, p["task"])
            if parsed.status != "ok":
                cause_counts[f"public_output:{parsed.status}"] += 1
            continue
        doc_id = p["id"].partition("__")[0]
        gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{doc_id}.json").read_text(encoding="utf-8"))
        causes = analyse_trade(gold, parse_for_eval(p, "TRADE_RAW"))
        if causes:
            cause_counts.update(c.split(":")[0] + ":" + c.split(":")[1] if c.count(":") else c for c in causes)
            failures.append({"id": p["id"], "causes": causes, "raw_head": (p.get("raw_response") or "")[:240]})
    shown = failures[: args.max]
    out = {"run": run_dir.name, "trade_documents": sum(p["task"] == "TRADE_RAW" for p in preds),
           "trade_documents_with_any_error": len(failures), "cause_counts_all": dict(cause_counts.most_common()),
           "examined": shown, "note": "fixed id order; at most N examined in detail; counts cover every document"}
    report = REPO / "reports" / "eval" / f"failures_{run_dir.name}.json"
    report.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = [f"# Failure analysis — {run_dir.name}", "",
             f"trade documents: {out['trade_documents']}, with any field error: {len(failures)}", "",
             "| cause | count |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in cause_counts.most_common()] + ["", "## Examined (fixed order)"]
    for f in shown:
        lines.append(f"- `{f['id']}`: " + ", ".join(sorted(set(f["causes"]))[:8]))
    (REPO / "reports" / "eval" / f"failures_{run_dir.name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"documents_with_error": len(failures), "top_causes": cause_counts.most_common(8)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
