"""P8a (plan.md): make a servable bf16 model from the QLoRA adapter without the precision mismatch.

The adapter was trained on the NF4-quantised base. Serving it on the original bf16 base changes the weights it was
trained against (P3: field accuracy 0.960 -> 0.847 on the same 20 dev documents, the document-total block dropped).
Here the NF4 base is dequantised to bf16 first — exactly the weights the adapter saw during training — and the LoRA
is merged into those weights. The result is a plain bf16 checkpoint that vLLM (or any server) can load without LoRA.

Usage (repo root, .venv-ml): python scripts/quant/merge_dequantized.py --adapter artifacts/adapters/m1_standard_v1 \
                                 --out models/merged/m1_v1_nf4deq_bf16
Writes the checkpoint + processor files + merge_metadata.json (input/output SHA256). models/ is git-ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(1 << 22):
            h.update(b)
    return h.hexdigest()


def clean_config(config) -> None:
    """Drop the bitsandbytes leftovers (quantization_config, _pre_quantization_dtype) from the config and every
    sub-config, and turn any torch.dtype value into its string, so save_pretrained can write plain JSON
    (first P8a run, 2026-11-14: "Object of type dtype is not JSON serializable")."""
    import torch

    configs = [config] + [getattr(config, k) for k in ("text_config", "vision_config") if hasattr(config, k)]
    for cfg in configs:
        for attr in ("quantization_config", "_pre_quantization_dtype"):
            if attr in cfg.__dict__:
                delattr(cfg, attr)
        for key, value in list(cfg.__dict__.items()):
            if isinstance(value, torch.dtype):
                setattr(cfg, key, str(value).replace("torch.", ""))
    config.dtype = "bfloat16"


def main() -> int:
    import torch
    from peft import PeftModel

    from invoiceguard.vlm import MODEL_DIR, MODEL_REVISION
    from invoiceguard.vlm.model import load_base

    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-merge", action="store_true",
                    help="save only the dequantised bf16 base; the LoRA is then applied unmerged (no bf16 rounding of the delta)")
    a = ap.parse_args()
    adapter, out = REPO / a.adapter, REPO / a.out
    t0 = time.time()
    model = load_base(patch_embed_fp32=False, precision="nf4")  # same quantisation as training
    model = model.dequantize()  # NF4 -> bf16 weights (bitsandbytes dequantisation), vision/lm_head were never quantised
    model = model.to(torch.bfloat16)
    lin4 = [n for n, m in model.named_modules() if type(m).__name__ == "Linear4bit"]
    if lin4:
        raise SystemExit(f"dequantize left {len(lin4)} Linear4bit modules")
    if not a.no_merge:
        model = PeftModel.from_pretrained(model, str(adapter)).merge_and_unload()
    out.mkdir(parents=True, exist_ok=True)
    clean_config(model.config)
    model.save_pretrained(str(out), safe_serialization=True, max_shard_size="10GB")
    for name in ("chat_template.json", "preprocessor_config.json", "video_preprocessor_config.json", "tokenizer.json",
                 "tokenizer_config.json", "vocab.json", "merges.txt", "generation_config.json"):
        if (MODEL_DIR / name).exists() and not (out / name).exists():
            shutil.copy2(MODEL_DIR / name, out / name)
    meta = {"kind": "nf4_dequantized_bf16_base_only" if a.no_merge else "nf4_dequantized_bf16_plus_merged_lora", "base_revision": MODEL_REVISION,
            "adapter": a.adapter, "adapter_sha256": sha(adapter / "adapter_model.safetensors"),
            "seconds": round(time.time() - t0, 1),
            "files_sha256": {p.name: sha(p) for p in sorted(out.glob("*.safetensors"))}}
    (out / "merge_metadata.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
