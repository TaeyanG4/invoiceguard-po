"""Torch-free serving core: one worker thread, bounded queue, per-request deadline, OpenAI-compatible HTTP subset.

hf_server.Engine subclasses BaseEngine and supplies the real GPU generation. Keeping the queue/deadline/HTTP logic
here lets the regression tests (tests/test_serving_core.py) exercise 429 / 504 / cancellation / error paths in the
CPU CI without a model. A test-only generator lives in the tests, never in a serving path (no hidden fallback).
"""
from __future__ import annotations

import base64
import io
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from PIL import Image

MAX_QUEUE = 2
DEFAULT_TIMEOUT_S = 120.0
MAX_IMAGE_PIXELS = 20_000_000


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

    def should_stop(self) -> bool:
        """Checked by the generator on every decoding step: cancelled or past the deadline -> stop generating."""
        return self.cancel.is_set() or time.monotonic() > self.deadline


class BaseEngine:
    """Subclasses implement _generate(job) -> {"text", "finish_reason", "prompt_tokens", "completion_tokens", "gpu_seconds"};
    finish_reason "timeout" means generation stopped at the deadline (it must check job.should_stop() each step)."""

    model_revision: str | None = None
    adapter_sha: str | None = None
    has_adapter: bool = False
    extra_adapters: dict[str, str] = {}  # served name -> adapter SHA-256, beside "m1" on the same base (multi-LoRA)

    def served(self) -> dict[str, str | None]:
        """Every model name this engine answers, with the adapter SHA-256 behind it (None = base weights only)."""
        return {"base": None, **({"m1": self.adapter_sha} if self.has_adapter else {}), **self.extra_adapters}

    def __init__(self, max_queue: int = MAX_QUEUE) -> None:
        self.jobs: queue.Queue[Job] = queue.Queue(maxsize=max_queue)
        self.busy = threading.Event()
        self.log: list[dict] = []
        threading.Thread(target=self._worker, daemon=True).start()

    def _generate(self, job: Job) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError

    def _worker(self) -> None:
        while True:
            job = self.jobs.get()
            self.busy.set()
            try:
                if time.monotonic() > job.deadline:
                    job.result = {"error": "timeout_in_queue"}
                else:
                    job.result = self._generate(job)
            except Exception as exc:  # noqa: BLE001 - recorded and returned as 500, the worker keeps serving
                job.result = {"error": repr(exc)[:200]}
            finally:
                self.busy.clear()
                job.done.set()
                self.log.append({"request_id": job.request_id, "model": job.model,
                                 **{k: v for k, v in (job.result or {}).items() if k != "text"}})


def decode_image(url: str) -> Image.Image:
    if not url.startswith("data:image/"):
        raise ValueError("only inline data: image URLs are accepted (no remote fetch)")
    raw = base64.b64decode(url.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as img:
        if img.size[0] * img.size[1] > MAX_IMAGE_PIXELS:
            raise ValueError("image too large")
        return img.convert("RGB")


def create_app(engine: BaseEngine, max_new_tokens: int, default_timeout_s: float = DEFAULT_TIMEOUT_S) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok", "model_revision": engine.model_revision, "adapter_sha256": engine.adapter_sha,
                "adapters": {k: v for k, v in engine.served().items() if v}, "busy": engine.busy.is_set(), "queued": engine.jobs.qsize()}

    @app.get("/v1/models")
    def models():
        return {"data": [{"id": name} for name in engine.served()]}

    @app.post("/v1/chat/completions")
    def chat(body: dict = Body(...)):
        model = body.get("model", "m1")
        if model not in engine.served():
            return JSONResponse({"error": {"code": "unknown_model"}}, status_code=404)
        try:
            content = body["messages"][-1]["content"]
            prompt = "".join(c.get("text", "") for c in content if c.get("type") == "text")
            image = decode_image(next(c["image_url"]["url"] for c in content if c.get("type") == "image_url"))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": {"code": "bad_request", "message": str(exc)[:200]}}, status_code=400)
        timeout = min(float(body.get("timeout_s", default_timeout_s)), default_timeout_s)
        job = Job(model, prompt, image, min(int(body.get("max_tokens", max_new_tokens)), max_new_tokens),
                  time.monotonic() + timeout)
        try:
            engine.jobs.put_nowait(job)
        except queue.Full:
            return JSONResponse({"error": {"code": "busy", "message": "queue full"}}, status_code=429)
        start = time.perf_counter()
        job.done.wait(timeout + 30)
        res = job.result or {"error": "no_result"}
        if "error" in res:
            return JSONResponse({"error": {"code": res["error"]}, "request_id": job.request_id},
                                status_code=504 if "timeout" in res["error"] else 500)
        if res["finish_reason"] == "timeout":
            return JSONResponse({"error": {"code": "timeout", "message": "generation stopped at deadline"},
                                 "request_id": job.request_id, "gpu_seconds": res["gpu_seconds"]}, status_code=504)
        return {"id": job.request_id, "object": "chat.completion", "model": model,
                "adapter_sha256": engine.served()[model],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": res["text"]}, "finish_reason": res["finish_reason"]}],
                "usage": {"prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"]},
                "timing": {"gpu_seconds": res["gpu_seconds"], "wall_seconds": round(time.perf_counter() - start, 3)}}

    return app
