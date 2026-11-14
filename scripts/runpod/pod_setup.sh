#!/usr/bin/env bash
# RunPod reproduction setup (run as root from /root/ig on the Pod; see reports/RUNPOD_APPROVAL.md).
# 1) Python 3.11.9 venv with the exact local lockfile (torch 2.9.1+cu126 ...), 2) pinned model + data download
# with SHA256 checks, 3) environment record. Base image torch is NOT used.
set -euo pipefail
cd /root/ig
export HF_HOME=/root/hf UV_CACHE_DIR=/root/uvcache
mkdir -p reports/runpod
uv --version
uv python install 3.11.9
[ -x /root/venv-ml/bin/python ] || uv venv -p 3.11.9 /root/venv-ml
grep -v '^#' requirements-ml.lock.txt > /tmp/lock.txt
uv pip install -p /root/venv-ml -r /tmp/lock.txt \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu126 \
  --index-strategy unsafe-best-match
uv pip freeze -p /root/venv-ml > reports/runpod/pod_freeze_ml.txt
/root/venv-ml/bin/python - <<'EOF' > reports/runpod/pod_env.json
import json, platform, subprocess
import torch, transformers, peft, trl, bitsandbytes, accelerate
smi = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip()
print(json.dumps({"python": platform.python_version(), "platform": platform.platform(), "torch": torch.__version__,
                  "torch_cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
                  "gpu": torch.cuda.get_device_name(0), "capability": list(torch.cuda.get_device_capability(0)),
                  "nvidia_smi": smi, "transformers": transformers.__version__, "peft": peft.__version__,
                  "trl": trl.__version__, "bitsandbytes": bitsandbytes.__version__,
                  "accelerate": accelerate.__version__}, indent=1))
EOF
cat reports/runpod/pod_env.json
PYTHONPATH=src /root/venv-ml/bin/python scripts/runpod/pod_fetch.py
echo SETUP_DONE
