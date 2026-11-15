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


def test_cord_task_scores_served_answers_with_the_cord_scorer_and_compares_with_cord_offline_runs(monkeypatch):
    """--task cord: positional CORD_RAW scoring with the document's masked slots, fence-stripped parse, CORD offline runs."""
    from invoiceguard import cord, cord_eval

    monkeypatch.setitem(vllm_bench.TARGET, "task", "cord")
    monkeypatch.setitem(vllm_bench.TARGET, "offline", {})
    monkeypatch.setattr(cord, "manifest_rows", lambda split: [{"id": "cord_dev_0007", "masked": ["menu.0.price"]}])
    monkeypatch.setattr(cord, "load_gold", lambda rid: {"doc": rid})
    seen = {}

    def score(gold, masked, parsed):
        seen.update(gold=gold, masked=masked, parsed=parsed)
        return {"strict": (3, 5)}
    monkeypatch.setattr(cord_eval, "score_document", score)
    assert vllm_bench._fields("cord_dev_0007", '```json\n{"menu": []}\n```', "stop") == (3, 5)
    assert seen["gold"] == {"doc": "cord_dev_0007"} and seen["masked"] == ["menu.0.price"]
    assert vllm_bench._offline_run("m1") == "cord_dev_m1cord_nf4" and vllm_bench._offline_run("m0") == "cord_dev_m0_nf4"
    monkeypatch.setitem(vllm_bench.TARGET, "offline", {"m1": "cord_dev_m1cordup_nf4"})
    assert vllm_bench._offline_run("m1") == "cord_dev_m1cordup_nf4"
    monkeypatch.setitem(vllm_bench.TARGET, "task", "trade")
    assert vllm_bench._offline_run("m1") == "m1_dev_v1"


def test_report_records_what_the_server_says_it_serves(monkeypatch):
    """Fable review 5: tie a serving report to the adapter hash the server reports, not only to a label."""
    import io
    import urllib.request

    bodies = {"health": b'{"status":"ok","adapter_sha256":"abc"}', "v1/models": b""}

    def fake_urlopen(url, timeout=10):
        route = url.split("/", 3)[3]
        if route not in bodies:
            raise OSError("down")
        return io.BytesIO(bodies[route])
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setitem(vllm_bench.TARGET, "port", 8001)
    assert vllm_bench._server_identity() == {"health": {"status": "ok", "adapter_sha256": "abc"}, "v1/models": {}}


def test_retry_client_turns_queue_full_answers_into_late_successes(monkeypatch):
    """--retry-429: a full queue is retried with backoff; the answer counts once, with end-to-end latency."""
    monkeypatch.setattr(vllm_bench, "_fields", lambda rid, raw, fin: (1, 1))
    monkeypatch.setattr(vllm_bench, "_gpu_mem_mb", lambda: None)
    monkeypatch.setitem(vllm_bench.TARGET, "retry_429", True)
    monkeypatch.setitem(vllm_bench.TARGET, "retry_backoff_s", 0.001)
    tries = {}

    def request(model, prompt, image_path):
        n = tries[image_path] = tries.get(image_path, 0) + 1
        if n <= 2:
            return {"ok": False, "latency_s": 0.0, "error": "HTTPError 429", "http_status": 429}
        return {"ok": True, "latency_s": 0.0, "raw_response": "x", "finish_reason": "stop"}
    out = vllm_bench._load("m1", [Doc("a"), Doc("b")], conc=2, reps=1, duration_s=None, c1_raw={"a": "x", "b": "x"}, request=request)
    assert out["requests"] == 2 and out["failures"] == 0 and out["status_codes"] == {"200": 2}
    assert out["retries_after_429"] == 4 and out["client"] == "retry_429" and out["identical_to_concurrency1_rate"] == 1.0
