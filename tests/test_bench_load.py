"""Serving bench load levels score every answer, not only latency (astra review 3), CPU only with a fake server."""
import time
from dataclasses import dataclass
from pathlib import Path

from invoiceguard.serving import vllm_bench


@dataclass
class Doc:
    record_id: str

    @property
    def image_path(self) -> Path:
        return Path(f"{self.record_id}.png")

    def prompt(self) -> str:
        return "p"


def _fake(answers: dict, delay: float = 0.0):
    """Answer by document (image name), so the result does not depend on thread completion order."""
    calls = []

    def request(model, prompt, image_path):
        calls.append(model)
        time.sleep(delay)
        return answers.get(Path(image_path).stem, answers.get("*"))
    return request, calls


def test_each_load_level_scores_answers_counts_truncation_and_status_codes(monkeypatch):
    monkeypatch.setattr(vllm_bench, "_fields", lambda rid, raw, fin: (2, 2) if raw == "good" else (0, 2))
    monkeypatch.setattr(vllm_bench, "_gpu_mem_mb", lambda: 1000)
    answers = {"a": {"ok": True, "latency_s": 1.0, "raw_response": "good", "finish_reason": "stop"},
               "b": {"ok": True, "latency_s": 2.0, "raw_response": "cut", "finish_reason": "length"},
               "c": {"ok": False, "latency_s": 0.1, "error": "HTTPError 429", "http_status": 429}}
    request, _ = _fake(answers)
    docs = [Doc("a"), Doc("b"), Doc("c")]
    out = vllm_bench._load("m1", docs, conc=2, reps=2, duration_s=None, c1_raw={"a": "good", "b": "good", "c": "good"}, request=request)
    assert out["requests"] == 6 and out["failures"] == 2 and out["status_codes"] == {"200": 4, "429": 2}
    assert out["fields"] == [4, 8] and out["field_accuracy"] == 0.5 and out["truncated"] == 2
    assert out["identical_to_concurrency1_rate"] == 0.5  # 2 of 4 answers equal the concurrency-1 answer


def test_sustained_load_keeps_requests_in_flight_until_the_time_is_up(monkeypatch):
    monkeypatch.setattr(vllm_bench, "_fields", lambda rid, raw, fin: (1, 1))
    monkeypatch.setattr(vllm_bench, "_gpu_mem_mb", lambda: None)
    request, calls = _fake({"*": {"ok": True, "latency_s": 0.02, "raw_response": "x", "finish_reason": "stop"}}, delay=0.02)
    out = vllm_bench._load("m0", [Doc("a"), Doc("b")], conc=3, reps=1, duration_s=0.3, c1_raw={}, request=request)
    assert out["sustained_s"] == 0.3 and out["requests"] == len(calls) > 6 and out["failures"] == 0
    assert out["field_accuracy"] == 1.0 and out["wall_s"] >= 0.3
