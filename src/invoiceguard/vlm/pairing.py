"""Adapter ↔ base-model pairing guard (plan P15).

A LoRA adapter only behaves as trained on the base weights it was trained on. Measured 2026-11-14
(reports/quant/precision_dev20.md): the QLoRA adapter trained on the NF4 base drops from 0.960 to 0.847–0.849
field accuracy when the same adapter is put on a bf16 / fp16 / fp32 / int8 base, on the local GPU and on vLLM alike.
So every load of an adapter checks the base it will sit on and refuses a mismatch unless the caller explicitly
allows it for an exploratory precision experiment (and records that it did).

Torch-free on purpose: the CPU CI tests it (tests/test_pairing.py).

  python -m invoiceguard.vlm.pairing check --adapter artifacts/adapters/m1_standard_v1 --base-precision bf16
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEQUANTISED_KINDS = {"nf4_dequantized_bf16_base_only"}  # merge_dequantized.py --no-merge: NF4 values stored as bf16


class PairingError(RuntimeError):
    pass


def _precision_from_label(label: str | None) -> str:
    if not label:
        return "unknown"
    low = label.lower()
    for name in ("nf4", "int8", "bf16", "fp16", "fp32"):
        if low.startswith(name):
            return name
    return "unknown"


def adapter_base(adapter_dir: Path) -> dict:
    """{'revision', 'precision', 'gpu'} of the base the adapter was trained on, from its run_metadata.json.
    New runs record config.base_precision; older QLoRA runs only carry env.precision ('nf4_double_quant…')."""
    meta_path = Path(adapter_dir) / "run_metadata.json"
    if not meta_path.exists():
        return {"revision": None, "precision": "unknown", "gpu": None}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    precision = (meta.get("config") or {}).get("base_precision") or _precision_from_label((meta.get("env") or {}).get("precision"))
    return {"revision": meta.get("base_revision"), "precision": precision, "gpu": (meta.get("env") or {}).get("gpu")}


def effective_base_precision(precision: str, model_dir: Path | None = None) -> str:
    """The precision of the weights the adapter will actually meet. A dequantised-NF4 base saved in bf16 still holds
    exactly the NF4 values, so it pairs with NF4-trained adapters."""
    if model_dir is not None:
        meta = Path(model_dir) / "merge_metadata.json"
        if meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("kind") in DEQUANTISED_KINDS:
            return "nf4"
    return precision


def check(adapter_dir: Path, base_precision: str, base_revision: str | None, model_dir: Path | None = None,
          allow_mismatch: bool = False) -> dict:
    """Return the pairing record; raise PairingError on a mismatch unless allow_mismatch."""
    trained = adapter_base(adapter_dir)
    serving = effective_base_precision(base_precision, model_dir)
    problems = []
    if trained["precision"] == "unknown":
        problems.append("adapter has no recorded base precision (run_metadata.json missing or unreadable)")
    elif trained["precision"] != serving:
        problems.append(f"adapter trained on a {trained['precision']} base, would be served on a {serving} base")
    if base_revision and trained["revision"] and trained["revision"] != base_revision:
        problems.append(f"adapter base revision {trained['revision'][:8]} != serving base {base_revision[:8]}")
    record = {"adapter": str(adapter_dir), "trained_base": trained, "serving_base_precision": serving,
              "problems": problems, "mismatch_allowed": bool(problems) and allow_mismatch}
    if problems and not allow_mismatch:
        raise PairingError("; ".join(problems) + " — train an adapter for this base, serve the matching base "
                           "(e.g. scripts/quant/merge_dequantized.py), or pass the explicit mismatch flag for an exploratory run")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--adapter", required=True)
    c.add_argument("--base-precision", required=True, choices=["nf4", "int8", "bf16", "fp16", "fp32"])
    c.add_argument("--base-revision")
    c.add_argument("--model-dir")
    a = ap.parse_args()
    try:
        rec = check(Path(a.adapter), a.base_precision, a.base_revision, Path(a.model_dir) if a.model_dir else None)
    except PairingError as exc:
        print(f"PAIRING REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
