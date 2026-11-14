"""README CORD v2 tables, generated from the CORD scoring files (no numbers typed by hand; docs/20_DECISIONS_V6.md).

  python -m invoiceguard.readme_cord            # rewrite the marked blocks in README.md / README.ko.md
  python -m invoiceguard.readme_cord --check    # exit 1 if a README block differs from a fresh build

Reads reports/eval/cord_{dev,test}_{m0,m1v1,m1cord}_nf4.json, compare_cord_*.json and the regression comparison
compare_m1cord_dev_v1__vs__m1_dev_v1.json. A file that does not exist yet (CORD test runs once, after the freeze)
becomes "—", so the README never shows a number that was not produced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "reports" / "eval"
STAGES = ("dev", "test")
ARMS = (("M0", "m0"), ("M1 v1", "m1v1"), ("M1-cord", "m1cord"))
DASH = "—"
EFFECT_MIN = 0.05  # docs/20: M1-cord - M0 strict >= +0.05 and CI lower bound > 0
REGRESSION_MAX_DROP = 0.03  # docs/20: no more than 0.03 below M1 v1 on the existing dev sets
REGRESSION_SETS = ("trade:dev", "public:dev|clean")
BLOCKS = ("cord-summary", "cord-metrics", "cord-criteria")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def score(stage: str, arm: str) -> dict | None:
    data = _json(EVAL / f"cord_{stage}_{arm}_nf4.json")
    return None if data is None else data["sets"][f"cord:{stage}"] | {"wall_seconds": data.get("wall_seconds")}


def compare(stage: str, a: str, b: str) -> dict | None:
    data = _json(EVAL / f"compare_cord_{stage}_{a}_nf4__vs__cord_{stage}_{b}_nf4.json")
    return None if data is None else data["sets"][f"cord:{stage}"]["all"]


def regression() -> dict | None:
    data = _json(EVAL / "compare_m1cord_dev_v1__vs__m1_dev_v1.json")
    return None if data is None else data["sets"]


def f3(x: float) -> str:
    return f"{x:.3f}"


def signed(x: float, d: int = 3) -> str:
    return ("+" if x >= 0 else "−") + f"{abs(x):.{d}f}"


def ci(x: dict, d: int = 3) -> str:
    return f"{signed(x['diff'], d)} [{signed(x['ci95'][0], d)}, {signed(x['ci95'][1], d)}]"


TEXT = {
    "ko": {
        "sum_head": "| CORD v2 · strict 필드 정확도 | M0<br><sub>기본 모델</sub> | M1 v1<br><sub>위 M1 (CORD 없이 학습)</sub> | M1-cord<br><sub>CORD train 추가 학습</sub> |",
        "dev_row": "dev 100장<br><sub>개발용 · 판정 아님</sub>", "test_row": "test 100장<br><sub>동결 후 1회 · 판정</sub>",
        "blank": " — = 아직 실행하지 않은 칸입니다.",
        "sum_note": "<sub>로컬 RTX 4070 Ti SUPER · 모두 NF4 · 같은 프롬프트·전처리·생성 설정.{blank} 판정 기준은 학습 전에 [`docs/20_DECISIONS_V6.md`](docs/20_DECISIONS_V6.md)에 고정했습니다. 표는 `python -m invoiceguard.readme_cord`가 `reports/eval/cord_*.json`에서 만듭니다.</sub>",
        "metric": "지표",
        "rows": {
            "strict": "**strict 필드 정확도** (주 지표)",
            "loose": "형식 무시 정확도<br><sub>숫자는 숫자만, 이름은 대소문자·공백 무시</sub>",
            "f1": "순서 무관 필드 F1<br><sub>정밀도 / 재현율</sub>",
            "unseen": "train과 정답이 겹치지 않는 문서만",
            "json": "펜스 없는 JSON",
            "filled": "정답에 없는 값을 채운 필드",
            "rows": "행 수 일치 · 문서 전체 일치",
            "time": "추론 시간",
        },
        "docs": "문서", "per_doc": "초/문서",
        "metric_note": "<sub>원본: `reports/eval/cord_*.json` · 채점기 [`cord_eval.py`](src/invoiceguard/cord_eval.py). 굵게 = 같은 split에서 가장 좋은 값. M1-cord의 추론이 짧은 것은 펜스 없이, 지어낸 필드도 훨씬 적게 답해 토큰이 적기 때문입니다.</sub>",
        "crit_head": "| 기준 | dev (참고 · 판정 아님) | test (판정) |",
        "effect": "파인튜닝 효과<br><sub>M1-cord − M0 strict ≥ +0.05 이고 95% CI 하한 > 0</sub>",
        "reading": "읽기도 좋아짐<br><sub>위 기준 + 형식 무시 차이의 CI 하한 > 0</sub>",
        "regress": "기존 성능 유지<br><sub>기존 dev에서 M1-cord가 M1 v1보다 0.03 넘게 떨어지지 않음</sub>",
        "met": "**충족**", "not_met": "**미충족**", "ref_met": "충족", "ref_not_met": "미충족",
        "short": "점추정이 기준보다 {gap} 낮음", "ci0": "CI가 0을 포함", "ci_ok": "CI 하한은 0 위",
        "needs_effect": "파인튜닝 효과 기준 미충족", "own_dev": "자체 dev", "pub_clean": "공개 dev clean",
        "not_test": "test 기준 아님", "not_run": "회귀 비교 없음",
        "crit_note": "<sub>같은 문서 쌍 bootstrap 2,000회(seed 20261113), 정답이 같은 문서는 한 묶음으로 재표집. 회귀 확인은 M1 v1의 dev 세트 7개 전부에서 했고 나머지 세트는 {others}입니다([`compare_m1cord_dev_v1__vs__m1_dev_v1.json`](reports/eval/compare_m1cord_dev_v1__vs__m1_dev_v1.json)).</sub>",
        "others_range": "{lo} ~ {hi} 범위(각 {nlo}–{nhi}문서)",
    },
    "en": {
        "sum_head": "| CORD v2 · strict field accuracy | M0<br><sub>base model</sub> | M1 v1<br><sub>the M1 above (no CORD)</sub> | M1-cord<br><sub>trained with CORD train</sub> |",
        "dev_row": "dev, 100 photos<br><sub>development · not the verdict</sub>", "test_row": "test, 100 photos<br><sub>once, after the freeze · verdict</sub>",
        "blank": " — = not run yet.",
        "sum_note": "<sub>Local RTX 4070 Ti SUPER · all NF4 · same prompt, preprocessing and generation settings.{blank} The pass criteria were fixed before training in [`docs/20_DECISIONS_V6.md`](docs/20_DECISIONS_V6.md) (Korean). Generated from `reports/eval/cord_*.json` by `python -m invoiceguard.readme_cord`.</sub>",
        "metric": "Metric",
        "rows": {
            "strict": "**strict field accuracy** (primary)",
            "loose": "format-insensitive accuracy<br><sub>digits only for numbers, names case/space-insensitive</sub>",
            "f1": "order-free field F1<br><sub>precision / recall</sub>",
            "unseen": "documents whose gold is not in train",
            "json": "fence-free JSON",
            "filled": "fields filled where the gold is empty",
            "rows": "row-count match · whole-document match",
            "time": "inference time",
        },
        "docs": " docs", "per_doc": " s/doc",
        "metric_note": "<sub>Source: `reports/eval/cord_*.json` · scorer [`cord_eval.py`](src/invoiceguard/cord_eval.py). Bold = best value within the same split. M1-cord is faster because it answers without a fence and with far fewer invented fields, so it generates fewer tokens.</sub>",
        "crit_head": "| Criterion | dev (reference, not the verdict) | test (verdict) |",
        "effect": "Fine-tuning effect<br><sub>M1-cord − M0 strict ≥ +0.05 and 95 % CI lower bound > 0</sub>",
        "reading": "Reads better, not just formats better<br><sub>the above, plus a format-insensitive difference with CI lower bound > 0</sub>",
        "regress": "No regression<br><sub>on the existing dev sets M1-cord does not fall more than 0.03 below M1 v1</sub>",
        "met": "**met**", "not_met": "**not met**", "ref_met": "met", "ref_not_met": "not met",
        "short": "point estimate {gap} short", "ci0": "CI includes 0", "ci_ok": "CI above 0",
        "needs_effect": "the fine-tuning effect criterion is not met", "own_dev": "own dev", "pub_clean": "public dev clean",
        "not_test": "not a test criterion", "not_run": "no regression comparison",
        "crit_note": "<sub>Document-paired bootstrap, 2,000 resamples (seed 20261113); documents with identical gold are resampled together. The regression check covered all seven M1 v1 dev sets; the other sets range {others} ([`compare_m1cord_dev_v1__vs__m1_dev_v1.json`](reports/eval/compare_m1cord_dev_v1__vs__m1_dev_v1.json)).</sub>",
        "others_range": "from {lo} to {hi} ({nlo}–{nhi} documents each)",
    },
}


def summary_block(lang: str) -> str:
    t = TEXT[lang]
    lines = [t["sum_head"], "|---|---:|---:|---:|"]
    for stage, label in (("dev", t["dev_row"]), ("test", t["test_row"])):
        vals = [(score(stage, arm) or {}).get("all") for _, arm in ARMS]
        accs = [v["strict_field_accuracy"]["accuracy"] if v else None for v in vals]
        present = [a for a in accs if a is not None]
        best = max(present) if len(present) > 1 else None
        cells = [DASH if a is None else f"**{f3(a)}**" if a == best else f3(a) for a in accs]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    blank = t["blank"] if any(DASH in line for line in lines[2:]) else ""
    return "\n".join(lines) + "\n\n" + t["sum_note"].format(blank=blank)


def metrics_block(lang: str) -> str:
    t = TEXT[lang]
    cols = [(stage, score(stage, arm)) for stage in STAGES for _, arm in ARMS]
    head = f"| {t['metric']} | " + " | ".join(f"{name}<br><sub>{stage}</sub>" for stage in STAGES for name, _ in ARMS) + " |"
    lines = [head, "|---|" + "---:|" * len(cols)]

    def acc(x: dict) -> str:
        return f3(x["accuracy"])

    def counts(x: dict) -> str:
        return f"<br><sub>{x['correct']:,}/{x['scored']:,}</sub>"

    sj = "strict_json_no_repair_all"
    rows = [  # key, cell text, value for "best", higher is better (None = no bold), suffix after the bold part
        ("strict", lambda sc: acc(sc["all"]["strict_field_accuracy"]), lambda sc: sc["all"]["strict_field_accuracy"]["accuracy"], True,
         lambda sc, first: counts(sc["all"]["strict_field_accuracy"])),
        ("loose", lambda sc: acc(sc["all"]["format_insensitive_accuracy"]), lambda sc: sc["all"]["format_insensitive_accuracy"]["accuracy"],
         True, None),
        ("f1", lambda sc: f3(sc["all"]["order_free_f1"]["f1"]), lambda sc: sc["all"]["order_free_f1"]["f1"], True,
         lambda sc, first: f"<br><sub>{sc['all']['order_free_f1']['precision']:.2f} / {sc['all']['order_free_f1']['recall']:.2f}</sub>"),
        ("unseen", lambda sc: acc(sc["content_unseen"]["strict_field_accuracy"]),
         lambda sc: sc["content_unseen"]["strict_field_accuracy"]["accuracy"], True,
         lambda sc, first: f"<br><sub>{sc['content_unseen']['documents']}{t['docs']}</sub>" if first else ""),
        ("json", lambda sc: f"{round(sc[sj]['json_valid_rate'] * sc[sj]['documents'])}/{sc[sj]['documents']}",
         lambda sc: sc[sj]["json_valid_rate"], True, None),
        ("filled", lambda sc: str(sc["all"]["absent_fields_filled"]), lambda sc: sc["all"]["absent_fields_filled"], False, None),
        ("rows", lambda sc: f"{sc['all']['row_count_match_rate']:.2f} · {sc['all']['doc_exact']:.2f}",
         lambda sc: sc["all"]["doc_exact"], True, None),
        ("time", lambda sc: f"{sc['wall_seconds'] / sc['all']['documents']:.1f}{t['per_doc']}" if sc.get("wall_seconds") else DASH,
         None, None, None),
    ]
    for key, text, value, higher, suffix in rows:
        out = []
        for stage in STAGES:
            group = [sc for s, sc in cols if s == stage]
            vals = [value(sc) if sc and value else None for sc in group]
            present = [v for v in vals if v is not None]
            best = (max(present) if higher else min(present)) if higher is not None and len(present) > 1 else None
            first_present = next((i for i, sc in enumerate(group) if sc), None)
            for i, (sc, v) in enumerate(zip(group, vals)):
                if not sc:
                    out.append(DASH)
                    continue
                cell = text(sc)
                cell = f"**{cell}**" if best is not None and v == best else cell
                out.append(cell + (suffix(sc, i == first_present) if suffix else ""))
        lines.append(f"| {t['rows'][key]} | " + " | ".join(out) + " |")
    return "\n".join(lines) + "\n\n" + t["metric_note"]


def _verdict(stage: str, lang: str) -> tuple[str, str]:
    """(effect cell, reading cell) for one split, per docs/20."""
    t = TEXT[lang]
    c = compare(stage, "m1cord", "m0")
    if c is None:
        return DASH, DASH
    s, l = c["strict_field_accuracy"], c["format_insensitive_accuracy"]
    effect = s["diff"] >= EFFECT_MIN and s["ci95"][0] > 0
    reading = effect and l["ci95"][0] > 0
    met, not_met = (t["met"], t["not_met"]) if stage == "test" else (t["ref_met"], t["ref_not_met"])
    why_e = []
    if s["diff"] < EFFECT_MIN:
        why_e.append(t["short"].format(gap=f"{EFFECT_MIN - s['diff']:.4f}"))
    why_e.append(t["ci_ok"] if s["ci95"][0] > 0 else t["ci0"])
    why_r = [t["ci_ok"] if l["ci95"][0] > 0 else t["ci0"]] + ([] if effect else [t["needs_effect"]])
    return (f"{ci(s, 4)} → {met if effect else not_met}<br><sub>{' · '.join(why_e)}</sub>",
            f"{ci(l)} → {met if reading else not_met}<br><sub>{' · '.join(why_r)}</sub>")


def criteria_block(lang: str) -> str:
    t = TEXT[lang]
    dev_e, dev_r = _verdict("dev", lang)
    test_e, test_r = _verdict("test", lang)
    reg = regression()
    if reg:
        named = {"trade:dev": t["own_dev"], "public:dev|clean": t["pub_clean"]}
        ok = all(reg[k]["field_acc_diff"] >= -REGRESSION_MAX_DROP for k in REGRESSION_SETS)
        reg_cell = "<br>".join(f"{named[k]} {signed(reg[k]['field_acc_diff'])} [{signed(reg[k]['field_acc_diff_ci95'][0])}, "
                               f"{signed(reg[k]['field_acc_diff_ci95'][1])}]" for k in REGRESSION_SETS) \
            + f" → {t['met'] if ok else t['not_met']}"
        others = [v for k, v in reg.items() if k not in REGRESSION_SETS]
        others_text = t["others_range"].format(lo=signed(min(v["field_acc_diff"] for v in others)),
                                               hi=signed(max(v["field_acc_diff"] for v in others)),
                                               nlo=min(v["n_docs"] for v in others), nhi=max(v["n_docs"] for v in others))
    else:
        reg_cell, others_text = t["not_run"], DASH
    lines = [t["crit_head"], "|---|---|---|",
             f"| {t['effect']} | {dev_e} | {test_e} |",
             f"| {t['reading']} | {dev_r} | {test_r} |",
             f"| {t['regress']} | {reg_cell} | {t['not_test']} |"]
    return "\n".join(lines) + "\n\n" + t["crit_note"].format(others=others_text)


BUILDERS = {"cord-summary": summary_block, "cord-metrics": metrics_block, "cord-criteria": criteria_block}


def apply(check: bool = False) -> list[str]:
    bad = []
    for name, lang in (("README.md", "en"), ("README.ko.md", "ko")):
        path = REPO / name
        text = path.read_text(encoding="utf-8")
        new = text
        for block in BLOCKS:
            start, end = f"<!-- {block}:start -->", f"<!-- {block}:end -->"
            if new.count(start) != 1 or new.count(end) != 1:
                bad.append(f"{name}: {block} markers missing")
                continue
            head, rest = new.split(start, 1)
            _, tail = rest.split(end, 1)
            new = head + start + "\n\n" + BUILDERS[block](lang) + "\n\n" + end + tail
        if new != text:
            bad.append(name)
            if not check:
                path.write_text(new, encoding="utf-8", newline="\n")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    changed = apply(a.check)
    print(("differs: " if a.check else "updated: ") + (", ".join(changed) or "none"))
    return 1 if a.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
