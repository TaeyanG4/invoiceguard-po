#!/usr/bin/env bash
# CORD v2 local chain on the RTX 4070 Ti SUPER, NF4 everywhere (docs/20_DECISIONS_V6.md), one GPU job at a time.
#   1. M1 v1 (frozen adapter, trained without CORD) on CORD dev
#   2. train M1-cord: existing train (public 200 + trade 160) + CORD train-eligible 742, QLoRA NF4, 240 steps
#   3. M1-cord on CORD dev
#   4. regression: M1-cord on the same local dev sets as m1_dev_v1 (public dev/stress, trade dev, stress)
# CORD test is NOT run here: it runs once, after configs/frozen_cord_v1.json is written.
# Each step prints "== <label> HH:MM:SS" (UTC) so scripts/runpod/timeline.py can build the timeline.
set -u
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
stamp() { echo "== $1 $(date -u +%H:%M:%S)"; }

stamp "cord dev M1 v1 (nf4)"
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_standard_v1 --set cord:dev --batch-size 1 --run-id cord_dev_m1v1_nf4
stamp "exit=$? train M1-cord (all_plus_cord, 240 steps)"
$PY -m invoiceguard.vlm.train --profile standard --data all_plus_cord --max-steps 240 --run-id m1_cord_v1
rc=$?
stamp "train exit=$rc"
if [ $rc -ne 0 ]; then stamp "abort"; exit $rc; fi
stamp "cord dev M1-cord (nf4)"
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_cord_v1 --set cord:dev --batch-size 1 --run-id cord_dev_m1cord_nf4
stamp "exit=$? regression dev M1-cord (same sets as m1_dev_v1)"
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_cord_v1 --set public:dev --set public:dev_stress --set trade:dev --set stress:all --run-id m1cord_dev_v1
stamp "exit=$? done"
