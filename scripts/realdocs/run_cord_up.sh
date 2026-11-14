#!/usr/bin/env bash
# docs/20 amendment 3 (exploratory): up-weight CORD receipts with a printed unit price, train once, evaluate on CORD dev only.
set -u
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
stamp() { echo "== $1 $(date -u +%H:%M:%S)"; }
stamp "train M1-cord-up (all_plus_cord_up, 240 steps)"
$PY -m invoiceguard.vlm.train --profile standard --data all_plus_cord_up --max-steps 240 --run-id m1_cord_up_v1
rc=$?
stamp "train exit=$rc"
if [ $rc -ne 0 ]; then stamp "abort"; exit $rc; fi
stamp "cord dev M1-cord-up (nf4)"
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_cord_up_v1 --set cord:dev --batch-size 1 --run-id cord_dev_m1cordup_nf4
stamp "exit=$? done"
