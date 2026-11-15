"""Score the Korean-English mixed layout T07 stress set (docs/20 amendment 6, pre-registered before the runs).

Three arms on the same 30 documents, same TRADE_RAW prompt, NF4, batch 1: M0 (t07_m0_nf4), M1 v1 (t07_m1v1_nf4,
the frozen synthetic adapter) and M1-cord (t07_m1cord_nf4). Same strict scorer as score_run (score_trade_document);
lenient (one ```json fence stripped) reported beside it. Paired bootstrap over documents (2,000, seed 20261113).
Also: reconciliation codes equal to the oracle's per document, and the item-name field (Korean + English) on its own.
T07 is never trained on and never used to choose settings.

Usage (.venv, CPU): python scripts/eval/t07_stress.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.evaluation import parse_for_eval, score_trade_document  # noqa: E402
from invoiceguard.reconciliation import reconcile  # noqa: E402

RUNS = {"M0": "t07_m0_nf4", "M1 v1": "t07_m1v1_nf4", "M1-cord": "t07_m1cord_nf4"}
PAIRS = (("M1 v1", "M0"), ("M1-cord", "M0"), ("M1-cord", "M1 v1"))
FIELDS = ["sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw",
          "invoice_number_raw", "currency_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw"]
NAMES = {"sku_raw": "품번", "description_raw": "품명 (한·영)", "quantity_raw": "수량", "unit_raw": "단위", "unit_price_raw": "단가",
         "line_total_raw": "행 금액", "invoice_number_raw": "인보이스 번호", "currency_raw": "통화", "subtotal_raw": "소계",
         "tax_raw": "세금", "discount_raw": "할인", "total_raw": "합계"}
ITER, SEED = 2000, 20261113


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def codes(result: dict | None) -> list[str]:
    return sorted(f["code"] for f in result["findings"]) if result else ["<no valid extraction>"]


def main() -> int:
    rows = _jsonl(REPO / "manifests" / "trade_raw_t07.jsonl")
    docs: dict[str, dict[str, dict]] = {}
    for arm, run in RUNS.items():
        path = REPO / "artifacts" / "predictions" / run / "predictions.jsonl"
        if not path.exists():
            raise SystemExit(f"{run} has not run yet")
        preds = {p["id"]: p for p in _jsonl(path)}
        docs[arm] = {}
        for r in rows:
            gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{r['doc_id']}.json").read_text(encoding="utf-8"))
            po = json.loads((REPO / "data" / "processed" / "trade" / "po" / f"{r['doc_id']}.json").read_text(encoding="utf-8"))
            p = preds.get(r["doc_id"], {"raw_response": None, "generation_status": "missing"})
            strict, lenient = parse_for_eval(p, "TRADE_RAW"), parse_for_eval(p, "TRADE_RAW", lenient=True)
            ok = lenient.status == "ok" and lenient.schema_valid and lenient.row_index_valid
            docs[arm][r["doc_id"]] = {
                "strict": score_trade_document(gold, strict)["fields"], "lenient": score_trade_document(gold, lenient)["fields"],
                "json_strict": strict.status == "ok",
                "codes_match": codes(reconcile(lenient.obj, po, "live_model") if ok else None) == codes(reconcile(gold, po, "oracle_fixture"))}
    ids = [r["doc_id"] for r in rows]

    def acc(arm: str, mode: str, sample: list[str], fields=FIELDS) -> float:
        c = sum(docs[arm][i][mode][f][0] for i in sample for f in fields if f in docs[arm][i][mode])
        n = sum(docs[arm][i][mode][f][1] for i in sample for f in fields if f in docs[arm][i][mode])
        return c / n if n else float("nan")

    rng = random.Random(SEED)
    samples = [[rng.choice(ids) for _ in ids] for _ in range(ITER)]
    lo, hi = int(0.025 * (ITER - 1)), int(0.975 * (ITER - 1))
    result = {"set": "trade:t07 (30 Korean-English mixed invoices, layout T07, dev-only stress set)", "runs": RUNS,
              "method": f"strict scorer as score_run; lenient = one fence stripped; paired document bootstrap {ITER}, seed {SEED}",
              "arms": {}, "pairs": {}, "fields": {}}
    for arm in RUNS:
        result["arms"][arm] = {"strict": round(acc(arm, "strict", ids), 4), "lenient": round(acc(arm, "lenient", ids), 4),
                               "json_strict_rate": round(sum(docs[arm][i]["json_strict"] for i in ids) / len(ids), 4),
                               "reconciliation_codes_match": sum(docs[arm][i]["codes_match"] for i in ids),
                               "documents": len(ids)}
    for a, b in PAIRS:
        for mode in ("strict", "lenient"):
            diffs = sorted(acc(a, mode, s) - acc(b, mode, s) for s in samples)
            result["pairs"][f"{a} - {b} ({mode})"] = {"diff": round(acc(a, mode, ids) - acc(b, mode, ids), 4),
                                                       "ci95": [round(diffs[lo], 4), round(diffs[hi], 4)]}
    for f in FIELDS:
        result["fields"][f] = {arm: {mode: round(acc(arm, mode, ids, [f]), 4) for mode in ("strict", "lenient")} for arm in RUNS}
    out = REPO / "reports" / "eval"
    (out / "t07_stress.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    def sig(x):
        return " *" if x["ci95"][0] > 0 or x["ci95"][1] < 0 else ""
    lines = ["---", "type: report", "title: 한영 혼합 레이아웃 T07 stress set — M0 · M1 v1 · M1-cord",
             "description: 학습에 없던 한국어+영어 인보이스 30장(dev 전용, docs/20 수정 6). 같은 strict 채점기, 문서 단위 paired bootstrap.",
             "generated: {by: scripts/eval/t07_stress.py}", "---", "", "# 한영 혼합 레이아웃 T07", "",
             f"방법: {result['method']}. `*` = 95% CI가 0을 포함하지 않음.", "",
             "| arm | strict | lenient | 펜스 없는 JSON | 대사 코드 일치 |", "|---|---:|---:|---:|---:|"]
    for arm, v in result["arms"].items():
        lines.append(f"| {arm} | {v['strict']:.3f} | {v['lenient']:.3f} | {v['json_strict_rate']:.2f} | {v['reconciliation_codes_match']}/{v['documents']} |")
    lines += ["", "| 비교 | 차이 [95% CI] |", "|---|---|"]
    lines += [f"| {k} | {v['diff']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]{sig(v)} |" for k, v in result["pairs"].items()]
    lines += ["", "| 필드 (strict / lenient) | " + " | ".join(RUNS) + " |", "|---|" + "---:|" * len(RUNS)]
    for f in FIELDS:
        lines.append(f"| {NAMES[f]} | " + " | ".join(f"{result['fields'][f][a]['strict']:.3f} / {result['fields'][f][a]['lenient']:.3f}" for a in RUNS) + " |")
    (out / "t07_stress.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines[8:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
