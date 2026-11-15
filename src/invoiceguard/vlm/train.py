"""M1 QLoRA SFT with TRL SFTTrainer + the verified completion-only collator (docs/05, docs/15 C).

Usage (.venv-ml):
  python -m invoiceguard.vlm.train --profile standard [--max-steps 80] [--run-id m1_standard_v1]

* Starts from the clean pinned base every time (never continues the smoke adapter).
* TRL's built-in assistant_only_loss needs `{% generation %}` markers in the chat template; the
  Qwen3-VL template has none, so the verified collator (vlm.sft.encode) supplies labels instead and
  every batch is re-checked (image/prompt/pad = -100, trained span decodes to the gold answer).
* No truncation: records over the sequence budget raise instead of being cut.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path

import torch

from . import MODEL_DIR, MODEL_ID, MODEL_REVISION, REPO
from .records import cord_records, cord_unit_price_records, public_records, trade_records, train_manifest_names
from .sft import IGNORE, encode, load_processor

SEED = 20261113
CONFIG = {"lr": 1e-4, "micro_batch": 1, "grad_accum": 8, "warmup_ratio": 0.05, "scheduler": "cosine",
          "max_steps": {"standard": 80, "mini": 40}}


class VerifiedCollator:
    def __init__(self, processor, records):
        self.processor, self.records = processor, records
        self.pad_id = processor.tokenizer.pad_token_id
        self.checked = 0

    def __call__(self, features):
        encoded = []
        for f in features:
            rec = self.records[f["idx"]]
            enc = encode(self.processor, rec.image(), rec.prompt(), rec.answer)
            if enc.check_errors:
                raise RuntimeError(f"loss-mask check failed for {rec.record_id}: {enc.check_errors}")
            encoded.append(enc)
            self.checked += 1
        width = max(e.n_total for e in encoded)
        ids = torch.full((len(encoded), width), self.pad_id, dtype=torch.long)
        mask = torch.zeros((len(encoded), width), dtype=torch.long)
        labels = torch.full((len(encoded), width), IGNORE, dtype=torch.long)
        for i, e in enumerate(encoded):  # right padding; pad positions stay -100
            n = e.n_total
            ids[i, :n] = e.batch["input_ids"][0]
            mask[i, :n] = e.batch["attention_mask"][0]
            labels[i, :n] = e.labels
        return {"input_ids": ids, "attention_mask": mask, "labels": labels,
                "pixel_values": torch.cat([e.batch["pixel_values"] for e in encoded]),
                "image_grid_thw": torch.cat([e.batch["image_grid_thw"] for e in encoded])}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["standard", "mini"], required=True)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--with-aug1", action="store_true", help="add the S5 train-only augmentation (manifests/trade_raw_aug1.jsonl)")
    parser.add_argument("--seed", type=int, default=SEED, help="seed variance runs (P6); the frozen M1 used 20261113")
    parser.add_argument("--base-precision", choices=["nf4", "bf16"], default="nf4",
                        help="nf4 = QLoRA (frozen recipe); bf16 = plain LoRA on the unquantised base (P14)")
    parser.add_argument("--data", choices=["all", "public_only", "all_plus_cord", "all_plus_cord_up"], default="all",
                        help="P6 ablation: public_only drops the own TRADE_RAW training documents; "
                             "all_plus_cord adds the train-eligible CORD v2 receipts (docs/20); all_plus_cord_up also repeats the "
                             "CORD receipts with a printed unit price once (docs/20 amendment 3, exploratory)")
    parser.add_argument("--lora-r", type=int, default=None, help="docs/20 amendment 5 ablation: LoRA rank (alpha = 2 r); default = recipe r 8")
    parser.add_argument("--lora-targets", choices=["qv", "qkvo"], default="qv",
                        help="docs/20 amendment 5 ablation: attention projections to adapt; default = recipe q_proj + v_proj")
    args = parser.parse_args()
    seed = args.seed

    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    from .model import ABLATION_TARGETS, attach_lora, load_base, trainable_report
    targets = ABLATION_TARGETS[args.lora_targets]
    from .smoke import _env

    role_field = f"{args.profile}_role"
    records = public_records(role_field) + (trade_records(role_field) if args.data in ("all", "all_plus_cord", "all_plus_cord_up") else [])
    if args.data in ("all_plus_cord", "all_plus_cord_up"):
        records += cord_records("train")
    if args.data == "all_plus_cord_up":
        records += cord_unit_price_records()
    if args.with_aug1:
        records += trade_records(role_field, "train", manifest="trade_raw_aug1.jsonl")
    random.Random(seed).shuffle(records)
    max_steps = args.max_steps or CONFIG["max_steps"][args.profile]
    run_id = args.run_id or f"m1_{args.profile}_{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir = REPO / "artifacts" / "adapters" / run_id
    torch.manual_seed(seed)
    random.seed(seed)
    # Optional cap on this process's GPU memory pool (allocator only — the math is unchanged). On the 16 GB Windows card
    # the caching allocator grew to ~15.9 GB while only ~7 GB was in use, so any desktop app tipped it into shared
    # system memory (5.9 -> 110-354 s/step, 2026-11-15). With a cap the allocator frees cache instead.
    mem_fraction = os.environ.get("INVOICEGUARD_CUDA_MEM_FRACTION")
    if mem_fraction:
        torch.cuda.set_per_process_memory_fraction(float(mem_fraction))

    processor = load_processor()
    template = processor.chat_template or ""
    if args.base_precision == "nf4":
        model = attach_lora(load_base(patch_embed_fp32=False), r=args.lora_r, targets=targets)  # kbit prep upcasts vision to fp32 itself
    else:  # bf16 Conv3d is the slow cuDNN path on this stack, so only the patch embed runs in fp32 (as in inference)
        model = attach_lora(load_base(patch_embed_fp32=True, precision="bf16"), quantized=False, r=args.lora_r, targets=targets)
    collator = VerifiedCollator(processor, records)
    cfg = SFTConfig(
        output_dir=str(REPO / "artifacts" / "trainer" / run_id), max_steps=max_steps,
        per_device_train_batch_size=CONFIG["micro_batch"], gradient_accumulation_steps=CONFIG["grad_accum"],
        learning_rate=CONFIG["lr"], lr_scheduler_type=CONFIG["scheduler"], warmup_ratio=CONFIG["warmup_ratio"],
        bf16=False,  # no autocast: it pushes the vision Conv3d onto the slow bf16 cuDNN path (~18 s/sample); bnb 4-bit layers still compute in bf16
        logging_steps=1, save_strategy="no", report_to="none", seed=seed, data_seed=seed,
        dataloader_num_workers=0, remove_unused_columns=False, max_length=None, packing=False,
        gradient_checkpointing=False,  # already enabled by prepare_model_for_kbit_training
        dataset_kwargs={"skip_prepare_dataset": True})
    from transformers import Trainer

    class LeanSFTTrainer(SFTTrainer):
        """TRL SFTTrainer whose compute_loss skips TRL's per-step entropy/token-accuracy metrics.

        Measured 2026-11-14: those metrics materialise extra fp32 copies of the 151,936-vocab logits each
        micro-step; on the 16 GB GPU the run grew to 14.9 GB, spilled into shared memory and stalled (GPU
        idle, 19 W). The loss itself is the standard causal-LM loss on our verified labels.
        """

        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            inputs["use_cache"] = False
            return Trainer.compute_loss(self, model, inputs, return_outputs=return_outputs,
                                        num_items_in_batch=num_items_in_batch)

    trainer = LeanSFTTrainer(model=model, args=cfg, train_dataset=Dataset.from_list([{"idx": i} for i in range(len(records))]),
                             data_collator=collator, processing_class=processor)
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    result = trainer.train()
    seconds = time.perf_counter() - t0
    model.save_pretrained(str(out_dir))

    losses = [{"step": h["step"], "loss": h["loss"], "lr": h.get("learning_rate"), "grad_norm": h.get("grad_norm")}
              for h in trainer.state.log_history if "loss" in h]
    manifests = {name: _sha(REPO / "manifests" / name) for name in train_manifest_names(args.data, args.with_aug1)}
    meta = {
        "run_id": run_id, "kind": "M1_qlora_sft",
        "framework": "trl 0.25.1 SFTTrainer (compute_loss = transformers Trainer loss; TRL logit metrics disabled for VRAM) + verified completion-only collator",
        "trl_assistant_only_loss_supported_by_template": "{% generation %}" in template,
        "profile": args.profile, "records": len(records),
        "records_by_task": {t: sum(r.task == t for r in records) for t in ("PUBLIC_CANONICAL", "TRADE_RAW", "CORD_RAW")},
        "optimizer_steps": trainer.state.global_step, "micro_steps_checked": collator.checked,
        "examples_seen": trainer.state.global_step * CONFIG["grad_accum"] * CONFIG["micro_batch"],
        "epochs_equivalent": round(trainer.state.global_step * CONFIG["grad_accum"] / len(records), 3),
        "config": CONFIG | {"max_steps": max_steps, "seed": seed, "data": args.data, "base_precision": args.base_precision,
                            "lora_r": args.lora_r or 8, "lora_alpha": 2 * (args.lora_r or 8), "lora_targets": list(targets)}, "train_seconds": round(seconds, 1),
        "train_loss": result.training_loss, "loss_log": losses,
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "trainable": trainable_report(model, targets), "base_model": MODEL_ID, "base_revision": MODEL_REVISION,
        "model_dir": str(MODEL_DIR.relative_to(REPO)).replace("\\", "/"),
        "adapter_dir": str(out_dir.relative_to(REPO)).replace("\\", "/"),
        "adapter_files_sha256": {p.name: _sha(p) for p in out_dir.iterdir() if p.is_file()},
        "train_manifests_sha256": manifests,
        "env": _env() | ({"precision": "bf16_base_unquantised; lora_fp32; patch_embed_fp32"} if args.base_precision == "bf16" else {})
        | ({"cuda_memory_fraction": float(mem_fraction), "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_CUDA_ALLOC_CONF")}
           if mem_fraction else {}),
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    report = REPO / "reports" / "model" / f"train_{run_id}.json"
    report.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: meta[k] for k in ("run_id", "optimizer_steps", "train_seconds", "train_loss", "peak_vram_gb")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
