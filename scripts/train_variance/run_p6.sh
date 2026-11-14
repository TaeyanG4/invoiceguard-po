#!/usr/bin/env bash
# P6 (plan.md): training evidence — two more seeds of the frozen recipe and one data ablation (public data only),
# each evaluated on dev only (public:dev 20 + trade:dev 24 = 44 documents, HF NF4 reference path, batch 1).
# The frozen M1 (m1_standard_v1, seed 20261113) is the reference; its dev predictions are m1_dev_v1.
# Waits for the P3 precision queue to finish first (one GPU job at a time).
# Usage (repo root, Git Bash): bash scripts/train_variance/run_p6.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
export PYTHONPATH=src IG_HOST=local_workstation
mkdir -p artifacts/p6
while ! grep -q ALL_DONE artifacts/quant_progress.log 2>/dev/null; do sleep 60; done
echo "== start $(date +%H:%M:%S)"
for spec in "m1_seed_20261114:--seed 20261114" "m1_seed_20261115:--seed 20261115" "m1_public_only:--data public_only"; do
  run=${spec%%:*}; opts=${spec#*:}
  echo "== train $run ($opts) $(date +%H:%M:%S)"
  $PY -m invoiceguard.vlm.train --profile standard --run-id "$run" $opts > "artifacts/p6/train_$run.log" 2>&1
  echo "   exit=$? $(grep -o '"train_loss": [0-9.]*' artifacts/p6/train_$run.log | tail -1)"
  echo "== dev $run $(date +%H:%M:%S)"
  $PY -m invoiceguard.vlm.infer --arm m1 --adapter "artifacts/adapters/$run" --set public:dev --set trade:dev \
      --batch-size 1 --run-id "dev44_$run" > "artifacts/p6/dev_$run.log" 2>&1
  echo "   exit=$? $(tail -1 artifacts/p6/dev_$run.log | cut -c1-120)"
done
echo "P6_DONE $(date +%H:%M:%S)"
