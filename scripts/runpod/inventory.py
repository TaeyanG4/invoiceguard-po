"""SHA256 inventory of the inputs a RunPod reproduction must share with the local run.

Usage (repo root, any Python >= 3.11):
  python scripts/runpod/inventory.py --out reports/runpod/inventory_local.json
  python scripts/runpod/inventory.py --out reports/runpod/inventory_pod.json --compare reports/runpod/inventory_local.json

Covers: base-model files, the two frozen train manifests, own TRADE_RAW images + gold, the public train
images extracted from the pinned parquet shards, the pinned shards themselves and the frozen M1 adapter.
Only hashes and sizes are written; no file content. Missing paths are listed, never skipped silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODEL_REV = "89644892e4d85e24eaac8bacfd4f463576704203"
DATA_REV = "673ff85be462eb7f3715ec188a295dd17ca11115"
GROUPS = {
    "model": (f"models/qwen3-vl-2b-instruct/{MODEL_REV}", "*"),
    "manifests": ("manifests", "*.jsonl"),
    "trade_images": ("data/processed/trade/images", "*.png"),
    "trade_gold": ("data/processed/trade/gold", "*.json"),
    "public_shards": (f"data/raw/invoice-ocr-synthetic/{DATA_REV}/data", "*.parquet"),
    "adapter_m1_standard_v1": ("artifacts/adapters/m1_standard_v1", "*"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 22):
            digest.update(block)
    return digest.hexdigest()


def public_train_images() -> list[Path]:
    rows = [json.loads(line) for line in (REPO / "manifests" / "public_canonical_v1.jsonl").read_text(encoding="utf-8").splitlines()]
    names = sorted(f"{r['base_id'][:-4]}__{r['quality']}.png" for r in rows if r["standard_role"] == "train")
    return [REPO / "data" / "processed" / "public" / "train_images" / n for n in names]


def build() -> dict:
    out: dict = {"groups": {}, "missing": []}
    for group, (rel, pattern) in GROUPS.items():
        root = REPO / rel
        files = sorted(p for p in root.glob(pattern) if p.is_file()) if root.exists() else []
        if not files:
            out["missing"].append(rel)
        out["groups"][group] = {p.relative_to(REPO).as_posix(): [p.stat().st_size, sha256(p)] for p in files
                                if p.name != "run_metadata.json"}
    imgs = public_train_images()
    out["missing"] += [p.relative_to(REPO).as_posix() for p in imgs if not p.exists()]
    out["groups"]["public_train_images"] = {p.relative_to(REPO).as_posix(): [p.stat().st_size, sha256(p)]
                                            for p in imgs if p.exists()}
    out["counts"] = {g: len(v) for g, v in out["groups"].items()}
    return out


def compare(mine: dict, ref: dict) -> dict:
    result = {}
    for group, ref_files in ref["groups"].items():
        cur = mine["groups"].get(group, {})
        diff = sorted(k for k in ref_files if ref_files[k][1] != cur.get(k, [None, None])[1])
        extra = sorted(set(cur) - set(ref_files))  # e.g. .gitattributes from the hub; reported, not a failure
        result[group] = {"reference": len(ref_files), "here": len(cur), "mismatch": len(diff), "examples": diff[:5],
                         "extra_here": extra[:10]}
    result["all_equal"] = all(v["mismatch"] == 0 for v in result.values() if isinstance(v, dict))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--compare")
    args = parser.parse_args()
    inv = build()
    if args.compare:
        inv["comparison"] = compare(inv, json.loads((REPO / args.compare).read_text(encoding="utf-8")))
    path = REPO / args.out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inv, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"counts": inv["counts"], "missing": inv["missing"][:10],
                      "comparison": inv.get("comparison")}, indent=1))
    return 0 if not args.compare or inv["comparison"]["all_equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
