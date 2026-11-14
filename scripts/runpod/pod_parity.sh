#!/usr/bin/env bash
# Inference parity on the Pod (dev only, never final): the same 8 own-dev documents through the reference
# HF NF4 path with (1) the frozen local adapter m1_standard_v1 and (2) the Pod-trained adapter m1_pod_a40.
set -euo pipefail
cd /root/ig
export PYTHONPATH=src IG_HOST=runpod_a40_ca-mtl-1 OMP_NUM_THREADS=7 MKL_NUM_THREADS=7 HF_HOME=/root/hf
PY=/root/venv-ml/bin/python
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_standard_v1 --set trade:dev --limit 8 --run-id pod_m1v1_dev8
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_pod_a40 --set trade:dev --limit 8 --run-id pod_m1pod_dev8
mkdir -p /workspace/out/predictions && cp -r artifacts/predictions/pod_m1v1_dev8 artifacts/predictions/pod_m1pod_dev8 /workspace/out/predictions/
echo PARITY_DONE
