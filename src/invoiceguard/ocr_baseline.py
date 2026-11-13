"""B0: Tesseract OCR + generic layout heuristics (docs/19 #3).

Input is the document image only (no PO, gold or file name). Heuristics were written while looking at
TRAIN/DEV layouts only (own T01–T04; public non-freelancer templates) and are frozen by git commit before
any final run. No rule targets a held-out layout (own T05–T06, public freelancer_invoice).

Usage (.venv):
  python -m invoiceguard.ocr_baseline ocr  --set trade:dev --psm 4      # run Tesseract in Docker
  python -m invoiceguard.ocr_baseline predict --set trade:dev --psm 4 --run-id b0_dev_psm4
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .canonical import canonical_str

REPO = Path(__file__).resolve().parents[2]
OCR_DIR = REPO / "data" / "processed" / "ocr"
IMAGE = "invoiceguard-ocr:tesseract"
B0_VERSION = "b0-1.1"

# ----------------------------------------------------------------------------- OCR words and lines
@dataclass
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def cy(self) -> float:
        return self.top + self.height / 2


@dataclass
class Phrase:
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def left(self) -> int:
        return self.words[0].left

    @property
    def right(self) -> int:
        return self.words[-1].right


@dataclass
class Line:
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def cy(self) -> float:
        return statistics.mean(w.cy for w in self.words)

    @property
    def height(self) -> float:
        return statistics.median(w.height for w in self.words)

    def phrases(self) -> list[Phrase]:
        """Split a line into cells: a gap wider than ~0.9 x text height starts a new phrase."""
        out: list[Phrase] = []
        gap_limit = max(12.0, 0.9 * self.height)
        for w in self.words:
            if out and w.left - out[-1].right <= gap_limit:
                out[-1].words.append(w)
            else:
                out.append(Phrase([w]))
        return out


def read_tsv(path: Path) -> list[Word]:
    words = []
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE):
            text = (row.get("text") or "").strip()
            if row.get("level") == "5" and text and float(row.get("conf") or -1) >= 0:
                words.append(Word(text, int(row["left"]), int(row["top"]), int(row["width"]), int(row["height"]),
                                  float(row["conf"])))
    return words


def build_lines(words: list[Word]) -> list[Line]:
    """Cluster words into visual lines by vertical centre (independent of Tesseract block ids)."""
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.cy, w.left)):
        if lines and abs(w.cy - lines[-1].cy) <= 0.55 * max(lines[-1].height, w.height):
            lines[-1].words.append(w)
        else:
            lines.append(Line([w]))
    for line in lines:
        line.words.sort(key=lambda w: w.left)
    return lines


# ----------------------------------------------------------------------------- shared helpers
MONEY = re.compile(r"^-?(?:[A-Z]{0,3}\$|[£€$])?-?\d[\d,]*(?:\.\d+)?$")
NUMERIC = re.compile(r"^[£€$]?\d[\d,]*(?:\.\d+)?$")


def last_money(text: str) -> str | None:
    tokens = [t for t in text.replace("(", " ").replace(")", " ").split() if MONEY.match(t)]
    return tokens[-1] if tokens else None


def strip_currency(token: str) -> str:
    return re.sub(r"^(?:[A-Z]{1,3}\$|US\$|[£€$])", "", token.strip())


def canonical_number(token: str | None) -> str | None:
    if not token:
        return None
    t = strip_currency(token).replace(",", "")
    try:
        return canonical_str(Decimal(t))
    except (InvalidOperation, ValueError):
        return None


@dataclass
class Column:
    name: str
    left: int
    right: int
    numeric: bool


def find_header(lines: list[Line], vocab: dict[str, list[str]], numeric: set[str], required: list[set[str]]):
    """Return (index, columns) of the first line whose phrases match enough header vocabulary."""
    for idx, line in enumerate(lines):
        cols = []
        ranked = sorted(((k, name) for name, keys in vocab.items() for k in keys), key=lambda kn: -len(kn[0]))
        for ph in line.phrases():
            low = ph.text.lower().strip(" :")
            # longest keyword first, so "unit price" never falls into the shorter "unit" column
            for key, name in ranked:
                if low == key or low.startswith(key + " ") or low.endswith(" " + key):
                    if name not in {c.name for c in cols}:
                        cols.append(Column(name, ph.left, ph.right, name in numeric))
                    break
        names = {c.name for c in cols}
        if all(names & group for group in required):
            return idx, sorted(cols, key=lambda c: c.left)
    return None, []


def assign(phrase: Phrase, columns: list[Column]) -> str:
    """Text columns align on the left edge, numeric columns on the right edge."""
    def dist(c: Column) -> float:
        return abs(phrase.right - c.right) if c.numeric else abs(phrase.left - c.left)
    return min(columns, key=dist).name


def table_rows(lines: list[Line], start: int, columns: list[Column], stop_words: tuple[str, ...], anchor: set[str]) -> list[dict]:
    rows: list[dict] = []
    for line in lines[start + 1:]:
        low = line.text.lower()
        if any(low.startswith(s) or f" {s}" in low for s in stop_words) and not rows == []:
            break
        cells: dict[str, list[str]] = {}
        for ph in line.phrases():
            cells.setdefault(assign(ph, columns), []).append(ph.text)
        if not cells:
            continue
        starts_row = bool(set(cells) & anchor)
        if starts_row or not rows:
            rows.append({k: " ".join(v) for k, v in cells.items()})
        else:  # wrapped continuation (description or a long quantity expression)
            for k, v in cells.items():
                rows[-1][k] = (rows[-1].get(k, "") + " " + " ".join(v)).strip()
    return rows


# ----------------------------------------------------------------------------- TRADE_RAW (own invoices)
TRADE_VOCAB = {
    "sku": ["item #", "item no", "item no.", "part no.", "part no", "part number", "item code", "sku"],
    "description": ["item description", "description"],
    "quantity": ["quantity", "qty"],
    "unit": ["uom", "u/m", "unit"],
    "unit_price": ["unit price", "unit cost", "price", "rate"],
    "line_total": ["line total", "ext. amount", "ext amount", "amount"],
    "_index": ["#", "no."],
    "_tax": ["tax rate", "tax", "vat"],
}
TRADE_NUMERIC = {"quantity", "unit_price", "line_total"}
TOTAL_LABELS = [("subtotal_raw", ("subtotal", "sub-total", "items total", "net")), ("discount_raw", ("less discount", "discount")),
                ("tax_raw", ("sales tax", "tax")),
                ("total_raw", ("invoice total", "amount due", "balance due", "total (usd)", "total"))]
INVOICE_NO = re.compile(r"^(?:INV-\d{4}-\d{3,6}|SI-\d{4,7}|\d{4}/\d{3,6}|\d{6,8})$")
TWO_LINE = re.compile(r"(?P<qty>\S.*?)\s+(?P<unit>[A-Za-z]{1,4})\s+@\s+(?P<price>[\d,]+\.\d+)\s+=\s+(?P<total>[\d,]+\.\d{2})\s*$")


def trade_doc_fields(lines: list[Line]) -> dict:
    out = {"invoice_number_raw": None, "currency_raw": None, "subtotal_raw": None, "tax_raw": None,
           "discount_raw": None, "total_raw": None}
    for line in lines:
        low = line.text.lower()
        if out["currency_raw"] is None and re.search(r"\busd\b", low):
            out["currency_raw"] = "USD"
        if out["invoice_number_raw"] is None:
            for w in line.words:
                if INVOICE_NO.match(w.text):
                    out["invoice_number_raw"] = w.text
                    break
        for key, labels in TOTAL_LABELS:
            if out[key] is None and any(low.startswith(l) or f" {l}" in low for l in labels):
                value = last_money(line.text)
                if value:
                    out[key] = value
                break
    return out


def trade_items(lines: list[Line]) -> list[dict]:
    idx, columns = find_header(lines, TRADE_VOCAB, TRADE_NUMERIC,
                               [{"quantity"}, {"unit_price", "line_total"}, {"sku", "description"}])
    items = []
    if idx is not None:
        stop = ("subtotal", "sub-total", "items total", "net", "discount", "tax", "total", "all amounts")
        for row in table_rows(lines, idx, columns, stop, anchor={"sku", "line_total"}):
            if not any(row.get(k) for k in ("quantity", "unit_price", "line_total")):
                continue
            items.append({"sku_raw": row.get("sku"), "description_raw": row.get("description"),
                          "quantity_raw": row.get("quantity"), "unit_raw": row.get("unit"),
                          "unit_price_raw": row.get("unit_price"), "line_total_raw": row.get("line_total")})
        return items
    # header-less two-line list: "SKU - description" followed by "qty unit @ price = total"
    previous = None
    for line in lines:
        text = re.sub(r"^.*?Amount\s+", "", line.text) if "Amount" in line.text and "@" in line.text else line.text
        match = TWO_LINE.search(text)
        if match and previous is not None:
            head = previous.text
            sku, _, desc = head.partition(" - ")
            items.append({"sku_raw": sku.strip() or None, "description_raw": desc.strip() or None,
                          "quantity_raw": match["qty"].strip(), "unit_raw": match["unit"], "unit_price_raw": match["price"],
                          "line_total_raw": match["total"]})
        previous = line
    return items


def predict_trade(words: list[Word]) -> dict:
    lines = build_lines(words)
    items = [dict(row_index=i, **it) for i, it in enumerate(trade_items(lines), start=1)]
    return {"schema_version": "1.0", "document_type": "invoice", **trade_doc_fields(lines), "items": items}


# ----------------------------------------------------------------------------- PUBLIC_CANONICAL
PUBLIC_VOCAB = {
    "description": ["description of work", "description", "item"],
    "quantity": ["quantity", "qty", "hours"],
    "unit_price": ["unit price", "price", "rate"],
    "amount": ["amount (gbp)", "amount (eur)", "amount (usd)", "amount (cad)", "amount (aud)", "amount", "value", "total"],
    "_index": ["#", "no."],
    "_tax": ["tax rate", "tax", "vat"],
}
PUBLIC_NUMERIC = {"quantity", "unit_price", "amount"}
TICKET = re.compile(r"(?P<qty>\d+(?:\.\d+)?)\s+x\s+(?P<desc>.+?)\s+(?P<amount>\S*\d[\d,]*\.\d{2})\s*$")
EACH = re.compile(r"@\s*(?P<price>\S*\d[\d,]*\.\d{2})\s+each", re.IGNORECASE)


def public_items(lines: list[Line]) -> list[dict]:
    idx, columns = find_header(lines, PUBLIC_VOCAB, PUBLIC_NUMERIC, [{"description"}, {"quantity", "amount"}])
    items = []
    if idx is not None:
        stop = ("subtotal", "net total", "sub-total", "total", "vat", "tax", "gst")
        for line in lines[idx + 1:]:
            low = line.text.lower()
            if any(low.startswith(s) for s in stop):
                break
            each = EACH.search(line.text)
            if each and items:
                items[-1]["unit_price"] = canonical_number(each["price"])
                continue
            cells: dict[str, list[str]] = {}
            for ph in line.phrases():
                cells.setdefault(assign(ph, columns), []).append(ph.text)
            nums = {k: canonical_number(" ".join(v).split()[-1]) for k, v in cells.items() if k in PUBLIC_NUMERIC}
            if nums.get("amount") is not None or nums.get("quantity") is not None:
                items.append({"description": " ".join(cells.get("description", [])) or None,
                              "quantity": nums.get("quantity"), "unit_price": nums.get("unit_price"),
                              "amount": nums.get("amount")})
            elif items and cells.get("description"):
                items[-1]["description"] = ((items[-1]["description"] or "") + " " + " ".join(cells["description"])).strip()
        return items
    for line in lines:  # header-less "2.0 x ITEM ... £90.00" rows
        match = TICKET.search(line.text)
        if match:
            items.append({"description": match["desc"].strip(), "quantity": canonical_number(match["qty"]),
                          "unit_price": None, "amount": canonical_number(match["amount"])})
    return items


def predict_public(words: list[Word]) -> dict:
    items = [dict(row_index=i, **it) for i, it in enumerate(public_items(build_lines(words)), start=1)]
    return {"schema_version": "public-1.0", "items": items}


# ----------------------------------------------------------------------------- variant selection
def consistency(obj: dict, task: str) -> float:
    """Score an extraction by its own arithmetic: rows where qty x price ~= total, plus sum(rows) ~= total."""
    from .normalization import parse_money, parse_quantity, parse_unit_price

    items = obj.get("items") or []
    if not items:
        return -1.0
    score, sums = 0.0, Decimal("0")
    for it in items:
        if task == "TRADE_RAW":
            q, pr, tot = parse_quantity(it.get("quantity_raw")), parse_unit_price(it.get("unit_price_raw")), parse_money(it.get("line_total_raw"))
            qv, pv, tv = (q.decimal if q.ok else None), (pr.decimal if pr.ok else None), (tot.decimal if tot.ok else None)
        else:
            qv, pv, tv = [Decimal(it[k]) if it.get(k) else None for k in ("quantity", "unit_price", "amount")]
        if tv is not None:
            sums += tv
            score += 0.25
        if None not in (qv, pv, tv) and abs(qv * pv - tv) <= Decimal("0.01"):
            score += 1.0
    if task == "TRADE_RAW":
        total = parse_money_safe(obj.get("total_raw"))
        if total is not None and abs(total - sums) <= Decimal("0.01"):
            score += 2.0
    return score / max(1, len(items)) + 0.01 * len(items)


def parse_money_safe(text):
    from .normalization import parse_money

    fr = parse_money(text)
    return fr.decimal if fr.ok else None


# ----------------------------------------------------------------------------- runners
def _records(spec: str):
    import importlib

    records = importlib.import_module("invoiceguard.vlm.records")
    kind, name = spec.split(":", 1)
    if kind == "public":
        return records.public_records("standard_role", name)
    if kind == "trade":
        return records.trade_records("standard_role", name)
    if kind == "stress":
        return importlib.import_module("invoiceguard.vlm.stress").stress_records(name)
    raise ValueError(spec)


def preprocess(src: Path, dst: Path, scale: int = 2, binarize: bool = True) -> None:
    """Generic OCR preprocessing (no layout knowledge): grayscale, invert dark horizontal bands
    (white-on-dark headers/banners), upscale 150 dpi renders x2 toward Tesseract's ~300 dpi sweet spot,
    then a global threshold at 165."""
    from PIL import Image, ImageOps

    with Image.open(src) as img:
        gray = ImageOps.grayscale(img)
    width, height = gray.size
    band = 6
    for y in range(0, height, band):
        box = (0, y, width, min(height, y + band))
        strip = gray.crop(box)
        hist = strip.histogram()
        dark = sum(hist[:110]) / max(1, sum(hist))
        if dark > 0.40:  # dark band -> light-on-dark text: invert only the dark x-range, never the margins
            px = strip.load()
            h = strip.size[1]
            cols = [x for x in range(width) if sum(px[x, yy] < 110 for yy in range(h)) * 2 > h]
            if cols and cols[-1] - cols[0] > width // 5:
                x0, x1 = cols[0], cols[-1] + 1
                sub = (x0, y, x1, min(height, y + band))
                gray.paste(ImageOps.invert(gray.crop(sub)), sub)
    gray = gray.resize((width * scale, height * scale), Image.LANCZOS)
    # global binarisation: light tinted boxes/stripes become white so Tesseract does not drop them as images
    if binarize:
        gray = gray.point(lambda v: 255 if v >= 165 else 0)
    dst.parent.mkdir(parents=True, exist_ok=True)
    gray.save(dst, format="PNG")


VARIANTS = {"bin": True, "gray": False}  # preprocessing variants OCR'd for every image


def tsv_dir(psm: int, variant: str) -> Path:
    return OCR_DIR / (f"tsv_psm{psm}_pre" if variant == "bin" else f"tsv_psm{psm}_{variant}")


def run_ocr(specs: list[str], psm: int, variant: str = "bin") -> Path:
    out = tsv_dir(psm, variant)
    out.mkdir(parents=True, exist_ok=True)
    jobs = OCR_DIR / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    data_root = REPO / "data"
    paths = []
    for spec in specs:
        for rec in _records(spec):
            src = OCR_DIR / ("pre" if variant == "bin" else f"pre_{variant}") / f"{rec.image_path.stem}.png"
            if not src.exists():
                preprocess(rec.image_path, src, binarize=VARIANTS[variant])
            rel = src.resolve().relative_to(data_root.resolve()).as_posix()
            paths.append(f"/data/{rel}")
    job = jobs / f"job_{int(time.time())}.txt"
    job.write_text("\n".join(paths) + "\n", encoding="utf-8", newline="\n")
    cmd = ["docker", "run", "--rm", "--network", "none", "-v", f"{data_root}:/data:ro", "-v", f"{out}:/out",
           "-v", f"{job}:/job/list.txt:ro", IMAGE, str(psm)]
    started = time.perf_counter()
    subprocess.run(cmd, check=True)
    print(f"ocr psm{psm}: {len(paths)} images in {time.perf_counter() - started:.0f}s -> {out}")
    return out


def run_predict(specs: list[str], psm: int, run_id: str) -> Path:
    out_dir = REPO / "artifacts" / "predictions" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in specs:
        for rec in _records(spec):
            started = time.perf_counter()
            candidates = []
            for variant in VARIANTS:
                tsv = tsv_dir(psm, variant) / f"{rec.image_path.stem}.tsv"
                if tsv.exists():
                    words = read_tsv(tsv)
                    obj = predict_trade(words) if rec.task == "TRADE_RAW" else predict_public(words)
                    candidates.append((consistency(obj, rec.task), variant == "bin", variant, obj))
            if not candidates:
                rows.append({"id": rec.record_id, "task": rec.task, "generation_status": "error", "raw_response": None,
                             "finish_reason": None, "error": "ocr_output_missing"})
                continue
            _, _, chosen, obj = max(candidates, key=lambda c: (c[0], c[1]))
            rows.append({"id": rec.record_id, "task": rec.task, "generation_status": "ok",
                         "raw_response": json.dumps(obj, ensure_ascii=False), "finish_reason": "stop",
                         "ocr_variant": chosen, "postprocess_s": round(time.perf_counter() - started, 4)})
    (out_dir / "predictions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                               encoding="utf-8", newline="\n")
    meta = {"run_id": run_id, "arm": "B0", "engine": "tesseract 4.1.1 (docker ubuntu:22.04)", "psm": psm,
            "preprocess_variants": list(VARIANTS), "selection": "max document-internal arithmetic consistency (no gold)",
            "b0_version": B0_VERSION, "sets": specs, "items": len(rows)}
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ocr", "predict"])
    parser.add_argument("--set", action="append", default=[])
    parser.add_argument("--psm", type=int, default=4)
    parser.add_argument("--run-id")
    parser.add_argument("--variant", choices=list(VARIANTS) + ["all"], default="all")
    args = parser.parse_args()
    if args.command == "ocr":
        for variant in (VARIANTS if args.variant == "all" else [args.variant]):
            run_ocr(args.set, args.psm, variant)
    else:
        print(run_predict(args.set, args.psm, args.run_id or f"b0_psm{args.psm}_{int(time.time())}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
