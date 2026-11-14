#!/usr/bin/env bash
# RunPod run 2 (plan.md P8b/Q7 + Q4 drafts), on one Ada GPU. Blocks are logged separately; a failing block does not
# stop later independent blocks. In-Pod comparisons (bf16 vs FP8, m0 vs m1) all run on this same GPU.
set -uo pipefail
cd /root/ig
export PYTHONPATH=src IG_HOST=runpod_run2 HF_HOME=/root/hf OMP_NUM_THREADS=8
PY=/root/venv-ml/bin/python
VLLM=/root/venv-vllm/bin/vllm
BASE=/root/ig/models/qwen3-vl-2b-instruct/89644892e4d85e24eaac8bacfd4f463576704203
MERGED=/root/ig/models/merged/m1_v1_nf4deq_bf16
TEACHER=Qwen/Qwen3-VL-32B-Instruct-FP8
mkdir -p reports/runpod2 /workspace/out /workspace/logs
log() { echo "== $* $(date -u +%H:%M:%S)"; }

serve() {  # serve <served-name> <model> <logname> [extra vllm args...]
  local name=$1 model=$2 lname=$3; shift 3
  $VLLM serve "$model" --host 127.0.0.1 --port 18001 --served-model-name "$name" --seed 20261113 "$@" \
      > "/workspace/logs/vllm_${lname}.log" 2>&1 &
  echo $! > /tmp/vllm.pid
  for i in $(seq 1 180); do curl -sf http://127.0.0.1:18001/health >/dev/null && { log "healthy $lname"; return 0; }; sleep 5; done
  log "NOT healthy $lname"; return 1
}
stop_serve() { kill "$(cat /tmp/vllm.pid)" 2>/dev/null; sleep 10; pkill -f "[v]llm serve" 2>/dev/null; sleep 5; }
SMALL=(--dtype bfloat16 --max-model-len 4096 --gpu-memory-utilization 0.85 --limit-mm-per-prompt '{"image":1}'
       --mm-processor-kwargs '{"min_pixels":65536,"max_pixels":786432}')
bench() {  # bench <label> <arm>
  $PY -m invoiceguard.serving.vllm_bench run --port 18001 --label "$1" --docs 20 --warmups 2 --reps 1 --conc 1,4,8,16 --arms "$2" \
      > "/workspace/logs/bench_$1.log" 2>&1; log "bench $1 exit=$?"
  cp reports/serving/"$1".json reports/runpod2/ 2>/dev/null
}

log "teacher download (background)"
( $PY -c "from huggingface_hub import snapshot_download, model_info; i=model_info('$TEACHER'); print('teacher_revision', i.sha); snapshot_download('$TEACHER', revision=i.sha)" \
    > /workspace/logs/teacher_download.log 2>&1 ) &
DL=$!

log "merge on Pod (parity with the local merge)"
$PY scripts/quant/merge_dequantized.py --adapter artifacts/adapters/m1_standard_v1 --out models/merged/m1_v1_nf4deq_bf16 \
    > /workspace/logs/merge.log 2>&1; log "merge exit=$?"
cp models/merged/m1_v1_nf4deq_bf16/merge_metadata.json reports/runpod2/pod_merge_metadata.json 2>/dev/null

serve base "$BASE" m0_bf16 "${SMALL[@]}" && bench vllm_run2_m0_bf16 m0; stop_serve
serve m1 "$MERGED" m1merged_bf16 "${SMALL[@]}" && bench vllm_run2_m1merged_bf16 m1; stop_serve
serve m1 "$MERGED" m1merged_fp8 "${SMALL[@]}" --quantization fp8 && bench vllm_run2_m1merged_fp8 m1; stop_serve
serve base "$BASE" m0_fp8 "${SMALL[@]}" --quantization fp8 && bench vllm_run2_m0_fp8 m0; stop_serve
serve m1 "$MERGED" m1merged_bf16_seqs4 "${SMALL[@]}" --max-num-seqs 4 && bench vllm_run2_m1merged_bf16_seqs4 m1; stop_serve
cp -r reports/runpod2 /workspace/out/

log "wait for teacher download"
wait $DL; log "download exit=$?"; grep teacher_revision /workspace/logs/teacher_download.log
serve teacher "$TEACHER" teacher --max-model-len 12288 --gpu-memory-utilization 0.92 --max-num-seqs 6 \
    --limit-mm-per-prompt '{"image":1}' --mm-processor-kwargs '{"max_pixels":3211264}' \
  && $PY scripts/realdocs/teacher_label.py --images data/processed/kaggle_gst/images --out reports/runpod2/teacher_raw.jsonl \
       --model teacher --workers 6 > /workspace/logs/teacher_label.log 2>&1; log "teacher exit=$?"
stop_serve
cp -r reports/runpod2 /workspace/out/
log "RUN2_DONE"
