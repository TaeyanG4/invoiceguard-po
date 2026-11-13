"""Extractor backends. Each declares its MODE; only a real model server may report LIVE_MODEL.

* LiveHTTPExtractor   — OpenAI-compatible model server on 127.0.0.1 (vLLM container / SSH tunnel). LIVE_MODEL.
* ReplayExtractor     — returns a SAVED raw response of a real model run for the same image sha256. REPLAY_OF_SAVED_RUN.
* UnavailableExtractor— no model configured: every call raises ModelUnavailable (HTTP 503). Never falls back.
The request carries only the fixed TRADE_RAW prompt and the image (extraction_request.build_request).
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..extraction_request import PRODUCT_TASK, build_request


class ModelUnavailable(Exception):
    pass


class ExtractionTimeout(Exception):
    pass


@dataclass
class ExtractionResult:
    raw_response: str | None
    finish_reason: str | None
    generation_status: str
    model_label: str
    prompt_sha256: str
    latency_s: float


class UnavailableExtractor:
    mode = "MODEL_UNAVAILABLE"
    label = "none"

    def extract(self, image_bytes: bytes) -> ExtractionResult:
        raise ModelUnavailable("no model backend configured")


class ReplayExtractor:
    """Replays raw responses saved by a real inference run (artifacts/predictions/<run>/predictions.jsonl)."""
    mode = "REPLAY_OF_SAVED_RUN"

    def __init__(self, run_dir: Path, image_index: dict[str, str]):
        self.label = f"replay:{run_dir.name}"
        rows = [json.loads(l) for l in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        by_id = {r["id"]: r for r in rows if r.get("task") == PRODUCT_TASK}
        self.by_sha = {sha: by_id[i] for sha, i in image_index.items() if i in by_id}

    def extract(self, image_bytes: bytes) -> ExtractionResult:
        req = build_request(PRODUCT_TASK, image_bytes)
        row = self.by_sha.get(req.image_sha256)
        if row is None:
            raise ModelUnavailable("no saved response for this image in the replay run")
        return ExtractionResult(row.get("raw_response"), row.get("finish_reason"), row.get("generation_status", "ok"),
                                self.label, req.prompt_sha256, 0.0)


class LiveHTTPExtractor:
    mode = "LIVE_MODEL"

    def __init__(self, base_url: str, model: str, timeout_s: float = 120.0):
        if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("model server must be on loopback (SSH tunnel / local container)")
        self.base_url, self.model, self.timeout_s = base_url.rstrip("/"), model, timeout_s
        self.label = f"live:{model}"

    def ready(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=5) as r:
                return r.status == 200
        except Exception:  # noqa: BLE001
            return False

    def extract(self, image_bytes: bytes) -> ExtractionResult:
        req = build_request(PRODUCT_TASK, image_bytes)
        body = {"model": self.model, "temperature": 0, "max_tokens": 1536,
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(req.image_bytes).decode()}},
                    {"type": "text", "text": req.prompt}]}]}
        http = urllib.request.Request(f"{self.base_url}/v1/chat/completions", data=json.dumps(body).encode(),
                                      headers={"Content-Type": "application/json"})
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(http, timeout=self.timeout_s) as r:
                payload = json.loads(r.read())
        except TimeoutError as exc:  # we close the socket; whether the server aborts generation is verified in S6, not assumed
            raise ExtractionTimeout(str(exc)) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ExtractionTimeout(str(exc)) from exc
            raise ModelUnavailable(str(exc.reason)) from exc
        choice = payload["choices"][0]
        return ExtractionResult(choice["message"]["content"], choice.get("finish_reason"), "ok", self.label,
                                req.prompt_sha256, time.perf_counter() - start)


def image_sha_index(records) -> dict[str, str]:
    """sha256(normalised PNG bytes as stored by the app) -> record_id, for replay lookups."""
    from .uploads import normalise_image

    index = {}
    for rec in records:
        png, _ = normalise_image(rec.image_path.read_bytes())
        index[hashlib.sha256(png).hexdigest()] = rec.record_id
    return index
