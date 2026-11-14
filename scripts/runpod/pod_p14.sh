#!/usr/bin/env bash
# RunPod run 2, part 2 (plan P14): plain LoRA on the bf16 base, trained and compared on the SAME GPU as its baselines.
# Waits for pod_run2.sh to finish (one GPU job at a time). All three dev evaluations use the HF reference path, batch 1.
set -uo pipefail
cd /root/ig
export PYTHONPATH=src IG_HOST=runpod_run2_l40s HF_HOME=/root/hf OMP_NUM_THREADS=8
PY=/root/venv-ml/bin/python
log() { echo "== $* $(date -u +%H:%M:%S)"; }
while ! grep -q RUN2_DONE /workspace/logs/run2.log 2>/dev/null; do sleep 30; done
log "shards (public train/dev images)"
$PY scripts/runpod/pod_fetch.py > /workspace/logs/fetch_shards.log 2>&1; log "fetch exit=$?"
cp reports/runpod/pod_fetch.json reports/runpod2/pod_fetch_shards.json
log "P14 train (bf16 base, plain LoRA)"
$PY -m invoiceguard.vlm.train --profile standard --run-id m1_bf16lora_l40s --base-precision bf16 > /workspace/logs/train_bf16lora.log 2>&1
log "train exit=$?"; cp reports/model/train_m1_bf16lora_l40s.json reports/runpod2/ 2>/dev/null
cp -r artifacts/adapters/m1_bf16lora_l40s /workspace/out/ 2>/dev/null
for spec in "dev44_l40s_m0_bf16:--arm m0 --precision bf16" \
            "dev44_l40s_m1_nf4:--arm m1 --adapter artifacts/adapters/m1_standard_v1 --precision nf4" \
            "dev44_l40s_m1_bf16lora:--arm m1 --adapter artifacts/adapters/m1_bf16lora_l40s --precision bf16"; do
  run=${spec%%:*}; opts=${spec#*:}
  $PY -m invoiceguard.vlm.infer $opts --set public:dev --set trade:dev --batch-size 1 --run-id "$run" > "/workspace/logs/$run.log" 2>&1
  log "$run exit=$?"
  mkdir -p reports/runpod2/predictions && cp -r "artifacts/predictions/$run" reports/runpod2/predictions/
done
cp -r reports/runpod2 /workspace/out/
log "P14_DONE"
