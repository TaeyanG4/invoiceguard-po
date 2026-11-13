"""NF4 4-bit loading (same for M0 and M1), language-only LoRA, trainability checks, greedy generation."""
from __future__ import annotations

import re
import time

import torch

from . import MODEL_DIR

# LoRA only on the language backbone's attention q/v projections (configs/project.yaml training.*)
LORA_TARGET_REGEX = r"model\.language_model\.layers\.\d+\.self_attn\.(q_proj|v_proj)"
LORA = {"r": 8, "lora_alpha": 16, "lora_dropout": 0.05}
# Vision tower and merger stay un-quantised (bf16) and frozen for BOTH M0 and M1, preserving reading
# quality; recorded in run metadata so the comparison condition is explicit.
SKIP_QUANT_MODULES = ["visual", "lm_head"]


def bnb_config():
    from transformers import BitsAndBytesConfig

    return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                              bnb_4bit_compute_dtype=torch.bfloat16, llm_int8_skip_modules=SKIP_QUANT_MODULES)


def load_base(model_dir=MODEL_DIR):
    from transformers import Qwen3VLForConditionalGeneration

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required; no CPU/mock fallback (CLAUDE.md contract 6)")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(model_dir), quantization_config=bnb_config(), dtype=torch.bfloat16, device_map={"": 0},
        attn_implementation="sdpa")
    model.eval()
    return model


def attach_lora(model):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                            gradient_checkpointing_kwargs={"use_reentrant": False})
    cfg = LoraConfig(target_modules=LORA_TARGET_REGEX, bias="none", task_type="CAUSAL_LM", **LORA)
    return get_peft_model(model, cfg)


def trainable_report(model) -> dict:
    names = [n for n, p in model.named_parameters() if p.requires_grad]
    bad = [n for n in names if "lora_" not in n or "visual" in n or not re.search(r"language_model\.layers\.\d+\.self_attn\.(q_proj|v_proj)", n)]
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {"trainable_tensors": len(names), "trainable_params": trainable, "total_params": total,
            "unexpected_trainable": bad[:20], "visual_trainable": any("visual" in n for n in names),
            "sample_names": names[:4]}


@torch.inference_mode()
def generate(model, processor, image, prompt: str, max_new_tokens: int = 1536) -> dict:
    from .sft import user_messages

    text = processor.apply_chat_template(user_messages(prompt), tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], return_tensors="pt").to(model.device)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, temperature=None,
                         top_p=None, top_k=None)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    new = out[0, inputs["input_ids"].shape[1]:]
    eos = set(model.generation_config.eos_token_id if isinstance(model.generation_config.eos_token_id, list)
              else [model.generation_config.eos_token_id])
    finished = len(new) > 0 and int(new[-1]) in eos
    return {"raw_response": processor.tokenizer.decode(new, skip_special_tokens=True),
            "generated_tokens": int(len(new)), "input_tokens": int(inputs["input_ids"].shape[1]),
            "finish_reason": "stop" if finished else ("length" if len(new) >= max_new_tokens else "unknown"),
            "latency_s": round(elapsed, 3), "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3)}
