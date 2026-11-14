"""Per-field paired differences with 95% CI on the synthetic FINAL own test (Fable review 3/4: "SKU / unit price per-field
paired CI table"). Same documents, same strict scorer as score_run, family-cluster bootstrap (2,000, seed 20261113).

Reads the saved FINAL predictions (artifacts/predictions/{m1,m0,b0}_final_*) and the local gold (git-ignored), writes
reports/eval/final_field_ci.{json,md}. Nothing is re-run; FINAL stays a single frozen run.

Usage (.venv, CPU): python scripts/eval/final_field_ci.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.evaluation import parse_for_eval, score_trade_document  # noqa: E402

RUNS = {"M1": "m1_final_v1", "M0": "m0_final_v1", "B0": "b0_final_v12"}
PAIRS = (("M1", "M0"), ("M1", "B0"))
FIELDS = ["sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw",
          "invoice_number_raw", "currency_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw"]
NAMES = {"sku_raw": "품번 (SKU)", "description_raw": "품명", "quantity_raw": "수량", "unit_raw": "단위", "unit_price_raw": "단가",
         "line_total_raw": "행 금액", "invoice_number_raw": "인보이스 번호", "currency_raw": "통화", "subtotal_raw": "소계",
         "tax_raw": "세금", "discount_raw": "할인", "total_raw": "합계"}
ITER, SEED = 2000, 20261113


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def per_document(run: str, rows: list[dict]) -> dict[str, dict[str, tuple[int, int]]]:
    preds = {p["id"]: p for p in _jsonl(REPO / "artifacts" / "predictions" / run / "predictions.jsonl")}
    out = {}
    for r in rows:
        gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{r['doc_id']}.json").read_text(encoding="utf-8"))
        pred = preds.get(r["doc_id"], {"raw_response": None, "generation_status": "missing"})
        out[r["doc_id"]] = score_trade_document(gold, parse_for_eval(pred, "TRADE_RAW"))["fields"]
    return out


def main() -> int:
    rows = [r for r in _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl") if r["split"] == "test"]
    docs = {arm: per_document(run, rows) for arm, run in RUNS.items()}
    families: dict[str, list[str]] = {}
    for r in rows:
        families.setdefault(r["family_id"], []).append(r["doc_id"])
    keys = sorted(families)
    rng = random.Random(SEED)
    samples = [[d for _ in keys for d in families[rng.choice(keys)]] for _ in range(ITER)]

    def acc(arm: str, field: str, ids: list[str]) -> float | None:
        c = sum(docs[arm][i][field][0] for i in ids if field in docs[arm][i])
        n = sum(docs[arm][i][field][1] for i in ids if field in docs[arm][i])
        return c / n if n else None

    all_ids = [r["doc_id"] for r in rows]
    result = {"set": "trade:test (FINAL, 40 documents, unseen layouts T05/T06)", "runs": RUNS, "method":
              f"family-cluster paired bootstrap, {ITER} resamples, seed {SEED}, strict scorer as score_run", "fields": {}}
    lo, hi = int(0.025 * (ITER - 1)), int(0.975 * (ITER - 1))
    for f in FIELDS:
        entry = {arm: {"accuracy": round(acc(arm, f, all_ids), 4),
                       "correct": sum(docs[arm][i][f][0] for i in all_ids), "scored": sum(docs[arm][i][f][1] for i in all_ids)}
                 for arm in RUNS}
        for a, b in PAIRS:
            diffs = sorted(acc(a, f, s) - acc(b, f, s) for s in samples)
            entry[f"{a}-{b}"] = {"diff": round(entry[a]["accuracy"] - entry[b]["accuracy"], 4),
                                 "ci95": [round(diffs[lo], 4), round(diffs[hi], 4)]}
        result["fields"][f] = entry
    out = REPO / "reports" / "eval"
    (out / "final_field_ci.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    def cell(x: dict) -> str:
        sig = x["ci95"][0] > 0 or x["ci95"][1] < 0
        return f"{x['diff']:+.3f} [{x['ci95'][0]:+.3f}, {x['ci95'][1]:+.3f}]" + (" *" if sig else "")
    lines = ["---", "type: report", "title: FINAL 자체 test — 필드별 paired 차이와 95% CI",
             "description: 같은 40문서, 같은 strict 채점기, family 단위 bootstrap. * = CI가 0을 포함하지 않음.",
             "generated: {by: scripts/eval/final_field_ci.py}", "---", "",
             "# FINAL 자체 test — 필드별 paired 차이", "",
             f"방법: {result['method']}. `*` = 95% CI가 0을 포함하지 않음.", "",
             "| 필드 | M1 | M0 | B0 | M1 − M0 | M1 − B0 |", "|---|---:|---:|---:|---|---|"]
    for f in FIELDS:
        e = result["fields"][f]
        lines.append(f"| {NAMES[f]} | {e['M1']['accuracy']:.3f} | {e['M0']['accuracy']:.3f} | {e['B0']['accuracy']:.3f} | "
                     f"{cell(e['M1-M0'])} | {cell(e['M1-B0'])} |")
    (out / "final_field_ci.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines[8:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
