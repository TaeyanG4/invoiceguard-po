"""Transformers+PEFT GPU model server (the original P0 serving path), OpenAI-compatible subset, loopback only.

  .venv-ml/Scripts/python.exe -m invoiceguard.serving.hf_server --adapter artifacts/adapters/m1_standard_v1 --port 8001

* Models: "m1" (base NF4 + adapter) and "base" (same weights, adapter disabled) — identical loading to the evaluation.
* One GPU worker thread, bounded queue (MAX_QUEUE waiting) -> 429 when full. Never parallel generate on the GPU.
* Real cancellation: a StoppingCriteria checks the request deadline (default 120 s) on every decoding step, so a
  timed-out request STOPS generating (finish_reason "timeout", HTTP 504) instead of running on as an orphan.
* No request content is logged; only request_id, model, timings and token counts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import torch
import uvicorn
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from PIL import Image
from transformers import StoppingCriteria, StoppingCriteriaList

from ..vlm import MODEL_REVISION, REPO
from ..vlm.sft import MAX_NEW_TOKENS, load_processor, user_messages

MAX_QUEUE = 2
DEFAULT_TIMEOUT_S = 120.0


class Deadline(StoppingCriteria):
    def __init__(self, deadline: float, cancel: threading.Event):
        self.deadline, self.cancel, self.hit = deadline, cancel, False

    def __call__(self, input_ids, scores, **kwargs) -> bool:
        if self.cancel.is_set() or time.monotonic() > self.deadline:
            self.hit = True
            return True
        return False


@dataclass
class Job:
    model: str
    prompt: str
    image: Image.Image
    max_tokens: int
    deadline: float
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    done: threading.Event = field(default_factory=threading.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    result: dict | None = None


class Engine:
    def __init__(self, adapter: Path | None):
        from peft import PeftModel

        from ..vlm.model import load_base

        self.processor = load_processor()
        self.processor.tokenizer.padding_side = "left"
        model = load_base()
        self.adapter_sha = None
        if adapter:
            self.adapter_sha = hashlib.sha256((adapter / "adapter_model.safetensors").read_bytes()).hexdigest()
            model = PeftModel.from_pretrained(model, str(adapter))
        self.model = model.eval()
        self.has_adapter = adapter is not None
        self.jobs: queue.Queue[Job] = queue.Queue(maxsize=MAX_QUEUE)
        self.busy = threading.Event()
        self.log: list[dict] = []
        threading.Thread(target=self._worker, daemon=True).start()

    def _generate(self, job: Job) -> dict:
        text = self.processor.apply_chat_template(user_messages(job.prompt), tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[text], images=[job.image], return_tensors="pt").to(self.model.device)
        stopper = Deadline(job.deadline, job.cancel)
        start = time.perf_counter()
        with torch.inference_mode():
            if job.model == "base" and self.has_adapter:
                with self.model.disable_adapter():
                    out = self.model.generate(**inputs, max_new_tokens=job.max_tokens, do_sample=False, temperature=None,
                                              top_p=None, top_k=None, stopping_criteria=StoppingCriteriaList([stopper]))
            else:
                out = self.model.generate(**inputs, max_new_tokens=job.max_tokens, do_sample=False, temperature=None,
                                          top_p=None, top_k=None, stopping_criteria=StoppingCriteriaList([stopper]))
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

    def _worker(self) -> None:
        while True:
            job = self.jobs.get()
            self.busy.set()
            try:
                if time.monotonic() > job.deadline:
                    job.result = {"error": "timeout_in_queue"}
                else:
                    job.result = self._generate(job)
            except Exception as exc:  # noqa: BLE001
                job.result = {"error": repr(exc)[:200]}
            finally:
                self.busy.clear()
                job.done.set()
                self.log.append({"request_id": job.request_id, "model": job.model,
                                 **{k: v for k, v in (job.result or {}).items() if k != "text"}})


def _decode_image(url: str) -> Image.Image:
    if not url.startswith("data:image/"):
        raise ValueError("only inline data: image URLs are accepted (no remote fetch)")
    raw = base64.b64decode(url.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as img:
        if img.size[0] * img.size[1] > 20_000_000:
            raise ValueError("image too large")
        return img.convert("RGB")


def create_app(engine: Engine) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok", "model_revision": MODEL_REVISION, "adapter_sha256": engine.adapter_sha,
                "busy": engine.busy.is_set(), "queued": engine.jobs.qsize()}

    @app.get("/v1/models")
    def models():
        return {"data": [{"id": "base"}] + ([{"id": "m1"}] if engine.has_adapter else [])}

    @app.post("/v1/chat/completions")
    def chat(body: dict = Body(...)):
        model = body.get("model", "m1")
        if model not in ("base", "m1") or (model == "m1" and not engine.has_adapter):
            return JSONResponse({"error": {"code": "unknown_model"}}, status_code=404)
        try:
            content = body["messages"][-1]["content"]
            prompt = "".join(c.get("text", "") for c in content if c.get("type") == "text")
            image = _decode_image(next(c["image_url"]["url"] for c in content if c.get("type") == "image_url"))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": {"code": "bad_request", "message": str(exc)[:200]}}, status_code=400)
        timeout = min(float(body.get("timeout_s", DEFAULT_TIMEOUT_S)), DEFAULT_TIMEOUT_S)
        job = Job(model, prompt, image, min(int(body.get("max_tokens", MAX_NEW_TOKENS)), MAX_NEW_TOKENS),
                  time.monotonic() + timeout)
        try:
            engine.jobs.put_nowait(job)
        except queue.Full:
            return JSONResponse({"error": {"code": "busy", "message": "queue full"}}, status_code=429)
        start = time.perf_counter()
        job.done.wait(timeout + 30)
        res = job.result or {"error": "no_result"}
        if "error" in res:
            return JSONResponse({"error": {"code": res["error"]}, "request_id": job.request_id}, status_code=504 if "timeout" in res["error"] else 500)
        if res["finish_reason"] == "timeout":
            return JSONResponse({"error": {"code": "timeout", "message": "generation stopped at deadline"},
                                 "request_id": job.request_id, "gpu_seconds": res["gpu_seconds"]}, status_code=504)
        return {"id": job.request_id, "object": "chat.completion", "model": model,
                "adapter_sha256": engine.adapter_sha if model == "m1" else None,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": res["text"]}, "finish_reason": res["finish_reason"]}],
                "usage": {"prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"]},
                "timing": {"gpu_seconds": res["gpu_seconds"], "wall_seconds": round(time.perf_counter() - start, 3)}}

    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    engine = Engine(REPO / args.adapter if args.adapter else None)
    uvicorn.run(create_app(engine), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
