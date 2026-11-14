#!/usr/bin/env bash
# vLLM 0.11.2 serving arm on the Pod: loopback only (127.0.0.1:18001; nginx in the image owns 8001).
# Same flags as serving/vllm_bench.py `up` (local Docker plan), plus the Pod-trained adapter as a 2nd LoRA.
set -euo pipefail
MODEL=/root/ig/models/qwen3-vl-2b-instruct/89644892e4d85e24eaac8bacfd4f463576704203
exec /root/venv-vllm/bin/vllm serve "$MODEL" --host 127.0.0.1 --port 18001 --served-model-name base \
  --dtype bfloat16 --enable-lora \
  --lora-modules m1=/root/ig/artifacts/adapters/m1_standard_v1 m1pod=/root/ig/artifacts/adapters/m1_pod_a40 \
  --max-lora-rank 8 --max-loras 2 --max-model-len 4096 --gpu-memory-utilization 0.82 \
  --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"min_pixels":65536,"max_pixels":786432}' \
  --seed 20261113
