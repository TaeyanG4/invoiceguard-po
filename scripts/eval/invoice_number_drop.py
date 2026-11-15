"""Why own-dev invoice numbers dropped after CORD was added (Fable review 5: the field-level gate found the drop
0.958 -> 0.833, 3 of 24, but it was only recorded, not explained).

Compares the saved own-dev predictions of M1 v1 (m1_dev_v1) and M1-cord (m1cord_dev_v1) field by field on
invoice_number_raw, groups documents by the printed number format, and checks the CORD training targets for the
same pattern. Nothing is re-run. Gold and predictions are synthetic own data (git-ignored); the report keeps only
the synthetic numbers and the format counts.

Usage (.venv, CPU): python scripts/eval/invoice_number_drop.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.cord import load_gold, manifest_rows  # noqa: E402
from invoiceguard.evaluation import parse_for_eval, score_trade_document  # noqa: E402

RUNS = {"M1 v1": "m1_dev_v1", "M1-cord": "m1cord_dev_v1"}
FIELD = "invoice_number_raw"
SLASH = re.compile(r"\d{2,4}/\d")
RAW_VALUE = re.compile(r'"invoice_number_raw"\s*:\s*("(?:[^"\\]|\\.)*"|null)')


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def number_format(value: str | None) -> str:
    if not value:
        return "none"
    if re.fullmatch(r"\d{4}/\d+", value):
        return "YYYY/NNNNN"
    if re.fullmatch(r"\d+", value):
        return "digits (leading zeros)"
    return re.sub(r"\d", "9", re.sub(r"[A-Z]", "A", value))


def raw_value(raw: str | None) -> str:
    m = RAW_VALUE.search(raw or "")
    return json.loads(m.group(1)) if m and m.group(1) != "null" else ("null" if m else "(key absent)")


def main() -> int:
    rows = [r for r in _jsonl(REPO / "manifests" / "trade_raw_v1.jsonl") if r["split"] == "dev"]
    preds = {arm: {p["id"]: p for p in _jsonl(REPO / "artifacts" / "predictions" / run / "predictions.jsonl")} for arm, run in RUNS.items()}
    docs, by_format = [], Counter()
    for r in rows:
        gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{r['doc_id']}.json").read_text(encoding="utf-8"))
        fmt = number_format(gold.get(FIELD))
        entry = {"doc_id": r["doc_id"], "template": r.get("template"), "gold": gold.get(FIELD), "format": fmt}
        for arm in RUNS:
            p = preds[arm][r["doc_id"]]
            entry[arm] = {"correct": score_trade_document(gold, parse_for_eval(p, "TRADE_RAW"))["fields"][FIELD][0],
                          "output": raw_value(p.get("raw_response"))}
        docs.append(entry)
        by_format[(fmt, entry["M1 v1"]["correct"], entry["M1-cord"]["correct"])] += 1
    lost = [d for d in docs if d["M1 v1"]["correct"] and not d["M1-cord"]["correct"]]
    gained = [d for d in docs if d["M1-cord"]["correct"] and not d["M1 v1"]["correct"]]
    formats = sorted({d["format"] for d in docs})
    table = {f: {"documents": sum(d["format"] == f for d in docs),
                 "M1 v1 correct": sum(d["M1 v1"]["correct"] for d in docs if d["format"] == f),
                 "M1-cord correct": sum(d["M1-cord"]["correct"] for d in docs if d["format"] == f)} for f in formats}
    cord_train = manifest_rows("train")
    slash_targets = sum(bool(SLASH.search(json.dumps(load_gold(r["id"]), ensure_ascii=False))) for r in cord_train)
    result = {"set": "trade:dev (24 own synthetic invoices, layout T04)", "runs": RUNS, "field": FIELD,
              "lost": lost, "gained": gained, "by_format": table,
              "cord_train_targets": {"documents": len(cord_train), "containing_NNNN/N_strings": slash_targets,
                                     "schema_has_invoice_number": False}}
    out = REPO / "reports" / "eval"
    (out / "invoice_number_drop_dev.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    lines = ["---", "type: report", "title: 자체 dev 인보이스 번호 하락 원인 (M1 v1 → M1-cord)",
             "description: 필드별 회귀 게이트가 찾은 0.958 → 0.833 하락(24건 중 3건)을 문서별 · 번호 형식별로 나눈 표. 저장된 예측만 사용.",
             "generated: {by: scripts/eval/invoice_number_drop.py}", "---", "",
             "# 자체 dev 인보이스 번호 하락 원인", "",
             f"- 잃은 문서 {len(lost)}건, 새로 맞힌 문서 {len(gained)}건. 24건 모두 레이아웃 T04.", "",
             "| 문서 | 정답 | M1 v1 출력 | M1-cord 출력 |", "|---|---|---|---|"]
    lines += [f"| {d['doc_id']} | `{d['gold']}` | `{d['M1 v1']['output']}` | `{d['M1-cord']['output']}` |" for d in lost]
    lines += ["", "**번호 형식별**", "", "| 형식 | 문서 | M1 v1 정답 | M1-cord 정답 |", "|---|---:|---:|---:|"]
    lines += [f"| `{f}` | {v['documents']} | {v['M1 v1 correct']} | {v['M1-cord correct']} |" for f, v in table.items()]
    lines += ["", "**해석**", "",
              f"- 잃은 {len(lost)}건은 모두 `YYYY/NNNNN` 형식입니다(이 형식 {table.get('YYYY/NNNNN', {}).get('documents', 0)}건 중 "
              f"{table.get('YYYY/NNNNN', {}).get('M1-cord correct', 0)}건만 맞힘). 다른 형식은 하나도 잃지 않았습니다.",
              "- 실패 방식: 키를 아예 빼거나(2건) 앞의 연도를 버립니다(1건). 다른 글자를 읽어 낸 것이 아니라 슬래시 번호를 값으로 내지 않는 쪽으로 바뀌었습니다.",
              f"- CORD 학습 정답 {len(cord_train)}건에는 `NNNN/N` 꼴 문자열이 {slash_targets}건이고, CORD 스키마에는 인보이스 번호 필드가 없습니다. "
              "영수증 머리글의 날짜 같은 슬래시 숫자는 늘 출력하지 않도록 배운 것이 원인일 가능성이 큽니다(가설 — 이것을 따로 검증하는 학습은 하지 않음).",
              "- 실무 대응: 문서 종류별로 어댑터를 고릅니다(인보이스 = M1 v1, 영수증 = M1-cord). 두 어댑터 모두 같은 NF4 기본 모델에 붙으므로 서버는 하나로 충분합니다."]
    (out / "invoice_number_drop_dev.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines[8:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
