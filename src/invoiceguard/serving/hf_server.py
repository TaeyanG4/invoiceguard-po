"""Transformers+PEFT GPU model server (the original P0 serving path), OpenAI-compatible subset, loopback only.

  .venv-ml/Scripts/python.exe -m invoiceguard.serving.hf_server --adapter artifacts/adapters/m1_standard_v1 --port 8001

* Models: "m1" (base NF4 + adapter) and "base" (same weights, adapter disabled) — identical loading to the evaluation.
* One GPU worker thread, bounded queue (MAX_QUEUE waiting) -> 429 when full. Never parallel generate on the GPU.
* Real cancellation: a StoppingCriteria checks the request deadline (default 120 s) on every decoding step, so a
  timed-out request STOPS generating (finish_reason "timeout", HTTP 504) instead of running on as an orphan.
* No request content is logged; only request_id, model, timings and token counts.
* Queue, deadline and HTTP handling live in serving/core.py (torch-free, regression-tested in tests/test_serving_core.py);
  this file adds only the GPU generation.
"""
from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path

import torch
import uvicorn
from transformers import StoppingCriteria, StoppingCriteriaList

from ..vlm import MODEL_REVISION, REPO
from ..vlm.sft import MAX_NEW_TOKENS, load_processor, user_messages
from .core import DEFAULT_TIMEOUT_S, MAX_QUEUE, BaseEngine, Job, create_app  # noqa: F401 - re-exported constants


class Deadline(StoppingCriteria):
    def __init__(self, job: Job):
        self.job, self.hit = job, False

    def __call__(self, input_ids, scores, **kwargs) -> bool:
        if self.job.should_stop():
            self.hit = True
            return True
        return False


class Engine(BaseEngine):
    model_revision = MODEL_REVISION

    def __init__(self, adapter: Path | None):
        from peft import PeftModel

        from ..vlm.model import load_base

        self.processor = load_processor()
        self.processor.tokenizer.padding_side = "left"
        model = load_base()
        if adapter:
            from ..vlm.pairing import check as check_pairing

            check_pairing(adapter, "nf4", MODEL_REVISION)  # this server loads the NF4 base (P15)
            self.adapter_sha = hashlib.sha256((adapter / "adapter_model.safetensors").read_bytes()).hexdigest()
            model = PeftModel.from_pretrained(model, str(adapter))
        self.model = model.eval()
        self.has_adapter = adapter is not None
        super().__init__()

    def _generate(self, job: Job) -> dict:
        text = self.processor.apply_chat_template(user_messages(job.prompt), tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[text], images=[job.image], return_tensors="pt").to(self.model.device)
        stopper = Deadline(job)
        start = time.perf_counter()
        kwargs = dict(max_new_tokens=job.max_tokens, do_sample=False, temperature=None, top_p=None, top_k=None,
                      stopping_criteria=StoppingCriteriaList([stopper]))
        with torch.inference_mode():
            if job.model == "base" and self.has_adapter:
                with self.model.disable_adapter():
                    out = self.model.generate(**inputs, **kwargs)
            else:
                out = self.model.generate(**inputs, **kwargs)
        torch.cuda.synchronize()
        new = out[0, inputs["input_ids"].shape[1]:]
        eos = self.model.generation_config.eos_token_id
        eos = set(eos if isinstance(eos, list) else [eos])
        tokens = [int(t) for t in new]
        stopped = any(t in eos for t in tokens)
        if stopped:
            tokens = tokens[: next(i for i, t in enumerate(tokens) if t in eos)]
        finish = "timeout" if stopper.hit else ("stop" if stopped else "length")
        return {"text": self.processor.tokenizer.decode(tokens, skip_special_tokens=True), "finish_reason": finish,
                "prompt_tokens": int(inputs["input_ids"].shape[1]), "completion_tokens": len(tokens),
                "gpu_seconds": round(time.perf_counter() - start, 3)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    engine = Engine(REPO / args.adapter if args.adapter else None)
    uvicorn.run(create_app(engine, MAX_NEW_TOKENS), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
