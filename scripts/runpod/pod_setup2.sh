#!/usr/bin/env bash
# RunPod run 2 setup (as root from /root/ig): training/eval venv from the lockfile, vLLM 0.11.2 venv, pinned 2B model only.
set -euo pipefail
cd /root/ig
export HF_HOME=/root/hf UV_CACHE_DIR=/root/uvcache
mkdir -p reports/runpod2 /workspace/logs
uv python install 3.11.9
[ -x /root/venv-ml/bin/python ] || uv venv -p 3.11.9 /root/venv-ml
grep -v '^#' requirements-ml.lock.txt > /tmp/lock.txt
uv pip install -p /root/venv-ml -r /tmp/lock.txt --index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
[ -x /root/venv-vllm/bin/python ] || uv venv -p 3.12 /root/venv-vllm
uv pip install -p /root/venv-vllm vllm==0.11.2
uv pip freeze -p /root/venv-ml > reports/runpod2/pod_freeze_ml.txt
uv pip freeze -p /root/venv-vllm > reports/runpod2/pod_freeze_vllm.txt
nvidia-smi > reports/runpod2/pod_nvidia_smi.txt
PYTHONPATH=src /root/venv-ml/bin/python scripts/runpod/pod_fetch.py --model-only
cp reports/runpod/pod_fetch.json reports/runpod2/pod_fetch.json
echo SETUP2_DONE
