"""Qwen3-VL extraction model: data records, loss masks, NF4 loading, LoRA, smoke tests.

Torch/transformers/peft/bitsandbytes live in the separate `.venv-ml` environment;
the CPU product environment never imports this package.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
MODEL_REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
MODEL_WEIGHTS_SHA256 = "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0"
MODEL_DIR = REPO / "models" / "qwen3-vl-2b-instruct" / MODEL_REVISION
