#!/usr/bin/env bash
# Run 2 teacher drafts with Qwen3-VL-8B-Instruct (bf16). The 32B FP8 teacher fit on the 48 GB L40S only with 1.35 GiB
# of KV cache: one request at a time at ~15 tokens/s (2 documents in 4 minutes, ~5.6 h for 169), beyond the approved
# cutoff. Its 2 finished drafts are kept as a quality reference (teacher_raw.jsonl).
set -uo pipefail
cd /root/ig
export PYTHONPATH=src HF_HOME=/root/hf PATH=/root/venv-vllm/bin:$PATH
log() { echo "== $* $(date -u +%H:%M:%S)"; }
pkill -f "[v]llm serve" 2>/dev/null; sleep 8
M=Qwen/Qwen3-VL-8B-Instruct
REV=$(/root/venv-ml/bin/python -c "from huggingface_hub import model_info; print(model_info('$M').sha)")
log "teacher8b revision $REV"
/root/venv-ml/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('$M', revision='$REV')" > /workspace/logs/teacher8b_download.log 2>&1
log "downloaded"
vllm serve "$M" --revision "$REV" --host 127.0.0.1 --port 18001 --served-model-name teacher8b --seed 20261113 --dtype bfloat16 \
  --max-model-len 12288 --gpu-memory-utilization 0.92 --max-num-seqs 16 \
  --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":3211264}' > /workspace/logs/vllm_teacher8b.log 2>&1 &
VP=$!
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:18001/health >/dev/null && break
  kill -0 $VP 2>/dev/null || { log "teacher8b server died"; tail -5 /workspace/logs/vllm_teacher8b.log; exit 1; }
  sleep 5
done
log "teacher8b healthy"
# Pod-side output path. Locally the drafts live in artifacts/private_realdocs/ and are never committed (real supplier names).
/root/venv-ml/bin/python scripts/realdocs/teacher_label.py --images data/processed/kaggle_gst/images \
  --out reports/runpod2/teacher8b_raw.jsonl --model teacher8b --workers 12 --max-tokens 6144 > /workspace/logs/teacher8b_label.log 2>&1
log "teacher8b_label exit=$?"
kill $VP; sleep 8; pkill -f "[v]llm serve" 2>/dev/null
cp -r reports/runpod2 /workspace/out/
log "TEACHER8B_DONE"
