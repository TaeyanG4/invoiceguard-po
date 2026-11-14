"""README figures, drawn from the recorded results (no plotting library, no network).

  python -m invoiceguard.readme_figures            # writes docs/images/*-{light,dark}.svg (+ *-ko-*.svg)

Reads reports/eval/{b0,m0,m1}_final_*.json, reports/eval/compare_*final*.json and
reports/model/train_m1_standard_v1.json. Every number in a figure comes from those files; nothing is
typed in by hand. Each figure is written for GitHub light and dark backgrounds (embedded with <picture>)
and in two languages: English (README.md, default file names) and Korean (README.ko.md, "-ko-" names). Series colours are the first three slots of a validated categorical palette, stepped per mode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "reports" / "eval"
OUT = REPO / "docs" / "images"

ARM_KEYS = [("b0", "B0"), ("m0", "M0"), ("m1", "M1")]
SET_KEYS = ["trade:test", "public:iid_final|clean", "public:iid_final|faded", "public:iid_final|bad_scan",
            "public:ood_final|clean", "public:ood_final|faded", "public:ood_final|bad_scan"]
TEXT = {
    "en": {
        "arms": {"b0": "OCR + rules (Tesseract)", "m0": "Qwen3-VL-2B base · NF4", "m1": "M0 + QLoRA adapter"},
        "sets": {"trade:test": ("Own test", "unseen layouts T05·T06"),
                 "public:iid_final|clean": ("Public IID · clean", "IID pool (+ event_ticket)"),
                 "public:iid_final|faded": ("Public IID · faded", "IID pool (+ event_ticket)"),
                 "public:iid_final|bad_scan": ("Public IID · bad_scan", "IID pool (+ event_ticket)"),
                 "public:ood_final|clean": ("Public OOD · clean", "freelancer · held out"),
                 "public:ood_final|faded": ("Public OOD · faded", "freelancer · held out"),
                 "public:ood_final|bad_scan": ("Public OOD · bad_scan", "freelancer · held out")},
        "ci": "95% CI (base/family bootstrap)",
        "lenient": "lenient: scored after stripping ```json fences from outputs that failed strict JSON",
        "acc_footer": "strict field accuracy · FINAL (run once after the freeze) · source: reports/eval/*_final_*.json · synthetic data",
        "missing": "not measured", "no_record": "no record",
        "sig": "CI excludes 0 (significant)", "ns": "CI includes 0 (not significant)",
        "pairs": "same document pairs · cluster bootstrap 95% CI",
        "loss": "loss: step 1 {first} → step {last_s} {last} · mean train_loss {mean} · {run}",
        "loss_x": "x = optimizer step (micro batch {mb} × grad accum {ga}, lr {lr}, {sched}, warmup {wu}) · source: reports/model/train_m1_standard_v1.json",
    },
    "ko": {
        "arms": {"b0": "OCR + 규칙 (Tesseract)", "m0": "Qwen3-VL-2B 기본 · NF4", "m1": "M0 + QLoRA 어댑터"},
        "sets": {"trade:test": ("자체 test", "학습에 없던 레이아웃 T05·T06"),
                 "public:iid_final|clean": ("공개 IID · clean", "IID 풀 · event_ticket은 학습에 없음"),
                 "public:iid_final|faded": ("공개 IID · faded", "IID 풀 · event_ticket은 학습에 없음"),
                 "public:iid_final|bad_scan": ("공개 IID · bad_scan", "IID 풀 · event_ticket은 학습에 없음"),
                 "public:ood_final|clean": ("공개 OOD · clean", "freelancer · 학습 제외"),
                 "public:ood_final|faded": ("공개 OOD · faded", "freelancer · 학습 제외"),
                 "public:ood_final|bad_scan": ("공개 OOD · bad_scan", "freelancer · 학습 제외")},
        "ci": "95% CI (base/family bootstrap)",
        "lenient": "lenient: strict JSON이 실패한 출력에서 ```json 펜스를 벗긴 뒤 채점",
        "acc_footer": "strict 필드 정확도 · FINAL (설정 동결 후 1회) · 원본: reports/eval/*_final_*.json · 합성 데이터",
        "missing": "미측정", "no_record": "기록 없음",
        "sig": "CI가 0을 포함하지 않음 (유의)", "ns": "CI가 0을 포함 (유의하지 않음)",
        "pairs": "같은 문서 쌍 · cluster bootstrap 95% CI",
        "loss": "loss: step 1 {first} → step {last_s} {last} · 평균 train_loss {mean} · {run}",
        "loss_x": "x = optimizer step (micro batch {mb} × grad accum {ga}, lr {lr}, {sched}, warmup {wu}) · 원본: reports/model/train_m1_standard_v1.json",
    },
}
LANGS = {"en": "", "ko": "-ko"}  # file-name infix per language; English keeps the plain names
THEMES = {
    "light": {"ink": "#1f2328", "mute": "#59636e", "grid": "#d1d9e0", "zero": "#818b98", "bg": "#ffffff", "border": "#d1d9e0",
              "series": {"b0": "#2a78d6", "m0": "#eb6834", "m1": "#1baf7a"}},
    "dark": {"ink": "#e6edf3", "mute": "#9198a1", "grid": "#3d444d", "zero": "#7d8590", "bg": "#151b23", "border": "#3d444d",
             "series": {"b0": "#3987e5", "m0": "#d95926", "m1": "#199e70"}},
}
FONT = "'Segoe UI','Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',Helvetica,Arial,sans-serif"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_finals(folder: Path = EVAL) -> dict[str, dict]:
    """Latest FINAL scoring file per arm (same rule as the dashboard snapshot)."""
    out: dict[str, dict] = {}
    for path in sorted(folder.glob("*_final_*.json")):
        arm = path.name.split("_")[0]
        if arm in {a for a, _ in ARM_KEYS}:
            out[arm] = _json(path)
    return out


def load_compare(a: str, b: str, folder: Path = EVAL) -> dict | None:
    hits = sorted(folder.glob(f"compare_{a}_final_*__vs__{b}_final_*.json"))
    return _json(hits[-1]) if hits else None


def _text_width(text: str, size: float) -> float:
    """Rough rendered width for layout: Hangul is about one em wide, Latin about 0.56 em."""
    return sum(size if "가" <= ch <= "힣" else size * 0.56 for ch in text)


def _t(x: float, y: float, text: str, color: str, size: float = 12, anchor: str = "start", weight: int = 400) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(text)}</text>')


MARGIN = 20  # padding inside the card so the first glyphs and end caps are never clipped


def _svg(width: int, height: int, body: list[str], title: str, th: dict) -> str:
    """Wrap a figure in an opaque rounded card of its own theme colours. GitHub picks the light or dark
    variant from the viewer's browser/OS setting, which can differ from the GitHub theme; the card keeps
    the text readable on either page background."""
    w, h = width + 2 * MARGIN, height + 2 * MARGIN
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}" role="img" aria-label="{escape(title)}">\n<title>{escape(title)}</title>\n'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{th["bg"]}" stroke="{th["border"]}"/>\n'
            f'<g transform="translate({MARGIN},{MARGIN})">\n' + "\n".join(body) + "\n</g>\n</svg>\n")


def _diamond(cx: float, cy: float, r: float, stroke: str, fill: str) -> str:
    return (f'<path d="M{cx:.1f} {cy - r:.1f} L{cx + r:.1f} {cy:.1f} L{cx:.1f} {cy + r:.1f} L{cx - r:.1f} {cy:.1f} Z" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')


def _whisker(x1: float, x2: float, y: float, color: str, cap: float = 4.5) -> str:
    return (f'<path d="M{x1:.1f} {y - cap:.1f} V{y + cap:.1f} M{x1:.1f} {y:.1f} H{x2:.1f} M{x2:.1f} {y - cap:.1f} V{y + cap:.1f}" '
            f'stroke="{color}" stroke-width="1.5" fill="none"/>')


def final_accuracy_svg(finals: dict[str, dict], mode: str, lang: str = "en") -> str:
    th, tx = THEMES[mode], TEXT[lang]
    arms = [(k, short, tx["arms"][k]) for k, short in ARM_KEYS if k in finals]
    label_w, x0, plot_w, right = 230, 250, 520, 190
    width = x0 + plot_w + right
    bar_h, gap, pad = 12, 4, 16
    group_h = len(arms) * bar_h + (len(arms) - 1) * gap + 2 * pad
    top = 74
    height = top + group_h * len(SET_KEYS) + 34
    X = lambda v: x0 + max(0.0, min(1.0, float(v))) * plot_w  # noqa: E731
    body: list[str] = []
    lx = 0
    for key, name, desc in arms:  # legend
        body.append(f'<rect x="{lx}" y="8" width="12" height="12" rx="3" fill="{th["series"][key]}"/>')
        body.append(_t(lx + 18, 18.5, f"{name}  {desc}", th["ink"], 12))
        lx += 40 + _text_width(f"{name}  {desc}", 12)
    body.append(_whisker(0, 16, 38, th["ink"]))
    body.append(_t(24, 42, tx["ci"], th["mute"], 11.5))
    dx = 24 + _text_width(tx["ci"], 11.5) + 28
    body.append(_diamond(dx, 38, 5, th["ink"], th["bg"]))
    body.append(_t(dx + 12, 42, tx["lenient"], th["mute"], 11.5))
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        body.append(f'<line x1="{X(t):.1f}" y1="{top - 6}" x2="{X(t):.1f}" y2="{height - 30}" stroke="{th["grid"]}" stroke-width="1"/>')
        body.append(_t(X(t), top - 10, f"{t:g}", th["mute"], 11, "middle"))
    for i, set_key in enumerate(SET_KEYS):
        name, desc = tx["sets"][set_key]
        gy = top + i * group_h
        if i:
            body.append(f'<line x1="0" y1="{gy:.1f}" x2="{x0 + plot_w}" y2="{gy:.1f}" stroke="{th["grid"]}" stroke-width="1"/>')
        n = next((finals[a]["headline"][set_key]["n"] for a, _, _ in arms if set_key in finals[a]["headline"]), None)
        body.append(_t(0, gy + group_h / 2 - 3, name, th["ink"], 13, weight=600))
        body.append(_t(0, gy + group_h / 2 + 13, f"{desc} · n {n}", th["mute"], 11))
        for j, (arm, short, _) in enumerate(arms):
            v = finals[arm]["headline"].get(set_key)
            y = gy + pad + j * (bar_h + gap)
            cy = y + bar_h / 2
            if v is None:
                body.append(_t(x0 + 4, cy + 4, f"{short} {tx['missing']}", th["mute"], 11))
                continue
            acc = float(v["fields_acc"])
            width_px = max(2.0, acc * plot_w)
            body.append(f'<rect x="{x0}" y="{y:.1f}" width="{width_px:.1f}" height="{bar_h}" rx="2" fill="{th["series"][arm]}"/>')
            end = acc
            if v.get("ci95"):
                lo, hi = (float(c) for c in v["ci95"])
                body.append(_whisker(X(lo), X(hi), cy, th["ink"]))
                end = max(end, hi)
            label = f"{acc:.3f}"
            if float(v.get("json_valid", 1)) < 1 and v.get("lenient_fields_acc") is not None:
                len_v = float(v["lenient_fields_acc"])
                body.append(_diamond(X(len_v), cy, 5, th["ink"], th["bg"]))
                end = max(end, len_v)
                label += f"  (◇ {len_v:.3f})"
            body.append(_t(X(end) + 8, cy + 4, label, th["ink"], 11.5, weight=600))
    body.append(_t(0, height - 8, tx["acc_footer"], th["mute"], 11))
    return _svg(width, height, body, "FINAL strict field accuracy by set: B0, M0, M1", th)


def paired_svg(comps: list[tuple[str, dict]], mode: str, lang: str = "en") -> str:
    th, tx = THEMES[mode], TEXT[lang]
    label_w, panel_w, text_w = 200, 250, 150
    width = label_w + len(comps) * (panel_w + text_w)
    row_h, top = 40, 62
    height = top + row_h * len(SET_KEYS) + 30
    body: list[str] = []
    body.append(f'<circle cx="6" cy="14" r="5" fill="{th["ink"]}"/>')
    body.append(_t(16, 18, tx["sig"], th["mute"], 11.5))
    x2 = 16 + _text_width(tx["sig"], 11.5) + 30
    body.append(f'<circle cx="{x2:.1f}" cy="14" r="5" fill="{th["bg"]}" stroke="{th["ink"]}" stroke-width="1.5"/>')
    body.append(_t(x2 + 10, 18, tx["ns"], th["mute"], 11.5))
    body.append(_t(x2 + 10 + _text_width(tx["ns"], 11.5) + 30, 18, tx["pairs"], th["mute"], 11.5))
    for p, (title, comp) in enumerate(comps):
        px = label_w + p * (panel_w + text_w)
        X = lambda d, px=px: px + (max(-1.0, min(1.0, float(d))) + 1) / 2 * panel_w  # noqa: E731
        body.append(_t(px + panel_w / 2, 42, title, th["ink"], 13, "middle", 700))
        for t in (-1, -0.5, 0, 0.5, 1):
            color = th["zero"] if t == 0 else th["grid"]
            dash = ' stroke-dasharray="4 3"' if t == 0 else ""
            body.append(f'<line x1="{X(t):.1f}" y1="{top - 4}" x2="{X(t):.1f}" y2="{height - 26}" stroke="{color}" stroke-width="1"{dash}/>')
            body.append(_t(X(t), height - 12, ("+" if t > 0 else "") + f"{t:g}", th["mute"], 10.5, "middle"))
        for i, set_key in enumerate(SET_KEYS):
            name = tx["sets"][set_key][0]
            v = (comp.get("sets") or {}).get(set_key)
            cy = top + i * row_h + row_h / 2
            if p == 0:
                body.append(_t(0, cy + 4, name, th["ink"], 12.5, weight=600))
            if not v:
                body.append(_t(px + panel_w + 10, cy + 4, tx["no_record"], th["mute"], 11))
                continue
            d = float(v["field_acc_diff"])
            lo, hi = (float(c) for c in v["field_acc_diff_ci95"])
            sig = lo > 0 or hi < 0
            body.append(_whisker(X(lo), X(hi), cy, th["ink"]))
            fill = th["ink"] if sig else th["bg"]
            body.append(f'<circle cx="{X(d):.1f}" cy="{cy:.1f}" r="5" fill="{fill}" stroke="{th["ink"]}" stroke-width="1.5"/>')
            body.append(_t(px + panel_w + 10, cy + 4, f"{d:+.3f} [{lo:+.2f}, {hi:+.2f}]", th["ink"], 11, weight=600 if sig else 400))
    return _svg(width, height, body, "Paired differences in strict field accuracy with 95% CI", th)


def training_svg(report: dict, mode: str, lang: str = "en") -> str:
    th, tx = THEMES[mode], TEXT[lang]
    log = [(int(x["step"]), float(x["loss"])) for x in report.get("loss_log", []) if x.get("loss") is not None]
    width, height = 960, 270
    x0, y0, w, h = 60, 30, 860, 180
    steps = [s for s, _ in log]
    hi = max(l for _, l in log) * 1.08
    X = lambda s: x0 + (s - min(steps)) / max(1, max(steps) - min(steps)) * w  # noqa: E731
    Y = lambda l: y0 + h - l / hi * h  # noqa: E731
    body: list[str] = []
    for t in [hi * k / 4 for k in range(5)]:
        body.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x0 + w}" y2="{Y(t):.1f}" stroke="{th["grid"]}" stroke-width="1"/>')
        body.append(_t(x0 - 8, Y(t) + 4, f"{t:.2f}", th["mute"], 10.5, "end"))
    for s in [1] + [k for k in range(10, max(steps) + 1, 10)]:
        body.append(_t(X(s), y0 + h + 18, str(s), th["mute"], 10.5, "middle"))
    pts = " ".join(f"{X(s):.1f},{Y(l):.1f}" for s, l in log)
    body.append(f'<polyline points="{pts}" fill="none" stroke="{th["series"]["m1"]}" stroke-width="2" stroke-linejoin="round"/>')
    last_s, last_l = log[-1]
    body.append(f'<circle cx="{X(last_s):.1f}" cy="{Y(last_l):.1f}" r="4" fill="{th["series"]["m1"]}"/>')
    body.append(_t(X(last_s) - 8, Y(last_l) - 10, f"step {last_s} · {last_l:.3f}", th["ink"], 11.5, "end", 600))
    cfg = report.get("config", {})
    body.append(_t(x0, height - 26, tx["loss"].format(first=f"{log[0][1]:.3f}", last_s=last_s, last=f"{last_l:.3f}",
                                                    mean=f"{float(report.get('train_loss', 0)):.4f}", run=report.get("run_id")),
                   th["ink"], 11.5, weight=600))
    body.append(_t(x0, height - 8, tx["loss_x"].format(mb=cfg.get("micro_batch"), ga=cfg.get("grad_accum"), lr=cfg.get("lr"),
                                                      sched=cfg.get("scheduler"), wu=cfg.get("warmup_ratio")), th["mute"], 11))
    return _svg(width, height, body, "M1 QLoRA training loss per optimizer step", th)


RUNPOD_TEXT = {
    "en": {"title": "Same training run on two machines — loss per optimizer step",
           "local": "local · RTX 4070 Ti SUPER · Windows", "pod": "RunPod · A40 · Linux",
           "sum": "max |Δ| per step {mx} · step 1 {l1} vs {p1} · mean of 80 {lm} vs {pm} · last 10 {lt} vs {pt}",
           "src": "same config, seed, data order, versions · source: reports/runpod/train_compare.json"},
    "ko": {"title": "같은 학습을 두 머신에서 — optimizer step별 loss",
           "local": "로컬 · RTX 4070 Ti SUPER · Windows", "pod": "RunPod · A40 · Linux",
           "sum": "step별 최대 |Δ| {mx} · step 1 {l1} vs {p1} · 80 step 평균 {lm} vs {pm} · 마지막 10 {lt} vs {pt}",
           "src": "같은 설정·seed·데이터 순서·버전 · 원본: reports/runpod/train_compare.json"},
}


def runpod_loss_svg(compare: dict, mode: str, lang: str = "en") -> str:
    """Local vs RunPod loss curves of the frozen M1 recipe (scripts/runpod/compare_train.py output)."""
    th, tx = THEMES[mode], RUNPOD_TEXT[lang]
    rows = compare["per_step"]
    width, height = 960, 290
    x0, y0, w, h = 60, 40, 860, 180
    steps = [r["step"] for r in rows]
    hi = max(max(r["local"], r["pod"]) for r in rows) * 1.08
    X = lambda s: x0 + (s - min(steps)) / max(1, max(steps) - min(steps)) * w  # noqa: E731
    Y = lambda l: y0 + h - l / hi * h  # noqa: E731
    body: list[str] = []
    for t in [hi * k / 4 for k in range(5)]:
        body.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x0 + w}" y2="{Y(t):.1f}" stroke="{th["grid"]}" stroke-width="1"/>')
        body.append(_t(x0 - 8, Y(t) + 4, f"{t:.2f}", th["mute"], 10.5, "end"))
    for s in [1] + [k for k in range(10, max(steps) + 1, 10)]:
        body.append(_t(X(s), y0 + h + 18, str(s), th["mute"], 10.5, "middle"))
    series = (("local", th["series"]["b0"], "5 4"), ("pod", th["series"]["m1"], None))
    # the curves coincide, so the wide solid Pod line goes underneath and the dashed local line on top
    for key, color, dash in (series[1], series[0]):
        pts = " ".join(f"{X(r['step']):.1f},{Y(r[key]):.1f}" for r in rows)
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        width_px = 2 if dash else 4.5
        body.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width_px}" stroke-linejoin="round" '
                    f'stroke-linecap="round"{extra}/>')
    for i, (key, color, dash) in enumerate(series):  # legend, right-aligned on the title row
        x = x0 + w - 470 + i * 260
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        body.append(f'<line x1="{x}" y1="{y0 - 18}" x2="{x + 22}" y2="{y0 - 18}" stroke="{color}" stroke-width="2.5"{extra}/>')
        body.append(_t(x + 28, y0 - 14, tx[key], th["ink"], 11.5))
    body.append(_t(x0, y0 - 14, tx["title"], th["ink"], 12, weight=600))
    c = compare["criteria"]
    body.append(_t(x0, height - 26, tx["sum"].format(
        mx=f"{compare['max_abs_step_diff']:.4f}", l1=f"{c['a_step1_rel_diff_le_2pct']['local']:.4f}",
        p1=f"{c['a_step1_rel_diff_le_2pct']['pod']:.4f}", lm=f"{c['b_mean80_rel_diff_le_10pct']['local']:.4f}",
        pm=f"{c['b_mean80_rel_diff_le_10pct']['pod']:.4f}", lt=f"{c['c_last10_abs_diff_le_0.01']['local']:.4f}",
        pt=f"{c['c_last10_abs_diff_le_0.01']['pod']:.4f}"), th["ink"], 11.5, weight=600))
    body.append(_t(x0, height - 8, tx["src"], th["mute"], 11))
    return _svg(width, height, body, tx["title"], th)


def build(out: Path = OUT) -> list[Path]:
    finals = load_finals()
    comps = [(f"M1 − M0", load_compare("m1", "m0")), (f"M1 − B0", load_compare("m1", "b0"))]
    comps = [(t, c) for t, c in comps if c]
    train = _json(REPO / "reports" / "model" / "train_m1_standard_v1.json")
    runpod_path = REPO / "reports" / "runpod" / "train_compare.json"
    runpod = _json(runpod_path) if runpod_path.exists() else None
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for lang, infix in LANGS.items():
        for mode in THEMES:
            for name, svg in (("final-accuracy", final_accuracy_svg(finals, mode, lang)), ("paired-diff", paired_svg(comps, mode, lang)),
                              ("training-loss", training_svg(train, mode, lang))):
                path = out / f"{name}{infix}-{mode}.svg"
                path.write_text(svg, encoding="utf-8", newline="\n")
                written.append(path)
            if runpod is not None:
                path = out / f"runpod-loss{infix}-{mode}.svg"
                path.write_text(runpod_loss_svg(runpod, mode, lang), encoding="utf-8", newline="\n")
                written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    for path in build(Path(args.out)):
        print(path.relative_to(REPO).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
