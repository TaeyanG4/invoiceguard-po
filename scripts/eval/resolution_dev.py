"""docs/20 amendment 8 (b): does the higher resolution (max_pixels 2,200,000) that fixed the Hangul misreads on T07 also
hold on the dev sets? Paired comparisons on the same documents, from saved predictions only:

* own dev (trade:dev, 24 invoices): M1 v1 at 2.2 MP (m1_dev_hires) vs the frozen 786,432 (m1_dev_v1) — strict scorer as
  score_run, family-cluster bootstrap (2,000, seed 20261113). m1_dev_v1 also covered public:dev, so only trade:dev is paired.
* CORD dev (100 receipts): read from the guarded CORD comparison report (compare_cord_dev_m1cord_hires_nf4__vs__cord_dev_m1cord_nf4).

Usage (.venv, CPU): python scripts/eval/resolution_dev.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.cord import manifest_rows  # noqa: E402
from invoiceguard.evaluation import parse_for_eval, score_trade_document  # noqa: E402

ITER, SEED = 2000, 20261113
RULE = "safe = point estimate not more than 0.01 lower AND CI lower bound above -0.02 on both sets; helps = CI above 0"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _meta(run: str) -> dict:
    return json.loads((REPO / "artifacts" / "predictions" / run / "run_metadata.json").read_text(encoding="utf-8"))


def own_dev() -> dict:
    rows = [r for r in _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl") if r["split"] == "dev"]
    runs = {"hires": "m1_dev_hires", "frozen": "m1_dev_v1"}
    docs = {}
    for arm, run in runs.items():
        preds = {p["id"]: p for p in _jsonl(REPO / "artifacts" / "predictions" / run / "predictions.jsonl")}
        docs[arm] = {}
        for r in rows:
            gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{r['doc_id']}.json").read_text(encoding="utf-8"))
            f = score_trade_document(gold, parse_for_eval(preds.get(r["doc_id"], {"raw_response": None}), "TRADE_RAW"))["fields"]
            docs[arm][r["doc_id"]] = (sum(c for c, _ in f.values()), sum(n for _, n in f.values()))
    families: dict[str, list[str]] = {}
    for r in rows:
        families.setdefault(r["family_id"], []).append(r["doc_id"])
    keys = sorted(families)

    def acc(arm: str, ids: list[str]) -> float:
        return sum(docs[arm][i][0] for i in ids) / sum(docs[arm][i][1] for i in ids)

    rng = random.Random(SEED)
    diffs = sorted(acc("hires", s) - acc("frozen", s)
                   for s in ([d for _ in keys for d in families[rng.choice(keys)]] for _ in range(ITER)))
    ids = [r["doc_id"] for r in rows]
    lo, hi = int(0.025 * (ITER - 1)), int(0.975 * (ITER - 1))
    return {"set": "trade:dev (24 own invoices, layout T04)", "runs": runs,
            "max_pixels": {arm: _meta(run)["fingerprint"]["max_pixels"] for arm, run in runs.items()},
            "strict": {"hires": round(acc("hires", ids), 4), "frozen": round(acc("frozen", ids), 4)},
            "diff": round(acc("hires", ids) - acc("frozen", ids), 4), "ci95": [round(diffs[lo], 4), round(diffs[hi], 4)],
            "seconds_per_document": round(_meta("m1_dev_hires")["wall_seconds"] / len(ids), 1)}


def cord_dev() -> dict:
    cmp = json.loads((REPO / "reports" / "eval" / "compare_cord_dev_m1cord_hires_nf4__vs__cord_dev_m1cord_nf4.json").read_text(encoding="utf-8"))
    a = json.loads((REPO / "reports" / "eval" / "cord_dev_m1cord_hires_nf4.json").read_text(encoding="utf-8"))
    b = json.loads((REPO / "reports" / "eval" / "cord_dev_m1cord_nf4.json").read_text(encoding="utf-8"))
    px = [r["width"] * r["height"] for r in manifest_rows("dev")]
    s = cmp["sets"]["cord:dev"]["all"]["strict_field_accuracy"]
    return {"set": "cord:dev (100 receipts)", "runs": {"hires": "cord_dev_m1cord_hires_nf4", "frozen": "cord_dev_m1cord_nf4"},
            "strict": {"hires": a["sets"]["cord:dev"]["all"]["strict_field_accuracy"]["accuracy"],
                       "frozen": b["sets"]["cord:dev"]["all"]["strict_field_accuracy"]["accuracy"]},
            "diff": s["diff"], "ci95": s["ci95"], "images_downscaled_at_786432": sum(p > 786_432 for p in px),
            "images_downscaled_at_2200000": sum(p > 2_200_000 for p in px),
            "seconds_per_document": round(_meta("cord_dev_m1cord_hires_nf4")["wall_seconds"] / len(px), 1)}


def main() -> int:
    sets = {"own_dev": own_dev(), "cord_dev": cord_dev()}
    safe = all(v["diff"] >= -0.01 and v["ci95"][0] > -0.02 for v in sets.values())
    helps = {k: v["ci95"][0] > 0 for k, v in sets.items()}
    verdict = ("safe" if safe else "not shown to be safe") + "; helps on " + (", ".join(k for k, h in helps.items() if h) or "neither")
    result = {"amendment": "docs/20 amendment 8 (b)", "rule": RULE, "sets": sets, "verdict": verdict}
    out = REPO / "reports" / "eval"
    (out / "resolution_dev.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = ["---", "type: report", "title: 해상도 2.2 MP — dev 세트에서의 효과 (수정 8 b)",
             "description: T07에서 한글 오독을 고친 max_pixels 2,200,000이 자체 dev · CORD dev에서도 안전한지. 저장된 예측만 사용.",
             "generated: {by: scripts/eval/resolution_dev.py}", "---", "", "# 해상도 2.2 MP — dev 세트", "",
             f"판정 규칙(사전 고정): {RULE}", "",
             "| 세트 | 786,432 | 2,200,000 | 차이 [95% CI] | 초/문서 (2.2 MP) |", "|---|---:|---:|---|---:|"]
    for v in sets.values():
        lines.append(f"| {v['set']} | {v['strict']['frozen']:.4f} | {v['strict']['hires']:.4f} | {v['diff']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}] | {v['seconds_per_document']} |")
    lines += ["", f"판정: **{verdict}**", "",
              f"CORD dev 100장 중 {sets['cord_dev']['images_downscaled_at_786432']}장이 786,432에서 축소되고, 2,200,000에서도 "
              f"{sets['cord_dev']['images_downscaled_at_2200000']}장은 축소됩니다."]
    (out / "resolution_dev.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines[8:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
