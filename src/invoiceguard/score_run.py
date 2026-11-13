"""Score a saved prediction run with the frozen metric contract, PER SET (never pooled across sets).

Usage (.venv): python -m invoiceguard.score_run artifacts/predictions/<run_id> [--allow-final]

* Expected documents are rebuilt from the run's `sets`; a missing prediction is scored as a failure
  (generation_status=missing) and duplicates abort scoring, so denominators can never shrink silently.
* Sets: public:<role>|<quality>, trade:<split>, stress:<variant>. Headline metrics, bootstrap intervals and
  E3 findings are computed per set (clean dev, each stress variant, iid, ood, test separately).
* Final sets require --allow-final and a matching frozen config (configs/frozen_v1.json + appendix).
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .evaluation import (
    PUBLIC_FIELDS, aggregate, aggregate_trade, cluster_bootstrap, finding_keys,
    parse_for_eval, score_findings, score_public_document, score_trade_document, strict_and_lenient,
)
from .public_data import canonical_items, dataset_root
from .reconciliation import BLOCKER_CODES, WARNING_CODES, reconcile

REPO = Path(__file__).resolve().parents[1].parent
FINDING_CODES = sorted(BLOCKER_CODES | WARNING_CODES)
FINAL_SETS = {"public:iid_final", "public:ood_final", "trade:test"}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _public_gold() -> dict[str, list[dict]]:
    raw = json.loads((dataset_root(REPO) / "ground_truth_released.json").read_text(encoding="utf-8"),
                     parse_float=Decimal, parse_int=Decimal)
    return {r["file_name"]: canonical_items(r) for r in raw}


def expected_ids(sets: list[str]) -> list[tuple[str, str]]:
    """(record_id, set_spec) for every document a run over `sets` must contain."""
    pub = _jsonl(REPO / "manifests" / "public_canonical_v1.jsonl")
    trade = _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl")
    out = []
    for spec in sets:
        kind, name = spec.split(":", 1)
        if kind == "public":
            out += [(f'{r["base_id"][:-4]}__{r["quality"]}', spec) for r in pub if r["standard_role"] == name]
        elif kind == "trade":
            out += [(r["doc_id"], spec) for r in trade if r["split"] == name]
        elif kind == "stress":
            out += [(r["id"], spec) for r in _jsonl(REPO / "manifests" / "stress_v1.jsonl") if name in ("all", r["variant"])]
    return out


def set_label(record_id: str, spec: str, pub_manifest: dict | None = None) -> str:
    if spec.startswith("public:"):
        return f'{spec}|{record_id.rpartition("__")[2]}'
    if spec.startswith("stress:"):
        return f'stress:{record_id.partition("__")[2]}'
    return spec


def score(run_dir: Path, allow_final: bool = False) -> dict:
    meta = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    sets = meta.get("sets") or []
    if FINAL_SETS & set(sets):
        from .freeze import verify_final_ready

        problems = verify_final_ready(meta)
        if problems or not allow_final:
            raise SystemExit(f"final sets need --allow-final and a matching freeze: {problems}")
    seen: dict[str, dict] = {}
    for p in _jsonl(run_dir / "predictions.jsonl"):
        if p["id"] in seen:
            raise SystemExit(f"duplicate prediction id {p['id']} — refusing to score")
        seen[p["id"]] = p
    expected = expected_ids(sets)
    expected_set = {i for i, _ in expected}
    missing = [i for i, _ in expected if i not in seen]
    pub_manifest = {(r["base_id"], r["quality"]): r for r in _jsonl(REPO / "manifests" / "public_canonical_v1.jsonl")}
    trade_manifest = {r["doc_id"]: r for r in _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl")}
    report: dict = {"run_id": meta.get("run_id"), "arm": meta.get("arm") or meta.get("fingerprint", {}).get("arm"),
                    "run_metadata": {k: meta.get(k) for k in ("sets", "fingerprint", "psm", "b0_version", "adapter",
                                                              "wall_seconds", "engine")},
                    "contract": "metric contract v2 (reports/eval/metric_contract_v2.md); strict primary; per set",
                    "denominator_check": {"expected": len(expected), "predicted": len(seen), "missing": len(missing),
                                          "unexpected_extra_ids": sorted(set(seen) - expected_set)[:20]},
                    "sets": {}}
    by_set: dict[str, list] = defaultdict(list)
    for record_id, spec in expected:
        task = "PUBLIC_CANONICAL" if spec.startswith("public:") else "TRADE_RAW"
        p = seen.get(record_id) or {"id": record_id, "task": task, "generation_status": "missing", "raw_response": None}
        by_set[set_label(record_id, spec)].append(p)

    public_gold = None
    for label, items in sorted(by_set.items()):
        if label.startswith("public:"):
            public_gold = public_gold or _public_gold()
            entries, clusters, templates = [], [], defaultdict(list)
            for p in items:
                base, _, quality = p["id"].rpartition("__")
                row = pub_manifest[(base + ".png", quality)]
                gold = [{k: v for k, v in it.items() if k != "field_status"} for it in public_gold[base + ".png"]]
                entries.append(((gold, row["visibility"]), p))
                clusters.append(base)
                templates[row["template"]].append(((gold, row["visibility"]), p))
            agg = lambda docs: aggregate(docs, PUBLIC_FIELDS)  # noqa: E731
            res = strict_and_lenient(score_public_document, entries, "PUBLIC_CANONICAL", agg)
            docs = [score_public_document(*g, parse_for_eval(p, "PUBLIC_CANONICAL")) for g, p in entries]
            res["bootstrap_all_fields_by_base"] = cluster_bootstrap(docs, clusters)
            res["n_bases"] = len(set(clusters))
            res["by_template_strict"] = {
                t: {k: v[k] for k in ("attempted", "all_scored_fields", "doc_exact")}
                for t, v in ((t, agg([score_public_document(*g, parse_for_eval(p, "PUBLIC_CANONICAL")) for g, p in e]))
                             for t, e in sorted(templates.items()))}
            report["sets"][label] = {"task": "E1_public", **res}
            continue
        entries, rows = [], []
        for p in items:
            doc_id = p["id"].partition("__")[0]
            gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{doc_id}.json").read_text(encoding="utf-8"))
            entries.append(((gold,), p))
            rows.append(trade_manifest[doc_id])
        res = strict_and_lenient(score_trade_document, entries, "TRADE_RAW", aggregate_trade)
        docs = [score_trade_document(*g, parse_for_eval(p, "TRADE_RAW")) for g, p in entries]
        res["bootstrap_all_fields_by_family"] = cluster_bootstrap(docs, [r["family_id"] for r in rows])
        res["n_families"] = len({r["family_id"] for r in rows})
        expected_k, predicted_k, status, actual_diff, extraction_error = [], [], [], [], []
        for ((gold,), p), row in zip(entries, rows):
            po = json.loads((REPO / "data" / "processed" / "trade" / "po" / f"{row['doc_id']}.json").read_text(encoding="utf-8"))
            expected_k.append(finding_keys(reconcile(gold, po, "oracle_fixture"), gold))
            parsed = parse_for_eval(p, "TRADE_RAW")
            if parsed.status == "ok" and parsed.schema_valid and parsed.row_index_valid:
                result = reconcile(parsed.obj, po, "live_model")
                predicted_k.append(finding_keys(result, parsed.obj))
                status.append(result["case_status"])
                sd = score_trade_document(gold, parsed)
                extraction_error.append(any(c < s for c, s in sd["fields"].values()))
            else:
                predicted_k.append(finding_keys(None, None))
                status.append("failed")
                extraction_error.append(True)
            actual_diff.append(bool(row["transaction_diff"]))
        e3 = score_findings(expected_k, predicted_k, FINDING_CODES, status, actual_diff, extraction_error)
        e3["per_code"] = {k: v for k, v in e3["per_code"].items() if v["support"] or v["fp"]}
        res["E3_findings"] = e3
        report["sets"][label] = {"task": "E2_trade", **res}
    return report


def headline(report: dict) -> dict:
    out = {}
    for label, res in report["sets"].items():
        s = res["strict"]
        out[label] = {"n": s["attempted"], "json_valid": s["json_valid_rate"], "schema_valid": s["schema_valid_rate"],
                      "fields_acc": s["all_scored_fields"]["accuracy"], "doc_exact": s["doc_exact"],
                      "cond_json_ok_acc": s["conditional_on_json_parse_ok"]["accuracy"],
                      "lenient_fields_acc": res["lenient_fence_strip"]["all_scored_fields"]["accuracy"],
                      "ci95": (res.get("bootstrap_all_fields_by_base") or res.get("bootstrap_all_fields_by_family") or {}).get("ci95")}
        if "E3_findings" in res:
            out[label]["E3_review_rate"] = res["E3_findings"]["review_rate"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--allow-final", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    report = score(run_dir, args.allow_final)
    report["headline"] = headline(report)
    out = REPO / "reports" / "eval" / f"{run_dir.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run": run_dir.name, "denominator_check": report["denominator_check"], "headline": report["headline"]},
                     indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
