"""Six structurally different English invoice layouts drawn with Pillow.

Only gold strings are drawn for extraction fields; every draw is recorded so the build can
prove rendered text == gold (no value change, nothing clipped, nothing outside the page).
Fonts are local system fonts (never copied into the repository); their file hashes are recorded.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PAGE = (1240, 1754)  # A4 at 150 dpi, same order of size as the public data
MARGIN = 70
MIN_CELL_FONT = 17  # px; smaller text becomes unreadable after the model's max_pixels resize
FONT_DIR = Path("C:/Windows/Fonts")
FONT_PAIRS = [  # (regular, bold); availability checked at runtime
    ("arial.ttf", "arialbd.ttf"), ("calibri.ttf", "calibrib.ttf"), ("verdana.ttf", "verdanab.ttf"),
    ("tahoma.ttf", "tahomabd.ttf"), ("georgia.ttf", "georgiab.ttf"), ("times.ttf", "timesbd.ttf"),
    ("segoeui.ttf", "segoeuib.ttf"), ("trebuc.ttf", "trebucbd.ttf"), ("consola.ttf", "consolab.ttf"),
]
ACCENTS = [(31, 58, 96), (20, 90, 70), (110, 40, 40), (60, 60, 60), (85, 50, 120), (0, 100, 130)]
LAYOUTS = ("T01", "T02", "T03", "T04", "T05", "T06")


def available_font_pairs(font_dir: Path = FONT_DIR) -> list[tuple[str, str]]:
    return [p for p in FONT_PAIRS if (font_dir / p[0]).exists() and (font_dir / p[1]).exists()]


def font_sha256(name: str, font_dir: Path = FONT_DIR) -> str:
    return hashlib.sha256((font_dir / name).read_bytes()).hexdigest()


@dataclass
class Canvas:
    regular: str
    bold: str
    accent: tuple[int, int, int]
    font_dir: Path = FONT_DIR
    img: Image.Image = field(init=False)
    draw: ImageDraw.ImageDraw = field(init=False)
    drawn: list[dict[str, Any]] = field(default_factory=list)
    _cache: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.img = Image.new("RGB", PAGE, "white")
        self.draw = ImageDraw.Draw(self.img)

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(str(self.font_dir / (self.bold if bold else self.regular)), size)
        return self._cache[key]

    def width(self, text: str, size: int, bold: bool = False) -> float:
        return self.draw.textlength(text, font=self.font(size, bold))

    def text(self, x: float, y: float, text: str, size: int = 22, bold: bool = False, fill=(25, 25, 25),
             align: str = "left", key: tuple | None = None, bounds: tuple | None = None) -> tuple[int, int, int, int]:
        anchor = {"left": "la", "right": "ra", "center": "ma"}[align]
        self.draw.text((x, y), text, font=self.font(size, bold), fill=fill, anchor=anchor)
        bbox = self.draw.textbbox((x, y), text, font=self.font(size, bold), anchor=anchor)
        if key is not None:
            self.drawn.append({"key": key, "text": text, "bbox": bbox, "size": size, "bounds": bounds})
        return bbox

    def fit(self, text: str, width: float, size: int, bold: bool = False, min_size: int = 14) -> int:
        while size > min_size and self.width(text, size, bold) > width:
            size -= 1
        return size

    def wrap(self, text: str, width: float, size: int, bold: bool = False) -> list[str]:
        words, lines, current = text.split(" "), [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if current and self.width(trial, size, bold) > width:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
        return lines

    def hline(self, x0, x1, y, width=1, fill=(180, 180, 180)):
        self.draw.line([(x0, y), (x1, y)], fill=fill, width=width)


# ----------------------------------------------------------------------------- shared blocks
def _cell_x(xp: float, w: float, align: str) -> float:
    return {"left": xp + 10, "right": xp + w - 10, "center": xp + w / 2}[align]


def _labelled(c: Canvas, x, y, label, value, key, size=22, align="left", label_w=None):
    c.text(x, y, label, size, bold=True, fill=(90, 90, 90))
    vx = x + (label_w if label_w else c.width(label + "  ", size, True))
    c.text(vx, y, value, size, key=key, align=align)


def _table(c: Canvas, gold: dict, columns: list[tuple[str, str, int, str]], x0: int, y: int, *,
           size: int = 21, header_fill=None, grid: bool = False, zebra: bool = False, row_pad: int = 14) -> int:
    """columns: (field, header, width, align). Description wraps; other cells shrink to fit."""
    x_positions = []
    x = x0
    for _, _, w, _ in columns:
        x_positions.append(x)
        x += w
    x_end = x
    head_h = size + 2 * row_pad
    if header_fill:
        c.draw.rectangle([x0, y, x_end, y + head_h], fill=header_fill)
    for (fld, header, w, align), xp in zip(columns, x_positions):
        c.text(_cell_x(xp, w, align), y + row_pad, header, size - 2, bold=True, align=align,
               fill=(255, 255, 255) if header_fill else (60, 60, 60))
    y += head_h
    c.hline(x0, x_end, y, 2, c.accent)
    for i, item in enumerate(gold["items"]):
        cells = {}  # field -> (font size, lines); shrink to MIN_CELL_FONT, then wrap inside the column
        for fld, _, w, _ in columns:
            s = size if fld == "description_raw" else c.fit(item[fld], w - 20, size, min_size=MIN_CELL_FONT)
            cells[fld] = (s, c.wrap(item[fld], w - 20, s))
        n_lines = max(len(v[1]) for v in cells.values())
        row_h = n_lines * (size + 6) + 2 * row_pad - 6
        if zebra and i % 2 == 1:
            c.draw.rectangle([x0, y, x_end, y + row_h], fill=(244, 246, 248))
        for (fld, _, w, align), xp in zip(columns, x_positions):
            s, segs = cells[fld]
            for j, seg in enumerate(segs):
                c.text(_cell_x(xp, w, align), y + row_pad + j * (size + 6), seg, s, align=align,
                       key=("item", i, fld), bounds=(xp, xp + w))
        y += row_h
        c.hline(x0, x_end, y, 1)
        if grid:
            for xp in x_positions[1:]:
                c.draw.line([(xp, y - row_h), (xp, y)], fill=(200, 200, 200))
    return y


def _totals(c: Canvas, gold: dict, x_label: int, x_value: int, y: int, labels: tuple, size: int = 22,
            bold_total: bool = True, gap: int = 38) -> int:
    for (lab, key) in zip(labels, ("subtotal_raw", "discount_raw", "tax_raw", "total_raw")):
        is_total = key == "total_raw"
        c.text(x_label, y, lab, size, bold=is_total and bold_total, align="right", fill=(70, 70, 70))
        c.text(x_value, y, gold[key], size + (2 if is_total else 0), bold=is_total, align="right", key=("doc", key))
        y += gap
    return y


def _notes(c: Canvas, ctx: dict, x: int, y: int, size: int = 18) -> int:
    c.text(x, y, f"Payment terms: {ctx['payment_terms']}", size, fill=(90, 90, 90))
    y += size + 10
    c.text(x, y, "Goods sold in units of EA. Tax and discount are stated explicitly above.", size, fill=(90, 90, 90))
    y += size + 10
    if ctx.get("injection_note"):
        c.text(x, y, ctx["injection_note"], size, fill=(90, 90, 90))
        y += size + 10
    return y


# ----------------------------------------------------------------------------- layouts
def layout_t01(c: Canvas, g: dict, ctx: dict) -> None:
    """Classic grid: supplier top-left, meta table top-right, SKU-first grid, totals bottom-right."""
    c.text(MARGIN, 70, ctx["supplier_name"], 34, bold=True, fill=c.accent)
    c.text(MARGIN, 120, ctx["supplier_address"], 20, fill=(90, 90, 90))
    c.text(PAGE[0] - MARGIN, 70, "INVOICE", 44, bold=True, align="right", fill=c.accent)
    y = 140
    for label, key, value in (("Invoice No.", "invoice_number_raw", g["invoice_number_raw"]),
                              ("Date", None, ctx["invoice_date"]), ("Currency", "currency_raw", g["currency_raw"])):
        c.text(760, y, label, 20, bold=True, fill=(90, 90, 90))
        c.text(PAGE[0] - MARGIN, y, value, 20, align="right", key=("doc", key) if key else None)
        y += 32
    c.text(MARGIN, 260, "BILL TO", 18, bold=True, fill=c.accent)
    c.text(MARGIN, 288, ctx["buyer_name"], 22, bold=True)
    c.text(MARGIN, 318, ctx["buyer_address"], 20)
    cols = [("sku_raw", "Item #", 150, "left"), ("description_raw", "Description", 400, "left"),
            ("quantity_raw", "Qty", 150, "right"), ("unit_raw", "Unit", 80, "left"),
            ("unit_price_raw", "Unit Price", 160, "right"), ("line_total_raw", "Amount", 160, "right")]
    y = _table(c, g, cols, MARGIN, 400, grid=True, header_fill=c.accent)
    y = _totals(c, g, 930, PAGE[0] - MARGIN, y + 30, ("Subtotal", "Discount", "Tax", "Total (USD)"))
    _notes(c, ctx, MARGIN, y + 40)


def layout_t02(c: Canvas, g: dict, ctx: dict) -> None:
    """Description-first striped table, meta boxes under a centred title, totals box bottom-left."""
    c.text(PAGE[0] / 2, 70, "COMMERCIAL INVOICE", 40, bold=True, align="center", fill=c.accent)
    box_w = (PAGE[0] - 2 * MARGIN - 40) / 3
    for i, (label, key, value) in enumerate((("Invoice Number", "invoice_number_raw", g["invoice_number_raw"]),
                                             ("Invoice Date", None, ctx["invoice_date"]),
                                             ("Currency", "currency_raw", g["currency_raw"]))):
        x = MARGIN + i * (box_w + 20)
        c.draw.rectangle([x, 150, x + box_w, 230], outline=c.accent, width=2)
        c.text(x + 16, 162, label, 17, bold=True, fill=(110, 110, 110))
        c.text(x + 16, 192, value, 23, key=("doc", key) if key else None)
    c.text(MARGIN, 270, "Sold to:", 20, bold=True)
    c.text(MARGIN + 100, 270, ctx["buyer_name"], 20)
    cols = [("description_raw", "Description", 380, "left"), ("sku_raw", "Part No.", 170, "left"),
            ("quantity_raw", "Quantity", 150, "right"), ("unit_raw", "UOM", 80, "center"),
            ("unit_price_raw", "Price", 160, "right"), ("line_total_raw", "Line Total", 160, "right")]
    y = _table(c, g, cols, MARGIN, 330, zebra=True)
    y += 40
    c.draw.rectangle([MARGIN, y, MARGIN + 470, y + 170], outline=c.accent, width=2)
    _totals(c, g, MARGIN + 230, MARGIN + 450, y + 14, ("Sub-total", "Discount", "Tax", "Invoice Total"))
    y += 210
    c.text(MARGIN, y, ctx["supplier_name"], 22, bold=True, fill=c.accent)
    c.text(MARGIN, y + 32, ctx["supplier_address"], 18, fill=(90, 90, 90))
    _notes(c, ctx, MARGIN, y + 70)


def layout_t03(c: Canvas, g: dict, ctx: dict) -> None:
    """Two-line list entries (no grid): 'SKU — description' then 'qty unit x price = amount'."""
    c.draw.rectangle([0, 0, PAGE[0], 150], fill=c.accent)
    c.text(MARGIN, 45, ctx["supplier_name"], 36, bold=True, fill=(255, 255, 255))
    c.text(MARGIN, 98, ctx["supplier_address"], 19, fill=(230, 230, 230))
    c.text(PAGE[0] - MARGIN, 190, "Invoice", 30, bold=True, align="right", fill=c.accent)
    _labelled(c, 760, 240, "No.", g["invoice_number_raw"], ("doc", "invoice_number_raw"), 21, label_w=150)
    c.text(760, 274, "Dated", 21, bold=True, fill=(90, 90, 90))
    c.text(910, 274, ctx["invoice_date"], 21)
    _labelled(c, 760, 308, "Currency", g["currency_raw"], ("doc", "currency_raw"), 21, label_w=150)
    c.text(MARGIN, 240, "Customer", 19, bold=True, fill=c.accent)
    c.text(MARGIN, 268, ctx["buyer_name"], 21)
    y = 380
    c.hline(MARGIN, PAGE[0] - MARGIN, y, 2, c.accent)
    y += 20
    for i, it in enumerate(g["items"]):
        c.text(MARGIN, y, it["sku_raw"], 22, bold=True, key=("item", i, "sku_raw"))
        x = MARGIN + c.width(it["sku_raw"], 22, True) + 24
        c.text(x - 14, y, "-", 22, fill=(120, 120, 120))
        for j, seg in enumerate(c.wrap(it["description_raw"], PAGE[0] - MARGIN - x, 22)):
            c.text(x + 6, y + j * 28, seg, 22, key=("item", i, "description_raw"))
            last = j
        y += 34 + last * 28
        xr = PAGE[0] - MARGIN
        parts = [("line_total_raw", it["line_total_raw"]), ("=", "="), ("unit_price_raw", it["unit_price_raw"]),
                 ("@", "@"), ("unit_raw", it["unit_raw"]), ("quantity_raw", it["quantity_raw"])]
        for name, text in parts:  # right-to-left placement on one line
            bold = name == "line_total_raw"
            c.text(xr, y, text, 21, bold=bold, align="right",
                   key=("item", i, name) if name not in ("=", "@") else None,
                   fill=(25, 25, 25) if name not in ("=", "@") else (130, 130, 130))
            xr -= c.width(text, 21, bold) + 16
        c.text(MARGIN + 20, y, "Qty / Unit / Price / Amount", 17, fill=(140, 140, 140))
        y += 40
        c.hline(MARGIN, PAGE[0] - MARGIN, y, 1)
        y += 18
    y = _totals(c, g, 960, PAGE[0] - MARGIN, y + 20, ("Subtotal", "Less discount", "Sales tax", "Amount due"))
    _notes(c, ctx, MARGIN, y + 40)


def layout_t04(c: Canvas, g: dict, ctx: dict) -> None:
    """Quantity-first columns, full-width banner with invoice no., currency sentence under table."""
    c.draw.rectangle([MARGIN, 60, PAGE[0] - MARGIN, 150], fill=(40, 40, 40))
    c.text(MARGIN + 24, 82, "INVOICE", 40, bold=True, fill=(255, 255, 255))
    c.text(PAGE[0] - MARGIN - 24, 92, g["invoice_number_raw"], 28, align="right", fill=(255, 255, 255),
           key=("doc", "invoice_number_raw"))
    c.text(MARGIN, 180, "From", 18, bold=True, fill=c.accent)
    c.text(MARGIN, 206, ctx["supplier_name"], 22, bold=True)
    c.text(MARGIN, 236, ctx["supplier_address"], 19)
    c.text(660, 180, "Ship / Bill to", 18, bold=True, fill=c.accent)
    c.text(660, 206, ctx["buyer_name"], 20)
    c.text(660, 236, "Issued " + ctx["invoice_date"], 19)
    cols = [("quantity_raw", "Qty", 150, "right"), ("unit_raw", "Unit", 80, "left"),
            ("sku_raw", "Part Number", 170, "left"), ("description_raw", "Description", 380, "left"),
            ("unit_price_raw", "Unit Cost", 160, "right"), ("line_total_raw", "Ext. Amount", 160, "right")]
    y = _table(c, g, cols, MARGIN, 310, header_fill=c.accent, size=21)
    c.text(MARGIN, y + 20, "All amounts in", 19, fill=(90, 90, 90))
    c.text(MARGIN + c.width("All amounts in ", 19), y + 20, g["currency_raw"], 19, bold=True,
           key=("doc", "currency_raw"))
    y = _totals(c, g, 930, PAGE[0] - MARGIN, y + 70, ("Net", "Discount", "Tax", "Balance Due"), gap=40)
    _notes(c, ctx, MARGIN, y + 40)


def layout_t05(c: Canvas, g: dict, ctx: dict) -> None:
    """Price-before-quantity columns, supplier top-right, invoice meta and currency at the bottom."""
    c.text(PAGE[0] - MARGIN, 70, ctx["supplier_name"], 30, bold=True, align="right", fill=c.accent)
    c.text(PAGE[0] - MARGIN, 112, ctx["supplier_address"], 19, align="right", fill=(90, 90, 90))
    c.text(MARGIN, 70, "Tax Invoice", 38, bold=True)
    c.text(MARGIN, 180, "Invoiced to", 18, bold=True, fill=c.accent)
    c.text(MARGIN, 206, ctx["buyer_name"], 21)
    c.text(MARGIN, 236, ctx["buyer_address"], 19)
    cols = [("sku_raw", "Item Code", 170, "left"), ("description_raw", "Item Description", 390, "left"),
            ("unit_price_raw", "Rate", 160, "right"), ("quantity_raw", "Qty", 140, "right"),
            ("unit_raw", "U/M", 80, "center"), ("line_total_raw", "Amount", 160, "right")]
    y = _table(c, g, cols, MARGIN, 310, size=21, grid=False)
    y = _totals(c, g, 930, PAGE[0] - MARGIN, y + 30, ("Items total", "Discount", "Tax", "TOTAL"))
    y += 40
    c.hline(MARGIN, PAGE[0] - MARGIN, y, 2, c.accent)
    y += 20
    _labelled(c, MARGIN, y, "Invoice ref:", g["invoice_number_raw"], ("doc", "invoice_number_raw"), 20)
    c.text(560, y, "Date: " + ctx["invoice_date"], 20)
    _labelled(c, 900, y, "Currency:", g["currency_raw"], ("doc", "currency_raw"), 20)
    _notes(c, ctx, MARGIN, y + 50)


def layout_t06(c: Canvas, g: dict, ctx: dict) -> None:
    """Item cards in two columns; totals panel ABOVE the items; labelled fields inside cards."""
    c.text(MARGIN, 60, ctx["supplier_name"], 32, bold=True, fill=c.accent)
    c.text(MARGIN, 104, "Invoice", 24, bold=True)
    _labelled(c, MARGIN, 140, "Number", g["invoice_number_raw"], ("doc", "invoice_number_raw"), 20, label_w=110)
    c.text(MARGIN, 172, "Date", 20, bold=True, fill=(90, 90, 90))
    c.text(MARGIN + 110, 172, ctx["invoice_date"], 20)
    _labelled(c, MARGIN, 204, "Currency", g["currency_raw"], ("doc", "currency_raw"), 20, label_w=110)
    c.draw.rectangle([700, 60, PAGE[0] - MARGIN, 250], outline=c.accent, width=3)
    _totals(c, g, 960, PAGE[0] - MARGIN - 20, 78, ("Subtotal", "Discount", "Tax", "Total"), size=21, gap=40)
    card_w, gap = (PAGE[0] - 2 * MARGIN - 30) / 2, 30
    y_cols = [300, 300]
    for i, it in enumerate(g["items"]):
        col = 0 if y_cols[0] <= y_cols[1] else 1
        x, y = MARGIN + col * (card_w + gap), y_cols[col]
        desc_lines = c.wrap(it["description_raw"], card_w - 40, 21)
        h = 60 + 30 * len(desc_lines) + 4 * 32 + 10
        c.draw.rounded_rectangle([x, y, x + card_w, y + h], radius=14, outline=(190, 190, 190), width=2)
        c.text(x + 20, y + 16, f"Line {i + 1}", 17, bold=True, fill=c.accent)
        c.text(x + card_w - 20, y + 16, it["sku_raw"], 21, bold=True, align="right", key=("item", i, "sku_raw"))
        yy = y + 52
        for seg in desc_lines:
            c.text(x + 20, yy, seg, 21, key=("item", i, "description_raw"))
            yy += 30
        for label, key in (("Quantity", "quantity_raw"), ("Unit", "unit_raw"), ("Unit price", "unit_price_raw"),
                           ("Amount", "line_total_raw")):
            c.text(x + 20, yy + 4, label, 19, fill=(110, 110, 110))
            c.text(x + card_w - 20, yy + 4, it[key], 21, align="right", key=("item", i, key),
                   bold=key == "line_total_raw")
            yy += 32
        y_cols[col] = y + h + 24
    _notes(c, ctx, MARGIN, max(y_cols) + 20)


RENDERERS = {"T01": layout_t01, "T02": layout_t02, "T03": layout_t03, "T04": layout_t04, "T05": layout_t05,
             "T06": layout_t06}


def render(family: dict, template: str, rng: random.Random, font_pairs: list[tuple[str, str]]) -> tuple[Image.Image, dict]:
    regular, bold = rng.choice(font_pairs)
    canvas = Canvas(regular, bold, rng.choice(ACCENTS))
    RENDERERS[template](canvas, family["gold"], family["context"])
    return canvas.img, {"font_regular": regular, "font_bold": bold, "accent": list(canvas.accent),
                        "drawn": canvas.drawn}


def verify_render(gold: dict, drawn: list[dict]) -> list[str]:
    """Rendered strings must equal gold exactly; every gold field drawn; nothing off-page."""
    errors = []
    by_key: dict[tuple, list[str]] = {}
    for d in drawn:
        by_key.setdefault(tuple(d["key"]), []).append(d["text"])
        x0, y0, x1, y1 = d["bbox"]
        if x0 < 10 or y0 < 10 or x1 > PAGE[0] - 10 or y1 > PAGE[1] - 10:
            errors.append(f"off_page:{d['key']}")
        if d.get("bounds") and (x0 < d["bounds"][0] + 2 or x1 > d["bounds"][1] - 2):
            errors.append(f"outside_column:{d['key']}")
        if d.get("size", MIN_CELL_FONT) < MIN_CELL_FONT:
            errors.append(f"font_too_small:{d['key']}")
    for i, item in enumerate(gold["items"]):
        for fld in ("sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw"):
            texts = by_key.get(("item", i, fld))
            if not texts:
                errors.append(f"not_drawn:item{i}.{fld}")
            elif " ".join(texts) != item[fld]:
                errors.append(f"value_changed:item{i}.{fld}")
    for fld in ("invoice_number_raw", "currency_raw", "subtotal_raw", "tax_raw", "discount_raw", "total_raw"):
        texts = by_key.get(("doc", fld))
        if not texts:
            errors.append(f"not_drawn:{fld}")
        elif any(t != gold[fld] for t in texts):
            errors.append(f"value_changed:{fld}")
    return errors


def overlap_errors(drawn: list[dict]) -> list[str]:
    """Different extraction fields must not overlap on the page (clipping/garbling check)."""
    errors = []
    boxes = [(tuple(d["key"]), d["bbox"]) for d in drawn]
    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            (ka, (ax0, ay0, ax1, ay1)), (kb, (bx0, by0, bx1, by1)) = boxes[a], boxes[b]
            if ka == kb:
                continue
            if ax0 < bx1 - 1 and bx0 < ax1 - 1 and ay0 < by1 - 1 and by0 < ay1 - 1:
                errors.append(f"overlap:{ka}~{kb}")
    return errors
