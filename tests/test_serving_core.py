"""Regression tests for the serving core (P12): bounded queue -> 429, deadline cancellation -> 504 with the worker
freed (no orphan generation), queue-expired requests, backend errors, input validation. No model is loaded: a
test-only generator stands in for the GPU. It exists only in this file, never in a serving path."""
import base64
import io
import threading
import time

from fastapi.testclient import TestClient
from PIL import Image

from invoiceguard.serving.core import BaseEngine, Job, create_app


class StepEngine(BaseEngine):
    """Generates `steps` tokens, one per `step_s`, checking job.should_stop() before each step like the real
    StoppingCriteria. `release` can hold a job at its first step so the tests can fill the queue deterministically."""

    has_adapter = True
    adapter_sha = "test"

    def __init__(self, steps=5, step_s=0.01, fail=False, max_queue=2):
        self.steps, self.step_s, self.fail = steps, step_s, fail
        self.release = threading.Event()
        self.release.set()
        self.started = threading.Event()
        self.generated = []  # token counts actually produced per job
        super().__init__(max_queue=max_queue)

    def _generate(self, job: Job) -> dict:
        self.started.set()
        if self.fail:
            raise RuntimeError("backend exploded")
        self.release.wait(10)
        n, hit = 0, False
        for _ in range(min(self.steps, job.max_tokens)):
            if job.should_stop():
                hit = True
                break
            time.sleep(self.step_s)
            n += 1
        self.generated.append(n)
        return {"text": f"{job.model}:{n}", "finish_reason": "timeout" if hit else "stop",
                "prompt_tokens": 7, "completion_tokens": n, "gpu_seconds": 0.0}


def _body(model="m1", timeout_s=None, url=None):
    if url is None:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
        url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    body = {"model": model, "max_tokens": 64,
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}},
                                                      {"type": "text", "text": "extract"}]}]}
    if timeout_s is not None:
        body["timeout_s"] = timeout_s
    return body


def _wait_idle(engine, limit=5.0):
    end = time.monotonic() + limit
    while (engine.busy.is_set() or engine.jobs.qsize()) and time.monotonic() < end:
        time.sleep(0.01)
    return not engine.busy.is_set() and engine.jobs.qsize() == 0


def test_normal_request_returns_openai_shape():
    engine = StepEngine(steps=3)
    r = TestClient(create_app(engine, max_new_tokens=64)).post("/v1/chat/completions", json=_body())
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "m1:3" and data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"] == {"prompt_tokens": 7, "completion_tokens": 3} and data["adapter_sha256"] == "test"


def test_deadline_stops_generation_and_frees_the_worker():
    engine = StepEngine(steps=10_000, step_s=0.01)  # would run ~100 s without cancellation
    client = TestClient(create_app(engine, max_new_tokens=100_000, default_timeout_s=5))
    t0 = time.monotonic()
    r = client.post("/v1/chat/completions", json=_body(timeout_s=0.3))
    assert r.status_code == 504 and r.json()["error"]["code"] == "timeout"
    assert time.monotonic() - t0 < 3  # returned near the deadline, not after the full generation
    assert _wait_idle(engine) and engine.generated[-1] < 200  # generation actually stopped: no orphan run


def test_queue_full_returns_429_and_recovers():
    engine = StepEngine(steps=1, max_queue=1)
    client = TestClient(create_app(engine, max_new_tokens=64))
    engine.release.clear()  # the first job blocks inside the worker
    results = []
    first = threading.Thread(target=lambda: results.append(client.post("/v1/chat/completions", json=_body()).status_code))
    first.start()
    assert engine.started.wait(5)
    second = threading.Thread(target=lambda: results.append(client.post("/v1/chat/completions", json=_body()).status_code))
    second.start()
    end = time.monotonic() + 5
    while engine.jobs.qsize() < 1 and time.monotonic() < end:  # the second request now waits in the queue
        time.sleep(0.01)
    third = client.post("/v1/chat/completions", json=_body())
    assert third.status_code == 429 and third.json()["error"]["code"] == "busy"
    engine.release.set()
    first.join(10)
    second.join(10)
    assert sorted(results) == [200, 200]
    assert client.post("/v1/chat/completions", json=_body()).status_code == 200  # serves again after the burst


def test_request_that_expires_in_the_queue_is_not_generated():
    engine = StepEngine(steps=1)
    client = TestClient(create_app(engine, max_new_tokens=64, default_timeout_s=5))
    engine.release.clear()
    first = threading.Thread(target=lambda: client.post("/v1/chat/completions", json=_body(timeout_s=5)))
    first.start()
    assert engine.started.wait(5)
    out = {}
    late = threading.Thread(target=lambda: out.setdefault("r", client.post("/v1/chat/completions", json=_body(timeout_s=0.2))))
    late.start()
    time.sleep(0.5)  # the queued request's deadline passes while the first job holds the worker
    engine.release.set()
    first.join(10)
    late.join(10)
    assert out["r"].status_code == 504 and out["r"].json()["error"]["code"] == "timeout_in_queue"
    assert len(engine.generated) == 1  # only the first job generated tokens


def test_backend_error_is_500_and_the_worker_keeps_serving():
    engine = StepEngine(fail=True)
    client = TestClient(create_app(engine, max_new_tokens=64))
    r = client.post("/v1/chat/completions", json=_body())
    assert r.status_code == 500 and "backend exploded" in r.json()["error"]["code"]
    engine.fail = False
    assert client.post("/v1/chat/completions", json=_body()).status_code == 200


def test_input_validation_and_model_names():
    engine = StepEngine()
    client = TestClient(create_app(engine, max_new_tokens=64))
    assert client.post("/v1/chat/completions", json=_body(url="https://example.com/a.png")).status_code == 400
    assert client.post("/v1/chat/completions", json=_body(model="gpt-4")).status_code == 404
    engine.has_adapter = False
    assert client.post("/v1/chat/completions", json=_body(model="m1")).status_code == 404
    health = client.get("/health").json()
    assert health["busy"] is False and health["queued"] == 0
