"""README data samples: small thumbnails and crops of each data type (needs the local data).

  python -m invoiceguard.readme_samples          # writes docs/images/data/*.jpg

Picks documents deterministically from the committed manifests (first match in sorted order), so a rerun
on the same data writes the same selection. Images come from:
  * public InvoiceOCR-Synth (CC BY 4.0) — extracted from the pinned parquet with SHA-256 verification,
  * this repository's renderer (fictional companies) and its dev-only stress variants.
Only a few downscaled samples are written; the datasets themselves stay out of the repository.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageOps

from .dashboard_server import DataStore

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "images" / "data"
TEMPLATES = ["formal_corporate", "modern_minimal", "utility_bill", "pos_thermal", "event_ticket", "freelancer_invoice"]
LAYOUTS = ["T01", "T02", "T03", "T04", "T05", "T06"]
QUALITY_BASE = "synth_0433_668d20e1.png"  # utility_bill, dev pool — also used in the dashboard screenshot
STRESS_DOC = "tr_69cab78e7dcd"
CARD = (300, 400)  # uniform thumbnail canvas so gallery rows line up
BORDER = (208, 215, 222)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _save(img: Image.Image, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    img.convert("RGB").save(path, "JPEG", quality=84, optimize=True, progressive=True)
    return path


def _card(img: Image.Image) -> Image.Image:
    """Whole page scaled into a fixed white card with a thin border."""
    page = img.convert("RGB")
    page.thumbnail((CARD[0] - 16, CARD[1] - 16), Image.LANCZOS)
    canvas = Image.new("RGB", CARD, (255, 255, 255))
    canvas.paste(page, ((CARD[0] - page.width) // 2, (CARD[1] - page.height) // 2))
    return ImageOps.expand(canvas, border=1, fill=BORDER)


def _crop(img: Image.Image, box: tuple[float, float, float, float], width: int = 420) -> Image.Image:
    """Same relative region of each variant, so degradations can be compared side by side."""
    page = img.convert("RGB")
    w, h = page.size
    region = page.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    region = region.resize((width, int(region.height * width / region.width)), Image.LANCZOS)
    return ImageOps.expand(region, border=1, fill=BORDER)


def build() -> list[Path]:
    store = DataStore(REPO)
    if not store.public_available() or not store.trade_available():
        raise SystemExit("local public parquet and generated trade data are required")
    written: list[Path] = []
    public = sorted(_jsonl(REPO / "manifests" / "public_canonical_v1.jsonl"), key=lambda r: r["base_id"])
    for template in TEMPLATES:  # one clean page per public template, a readable 3-5 item document
        row = next(r for r in public if r["template"] == template and r["quality"] == "clean" and 3 <= r["n_items"] <= 5)
        path = store.public_image(row["base_id"], "clean", row["image_sha256"])
        written.append(_save(_card(Image.open(path)), f"public-{template}.jpg"))
    for quality in ("clean", "faded", "bad_scan"):  # the same document at the three published qualities
        row = next(r for r in public if r["base_id"] == QUALITY_BASE and r["quality"] == quality)
        path = store.public_image(row["base_id"], quality, row["image_sha256"])
        written.append(_save(_crop(Image.open(path), (0.08, 0.05, 0.92, 0.52)), f"public-quality-{quality}.jpg"))
    trade = sorted(_jsonl(REPO / "manifests" / "trade_raw_v1.jsonl"), key=lambda r: r["doc_id"])
    for layout in LAYOUTS:  # one page per own layout, plain scenario, no injected note
        row = next(r for r in trade if r["template"] == layout and r["scenario_type"] == "normal" and not r["has_injection_text"])
        written.append(_save(_card(Image.open(store.trade_dir / "images" / f"{row['doc_id']}.png")), f"trade-{layout}.jpg"))
    box = (0.0, 0.0, 0.62, 0.36)
    written.append(_save(_crop(Image.open(store.trade_dir / "images" / f"{STRESS_DOC}.png"), box, 360), "stress-original.jpg"))
    for variant in ("blur_jpeg", "fade_noise", "skew_lowres"):
        path = REPO / "data" / "processed" / "stress" / variant / f"{STRESS_DOC}.png"
        written.append(_save(_crop(Image.open(path), box, 360), f"stress-{variant}.jpg"))
    return written


def main() -> int:
    for path in build():
        print(path.relative_to(REPO).as_posix(), path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
