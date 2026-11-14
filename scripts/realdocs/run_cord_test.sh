#!/usr/bin/env bash
# CORD test (docs/20_DECISIONS_V6.md): runs ONCE per frozen arm, after configs/frozen_cord_v1.json exists.
# Local RTX 4070 Ti SUPER, NF4, batch 1 — exactly the dev settings recorded in the freeze. One GPU job at a time.
# Order: the primary pair first (M0, M1-cord), then the auxiliary arm (M1 v1). infer.py refuses a second test run
# of the same arm/adapter under a different run id.
# Each step prints "== <label> HH:MM:SS" (UTC) for the timeline.
set -u
cd "$(dirname "$0")/../.."
PY=.venv-ml/Scripts/python.exe
stamp() { echo "== $1 $(date -u +%H:%M:%S)"; }
if [ ! -f configs/frozen_cord_v1.json ]; then echo "configs/frozen_cord_v1.json missing — freeze first"; exit 2; fi

stamp "cord test M0 (nf4)"
$PY -m invoiceguard.vlm.infer --arm m0 --set cord:test --batch-size 1 --allow-final --run-id cord_test_m0_nf4
stamp "exit=$? cord test M1-cord (nf4)"
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_cord_v1 --set cord:test --batch-size 1 --allow-final --run-id cord_test_m1cord_nf4
stamp "exit=$? cord test M1 v1 (nf4)"
$PY -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_standard_v1 --set cord:test --batch-size 1 --allow-final --run-id cord_test_m1v1_nf4
stamp "exit=$? done"
