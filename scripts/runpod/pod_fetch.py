"""Download the pinned base model and the two pinned public parquet shards on the Pod, then verify hashes.

Usage (Pod, training venv):  python scripts/runpod/pod_fetch.py
The expected hashes come from configs/frozen_v1.json (model weights) and invoiceguard.public_data
(shard SHA256). Anything that does not match stops the run (exit 1) before any training.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from invoiceguard.public_data import DATASET_ID, DATASET_REVISION, SHARD_SHA256, dataset_root, sha256_file  # noqa: E402
from invoiceguard.vlm import MODEL_DIR, MODEL_ID, MODEL_REVISION  # noqa: E402


def main() -> int:
    from huggingface_hub import hf_hub_download, snapshot_download

    frozen = json.loads((REPO / "configs" / "frozen_v1.json").read_text(encoding="utf-8"))
    report = {"model_id": MODEL_ID, "model_revision": MODEL_REVISION, "dataset_id": DATASET_ID,
              "dataset_revision": DATASET_REVISION, "checks": {}}
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=str(MODEL_DIR))
    weights = sha256_file(MODEL_DIR / "model.safetensors")
    report["checks"]["model.safetensors"] = {"sha256": weights, "expected": frozen["model"]["weights_sha256"],
                                             "ok": weights == frozen["model"]["weights_sha256"]}
    root = dataset_root(REPO)
    for rel, expected in SHARD_SHA256.items():
        hf_hub_download(DATASET_ID, rel, repo_type="dataset", revision=DATASET_REVISION, local_dir=str(root))
        got = sha256_file(root / rel)
        report["checks"][rel] = {"sha256": got, "expected": expected, "ok": got == expected}
    report["all_ok"] = all(c["ok"] for c in report["checks"].values())
    out = REPO / "reports" / "runpod" / "pod_fetch.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=1))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
