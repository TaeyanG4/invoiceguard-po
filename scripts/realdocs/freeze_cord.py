"""Write configs/frozen_cord_v1.json before the single CORD test run (docs/20_DECISIONS_V6.md, "동결").

The generation settings are copied from the dev runs' fingerprints (all must agree), so test runs exactly what dev ran.
Arms: M0 (no adapter), M1 v1 (frozen adapter, no CORD) and M1-cord. Each may run cord:test once (enforced by infer.py).

Usage (.venv-ml): python scripts/realdocs/freeze_cord.py --dev-runs cord_dev_m0_nf4 cord_dev_m1v1_nf4 cord_dev_m1cord_nf4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KEYS = ("model_revision", "max_pixels", "max_new_tokens", "do_sample", "precision", "batch_size", "padding_side",
        "cord_prompt_sha256", "cord_manifest_sha256")
ARMS = {"M0": ("m0", None), "M1_v1": ("m1", "artifacts/adapters/m1_standard_v1"), "M1_cord": ("m1", "artifacts/adapters/m1_cord_v1")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-runs", nargs="+", required=True)
    a = ap.parse_args()
    out = REPO / "configs" / "frozen_cord_v1.json"
    if out.exists():
        raise SystemExit(f"{out} already exists; a freeze is written once")
    fps = [json.loads((REPO / "artifacts" / "predictions" / r / "run_metadata.json").read_text(encoding="utf-8"))["fingerprint"]
           for r in a.dev_runs]
    gen = {k: fps[0].get(k) for k in KEYS}
    for r, fp in zip(a.dev_runs, fps):
        diff = [k for k in KEYS if fp.get(k) != gen[k]]
        if diff:
            raise SystemExit(f"dev run {r} differs on {diff}")
    if gen["cord_manifest_sha256"] != sha(REPO / "manifests" / "cord_v2.jsonl"):
        raise SystemExit("manifest changed since the dev runs")
    arms = {}
    for name, (arm, adapter) in ARMS.items():
        arms[name] = {"arm": arm, "adapter": adapter,
                      "adapter_sha256": sha(REPO / adapter / "adapter_model.safetensors") if adapter else None}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "prompts", "schemas", "manifests"],
                                capture_output=True, text=True, cwd=REPO).stdout.strip())
    frozen = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "contract": "docs/20_DECISIONS_V6.md",
              "git_commit": commit, "code_dirty_at_freeze": dirty,
              "generation": {k: gen[k] for k in KEYS if not k.startswith("cord_")},
              "cord_prompt_sha256": gen["cord_prompt_sha256"], "cord_manifest_sha256": gen["cord_manifest_sha256"],
              "evaluator_sha256": {p: sha(REPO / p) for p in ("src/invoiceguard/cord_eval.py", "src/invoiceguard/cord.py",
                                                              "src/invoiceguard/model_output.py")},
              "arms": arms, "dev_runs": a.dev_runs,
              "rule": "cord:test runs once per arm with --allow-final; primary metric and criteria as in docs/20"}
    out.write_text(json.dumps(frozen, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(frozen, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
