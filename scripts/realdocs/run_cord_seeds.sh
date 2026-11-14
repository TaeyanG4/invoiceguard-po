#!/usr/bin/env bash
# docs/20 amendment 2: two more M1-cord seeds, same recipe, evaluated on CORD dev only (no CORD test — not frozen arms).
# Local RTX 4070 Ti SUPER, NF4, one GPU job at a time. "== <label> HH:MM:SS" (UTC) stamps feed the timeline.
set -u
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
stamp() { echo "== $1 $(date -u +%H:%M:%S)"; }

for seed in 20261114 20261115; do
  stamp "train M1-cord seed $seed"
  $PY -m invoiceguard.vlm.train --profile standard --data all_plus_cord --max-steps 240 --seed $seed --run-id m1_cord_s$seed
  rc=$?
  stamp "train exit=$rc seed $seed"
  if [ $rc -ne 0 ]; then stamp "abort"; exit $rc; fi
  stamp "cord dev M1-cord seed $seed (nf4)"
  $PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_cord_s$seed --set cord:dev --batch-size 1 --run-id cord_dev_m1cord_s${seed}_nf4
  stamp "exit=$? dev seed $seed"
done
stamp "done"
