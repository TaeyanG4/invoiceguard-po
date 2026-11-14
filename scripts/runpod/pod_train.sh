#!/usr/bin/env bash
# RunPod reproduction of the frozen M1 run (m1_standard_v1). Each gate must pass before the next starts
# (set -e: masks / inventory / smoke return non-zero on failure). Run as root from /root/ig on the Pod.
set -euo pipefail
cd /root/ig
export PYTHONPATH=src IG_HOST=runpod_a40_ca-mtl-1 OMP_NUM_THREADS=7 MKL_NUM_THREADS=7 HF_HOME=/root/hf
PY=/root/venv-ml/bin/python
mkdir -p reports/runpod /workspace/out
echo "== masks $(date -u +%FT%TZ)"
$PY -m invoiceguard.vlm.smoke masks
cp reports/model/local_smoke_masks.json reports/runpod/pod_smoke_masks.json
echo "== inventory $(date -u +%FT%TZ)"
$PY scripts/runpod/inventory.py --out reports/runpod/inventory_pod.json --compare reports/runpod/inventory_local.json
echo "== smoke train $(date -u +%FT%TZ)"
$PY -m invoiceguard.vlm.smoke train
cp reports/model/local_smoke_train.json reports/runpod/pod_smoke_train.json
cp -r reports/runpod /workspace/out/
echo "== full train $(date -u +%FT%TZ)"
$PY -m invoiceguard.vlm.train --profile standard --run-id m1_pod_a40
cp reports/model/train_m1_pod_a40.json reports/runpod/train_m1_pod_a40.json
cp -r artifacts/adapters/m1_pod_a40 reports/runpod /workspace/out/
echo "TRAIN_DONE $(date -u +%FT%TZ)"
