"""T07: Korean-English mixed invoice layout — a DEV-ONLY stress set, never used for training or tuning
(docs/20_DECISIONS_V6.md amendment 6; Fable/astra reviews asked for Korean-English documents).

Usage (.venv, CPU): python -m invoiceguard.synth.t07

* Same PO-first generator as T01–T06 (scenarios.build_family); 30 families, own seed namespace, no overlap with the
  trade_raw_v1 families. Gold = exactly the strings drawn, as before.
* What changes: bilingual labels (거래명세서 / INVOICE, 품번 Part No., 단가 Unit Price, 합계 Total ...), item names printed
  Korean + English ("열전대 K형 (Thermocouple type K)"), a Korean company line, and Malgun Gothic (Windows system font,
  never copied into the repository; its hash is recorded).
* Images/gold/PO go to data/processed/trade/{images,gold,po}/t7_*.(png|json) (git-ignored); the manifest
  manifests/trade_raw_t07.jsonl is committed. Split and standard_role are "stress".
"""
from __future__ import annotations

import collections
import json
import random
from pathlib import Path

import jsonschema

from ..reconciliation import reconcile, validate_po
from ..splits import stable_key
from . import GENERATOR_VERSION
from .build import SEED, _sha
from .render import FONT_DIR, MARGIN, PAGE, Canvas, _labelled, _notes, _table, _totals, font_sha256, overlap_errors, verify_render
from .scenarios import build_family

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "processed" / "trade"
MANIFEST = REPO / "manifests" / "trade_raw_t07.jsonl"
SUMMARY = REPO / "manifests" / "trade_raw_t07.summary.json"
FONTS = ("malgun.ttf", "malgunbd.ttf")
ACCENT = (31, 58, 96)
PLAN = [("normal", 12), ("price_change", 4), ("quantity_change", 4), ("unknown_sku", 3),
        ("ambiguous_quantity", 3), ("missing_po_line", 2), ("duplicate_sku", 2)]
KO = {
    "Sensor module": "센서 모듈", "Signal cable 2m": "신호 케이블 2m", "Hex bolt M6x20": "육각 볼트 M6x20",
    "Flat washer M8": "평와셔 M8", "Relay 24V DC": "릴레이 24V DC", "Fuse holder 5x20": "퓨즈 홀더 5x20",
    "Terminal block 4P": "단자대 4P", "Cable gland PG9": "케이블 글랜드 PG9", "Limit switch roller": "리밋 스위치 롤러형",
    "Proximity sensor M12": "근접 센서 M12", "DIN rail 35mm": "DIN 레일 35mm", "Heat shrink tube 6mm": "수축 튜브 6mm",
    "Ferrite core clip": "페라이트 코어 클립", "Toggle switch SPDT": "토글 스위치 SPDT", "Pressure gauge 0-10 bar": "압력계 0-10 bar",
    "O-ring NBR 20x2": "오링 NBR 20x2", "Ball bearing 6202": "볼 베어링 6202", "Timing belt HTD 5M": "타이밍 벨트 HTD 5M",
    "Stepper motor NEMA17": "스테핑 모터 NEMA17", "Power supply 12V 5A": "전원 공급기 12V 5A", "LED indicator green": "LED 표시등 녹색",
    "Push button red": "푸시 버튼 적색", "Panel connector RJ45": "패널 커넥터 RJ45", "Copper busbar 20x5": "동 부스바 20x5",
    "Shielded cable 4C": "차폐 케이블 4C", "Thermocouple type K": "열전대 K형", "Solenoid valve 1/4in": "솔레노이드 밸브 1/4in",
    "Linear guide rail 300mm": "리니어 가이드 레일 300mm", "Coupling 5-8mm": "커플링 5-8mm", "Cooling fan 80mm": "냉각 팬 80mm",
    "Circuit breaker 2P 16A": "차단기 2P 16A", "Mounting bracket steel": "고정 브래킷 강철", "Spring washer M5": "스프링 와셔 M5",
    "Nylon spacer 10mm": "나일론 스페이서 10mm", "Crimp terminal ring": "압착 단자 링형", "Silicone gasket sheet": "실리콘 개스킷 시트",
    "Encoder 600 PPR": "엔코더 600 PPR", "Hydraulic hose fitting": "유압 호스 피팅", "Air filter regulator": "에어 필터 레귤레이터",
    "Rubber foot 15mm": "고무 받침 15mm", "Junction box IP65": "정션 박스 IP65", "Spirit level vial": "수평계 기포관",
    "Stainless rivet 4mm": "스테인리스 리벳 4mm", "Flow meter pulse output": "유량계 펄스 출력", "Thermal pad 1mm": "방열 패드 1mm",
    "Fiber patch cord LC": "광 패치 코드 LC", "Motor driver board": "모터 드라이버 보드", "Optical isolator": "광 아이솔레이터",
    "Capacitor kit 100pcs": "콘덴서 키트 100pcs", "Voltage regulator module": "전압 레귤레이터 모듈", "Carbon brush set": "카본 브러시 세트",
    "Vibration damper": "방진 댐퍼", "Industrial caster 75mm": "산업용 캐스터 75mm", "Precision shim pack": "정밀 심 팩",
    "Sealing tape PTFE": "실링 테이프 PTFE",
}
KO_COMPANY_A = ["한빛", "대성", "세진", "동양", "미래", "청솔", "우진", "삼호", "태광", "보람"]
KO_COMPANY_B = ["정밀", "산업", "전자", "기공", "테크", "상사"]


