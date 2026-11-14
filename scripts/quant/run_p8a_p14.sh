#!/usr/bin/env bash
# Queue (plan.md): P8a again (merge script fixed), then P14 (plain LoRA on the bf16 base) and the
# dev comparisons it needs. One GPU job at a time. Usage: bash scripts/quant/run_after_p6.sh > artifacts/after_p6.log 2>&1
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
export PYTHONPATH=src IG_HOST=local_workstation
# (no wait: P6 on the easy set was cancelled 2026-11-14 20:40 — both advisors: move seeds to the new hard data)
echo "== P8a (retry) $(date +%H:%M:%S)"
rm -rf models/merged
$PY scripts/quant/merge_dequantized.py --adapter artifacts/adapters/m1_standard_v1 --out models/merged/m1_v1_nf4deq_bf16 > artifacts/quant/merge_full.log 2>&1; echo "   merge exit=$?"
$PY scripts/quant/merge_dequantized.py --adapter artifacts/adapters/m1_standard_v1 --out models/merged/nf4deq_bf16_base --no-merge > artifacts/quant/merge_base.log 2>&1; echo "   dequant-only exit=$?"
for spec in "prec_m1merged_bf16_dev20:--arm m1merged --model-dir models/merged/m1_v1_nf4deq_bf16" \
            "prec_m1deqlora_bf16_dev20:--arm m1 --adapter artifacts/adapters/m1_standard_v1 --model-dir models/merged/nf4deq_bf16_base"; do
  run=${spec%%:*}; opts=${spec#*:}
  $PY -m invoiceguard.vlm.infer $opts --precision bf16 --set trade:dev --limit 20 --batch-size 1 --run-id "$run" > "artifacts/quant/$run.log" 2>&1
  echo "   $run exit=$? $(tail -1 artifacts/quant/$run.log | cut -c1-100)"
done
echo "== P14 train $(date +%H:%M:%S)"
$PY -m invoiceguard.vlm.train --profile standard --run-id m1_bf16lora --base-precision bf16 > artifacts/p6/train_m1_bf16lora.log 2>&1
echo "   exit=$? $(grep -o '"train_loss": [0-9.]*' artifacts/p6/train_m1_bf16lora.log | tail -1)"
for spec in "dev44_m1_bf16lora:--arm m1 --adapter artifacts/adapters/m1_bf16lora --precision bf16" \
            "dev44_m0_bf16:--arm m0 --precision bf16"; do
  run=${spec%%:*}; opts=${spec#*:}
  $PY -m invoiceguard.vlm.infer $opts --set public:dev --set trade:dev --batch-size 1 --run-id "$run" > "artifacts/p6/$run.log" 2>&1
  echo "   $run exit=$? $(tail -1 artifacts/p6/$run.log | cut -c1-100)"
done
echo "AFTER_P6_DONE $(date +%H:%M:%S)"
