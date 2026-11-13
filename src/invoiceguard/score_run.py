"""Score a saved prediction run (raw responses first, scoring second) with the frozen metric contract.

Usage (.venv): python -m invoiceguard.score_run artifacts/predictions/<run_id> [--label dev]
Writes reports/eval/<run_id>.json. Works for B0, M0 and M1 identically (same gold, same denominators).
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .evaluation import (
    PUBLIC_FIELDS, TRADE_DOC_FIELDS, TRADE_ROW_FIELDS, aggregate, aggregate_trade, cluster_bootstrap, finding_keys,
    parse_for_eval, score_findings, score_public_document, score_trade_document, strict_and_lenient,
)
from .public_data import canonical_items, dataset_root
from .reconciliation import WARNING_CODES, BLOCKER_CODES, reconcile

REPO = Path(__file__).resolve().parents[1].parent
FINDING_CODES = sorted(BLOCKER_CODES | WARNING_CODES)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _public_gold() -> dict[str, list[dict]]:
    raw = json.loads((dataset_root(REPO) / "ground_truth_released.json").read_text(encoding="utf-8"),
                     parse_float=Decimal, parse_int=Decimal)
    return {r["file_name"]: canonical_items(r) for r in raw}


def score(run_dir: Path) -> dict:
    preds = _jsonl(run_dir / "predictions.jsonl")
    meta = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    pub_manifest = {(r["base_id"], r["quality"]): r for r in _jsonl(REPO / "manifests" / "public_canonical_v1.jsonl")}
    trade_manifest = {r["doc_id"]: r for r in _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl")}
    report: dict = {"run_id": meta.get("run_id"), "arm": meta.get("arm") or meta.get("fingerprint", {}).get("arm"),
                    "run_metadata": {k: meta.get(k) for k in ("sets", "fingerprint", "psm", "b0_version", "adapter",
                                                              "wall_seconds", "engine")},
                    "contract": "metric contract v2 (reports/eval/metric_contract_v2.md); strict primary"}

    pub_items, pub_groups = [], defaultdict(list)
    trade_items, trade_groups = [], defaultdict(list)
    public_gold = None
    for p in preds:
        if p["task"] == "PUBLIC_CANONICAL":
            public_gold = public_gold or _public_gold()
            base, _, quality = p["id"].rpartition("__")
            row = pub_manifest[(base + ".png", quality)]
            gold_items = [{k: v for k, v in it.items() if k != "field_status"} for it in public_gold[base + ".png"]]
            entry = ((gold_items, row["visibility"]), p)
            pub_items.append(entry)
            pub_groups[f'{row["standard_role"]}|{quality}'].append(entry)
            pub_groups[f'template:{row["template"]}'].append(entry)
        else:
            doc_id, _, variant = p["id"].partition("__")  # dev stress ids: <doc_id>__<variant>
            row = dict(trade_manifest[doc_id], _doc_id=doc_id)
            gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{doc_id}.json").read_text(encoding="utf-8"))
            entry = ((gold,), p)
            trade_items.append((entry, row))
            trade_groups[f'{row["split"]}|{row["template"]}' + (f"|stress:{variant}" if variant else "")].append(entry)

    if pub_items:
        agg = lambda docs: aggregate(docs, PUBLIC_FIELDS)  # noqa: E731
        report["E1_public"] = strict_and_lenient(score_public_document, pub_items, "PUBLIC_CANONICAL", agg)
        strict_docs = [score_public_document(*g, parse_for_eval(p, "PUBLIC_CANONICAL")) for g, p in pub_items]
        report["E1_public"]["bootstrap_all_fields_by_base"] = cluster_bootstrap(
            strict_docs, [p["id"].rpartition("__")[0] for _, p in pub_items])
        report["E1_public"]["n_bases"] = len({p["id"].rpartition("__")[0] for _, p in pub_items})
        report["E1_public"]["by_group_strict"] = {
            k: {kk: v[kk] for kk in ("attempted", "json_valid_rate", "all_scored_fields", "doc_exact", "masked")}
            for k, v in ((k, agg([score_public_document(*g, parse_for_eval(p, "PUBLIC_CANONICAL")) for g, p in items]))
                         for k, items in sorted(pub_groups.items()))}

    if trade_items:
        entries = [e for e, _ in trade_items]
        report["E2_trade"] = strict_and_lenient(score_trade_document, entries, "TRADE_RAW", aggregate_trade)
        strict_docs = [score_trade_document(*g, parse_for_eval(p, "TRADE_RAW")) for g, p in entries]
        report["E2_trade"]["bootstrap_all_fields_by_family"] = cluster_bootstrap(strict_docs, [r["family_id"] for _, r in trade_items])
        report["E2_trade"]["by_group_strict"] = {
            k: {kk: v[kk] for kk in ("attempted", "json_valid_rate", "all_scored_fields", "doc_exact")}
            for k, v in ((k, aggregate_trade([score_trade_document(*g, parse_for_eval(p, "TRADE_RAW")) for g, p in items]))
                         for k, items in sorted(trade_groups.items()))}
        # E3: live findings from the model's own extraction vs the oracle findings for the gold invoice
        expected, predicted, status, actual_diff, extraction_error = [], [], [], [], []
        for ((gold,), p), row in trade_items:
            po = json.loads((REPO / "data" / "processed" / "trade" / "po" / f"{row['_doc_id']}.json").read_text(encoding="utf-8"))
            expected.append(finding_keys(reconcile(gold, po, "oracle_fixture"), gold))
            parsed = parse_for_eval(p, "TRADE_RAW")
            if parsed.status == "ok" and parsed.schema_valid and parsed.row_index_valid:
                result = reconcile(parsed.obj, po, "live_model")
                predicted.append(finding_keys(result, parsed.obj))
                status.append(result["case_status"])
                err = any(score_trade_document(gold, parsed)["fields"][f][0] < score_trade_document(gold, parsed)["fields"][f][1]
                          for f in TRADE_ROW_FIELDS + TRADE_DOC_FIELDS)
            else:
                predicted.append(finding_keys(None, None))
                status.append("failed")
                err = True
            actual_diff.append(bool(row["transaction_diff"]))
            extraction_error.append(err)
        report["E3_findings"] = score_findings(expected, predicted, FINDING_CODES, status, actual_diff, extraction_error)
        report["E3_findings"]["per_code"] = {k: v for k, v in report["E3_findings"]["per_code"].items() if v["support"] or v["fp"]}
        report["E3_findings"]["note"] = "live findings from the arm's own extraction; oracle findings from gold. n per code is small."
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    report = score(run_dir)
    out = REPO / "reports" / "eval" / f"{run_dir.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    summary = {"run": run_dir.name}
    for key in ("E1_public", "E2_trade"):
        if key in report:
            s = report[key]["strict"]
            summary[key] = {"attempted": s["attempted"], "json_valid": s["json_valid_rate"],
                            "fields_acc": s["all_scored_fields"]["accuracy"], "doc_exact": s["doc_exact"],
                            "cond_valid_acc": s["conditional_on_valid_json"]["accuracy"],
                            "lenient_fields_acc": report[key]["lenient_fence_strip"]["all_scored_fields"]["accuracy"]}
    if "E3_findings" in report:
        e3 = report["E3_findings"]
        summary["E3"] = {"review_rate": e3["review_rate"], "failed_rate": e3["failed_rate"],
                         "recall": {k: v["recall"] for k, v in e3["per_code"].items() if v["support"]}}
    print(json.dumps(summary, indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