def bilingual(en: str, rng: random.Random) -> str:
    return rng.choice(["{ko} ({en})", "{ko} {en}", "{ko} / {en}"]).format(ko=KO[en], en=en)


def layout_t07(c: Canvas, g: dict, ctx: dict) -> None:
    """Bilingual header and labels, Korean company line, bilingual item names, grid table, totals bottom-right."""
    c.text(MARGIN, 58, "거래명세서", 40, bold=True)
    c.text(MARGIN + c.width("거래명세서  ", 40, True), 74, "INVOICE", 26, bold=True, fill=c.accent)
    _labelled(c, 720, 66, "번호 No.", g["invoice_number_raw"], ("doc", "invoice_number_raw"), 22)
    c.text(720, 106, "일자 Date  " + ctx["invoice_date"], 20, fill=(70, 70, 70))
    c.text(MARGIN, 176, "공급자 Supplier", 18, bold=True, fill=c.accent)
    c.text(MARGIN, 202, ctx["ko_company"], 22, bold=True)
    c.text(MARGIN, 232, ctx["supplier_name"], 19)
    c.text(MARGIN, 258, ctx["supplier_address"], 18, fill=(90, 90, 90))
    c.text(660, 176, "공급받는자 Buyer", 18, bold=True, fill=c.accent)
    c.text(660, 202, ctx["buyer_name"], 20)
    cols = [("sku_raw", "품번 Part No.", 150, "left"), ("description_raw", "품명 Description", 400, "left"),
            ("quantity_raw", "수량 Qty", 100, "right"), ("unit_raw", "단위 Unit", 90, "center"),
            ("unit_price_raw", "단가 Unit Price", 170, "right"), ("line_total_raw", "금액 Amount", 190, "right")]
    y = _table(c, g, cols, MARGIN, 320, header_fill=c.accent, size=20, grid=True)
    _labelled(c, MARGIN, y + 24, "통화 Currency", g["currency_raw"], ("doc", "currency_raw"), 20)
    y = _totals(c, g, 930, PAGE[0] - MARGIN, y + 70, ("공급가액 Subtotal", "할인 Discount", "세액 Tax", "합계 Total"), gap=40)
    _notes(c, ctx, MARGIN, y + 40)


def plan() -> list[tuple[str, str]]:
    return [(f"t7fam_{scenario}_{i:02d}", scenario) for scenario, n in PLAN for i in range(n)]


