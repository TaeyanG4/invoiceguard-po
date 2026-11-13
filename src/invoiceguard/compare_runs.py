"""Paired comparison of two scored arms on IDENTICAL documents (e.g. M1 vs M0, M1 vs B0).

Usage (.venv): python -m invoiceguard.compare_runs <runA> <runB>   (run ids under artifacts/predictions)
Asserts both runs cover exactly the same record ids per set, then reports the difference A-B of strict field
accuracy and document exact match with a cluster-paired bootstrap (clusters = public base / trade family).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .evaluation import parse_for_eval, score_public_document, score_trade_document
from .score_run import REPO, _jsonl, _public_gold, expected_ids, set_label

SEED = 20261113


def _doc_scores(run: str) -> tuple[dict, dict]:
    run_dir = REPO / "artifacts" / "predictions" / run
    meta = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    preds = {p["id"]: p for p in _jsonl(run_dir / "predictions.jsonl")}
    pub_manifest = {(r["base_id"], r["quality"]): r for r in _jsonl(REPO / "manifests" / "public_canonical_v1.jsonl")}
    trade_manifest = {r["doc_id"]: r for r in _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl")}
    gold_pub = None
    scores, labels = {}, {}
    for rid, spec in expected_ids(meta.get("sets") or []):
        p = preds.get(rid) or {"id": rid, "generation_status": "missing", "raw_response": None}
        label = set_label(rid, spec, pub_manifest)
        if spec.startswith("public:"):
            gold_pub = gold_pub or _public_gold()
            base, _, quality = rid.rpartition("__")
            gold = [{k: v for k, v in it.items() if k != "field_status"} for it in gold_pub[base + ".png"]]
            s = score_public_document(gold, pub_manifest[(base + ".png", quality)]["visibility"], parse_for_eval(p, "PUBLIC_CANONICAL"))
            cluster = base
        else:
            doc_id = rid.partition("__")[0]
            gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{doc_id}.json").read_text(encoding="utf-8"))
            s = score_trade_document(gold, parse_for_eval(p, "TRADE_RAW"))
            cluster = trade_manifest[doc_id]["family_id"]
        scores[rid] = (sum(c for c, _ in s["fields"].values()), sum(n for _, n in s["fields"].values()), int(s["doc_exact"]), cluster)
        labels[rid] = label
    return scores, labels


def paired(a: dict, b: dict, ids: list[str], iterations: int = 2000) -> dict:
    clusters: dict[str, list[str]] = {}
    for i in ids:
        clusters.setdefault(a[i][3], []).append(i)
    keys = sorted(clusters)

    def stats(sample):
        ca = sum(a[i][0] for i in sample); na = sum(a[i][1] for i in sample)
        cb = sum(b[i][0] for i in sample); nb = sum(b[i][1] for i in sample)
        fa, fb = (ca / na if na else 0.0), (cb / nb if nb else 0.0)
        da = sum(a[i][2] for i in sample) / len(sample); db = sum(b[i][2] for i in sample) / len(sample)
        return fa - fb, da - db

    point = stats(ids)
    rng = random.Random(SEED)
    fd, dd = [], []
    for _ in range(iterations):
        sample = [i for _ in keys for i in clusters[rng.choice(keys)]]
        f, d = stats(sample)
        fd.append(f); dd.append(d)
    fd.sort(); dd.sort()
    lo, hi = int(0.025 * (iterations - 1)), int(0.975 * (iterations - 1))
    return {"n_docs": len(ids), "n_clusters": len(keys),
            "field_acc_diff": round(point[0], 4), "field_acc_diff_ci95": [round(fd[lo], 4), round(fd[hi], 4)],
            "doc_exact_diff": round(point[1], 4), "doc_exact_diff_ci95": [round(dd[lo], 4), round(dd[hi], 4)]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    args = parser.parse_args()
    a, la = _doc_scores(args.run_a)
    b, lb = _doc_scores(args.run_b)
    if set(a) != set(b) or la != lb:
        raise SystemExit(f"runs do not cover identical documents/sets: only_a={len(set(a) - set(b))} only_b={len(set(b) - set(a))}")
    out = {"a": args.run_a, "b": args.run_b, "method": "cluster-paired bootstrap (2000, seed 20261113), A minus B, strict",
           "sets": {}}
    for label in sorted(set(la.values())):
        ids = sorted(i for i in la if la[i] == label)
        out["sets"][label] = paired(a, b, ids)
    path = REPO / "reports" / "eval" / f"compare_{args.run_a}__vs__{args.run_b}.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
