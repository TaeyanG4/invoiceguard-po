"""Per-tensor SHA256 + simple statistics of a safetensors checkpoint, to compare two builds of the same model
(e.g. the merged checkpoint built on the local RTX 4070 Ti SUPER vs on a RunPod GPU) and see WHICH tensors differ.

Usage: python scripts/quant/tensor_hashes.py <model.safetensors> --out <json> [--dump name1,name2 --dump-out <file>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dump", help="comma-separated tensor names to save for a direct diff")
    ap.add_argument("--dump-out")
    a = ap.parse_args()
    rows, dump = {}, {}
    wanted = set(a.dump.split(",")) if a.dump else set()
    with safe_open(a.path, framework="pt") as f:
        for name in f.keys():
            t = f.get_tensor(name)
            raw = t.contiguous().view(torch.uint8).numpy().tobytes() if t.dtype != torch.bool else t.numpy().tobytes()
            x = t.float()
            rows[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "dtype": str(t.dtype).replace("torch.", ""),
                          "shape": list(t.shape), "sum": float(x.sum()), "abs_mean": float(x.abs().mean())}
            if name in wanted:
                dump[name] = t.contiguous()
    Path(a.out).write_text(json.dumps(rows) + "\n", encoding="utf-8")
    if dump and a.dump_out:
        save_file(dump, a.dump_out)
    print(json.dumps({"tensors": len(rows), "dumped": len(dump)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
