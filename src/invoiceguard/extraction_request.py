"""The ONLY way to build a VLM extraction request (D06 input boundary).

A request carries: a fixed task selector chosen by the server, the fixed prompt text for that
task (with its hash), and the image bytes. It never carries a PO, gold labels, file names,
scenario IDs or anything parsed from the document. Invoice text is untrusted data.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROMPT_FILES = {
    "TRADE_RAW": REPO / "prompts" / "EXTRACT_V1.txt",
    "PUBLIC_CANONICAL": REPO / "prompts" / "EXTRACT_PUBLIC_CANONICAL.txt",
}
PRODUCT_TASK = "TRADE_RAW"  # the product API only ever calls TRADE_RAW (docs/15 B)


def load_prompt(task: str) -> tuple[str, str]:
    if task not in PROMPT_FILES:
        raise ValueError(f"unknown task {task!r}")
    raw = PROMPT_FILES[task].read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ExtractionRequest:
    task: str
    prompt: str
    prompt_sha256: str
    image_bytes: bytes
    image_sha256: str

    def audit_view(self) -> dict:
        """Loggable view: hashes only, no image bytes, no prompt-external content."""
        return {"task": self.task, "prompt_sha256": self.prompt_sha256, "image_sha256": self.image_sha256,
                "image_bytes": len(self.image_bytes)}


def build_request(task: str, image_bytes: bytes) -> ExtractionRequest:
    if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
        raise ValueError("image bytes required")
    prompt, prompt_sha = load_prompt(task)
    return ExtractionRequest(task, prompt, prompt_sha, bytes(image_bytes), hashlib.sha256(image_bytes).hexdigest())
