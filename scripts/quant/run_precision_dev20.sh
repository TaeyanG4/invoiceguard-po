#!/usr/bin/env bash
# P3/P5 (plan.md): the same 20 own-dev documents (trade:dev, first 20 = the vLLM bench documents) through the
# reference HF path with different base-model precisions. Exploratory dev comparison — never final sets.
# NF4 baselines are the existing local runs m0_dev_v1 / m1_dev_v1 (same settings, batch 1).
# Usage (repo root, Git Bash): bash scripts/quant/run_precision_dev20.sh [order...]
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
export PYTHONPATH=src IG_HOST=local_workstation
mkdir -p artifacts/quant
ORDER=${*:-"m1:bf16 m1:fp32 m1:fp16 m1:int8 m0:bf16 m0:int8 m0:fp16 m0:fp32"}
for item in $ORDER; do
  arm=${item%%:*}; prec=${item##*:}
  run="prec_${arm}_${prec}_dev20"
  adapter=(); [ "$arm" = m1 ] && adapter=(--adapter artifacts/adapters/m1_standard_v1)
  # the m1 rows deliberately put the NF4-trained adapter on other bases (that is the experiment); since P15 this needs the flag
  [ "$arm" = m1 ] && [ "$prec" != nf4 ] && adapter+=(--allow-precision-mismatch)
  echo "== $run $(date +%H:%M:%S)"
  $PY -m invoiceguard.vlm.infer --arm "$arm" "${adapter[@]}" --set trade:dev --limit 20 --batch-size 1 \
      --precision "$prec" --run-id "$run" > "artifacts/quant/$run.log" 2>&1
  echo "   exit=$? $(tail -1 artifacts/quant/$run.log | cut -c1-160)"
done
echo "ALL_DONE $(date +%H:%M:%S)"
