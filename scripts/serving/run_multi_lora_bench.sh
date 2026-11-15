#!/usr/bin/env bash
# One local HF+PEFT server, one NF4 base, two LoRA adapters (m1 = M1 v1 for invoices, cord = M1-cord for receipts),
# chosen per request. Full dev sets, every answer scored, then a 5-minute sustained load (Fable review 5:
# "10 documents, one repetition"; serving reports now record the adapter hash the server reports).
# Local RTX 4070 Ti SUPER, loopback only. "== <label> HH:MM:SS" (UTC) stamps.
set -u
cd "$(dirname "$0")/../.."
stamp() { echo "== $1 $(date -u +%H:%M:%S)"; }
export PYTHONIOENCODING=utf-8
stamp "server start"
.venv-ml/Scripts/python.exe -m invoiceguard.serving.hf_server --adapter artifacts/adapters/m1_standard_v1 \
  --extra-adapter cord=artifacts/adapters/m1_cord_v1 --port 8001 > artifacts/logs/hf_server_multi.log 2>&1 &
for i in $(seq 1 180); do curl -s -m 2 http://127.0.0.1:8001/health > /dev/null 2>&1 && break; sleep 2; done
curl -s http://127.0.0.1:8001/health; echo
B=".venv/Scripts/python.exe -m invoiceguard.serving.vllm_bench run --port 8001"
stamp "trade (M1 v1 as m1), 24 own dev"
$B --label hf_multi_lora_trade --task trade --arms m1 --docs 24 --conc 1,2,4 --warmups 2 --reps 1; stamp "exit=$? trade"
stamp "cord (M1-cord as cord), 100 CORD dev"
$B --label hf_multi_lora_cord --task cord --arms m1 --m1-model cord --docs 100 --conc 1,2,4 --warmups 2 --reps 1; stamp "exit=$? cord"
stamp "cord sustained 300 s"
$B --label hf_multi_lora_cord_sustained --task cord --arms m1 --m1-model cord --docs 100 --conc 2 --duration 300 --warmups 1 --reps 1; stamp "exit=$? sustained"
stamp "server stop"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*hf_server*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
stamp "ALL DONE"
