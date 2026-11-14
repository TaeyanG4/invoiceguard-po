"""README figures, drawn from the recorded results (no plotting library, no network).

  python -m invoiceguard.readme_figures            # writes docs/images/*-{light,dark}.svg

Reads reports/eval/{b0,m0,m1}_final_*.json, reports/eval/compare_*final*.json and
reports/model/train_m1_standard_v1.json. Every number in a figure comes from those files; nothing is
typed in by hand. Each figure is written twice (GitHub light and dark backgrounds) and embedded with
<picture>. Series colours are the first three slots of a validated categorical palette, stepped per mode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "reports" / "eval"
OUT = REPO / "docs" / "images"

ARMS = [("b0", "B0", "OCR + 규칙 (Tesseract)"), ("m0", "M0", "Qwen3-VL-2B 기본 · NF4"), ("m1", "M1", "M0 + QLoRA 어댑터")]
SETS = [
    ("trade:test", "자체 test", "학습에 없던 레이아웃 T05·T06"),
    ("public:iid_final|clean", "공개 IID · clean", "IID 풀 · event_ticket은 학습에 없음"),
    ("public:iid_final|faded", "공개 IID · faded", "IID 풀 · event_ticket은 학습에 없음"),
    ("public:iid_final|bad_scan", "공개 IID · bad_scan", "IID 풀 · event_ticket은 학습에 없음"),
    ("public:ood_final|clean", "공개 OOD · clean", "freelancer · 학습 제외"),
    ("public:ood_final|faded", "공개 OOD · faded", "freelancer · 학습 제외"),
    ("public:ood_final|bad_scan", "공개 OOD · bad_scan", "freelancer · 학습 제외"),
]
THEMES = {
    "light": {"ink": "#1f2328", "mute": "#59636e", "grid": "#d1d9e0", "zero": "#818b98", "bg": "#ffffff",
              "series": {"b0": "#2a78d6", "m0": "#eb6834", "m1": "#1baf7a"}},
    "dark": {"ink": "#e6edf3", "mute": "#9198a1", "grid": "#3d444d", "zero": "#7d8590", "bg": "#0d1117",
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
        if arm in {a for a, _, _ in ARMS}:
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


MARGIN = 14  # breathing room so the first glyphs and end caps are never clipped


def _svg(width: int, height: int, body: list[str], title: str) -> str:
    w, h = width + 2 * MARGIN, height + 2 * MARGIN
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}" role="img" aria-label="{escape(title)}">\n<title>{escape(title)}</title>\n'
            f'<g transform="translate({MARGIN},{MARGIN})">\n' + "\n".join(body) + "\n</g>\n</svg>\n")


def _diamond(cx: float, cy: float, r: float, stroke: str, fill: str) -> str:
    return (f'<path d="M{cx:.1f} {cy - r:.1f} L{cx + r:.1f} {cy:.1f} L{cx:.1f} {cy + r:.1f} L{cx - r:.1f} {cy:.1f} Z" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')


def _whisker(x1: float, x2: float, y: float, color: str, cap: float = 4.5) -> str:
    return (f'<path d="M{x1:.1f} {y - cap:.1f} V{y + cap:.1f} M{x1:.1f} {y:.1f} H{x2:.1f} M{x2:.1f} {y - cap:.1f} V{y + cap:.1f}" '
            f'stroke="{color}" stroke-width="1.5" fill="none"/>')


def final_accuracy_svg(finals: dict[str, dict], mode: str) -> str:
    th = THEMES[mode]
    arms = [a for a in ARMS if a[0] in finals]
    label_w, x0, plot_w, right = 230, 250, 520, 190
    width = x0 + plot_w + right
    bar_h, gap, pad = 12, 4, 16
    group_h = len(arms) * bar_h + (len(arms) - 1) * gap + 2 * pad
    top = 74
    height = top + group_h * len(SETS) + 34
    X = lambda v: x0 + max(0.0, min(1.0, float(v))) * plot_w  # noqa: E731
    body: list[str] = []
    lx = 0
    for key, name, desc in arms:  # legend
        body.append(f'<rect x="{lx}" y="8" width="12" height="12" rx="3" fill="{th["series"][key]}"/>')
        body.append(_t(lx + 18, 18.5, f"{name}  {desc}", th["ink"], 12))
        lx += 40 + _text_width(f"{name}  {desc}", 12)
    body.append(_whisker(0, 16, 38, th["ink"]))
    body.append(_t(24, 42, "95% CI (base/family bootstrap)", th["mute"], 11.5))
    body.append(_diamond(238, 38, 5, th["ink"], th["bg"]))
    body.append(_t(250, 42, "lenient: strict JSON이 실패한 출력에서 ```json 펜스를 벗긴 뒤 채점", th["mute"], 11.5))
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        body.append(f'<line x1="{X(t):.1f}" y1="{top - 6}" x2="{X(t):.1f}" y2="{height - 30}" stroke="{th["grid"]}" stroke-width="1"/>')
        body.append(_t(X(t), top - 10, f"{t:g}", th["mute"], 11, "middle"))
    for i, (set_key, name, desc) in enumerate(SETS):
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
                body.append(_t(x0 + 4, cy + 4, f"{short} 미측정", th["mute"], 11))
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
    body.append(_t(0, height - 8, "strict 필드 정확도 · FINAL (설정 동결 후 1회) · 원본: reports/eval/*_final_*.json · 합성 데이터", th["mute"], 11))
    return _svg(width, height, body, "FINAL strict field accuracy by set: B0, M0, M1")


def paired_svg(comps: list[tuple[str, dict]], mode: str) -> str:
    th = THEMES[mode]
    label_w, panel_w, text_w = 200, 250, 150
    width = label_w + len(comps) * (panel_w + text_w)
    row_h, top = 40, 62
    height = top + row_h * len(SETS) + 30
    body: list[str] = []
    body.append(f'<circle cx="6" cy="14" r="5" fill="{th["ink"]}"/>')
    body.append(_t(16, 18, "CI가 0을 포함하지 않음 (유의)", th["mute"], 11.5))
    body.append(f'<circle cx="206" cy="14" r="5" fill="{th["bg"]}" stroke="{th["ink"]}" stroke-width="1.5"/>')
    body.append(_t(216, 18, "CI가 0을 포함 (유의하지 않음)", th["mute"], 11.5))
    body.append(_t(420, 18, "같은 문서 쌍 · cluster bootstrap 95% CI", th["mute"], 11.5))
    for p, (title, comp) in enumerate(comps):
        px = label_w + p * (panel_w + text_w)
        X = lambda d, px=px: px + (max(-1.0, min(1.0, float(d))) + 1) / 2 * panel_w  # noqa: E731
        body.append(_t(px + panel_w / 2, 42, title, th["ink"], 13, "middle", 700))
        for t in (-1, -0.5, 0, 0.5, 1):
            color = th["zero"] if t == 0 else th["grid"]
            dash = ' stroke-dasharray="4 3"' if t == 0 else ""
            body.append(f'<line x1="{X(t):.1f}" y1="{top - 4}" x2="{X(t):.1f}" y2="{height - 26}" stroke="{color}" stroke-width="1"{dash}/>')
            body.append(_t(X(t), height - 12, ("+" if t > 0 else "") + f"{t:g}", th["mute"], 10.5, "middle"))
        for i, (set_key, name, _) in enumerate(SETS):
            v = (comp.get("sets") or {}).get(set_key)
            cy = top + i * row_h + row_h / 2
            if p == 0:
                body.append(_t(0, cy + 4, name, th["ink"], 12.5, weight=600))
            if not v:
                body.append(_t(px + panel_w + 10, cy + 4, "기록 없음", th["mute"], 11))
                continue
            d = float(v["field_acc_diff"])
            lo, hi = (float(c) for c in v["field_acc_diff_ci95"])
            sig = lo > 0 or hi < 0
            body.append(_whisker(X(lo), X(hi), cy, th["ink"]))
            fill = th["ink"] if sig else th["bg"]
            body.append(f'<circle cx="{X(d):.1f}" cy="{cy:.1f}" r="5" fill="{fill}" stroke="{th["ink"]}" stroke-width="1.5"/>')
            body.append(_t(px + panel_w + 10, cy + 4, f"{d:+.3f} [{lo:+.2f}, {hi:+.2f}]", th["ink"], 11, weight=600 if sig else 400))
    return _svg(width, height, body, "Paired differences in strict field accuracy with 95% CI")


def training_svg(report: dict, mode: str) -> str:
    th = THEMES[mode]
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
    body.append(_t(x0, height - 26, f"loss: step 1 {log[0][1]:.3f} → step {last_s} {last_l:.3f} · 평균 train_loss {float(report.get('train_loss', 0)):.4f} · "
                   f"{report.get('run_id')}", th["ink"], 11.5, weight=600))
    body.append(_t(x0, height - 8, f"x = optimizer step (micro batch {cfg.get('micro_batch')} × grad accum {cfg.get('grad_accum')}, lr {cfg.get('lr')}, "
                   f"{cfg.get('scheduler')}, warmup {cfg.get('warmup_ratio')}) · 원본: reports/model/train_m1_standard_v1.json", th["mute"], 11))
    return _svg(width, height, body, "M1 QLoRA training loss per optimizer step")


def build(out: Path = OUT) -> list[Path]:
    finals = load_finals()
    comps = [(f"M1 − M0", load_compare("m1", "m0")), (f"M1 − B0", load_compare("m1", "b0"))]
    comps = [(t, c) for t, c in comps if c]
    train = _json(REPO / "reports" / "model" / "train_m1_standard_v1.json")
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for mode in THEMES:
        for name, svg in (("final-accuracy", final_accuracy_svg(finals, mode)), ("paired-diff", paired_svg(comps, mode)),
                          ("training-loss", training_svg(train, mode))):
            path = out / f"{name}-{mode}.svg"
            path.write_text(svg, encoding="utf-8", newline="\n")
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
