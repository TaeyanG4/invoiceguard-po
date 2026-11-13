"""Local GPU smoke (RTX 4070 Ti SUPER) BEFORE any paid RunPod time.

Usage (.venv-ml):
  python -m invoiceguard.vlm.smoke masks     # M01 over every standard train record (processor only)
  python -m invoiceguard.vlm.smoke pilot     # 8 TRAIN images, base NF4 greedy: tokens/latency/VRAM/parse
  python -m invoiceguard.vlm.smoke train     # 10 optimizer steps, grads/updates, save, full reload, 1 inference

Outputs go to reports/model/local_smoke_*.json (+ raw responses under artifacts/runs/). Train data only;
dev/final images are never touched here. This is NOT the M1 training run: M1 restarts from the clean base.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import random
import statistics
import time
from pathlib import Path

import torch

from ..model_output import parse_response
from . import MODEL_DIR, MODEL_ID, MODEL_REVISION, REPO
from .records import public_records, trade_records
from .sft import IGNORE, MAX_PIXELS, encode, load_processor

OUT = REPO / "reports" / "model"
RUNS = REPO / "artifacts" / "runs"
SEED = 20261113


def _env() -> dict:
    import bitsandbytes
    import peft
    import transformers

    return {"host": "local_workstation", "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "torch": torch.__version__, "cuda": torch.version.cuda, "transformers": transformers.__version__,
            "peft": peft.__version__, "bitsandbytes": bitsandbytes.__version__, "python": platform.python_version(),
            "model_id": MODEL_ID, "model_revision": MODEL_REVISION, "max_pixels": MAX_PIXELS,
            "precision": "nf4_double_quant_bf16_compute; vision+lm_head not quantised"}


def _write(name: str, data: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def _records() -> list:
    return public_records() + trade_records()


def cmd_masks() -> int:
    processor = load_processor()
    stats, failures = [], []
    for rec in _records():
        enc = encode(processor, rec.image(), rec.prompt(), rec.answer)
        stats.append({"id": rec.record_id, "task": rec.task, "image_tokens": enc.n_image_tokens,
                      "prompt_tokens": enc.n_prompt, "answer_tokens": enc.n_answer, "total": enc.n_total})
        if enc.check_errors:
            failures.append({"id": rec.record_id, "errors": enc.check_errors})
    by_task = {}
    for task in ("PUBLIC_CANONICAL", "TRADE_RAW"):
        rows = [s for s in stats if s["task"] == task]
        by_task[task] = {k: {"min": min(r[k] for r in rows), "median": statistics.median(r[k] for r in rows),
                             "max": max(r[k] for r in rows)} for k in ("image_tokens", "answer_tokens", "total")}
        by_task[task]["records"] = len(rows)
    result = {"kind": "M01_loss_mask_audit_expanded_image_tokens", "records": len(stats), "failures": failures,
              "pass": not failures and len(stats) > 0, "by_task": by_task, "env": _env()}
    print(_write("local_smoke_masks.json", result))
    print(json.dumps({"records": len(stats), "failures": len(failures), "by_task": by_task}, indent=1))
    return 0 if result["pass"] else 1


def cmd_pilot() -> int:
    from .model import generate, load_base

    rng = random.Random(SEED)
    pub, trade = public_records(), trade_records()
    picks = rng.sample(pub, 4) + rng.sample(trade, 4)
    processor = load_processor()
    t0 = time.perf_counter()
    model = load_base()
    load_s = time.perf_counter() - t0
    run_dir = RUNS / f"local_pilot_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for rec in picks:
        gen = generate(model, processor, rec.image(), rec.prompt())
        parsed = parse_response(gen["raw_response"], rec.task, finish_reason=gen["finish_reason"])
        target_tokens = len(processor.tokenizer(rec.answer)["input_ids"])
        (run_dir / f"{rec.record_id}.txt").write_text(gen["raw_response"], encoding="utf-8", newline="\n")
        rows.append({"id": rec.record_id, "task": rec.task, **{k: v for k, v in gen.items() if k != "raw_response"},
                     "target_answer_tokens": target_tokens, "parse_status": parsed.status,
                     "schema_valid": parsed.schema_valid, "exact_answer_match": gen["raw_response"].strip() == rec.answer})
    result = {"kind": "local_pilot_base_nf4_train_images_only", "model_load_s": round(load_s, 1),
              "rows": rows, "raw_dir": str(run_dir.relative_to(REPO)).replace("\\", "/"), "env": _env(),
              "note": "Untuned base (M0 condition) on TRAIN images; diagnostic only, not an evaluation result."}
    print(_write("local_smoke_pilot.json", result))
    for r in rows:
        print(r["id"][:28], r["task"][:6], r["generated_tokens"], r["finish_reason"], r["latency_s"], r["peak_vram_gb"],
              r["parse_status"], r["schema_valid"])
    return 0


def _lora_snapshot(model) -> dict:
    return {n: p.detach().float().clone().cpu() for n, p in model.named_parameters() if p.requires_grad}


def cmd_train(steps: int = 10, accum: int = 8, lr: float = 1e-4) -> int:
    from peft import PeftModel

    from .model import attach_lora, generate, load_base, trainable_report

    torch.manual_seed(SEED)
    random.seed(SEED)
    processor = load_processor()
    records = _records()
    random.Random(SEED).shuffle(records)
    model = attach_lora(load_base(patch_embed_fp32=False))
    model.train()
    report = {"kind": "local_10_step_qlora_smoke", "steps": steps, "grad_accumulation": accum, "lr": lr,
              "trainable": trainable_report(model), "env": _env()}
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=lr)
    before = _lora_snapshot(model)
    log, micro, nonfinite, mask_fail = [], 0, 0, 0
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    for step in range(steps):
        losses = []
        for _ in range(accum):
            rec = records[micro % len(records)]
            micro += 1
            enc = encode(processor, rec.image(), rec.prompt(), rec.answer)
            if enc.check_errors:
                mask_fail += 1
                raise RuntimeError(f"mask check failed for {rec.record_id}: {enc.check_errors}")
            batch = {k: v.to(model.device) for k, v in enc.batch.items()}
            out = model(**batch, labels=enc.labels.unsqueeze(0).to(model.device))
            if not torch.isfinite(out.loss):
                nonfinite += 1
            (out.loss / accum).backward()
            losses.append(float(out.loss))
        grads = [p.grad for p in params if p.grad is not None]
        finite = all(torch.isfinite(g).all() for g in grads)
        nonzero = sum(int(g.abs().sum() > 0) for g in grads)
        gnorm = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        log.append({"step": step + 1, "mean_loss": round(statistics.mean(losses), 4), "grad_norm": round(gnorm, 4),
                    "grads_finite": bool(finite), "tensors_with_nonzero_grad": nonzero, "tensors_with_grad": len(grads)})
        print(log[-1])
    train_s = time.perf_counter() - t0
    after = _lora_snapshot(model)
    changed = sum(int(not torch.equal(before[n], after[n])) for n in before)
    report.update({"log": log, "micro_steps": micro, "optimizer_steps": steps, "train_seconds": round(train_s, 1),
                   "seconds_per_optimizer_step": round(train_s / steps, 2),
                   "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3),
                   "nonfinite_losses": nonfinite, "mask_failures": mask_fail,
                   "lora_tensors_changed": changed, "lora_tensors_total": len(before)})

    adapter_dir = REPO / "artifacts" / "adapters" / "local_smoke_10step"
    model.save_pretrained(str(adapter_dir))
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in adapter_dir.iterdir() if p.is_file()}
    report["adapter_dir"] = str(adapter_dir.relative_to(REPO)).replace("\\", "/")
    report["adapter_files_sha256"] = files

    # full unload, then reload base + adapter from disk and compare a LoRA tensor
    probe = next(n for n in after if "lora_B" in n)
    del model, optimizer, params
    gc.collect()
    torch.cuda.empty_cache()
    reloaded = PeftModel.from_pretrained(load_base(), str(adapter_dir))
    reloaded.eval()
    rp = dict(reloaded.named_parameters())
    probe_key = next(k for k in rp if k.endswith(probe.split("base_model.model.")[-1]))
    report["reload_tensor_equal"] = bool(torch.equal(rp[probe_key].detach().float().cpu(), after[probe]))
    rec = records[0]
    gen = generate(reloaded, processor, rec.image(), rec.prompt())
    parsed = parse_response(gen["raw_response"], rec.task, finish_reason=gen["finish_reason"])
    report["reload_inference"] = {"id": rec.record_id, "task": rec.task, "parse_status": parsed.status,
                                  "schema_valid": parsed.schema_valid,
                                  **{k: v for k, v in gen.items() if k != "raw_response"}}
    report["pass"] = (mask_fail == 0 and nonfinite == 0 and all(l["grads_finite"] for l in log) and changed > 0
                      and not report["trainable"]["unexpected_trainable"] and not report["trainable"]["visual_trainable"]
                      and report["reload_tensor_equal"])
    print(_write("local_smoke_train.json", report))
    print(json.dumps({k: report[k] for k in ("pass", "lora_tensors_changed", "lora_tensors_total", "peak_vram_gb",
                                              "seconds_per_optimizer_step", "reload_tensor_equal")}, indent=1))
    return 0 if report["pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["masks", "pilot", "train"])
    args = parser.parse_args()
    return {"masks": cmd_masks, "pilot": cmd_pilot, "train": cmd_train}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
