"""Pre-defined, seeded stress variants of the own DEV set only (docs/19 #4). Never part of final tables.

Usage: python -m invoiceguard.vlm.stress build      (writes data/processed/stress/* + manifests/stress_v1.jsonl)
Record ids are "<doc_id>__<variant>"; gold/PO are the unchanged dev documents.
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

from . import REPO
from .records import Record, trade_answer, trade_records

STRESS_DIR = REPO / "data" / "processed" / "stress"
MANIFEST = REPO / "manifests" / "stress_v1.jsonl"
SEED = 20261113
VARIANTS = {
    "blur_jpeg": "Gaussian blur r=1.3 then JPEG q=30 round-trip",
    "skew_lowres": "rotate +-1.5..2.5 deg (white fill), downscale to 55% and back up (bicubic)",
    "fade_noise": "contrast 0.55, brightness 1.12, seeded uniform per-pixel noise blended at 0.18",
}


def _apply(img: Image.Image, variant: str, rng: random.Random) -> Image.Image:
    img = img.convert("RGB")
    if variant == "blur_jpeg":
        img = img.filter(ImageFilter.GaussianBlur(1.3))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=30)
        return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    if variant == "skew_lowres":
        angle = rng.choice([-1, 1]) * rng.uniform(1.5, 2.5)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
        w, h = img.size
        return img.resize((int(w * 0.55), int(h * 0.55)), Image.BICUBIC).resize((w, h), Image.BICUBIC)
    if variant == "fade_noise":
        img = ImageEnhance.Brightness(ImageEnhance.Contrast(img).enhance(0.55)).enhance(1.12)
        noise = Image.frombytes("L", img.size, rng.randbytes(img.size[0] * img.size[1]))  # seeded, reproducible
        return Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.18)
    raise ValueError(variant)


def build() -> None:
    rows = []
    for rec in trade_records("standard_role", "dev"):
        for variant in VARIANTS:
            rng = random.Random(f"{SEED}|{rec.record_id}|{variant}")
            out = STRESS_DIR / variant / f"{rec.record_id}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            _apply(rec.image(), variant, rng).save(out, format="PNG")
            rows.append({"id": f"{rec.record_id}__{variant}", "doc_id": rec.record_id, "variant": variant,
                         "params": VARIANTS[variant], "split": "dev", "task": "TRADE_RAW",
                         "image_sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "final": False})
    MANIFEST.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    print(f"{len(rows)} stress images; manifest sha256 {hashlib.sha256(MANIFEST.read_bytes()).hexdigest()}")


def stress_records(name: str) -> list[Record]:
    """name: a variant key or 'all'. Only dev documents exist here by construction."""
    rows = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    base = {r.record_id: r for r in trade_records("standard_role", "dev")}
    out = []
    for row in rows:
        if name in ("all", row["variant"]):
            src = base[row["doc_id"]]
            out.append(Record(row["id"], "TRADE_RAW", STRESS_DIR / row["variant"] / f"{row['doc_id']}.png", src.answer, "dev_stress"))
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build()
