#!/usr/bin/env bash
# Run 2 teacher drafts, third attempt (second: ninja missing from PATH) (first: KV cache 0.47 GiB after 33.5 GiB weights + profiling with 3.2 MP images).
set -uo pipefail
cd /root/ig
export PYTHONPATH=src HF_HOME=/root/hf PATH=/root/venv-vllm/bin:$PATH  # flashinfer JIT for the fp8 KV cache needs ninja on PATH (attempt 2 failed without it)
while ! grep -q P14_DONE /workspace/logs/p14.log 2>/dev/null; do sleep 30; done  # one GPU job at a time
log() { echo "== $* $(date -u +%H:%M:%S)"; }
pkill -f "[v]llm serve" 2>/dev/null; sleep 5
/root/venv-vllm/bin/vllm serve Qwen/Qwen3-VL-32B-Instruct-FP8 --revision 4bf2c2f39c37c0fede78bede4056e1f18cdf8109 \
  --host 127.0.0.1 --port 18001 --served-model-name teacher --seed 20261113 \
  --max-model-len 8192 --gpu-memory-utilization 0.97 --kv-cache-dtype fp8 --max-num-seqs 4 --max-num-batched-tokens 8192 \
  --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":2359296}' > /workspace/logs/vllm_teacher2.log 2>&1 &
VP=$!
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:18001/health >/dev/null && break
  kill -0 $VP 2>/dev/null || { log "teacher server died"; tail -5 /workspace/logs/vllm_teacher2.log; exit 1; }
  sleep 5
done
log "teacher healthy"
/root/venv-ml/bin/python scripts/realdocs/teacher_label.py --images data/processed/kaggle_gst/images \
  --out reports/runpod2/teacher_raw.jsonl --model teacher --workers 4 --max-tokens 4096 > /workspace/logs/teacher_label.log 2>&1
log "teacher_label exit=$?"
kill $VP; sleep 10; pkill -f "[v]llm serve" 2>/dev/null
cp -r reports/runpod2 /workspace/out/
echo TEACHER_DONE >> /workspace/logs/teacher_run.log
