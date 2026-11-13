"""Validate this planning package, not the planned application or model.

Usage:
    python -m pip install jsonschema PyYAML
    python scripts/verify_pack.py
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import unquote

try:
    from jsonschema import Draft202012Validator
    import yaml
except ImportError as exc:
    raise SystemExit("Install jsonschema and PyYAML to validate the document pack.") from exc

ROOT = Path(__file__).resolve().parents[1]
checks: list[dict[str, str]] = []

def record(name: str, condition: bool, detail: str = "") -> None:
    checks.append({"check": name, "status": "pass" if condition else "failed", "detail": detail})

def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))

for schema_path in sorted((ROOT / "schemas").glob("*.json")):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
        record(f"schema:{schema_path.name}", True)
    except Exception as exc:
        record(f"schema:{schema_path.name}", False, str(exc))

for example, schema in [
    ("examples/purchase_order.json", "schemas/purchase_order.schema.json"),
    ("examples/invoice_oracle.json", "schemas/extraction.schema.json"),
    ("examples/expected_findings.json", "schemas/findings.schema.json"),
    ("examples/public_canonical.json", "schemas/public_extraction.schema.json"),
]:
    errors = list(Draft202012Validator(read_json(schema)).iter_errors(read_json(example)))
    record(f"example:{example}", not errors, "; ".join(e.message for e in errors))

po = read_json("examples/purchase_order.json")
inv = read_json("examples/invoice_oracle.json")
expected = read_json("examples/expected_findings.json")
record("leading_zero_fixture", po["items"][0]["sku"] == inv["items"][0]["sku_raw"] == "000125")
po_total = sum(Decimal(i["quantity"]) * Decimal(i["unit_price"]) for i in po["items"])
line_totals = [Decimal(i["line_total_raw"]) for i in inv["items"]]
for i in inv["items"]:
    calculated = (Decimal(i["quantity_raw"]) * Decimal(i["unit_price_raw"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    record(f"invoice_fixture_arithmetic:row{i['row_index']}", calculated == Decimal(i["line_total_raw"]))
record("invoice_fixture_total", sum(line_totals) == Decimal(inv["total_raw"]))
record("fixture_delta_25", Decimal(inv["total_raw"]) - po_total == Decimal(expected["reference_total_difference"]) == Decimal("25.00"))
record("fixture_is_not_live_output", expected["source"] == "oracle_fixture")
record("expected_price_warning", [x["code"] for x in expected["findings"]] == ["UNIT_PRICE_DIFF"])

cfg = yaml.safe_load((ROOT / "configs/project.yaml").read_text(encoding="utf-8"))
synth = cfg["data"]["synthetic"]
for split, n in synth["counts"].items():
    record(f"synthetic_count:{split}", sum(synth["type_counts"][split].values()) == n)
sets = {k:set(v) for k,v in synth["templates"].items()}
record("template_split_disjoint", not (sets["train"] & sets["validation"] or sets["train"] & sets["test"] or sets["validation"] & sets["test"]))
record("total_synthetic_planned_224", sum(synth["counts"].values()) == 224)
record("config_not_measured", cfg["project"]["status"] == "planned_not_executed")
record("no_model_revision_fabricated", cfg["model"]["revision"] is None)

# v3 planning: English source, user GPU, RunPod budget constraints (not account access).
record("english_primary_dataset", cfg["data"]["english_invoice_ocr"]["dataset_id"] == "alamgirqazi/invoice-ocr-synthetic")
record("english_locale", cfg["scope"]["language"] == "en")
record("english_group_key", cfg["data"]["english_invoice_ocr"]["grouped_split_key"] == "full_file_name_plus_business_content_components")
record("english_quality_three", set(cfg["data"]["english_invoice_ocr"]["quality_values"]) == {"clean", "faded", "bad_scan"})
record("local_16gb", cfg["hardware"]["local_vram_gb"] == 16)
record("runpod_primary", cfg["hardware"]["primary_runtime"] == "runpod_pod")
record("budget_guard", cfg["hardware"]["spend_soft_stop_usd"] + cfg["hardware"]["reserve_usd"] <= cfg["hardware"]["prepaid_balance_usd_user_reported"] and not cfg["hardware"]["allowed_new_charge_without_approval"])

results = read_json("reports/RESULTS_TEMPLATE.json")
record("unmeasured_metrics_null", results["status"] == "not_run" and all(v is None for v in results["metrics"].values()))

links = 0
for md in ROOT.rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = target.strip().split(" ", 1)[0]
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        rel = unquote(target.split("#", 1)[0])
        if rel:
            links += 1
            record(f"link:{md.relative_to(ROOT)}:{rel}", (md.parent / rel).exists())
record("local_links_checked", links > 10, f"{links} local Markdown links")

report = {
    "scope": "planning-package-only; not data download, application, training, or serving validation",
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "pass" if all(x["status"] == "pass" for x in checks) else "failed",
    "checks": checks,
    "not_performed": ["full_dataset_download", "synthetic_image_rendering", "VLM_inference", "QLoRA_training", "GPU_API", "application_tests"],
}
path = ROOT / "reports/PACK_VALIDATION.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{report['status']}: {len(checks)} package checks; report={path}")
for check in checks:
    if check["status"] != "pass":
        print(check)
raise SystemExit(0 if report["status"] == "pass" else 1)
