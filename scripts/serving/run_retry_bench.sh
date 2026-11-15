#!/usr/bin/env bash
# Goodput under overload with a client that retries 429 (queue full) with backoff — the behaviour the bounded queue
# expects. Same two-adapter server as run_multi_lora_bench.sh; the concurrency-1 parity answers are reused from that run
# (same documents and adapter hash, checked). Local RTX 4070 Ti SUPER, loopback only.
set -u
cd "$(dirname "$0")/../.."
stamp() { echo "== $1 $(date -u +%H:%M:%S)"; }
export PYTHONIOENCODING=utf-8
stamp "server start"
.venv-ml/Scripts/python.exe -m invoiceguard.serving.hf_server --adapter artifacts/adapters/m1_standard_v1 \
  --extra-adapter cord=artifacts/adapters/m1_cord_v1 --port 8001 > artifacts/logs/hf_server_retry.log 2>&1 &
for i in $(seq 1 180); do curl -s -m 2 http://127.0.0.1:8001/health > /dev/null 2>&1 && break; sleep 2; done
B=".venv/Scripts/python.exe -m invoiceguard.serving.vllm_bench run --port 8001 --retry-429 --warmups 1 --reps 1"
stamp "cord retry, concurrency 4 and 8"
$B --label hf_multi_lora_cord_retry --task cord --arms m1 --m1-model cord --docs 100 --conc 4,8 \
  --parity-from reports/serving/hf_multi_lora_cord.json; stamp "exit=$? cord retry"
stamp "trade retry, concurrency 4"
$B --label hf_multi_lora_trade_retry --task trade --arms m1 --docs 24 --conc 4 \
  --parity-from reports/serving/hf_multi_lora_trade.json; stamp "exit=$? trade retry"
stamp "server stop"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*hf_server*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
stamp "ALL DONE"
