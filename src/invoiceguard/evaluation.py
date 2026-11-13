"""Evaluator for E1 (PUBLIC_CANONICAL), E2 (TRADE_RAW) and E3 (PO findings).

Rules (docs/06, docs/15):
* Every attempted document stays in the denominator. Generation/JSON failures score every
  gold field as wrong; nothing is dropped to raise accuracy.
* Rows are aligned by reading order (array position); no silent re-ordering.
  Missing rows -> gold fields wrong; extra rows -> excess_rows and document-exact failure.
* Only `visible_exact` public fields are scored; masked fields are counted and reported.
* Quality variants are paired by base; the independent n is the number of bases.
* precision/recall with a zero denominator are null, never 0 or 1.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any, Iterable

from .canonical import parse_canonical_prediction
from .model_output import ParsedOutput, parse_response
from .normalization import parse_money, parse_quantity, parse_unit_price
from .public_data import nfkc_ws
from .public_visibility import SCORED

PUBLIC_FIELDS = ("description", "quantity", "unit_price", "amount")
TRADE_ROW_FIELDS = ("sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw")
TRADE_DOC_FIELDS = ("invoice_number_raw", "currency_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw")
TRADE_NUMERIC = {"quantity_raw": parse_quantity, "unit_price_raw": parse_unit_price, "line_total_raw": parse_money,
                 "subtotal_raw": parse_money, "tax_raw": parse_money, "discount_raw": parse_money, "total_raw": parse_money}


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else round(num / den, 6)


def _pred_items(parsed: ParsedOutput) -> list[dict[str, Any]]:
    if parsed.status != "ok" or parsed.obj is None:
        return []
    items = parsed.obj.get("items")
    return [it if isinstance(it, dict) else {} for it in items] if isinstance(items, list) else []


# --------------------------------------------------------------------------- E1 public canonical
def score_public_document(gold_items: list[dict[str, Any]], visibility: list[dict[str, str]],
                          parsed: ParsedOutput) -> dict[str, Any]:
    preds = _pred_items(parsed)
    fields = {f: [0, 0] for f in PUBLIC_FIELDS}  # [correct, scored]
    masked = Counter()
    casefold = [0, 0]
    row_exact = 0
    for i, gold in enumerate(gold_items):
        pred = preds[i] if i < len(preds) else None
        row_ok = True
        for field in PUBLIC_FIELDS:
            status = visibility[i][field]
            pred_value = pred.get(field) if pred is not None else None
            if field == "description" and status == "case_transformed":
                casefold[1] += 1
                if isinstance(pred_value, str) and gold[field] and nfkc_ws(pred_value).casefold() == nfkc_ws(gold[field]).casefold():
                    casefold[0] += 1
            if status != SCORED:
                masked[f"{field}:{status}"] += 1
                continue
            fields[field][1] += 1
            if pred is None:
                ok = False
            elif field == "description":
                ok = isinstance(pred_value, str) and nfkc_ws(pred_value) == nfkc_ws(gold[field])
            else:
                parsed_value = parse_canonical_prediction(pred_value)
                ok = parsed_value.status == "ok" and parsed_value.value == Decimal(gold[field])
            fields[field][0] += ok
            row_ok &= ok
        row_exact += row_ok
    excess = max(0, len(preds) - len(gold_items))
    scored_total = sum(v[1] for v in fields.values())
    correct_total = sum(v[0] for v in fields.values())
    return {"status": parsed.status, "schema_valid": parsed.schema_valid, "row_index_valid": parsed.row_index_valid,
            "fields": fields, "masked": dict(masked), "casefold_description": casefold,
            "gold_rows": len(gold_items), "pred_rows": len(preds), "excess_rows": excess,
            "missing_rows": max(0, len(gold_items) - len(preds)), "row_exact": row_exact,
            "doc_exact": parsed.status == "ok" and excess == 0 and len(preds) == len(gold_items)
            and correct_total == scored_total}


def aggregate(doc_scores: list[dict[str, Any]], field_names: Iterable[str]) -> dict[str, Any]:
    n = len(doc_scores)
    field_names = list(field_names)
    status = Counter(d["status"] for d in doc_scores)
    out: dict[str, Any] = {
        "attempted": n, "status_counts": dict(status),
        "json_valid_rate": _ratio(sum(d["status"] == "ok" for d in doc_scores), n),
        "schema_valid_rate": _ratio(sum(bool(d["schema_valid"]) for d in doc_scores), n),
        "row_index_valid_rate": _ratio(sum(bool(d["row_index_valid"]) for d in doc_scores), n),
        "doc_exact": _ratio(sum(d["doc_exact"] for d in doc_scores), n),
        "row_exact": _ratio(sum(d["row_exact"] for d in doc_scores), sum(d["gold_rows"] for d in doc_scores)),
        "row_count_match": _ratio(sum(d["pred_rows"] == d["gold_rows"] for d in doc_scores), n),
        "excess_rows": sum(d["excess_rows"] for d in doc_scores),
        "missing_rows": sum(d["missing_rows"] for d in doc_scores),
        "fields": {}, "masked": dict(sum((Counter(d.get("masked", {})) for d in doc_scores), Counter())),
    }
    for field in field_names:
        correct = sum(d["fields"][field][0] for d in doc_scores)
        scored = sum(d["fields"][field][1] for d in doc_scores)
        out["fields"][field] = {"correct": correct, "scored": scored, "accuracy": _ratio(correct, scored)}
    all_c = sum(v["correct"] for v in out["fields"].values())
    all_s = sum(v["scored"] for v in out["fields"].values())
    out["all_scored_fields"] = {"correct": all_c, "scored": all_s, "accuracy": _ratio(all_c, all_s)}
    # metric contract v2 (docs/19 #5): reading accuracy conditional on a strictly parsed JSON object,
    # reported with its own denominator so format failures and reading failures are separable.
    valid = [d for d in doc_scores if d["status"] == "ok"]
    vc = sum(c for d in valid for c, _ in d["fields"].values())
    vs = sum(s for d in valid for _, s in d["fields"].values())
    out["conditional_on_json_parse_ok"] = {"documents": len(valid), "correct": vc, "scored": vs, "accuracy": _ratio(vc, vs),
                                        "fields": {f: {"correct": sum(d["fields"][f][0] for d in valid),
                                                       "scored": sum(d["fields"][f][1] for d in valid),
                                                       "accuracy": _ratio(sum(d["fields"][f][0] for d in valid),
                                                                          sum(d["fields"][f][1] for d in valid))}
                                                   for f in field_names}}
    if any("casefold_description" in d for d in doc_scores):
        c = [sum(d.get("casefold_description", [0, 0])[k] for d in doc_scores) for k in (0, 1)]
        out["secondary_casefold_description_case_transformed"] = {"correct": c[0], "scored": c[1], "accuracy": _ratio(*c)}
    return out


def cluster_bootstrap(doc_scores: list[dict[str, Any]], cluster_of: list[str], field: str | None = None,
                      iterations: int = 2000, seed: int = 20261113) -> dict[str, Any]:
    """95% percentile CI of field accuracy, resampling bases/families (not images)."""
    clusters: dict[str, list[int]] = defaultdict(list)
    for index, cid in enumerate(cluster_of):
        clusters[cid].append(index)
    keys = sorted(clusters)
    if not keys:
        return {"n_clusters": 0, "ci95": None}

    def acc(indices: list[int]) -> float | None:
        c = s = 0
        for i in indices:
            for f, (cc, ss) in doc_scores[i]["fields"].items():
                if field is None or f == field:
                    c, s = c + cc, s + ss
        return None if s == 0 else c / s

    rng = random.Random(seed)
    values = []
    for _ in range(iterations):
        sample = [i for _ in keys for i in clusters[rng.choice(keys)]]
        value = acc(sample)
        if value is not None:
            values.append(value)
    values.sort()
    if not values:
        return {"n_clusters": len(keys), "ci95": None}
    lo, hi = values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]
    return {"n_clusters": len(keys), "iterations": iterations, "ci95": [round(lo, 4), round(hi, 4)]}


# --------------------------------------------------------------------------- E2 trade raw
def _numeric_equal(field: str, gold: str | None, pred: Any) -> bool | None:
    """None when the gold value is not a supported number (e.g. '2 cartons / 100 pcs')."""
    fn = TRADE_NUMERIC.get(field)
    if fn is None:
        return None
    g = fn(gold)
    if not g.ok:
        return None
    p = fn(pred) if isinstance(pred, str) else None
    return bool(p and p.ok and p.decimal == g.decimal)


def score_trade_document(gold: dict[str, Any], parsed: ParsedOutput) -> dict[str, Any]:
    preds = _pred_items(parsed)
    obj = parsed.obj if parsed.status == "ok" and parsed.obj else {}
    raw_fields = {f: [0, 0] for f in TRADE_ROW_FIELDS + TRADE_DOC_FIELDS}
    num_fields = {f: [0, 0] for f in TRADE_NUMERIC}
    row_exact = 0
    for i, g in enumerate(gold["items"]):
        p = preds[i] if i < len(preds) else None
        row_ok = True
        for field in TRADE_ROW_FIELDS:
            gv = g.get(field)
            pv = p.get(field) if p is not None else None
            if field == "description_raw":
                ok = isinstance(pv, str) and gv is not None and nfkc_ws(pv) == nfkc_ws(gv)
            else:
                ok = isinstance(pv, str) and gv is not None and pv.strip() == gv.strip()
            if gv is None:  # renderer did not print a value: correct only if model returns null
                ok = p is not None and pv is None
            raw_fields[field][0] += ok
            raw_fields[field][1] += 1
            row_ok &= ok
            num = _numeric_equal(field, gv, pv)
            if num is not None:
                num_fields[field][0] += num
                num_fields[field][1] += 1
        row_exact += row_ok
    for field in TRADE_DOC_FIELDS:
        gv, pv = gold.get(field), obj.get(field)
        ok = parsed.status == "ok" and ((pv is None) if gv is None else (isinstance(pv, str) and pv.strip() == gv.strip()))
        raw_fields[field][0] += ok
        raw_fields[field][1] += 1
        num = _numeric_equal(field, gv, pv)
        if num is not None:
            num_fields[field][0] += num
            num_fields[field][1] += 1
    excess = max(0, len(preds) - len(gold["items"]))
    all_ok = all(c == s for c, s in raw_fields.values())
    return {"status": parsed.status, "schema_valid": parsed.schema_valid, "row_index_valid": parsed.row_index_valid,
            "fields": raw_fields, "numeric_fields": num_fields, "gold_rows": len(gold["items"]),
            "pred_rows": len(preds), "excess_rows": excess, "missing_rows": max(0, len(gold["items"]) - len(preds)),
            "row_exact": row_exact, "doc_exact": parsed.status == "ok" and excess == 0 and all_ok}


def aggregate_trade(doc_scores: list[dict[str, Any]]) -> dict[str, Any]:
    out = aggregate(doc_scores, TRADE_ROW_FIELDS + TRADE_DOC_FIELDS)
    out["numeric_value_em"] = {}
    for field in TRADE_NUMERIC:
        c = sum(d["numeric_fields"][field][0] for d in doc_scores)
        s = sum(d["numeric_fields"][field][1] for d in doc_scores)
        out["numeric_value_em"][field] = {"correct": c, "scored": s, "accuracy": _ratio(c, s)}
    return out


# --------------------------------------------------------------------------- E3 findings
def finding_keys(result: dict[str, Any] | None, invoice: dict[str, Any] | None) -> Counter:
    """(code, anchor) multiset. Row findings are anchored by the row's SKU text, not row_index,
    so a dropped row does not shift every later finding."""
    keys: Counter = Counter()
    if result is None:
        return keys
    rows = {it.get("row_index"): it for it in (invoice or {}).get("items") or [] if isinstance(it, dict)}
    for f in result["findings"]:
        if f["code"] == "PO_LINE_NOT_FOUND":
            anchor = f["expected"]
        elif f["row_index"] is not None:
            anchor = (rows.get(f["row_index"]) or {}).get("sku_raw")
            anchor = anchor.strip() if isinstance(anchor, str) else f"row{f['row_index']}"
        else:
            anchor = f["field"]
        keys[(f["code"], anchor)] += 1
    return keys


def score_findings(expected: list[Counter], predicted: list[Counter], codes: Iterable[str],
                   predicted_status: list[str], actual_has_diff: list[bool],
                   extraction_error: list[bool]) -> dict[str, Any]:
    """Per-code TP/FP/FN over documents plus review-rate statistics (docs/06 PO metrics)."""
    per_code = {}
    for code in codes:
        tp = fp = fn = 0
        for exp, pred in zip(expected, predicted):
            e = Counter({k: v for k, v in exp.items() if k[0] == code})
            p = Counter({k: v for k, v in pred.items() if k[0] == code})
            inter = sum((e & p).values())
            tp, fp, fn = tp + inter, fp + sum(p.values()) - inter, fn + sum(e.values()) - inter
        per_code[code] = {"tp": tp, "fp": fp, "fn": fn, "support": tp + fn,
                          "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn)}
    n = len(predicted_status)
    candidates = [i for i, s in enumerate(predicted_status) if s == "matched_candidate"]
    return {"documents": n, "per_code": per_code,
            "review_rate": _ratio(sum(s == "needs_review" for s in predicted_status), n),
            "failed_rate": _ratio(sum(s == "failed" for s in predicted_status), n),
            "matched_candidate_rate": _ratio(len(candidates), n),
            "candidates_with_actual_transaction_diff": _ratio(sum(actual_has_diff[i] for i in candidates), len(candidates)),
            "candidates_with_extraction_error": _ratio(sum(extraction_error[i] for i in candidates), len(candidates))}


def parse_for_eval(record: dict[str, Any], task: str, lenient: bool = False) -> ParsedOutput:
    return parse_response(record.get("raw_response"), task, record.get("generation_status", "ok"),
                          record.get("finish_reason"), lenient=lenient)


def strict_and_lenient(score_fn, items: list[tuple[Any, dict[str, Any]]], task: str, aggregate_fn) -> dict[str, Any]:
    """Score the same predictions twice: strict (primary) and lenient fence-strip (secondary, labelled).

    items: [(gold_args, prediction_record)], where score_fn(*gold_args, parsed) -> doc score.
    The lenient path never repairs truncation or JSON syntax; it only removes one ```json fence.
    """
    out = {}
    for mode, lenient in (("strict", False), ("lenient_fence_strip", True)):
        docs = [score_fn(*gold, parse_for_eval(pred, task, lenient=lenient)) for gold, pred in items]
        out[mode] = aggregate_fn(docs)
        if lenient:
            out[mode]["repaired_documents"] = sum(
                parse_for_eval(pred, task, lenient=True).repair is not None for _, pred in items)
    out["note"] = "strict is the primary metric; lenient only strips a single ```json fence and is reported separately."
    return out
