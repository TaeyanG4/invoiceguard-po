"""Freeze appendix for final evaluation (Fable mid-course review blocker 2).

  python -m invoiceguard.freeze write     # record hashes after dev work is finished (before any final run)
  python -m invoiceguard.freeze verify    # show what would block a final run

Final runs (B0 predict, HF infer, scoring) require: --allow-final, a clean git tree, and every hash below
identical to configs/frozen_v1_appendix.json. configs/frozen_v1.json (generation settings) is unchanged.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APPENDIX = REPO / "configs" / "frozen_v1_appendix.json"
TRACKED_FILES = {
    "b0_code": ["src/invoiceguard/ocr_baseline.py", "docker/ocr/Dockerfile", "docker/ocr/run.sh"],
    "evaluator_code": ["src/invoiceguard/evaluation.py", "src/invoiceguard/score_run.py", "src/invoiceguard/canonical.py",
                       "src/invoiceguard/normalization.py", "src/invoiceguard/reconciliation.py",
                       "src/invoiceguard/model_output.py", "src/invoiceguard/public_visibility.py"],
    "inference_code": ["src/invoiceguard/vlm/infer.py", "src/invoiceguard/vlm/model.py", "src/invoiceguard/vlm/sft.py",
                       "src/invoiceguard/vlm/records.py", "src/invoiceguard/extraction_request.py"],
    "frozen_config": ["configs/frozen_v1.json"],
    "manifests": ["manifests/public_canonical_v1.jsonl", "manifests/trade_raw_v1.jsonl", "manifests/stress_v1.jsonl"],
    "prompts": ["prompts/EXTRACT_PUBLIC_CANONICAL.txt", "prompts/EXTRACT_V1.txt"],
}
ADAPTER = "artifacts/adapters/m1_standard_v1/adapter_model.safetensors"
OCR_IMAGE = "invoiceguard-ocr:tesseract"


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _ocr_image_id() -> str | None:
    out = subprocess.run(["docker", "image", "inspect", OCR_IMAGE, "--format", "{{.Id}}"], capture_output=True, text=True)
    return out.stdout.strip() or None


def snapshot() -> dict:
    files = {group: {rel: _sha(rel) for rel in rels} for group, rels in TRACKED_FILES.items()}
    adapter = REPO / ADAPTER
    from .ocr_baseline import B0_VERSION

    return {"files": files, "m1_adapter_sha256": _sha(ADAPTER) if adapter.exists() else None,
            "ocr_docker_image_id": _ocr_image_id(), "b0_version": B0_VERSION, "b0_psm": 4}


def git_state() -> tuple[str, list[str]]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    # evaluation OUTPUTS (reports/) may change between final runs; code, configs, manifests and prompts may not
    dirty = [l for l in subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
             if l.strip() and not l[3:].strip().strip('"').startswith("reports/")]
    return head, dirty


def verify_final_ready(meta: dict | None = None) -> list[str]:
    problems = []
    if not APPENDIX.exists():
        return ["freeze_appendix_missing"]
    frozen = json.loads(APPENDIX.read_text(encoding="utf-8"))
    current = snapshot()
    for group, files in frozen["files"].items():
        for rel, digest in files.items():
            if current["files"].get(group, {}).get(rel) != digest:
                problems.append(f"changed:{rel}")
    for key in ("m1_adapter_sha256", "ocr_docker_image_id", "b0_version", "b0_psm"):
        if current[key] != frozen[key]:
            problems.append(f"changed:{key}")
    _, dirty = git_state()
    if dirty:
        problems.append(f"git_tree_dirty:{len(dirty)}")
    if meta and meta.get("fingerprint", {}).get("adapter_sha256") not in (None, frozen["m1_adapter_sha256"]):
        problems.append("run_adapter_not_frozen_adapter")
    return problems


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "write":
        head, dirty = git_state()
        if dirty:
            raise SystemExit(f"commit first: {len(dirty)} uncommitted paths")
        data = {"written_at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "git_commit": head,
                "rule": "final runs only with --allow-final, clean git tree and identical hashes", **snapshot()}
        APPENDIX.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {APPENDIX} at {head[:8]} — commit it before running final")
        return 0
    problems = verify_final_ready()
    print(json.dumps({"final_ready": not problems, "problems": problems}, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
