"""Summarise the P3/P5 precision runs (plan.md): the same 20 own-dev documents through the HF reference path with
base precision nf4 (existing m0_dev_v1 / m1_dev_v1), int8, bf16, fp16, fp32, plus the RunPod vLLM bf16 run.

Per run: strict field accuracy (same scorer as dev/final; failures stay in the denominator), per-field accuracy,
how many documents keep all four document-total fields, mean generated tokens, latency per document, peak VRAM.
For the vLLM run, generated-token counts per document are compared with each HF run (raw text was not stored).

Usage (repo root): python scripts/quant/compare_precision.py  -> reports/quant/precision_dev20.{json,md}
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.evaluation import parse_for_eval, score_trade_document  # noqa: E402

PRED = REPO / "artifacts" / "predictions"
TOTALS = ("subtotal_raw", "tax_raw", "discount_raw", "total_raw")
RUNS = {  # (arm, precision) -> prediction run id
    ("m0", "nf4"): "m0_dev_v1", ("m1", "nf4"): "m1_dev_v1",
    **{(arm, p): f"prec_{arm}_{p}_dev20" for arm in ("m0", "m1") for p in ("int8", "bf16", "fp16", "fp32")},
    ("m1", "nf4-dequantised bf16 + merged LoRA"): "prec_m1merged_bf16_dev20",
    ("m1", "nf4-dequantised bf16 + unmerged LoRA"): "prec_m1deqlora_bf16_dev20",
}


def load(run: str) -> dict:
    path = PRED / run / "predictions.jsonl"
    if not path.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> int:
    bench = json.loads((REPO / "reports" / "serving" / "vllm_bf16_a40.json").read_text(encoding="utf-8"))
    docs = bench["docs"]  # the 20 trade:dev documents used by both the vLLM bench and the HF runs
    vllm_tokens = {arm: {r["id"]: r.get("completion_tokens") for r in bench["arms"][arm]["requests_c1"]} for arm in ("m0", "m1")}
    vllm_tokens["m1merged"] = vllm_tokens["m1"]
    vllm_acc = {arm: bench["arms"][arm]["server_field_accuracy"] for arm in ("m0", "m1")}
    gold = {d: json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{d}.json").read_text(encoding="utf-8")) for d in docs}
    out = {"documents": docs, "set": "trade:dev first 20 (= vLLM bench documents)", "runs": {}}
    for (arm, prec), run in RUNS.items():
        preds = load(run)
        if not all(d in preds for d in docs):
            out["runs"][f"{arm}/{prec}"] = {"run": run, "status": "not_run" if not preds else f"incomplete {sum(d in preds for d in docs)}/20"}
            continue
        meta_path = PRED / run / "run_metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        correct = scored = 0
        per_field: dict[str, list[int]] = {}
        totals_kept, toks, lat = 0, [], []
        for d in docs:
            s = score_trade_document(gold[d], parse_for_eval(preds[d], "TRADE_RAW"))
            for k, (c, n) in s["fields"].items():
                correct, scored = correct + c, scored + n
                per_field.setdefault(k, [0, 0])
                per_field[k][0] += c
                per_field[k][1] += n
            raw = preds[d].get("raw_response") or ""
            totals_kept += all(f'"{k}"' in raw for k in TOTALS)
            toks.append(preds[d].get("generated_tokens", 0))
            if preds[d].get("batch_latency_s") is not None:
                lat.append(preds[d]["batch_latency_s"])
        vt = vllm_tokens[arm]
        tok_match = sum(1 for d in docs if vt.get(d) is not None and abs((vt[d] or 0) - preds[d].get("generated_tokens", 0)) <= 1)
        out["runs"][f"{arm}/{prec}"] = {
            "run": run, "status": "ok", "field_accuracy": round(correct / scored, 4), "correct": correct, "scored": scored,
            "per_field": {k: round(c / n, 4) for k, (c, n) in per_field.items() if n},
            "docs_with_all_four_totals": totals_kept, "mean_generated_tokens": round(statistics.mean(toks), 1),
            "mean_latency_s_per_doc": round(statistics.mean(lat), 2) if lat else None,
            "peak_vram_gb": meta.get("peak_vram_gb"), "gpu": (meta.get("env") or {}).get("gpu"),
            "token_count_within_1_of_vllm": f"{tok_match}/20"}
    out["vllm_bf16_a40"] = {"field_accuracy": vllm_acc, "note": "RunPod A40, vLLM 0.11.2, bf16 base (+ LoRA m1 for M1); raw text not stored"}
    qdir = REPO / "reports" / "quant"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "precision_dev20.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = ["| arm / base precision | field acc | docs with all 4 totals | mean tokens | s / doc | peak VRAM GB | tokens ≈ vLLM |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for key, r in out["runs"].items():
        if r["status"] != "ok":
            lines.append(f"| {key} | {r['status']} | | | | | |")
            continue
        lines.append(f"| {key} | {r['field_accuracy']:.3f} ({r['correct']}/{r['scored']}) | {r['docs_with_all_four_totals']}/20 | "
                     f"{r['mean_generated_tokens']} | {r['mean_latency_s_per_doc']} | {r['peak_vram_gb']} | {r['token_count_within_1_of_vllm']} |")
    lines.append(f"| vLLM bf16 (A40) m0 / m1 | {vllm_acc['m0']:.3f} / {vllm_acc['m1']:.3f} | | | | | |")
    (qdir / "precision_dev20.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
