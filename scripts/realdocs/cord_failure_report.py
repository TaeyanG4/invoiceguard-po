"""CORD dev failure types per arm (Fable/astra review 3: the unit-price and sub-item analysis lived only in handoff.md).

Reads the saved dev predictions and the local gold (data/processed/cord, git-ignored), classifies every gold-present
slot and every invented value with the pre-registered scorer's own normalisation (cord_eval.strict_norm / loose_norm),
and writes reports/eval/cord_failure_dev.{json,md}. Dev only: improvement decisions never look at CORD test.

Usage (.venv, CPU): python scripts/realdocs/cord_failure_report.py [--runs cord_dev_m0_nf4 cord_dev_m1cord_nf4 ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard import cord_eval as ce  # noqa: E402
from invoiceguard.cord import load_gold, manifest_rows  # noqa: E402
from invoiceguard.evaluation import parse_for_eval  # noqa: E402

DEFAULT_RUNS = {"cord_dev_m0_nf4": "M0", "cord_dev_m1v1_nf4": "M1 v1", "cord_dev_m1cord_nf4": "M1-cord"}
GROUPS = ("item.name", "item.count", "item.unit_price", "item.price", "sub.name", "sub.count", "sub.price",
          "doc.subtotal", "doc.tax", "doc.total")


def _predictions(run: str) -> dict[str, dict]:
    path = REPO / "artifacts" / "predictions" / run / "predictions.jsonl"
    return {json.loads(line)["id"]: json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def classify(field: str, gold, pred) -> str:
    if pred is None:
        return "omitted"
    if ce.strict_norm(pred) == ce.strict_norm(gold):
        return "ok"
    lp = ce.loose_norm(field, pred)
    return "format_only" if lp is not None and lp == ce.loose_norm(field, gold) else "wrong_value"


def analyse(run: str) -> dict:
    preds = _predictions(run)
    by_group: dict[str, Counter] = {g: Counter() for g in GROUPS}
    invented: Counter = Counter()
    unit_null = Counter()  # printed unit price left null on an emitted row, by pattern
    rows = Counter()
    for r in manifest_rows("dev"):
        gold = ce.load_gold(r["id"]) if hasattr(ce, "load_gold") else load_gold(r["id"])
        skip = ce._masked_keys(r["masked"])
        parsed = parse_for_eval(preds.get(r["id"], {"raw_response": None, "generation_status": "missing"}), "CORD_RAW", lenient=True)
        obj = parsed.obj if parsed.status == "ok" else None
        pred = {k: v for k, _, v in ce.slots(obj)}
        for key, field, value in ce.slots(gold):
            if key in skip:
                continue
            group = f"{key[0]}.{field}"
            if value is None:
                invented[group] += pred.get(key) is not None
                continue
            if group in by_group:
                by_group[group][classify(field, value, pred.get(key))] += 1
        g_items, p_items = gold.get("items") or [], (obj or {}).get("items") or []
        g_items = [x for x in g_items if isinstance(x, dict)]
        p_items = [x for x in p_items if isinstance(x, dict)]
        rows["gold_rows"] += len(g_items)
        rows["pred_rows"] += len(p_items)
        rows["docs_fewer_rows"] += len(p_items) < len(g_items)
        rows["docs_more_rows"] += len(p_items) > len(g_items)
        gold_sub = sum(len(x.get("sub_items") or []) for x in g_items)
        pred_sub = sum(len(x.get("sub_items") or []) for x in p_items if isinstance(x.get("sub_items"), list))
        rows["gold_sub_items"] += gold_sub
        rows["pred_sub_items"] += pred_sub
        for i, it in enumerate(g_items):
            if it.get("unit_price") is None or i >= len(p_items) or p_items[i].get("unit_price") is not None:
                continue
            p = p_items[i]
            if isinstance(p.get("price"), str) and p["price"].lstrip().startswith("@"):
                unit_null["unit price put in the price field ('@…')"] += 1
            elif ce.loose_norm("price", it.get("unit_price")) == ce.loose_norm("price", it.get("price")):
                unit_null["unit price equals the line total (printed twice)"] += 1
            else:
                unit_null["other"] += 1
    return {"run": run, "by_group": {g: dict(c) for g, c in by_group.items()}, "invented_by_group": dict(invented),
            "rows": dict(rows), "printed_unit_price_left_null": dict(unit_null), "parse_status": parsed.status}


def to_markdown(results: dict[str, dict], labels: dict[str, str]) -> str:
    runs = list(results)
    lines = ["---", "type: report", "title: CORD dev 실패 유형 (arm별)",
             "description: 정답에 값이 있는 칸을 일치·형식만 다름·틀림·빠뜨림으로, 정답에 없는 칸을 지어냄으로 나눈 표. dev만 사용.",
             "generated: {by: scripts/realdocs/cord_failure_report.py}", "---", "",
             "# CORD dev 실패 유형", "",
             "칸 = 개수 (일치 / 형식만 다름 / 틀림 / 빠뜨림). 채점 정규화는 사전 고정 채점기(`cord_eval.py`)와 같습니다. test는 보지 않았습니다.", "",
             "| 필드 | " + " | ".join(labels[r] for r in runs) + " |", "|---|" + "---|" * len(runs)]
    for g in GROUPS:
        cells = []
        for r in runs:
            c = results[r]["by_group"].get(g, {})
            cells.append(f"{c.get('ok', 0)} / {c.get('format_only', 0)} / {c.get('wrong_value', 0)} / {c.get('omitted', 0)}")
        lines.append(f"| {g} | " + " | ".join(cells) + " |")
    lines += ["", "**정답에 없는 칸을 채운 수 (지어냄)**", "", "| 필드 | " + " | ".join(labels[r] for r in runs) + " |", "|---|" + "---|" * len(runs)]
    for g in sorted({g for r in runs for g in results[r]["invented_by_group"]}):
        lines.append(f"| {g} | " + " | ".join(str(results[r]["invented_by_group"].get(g, 0)) for r in runs) + " |")
    lines += ["", "**행 구조**", "", "| | " + " | ".join(labels[r] for r in runs) + " |", "|---|" + "---|" * len(runs)]
    for k, label in (("gold_rows", "정답 품목 행"), ("pred_rows", "예측 품목 행"), ("docs_fewer_rows", "행을 덜 낸 문서"),
                     ("docs_more_rows", "행을 더 낸 문서"), ("gold_sub_items", "정답 하위 품목"), ("pred_sub_items", "예측 하위 품목")):
        lines.append(f"| {label} | " + " | ".join(str(results[r]["rows"].get(k, 0)) for r in runs) + " |")
    lines += ["", "**인쇄된 단가를 행은 냈는데 null로 둔 경우 (유형별)**", "", "| 유형 | " + " | ".join(labels[r] for r in runs) + " |", "|---|" + "---|" * len(runs)]
    kinds = sorted({k for r in runs for k in results[r]["printed_unit_price_left_null"]})
    for k in kinds:
        lines.append(f"| {k} | " + " | ".join(str(results[r]["printed_unit_price_left_null"].get(k, 0)) for r in runs) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+")
    a = ap.parse_args()
    labels = dict(DEFAULT_RUNS) | {r: r for r in (a.runs or []) if r not in DEFAULT_RUNS}
    runs = a.runs or list(DEFAULT_RUNS)
    runs = [r for r in runs if (REPO / "artifacts" / "predictions" / r / "predictions.jsonl").exists()]
    results = {r: analyse(r) for r in runs}
    out = REPO / "reports" / "eval"
    (out / "cord_failure_dev.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (out / "cord_failure_dev.md").write_text(to_markdown(results, labels), encoding="utf-8", newline="\n")
    print(f"wrote reports/eval/cord_failure_dev.{{json,md}} for {runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