def main() -> int:
    for sub in ("images", "gold", "po"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    if not all((FONT_DIR / f).exists() for f in FONTS):
        raise SystemExit(f"Malgun Gothic not found in {FONT_DIR}")
    extraction_schema = json.loads((REPO / "schemas" / "extraction.schema.json").read_text(encoding="utf-8"))
    po_schema = json.loads((REPO / "schemas" / "purchase_order.schema.json").read_text(encoding="utf-8"))
    rows, errors = [], []
    for family_id, scenario in plan():
        rng = random.Random(f"{SEED}|t07|{family_id}")
        fam = build_family(rng, family_id, scenario)
        for item in fam["gold"]["items"]:
            item["description_raw"] = bilingual(item["description_raw"], rng)
        fam["context"]["ko_company"] = "(주)" + rng.choice(KO_COMPANY_A) + rng.choice(KO_COMPANY_B)
        canvas = Canvas(*FONTS, ACCENT)
        layout_t07(canvas, fam["gold"], fam["context"])
        doc_id = "t7_" + stable_key(SEED, "t07doc", family_id)[:12]
        problems = verify_render(fam["gold"], canvas.drawn) + overlap_errors(canvas.drawn)
        try:
            jsonschema.validate(fam["gold"], extraction_schema)
            jsonschema.validate(fam["po"], po_schema)
        except jsonschema.ValidationError as exc:
            problems.append(f"schema:{exc.message[:80]}")
        problems += [f"po:{e}" for e in validate_po(fam["po"])]
        oracle_codes = sorted(f["code"] for f in reconcile(fam["gold"], fam["po"], "oracle_fixture")["findings"])
        if oracle_codes != sorted(fam["expected_codes"]):
            problems.append(f"oracle_mismatch:{oracle_codes}!={fam['expected_codes']}")
        if problems:
            errors.append({"doc_id": doc_id, "problems": problems[:5]})
        png = OUT / "images" / f"{doc_id}.png"
        canvas.img.save(png, format="PNG", optimize=True)
        gold_bytes = json.dumps(fam["gold"], ensure_ascii=False, indent=1).encode("utf-8")
        po_bytes = json.dumps(fam["po"], ensure_ascii=False, indent=1).encode("utf-8")
        (OUT / "gold" / f"{doc_id}.json").write_bytes(gold_bytes)
        (OUT / "po" / f"{doc_id}.json").write_bytes(po_bytes)
        rows.append({
            "doc_id": doc_id, "family_id": family_id, "split": "stress", "standard_role": "stress", "mini_role": None,
            "template": "T07", "scenario_type": scenario, "task": "TRADE_RAW", "origin": "synthetic_self_generated",
            "generator_version": GENERATOR_VERSION + "+t07", "seed": SEED, "quality": "clean", "language": "ko+en",
            "image_sha256": _sha(png.read_bytes()), "gold_sha256": _sha(gold_bytes), "po_sha256": _sha(po_bytes),
            "width": canvas.img.width, "height": canvas.img.height, "n_rows": len(fam["gold"]["items"]),
            "font_regular": FONTS[0], "font_bold": FONTS[1], "font_sha256": [font_sha256(FONTS[0]), font_sha256(FONTS[1])],
            "has_injection_text": fam["context"]["injection_note"] is not None,
            "expected_codes": fam["expected_codes"], "transaction_diff": fam["transaction_diff"],
            "render_check": "pass" if not problems else "fail",
        })
    MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    base = [json.loads(line) for line in (REPO / "manifests" / "trade_raw_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    overlap = {k: sorted({r[k] for r in rows} & {b[k] for b in base}) for k in ("family_id", "doc_id", "image_sha256", "gold_sha256")}
    summary = {"manifest": "manifests/trade_raw_t07.jsonl", "sha256": _sha(MANIFEST.read_bytes()), "documents": len(rows),
               "role": "dev-only stress set (docs/20 amendment 6): never trained on, never used to choose settings",
               "by_scenario": dict(collections.Counter(r["scenario_type"] for r in rows)),
               "rows_per_doc": dict(sorted(collections.Counter(r["n_rows"] for r in rows).items())),
               "overlap_with_trade_raw_v1": overlap, "render_errors": errors,
               "pass": not errors and not any(overlap.values())}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: summary[k] for k in ("documents", "sha256", "pass")} | {"errors": errors[:3]}, ensure_ascii=False))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
