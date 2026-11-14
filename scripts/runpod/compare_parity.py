"""Compare Pod HF-path predictions with the local ones on the same own-dev documents (dev only).

Usage (repo root, local .venv):  python scripts/runpod/compare_parity.py
Reads artifacts/predictions/{m1_dev_v1 (local, adapter m1_standard_v1), pod_m1v1_dev8, pod_m1pod_dev8}.
Reports, per document: raw-response identity with the local run and strict field accuracy (same scorer as
the dev/final evaluation). Field accuracy keeps failed/unparsed documents in the denominator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.evaluation import parse_for_eval, score_trade_document  # noqa: E402

PRED = REPO / "artifacts" / "predictions"


def load(run: str) -> dict:
    rows = [json.loads(line) for line in (PRED / run / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["id"]: r for r in rows}


def fields(row: dict, gold: dict) -> tuple[int, int]:
    scored = score_trade_document(gold, parse_for_eval(row, "TRADE_RAW"))
    return sum(c for c, _ in scored["fields"].values()), sum(s for _, s in scored["fields"].values())


def main() -> int:
    local, pod_v1, pod_new = load("m1_dev_v1"), load("pod_m1v1_dev8"), load("pod_m1pod_dev8")
    ids = list(pod_v1)
    rows, tot = [], {"local_v1": [0, 0], "pod_v1": [0, 0], "pod_trained": [0, 0]}
    for doc in ids:
        gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{doc}.json").read_text(encoding="utf-8"))
        entry = {"id": doc}
        for key, run in (("local_v1", local), ("pod_v1", pod_v1), ("pod_trained", pod_new)):
            c, s = fields(run[doc], gold)
            tot[key][0] += c
            tot[key][1] += s
            entry[key] = [c, s]
        entry["pod_v1_raw_identical_to_local_v1"] = (pod_v1[doc].get("raw_response") or "").strip() == (local[doc].get("raw_response") or "").strip()
        entry["pod_trained_raw_identical_to_local_v1"] = (pod_new[doc].get("raw_response") or "").strip() == (local[doc].get("raw_response") or "").strip()
        rows.append(entry)
    result = {"documents": ids, "set": "trade:dev (first 8 by manifest order)", "path": "HF NF4 reference path, batch 1, greedy",
              "field_accuracy": {k: {"correct": v[0], "scored": v[1], "acc": round(v[0] / v[1], 4)} for k, v in tot.items()},
              "raw_identical_rate": {
                  "pod_v1_vs_local_v1": round(sum(r["pod_v1_raw_identical_to_local_v1"] for r in rows) / len(rows), 4),
                  "pod_trained_vs_local_v1": round(sum(r["pod_trained_raw_identical_to_local_v1"] for r in rows) / len(rows), 4)},
              "rows": rows}
    out = REPO / "reports" / "runpod" / "parity_dev8.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
