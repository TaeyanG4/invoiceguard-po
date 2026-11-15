"""S6: vLLM serving arm (local Docker on the 16 GB GPU, loopback only) — parity vs HF and load benchmark.

Usage (.venv):
  python -m invoiceguard.serving.vllm_bench up   [--quant none|fp8]   # start container, wait for /health
  python -m invoiceguard.serving.vllm_bench run  --label vllm_bf16      # parity + concurrency benchmark
  python -m invoiceguard.serving.vllm_bench down

Rules (docs/19 #1): HF NF4 stays the reference evaluation path. vLLM is a separate serving arm; accuracy
"parity" is reported only as field agreement on the same dev documents; speed only for the same documents
and the same max_tokens. vLLM uses continuous batching, so concurrency > 1 is real batching here.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
IMAGE = "vllm/vllm-openai:v0.11.2"
CONTAINER = "invoiceguard-vllm"
PORT = 8001
MODEL_DIR = REPO / "models" / "qwen3-vl-2b-instruct" / "89644892e4d85e24eaac8bacfd4f463576704203"
ADAPTER_DIR = REPO / "artifacts" / "adapters" / "m1_standard_v1"
OUT = REPO / "reports" / "serving"
TARGET = {"port": PORT, "conc": (1, 2, 4, 8), "arms": ("m0", "m1")}  # overridable from the CLI
MAX_TOKENS = 1536


def pairing_for_up(allow_mismatch: bool = False) -> dict:
    """up() serves the raw bf16 checkpoint with the LoRA adapter attached (--enable-lora). The M1 adapter was trained
    on the NF4 base, so this pairing is refused (P15; run 1 lost 0.960 -> 0.849 this way) unless explicitly allowed
    for a precision experiment. The fixed path is the dequantised-NF4 merge served without LoRA (reports/runpod2/)."""
    from ..vlm.pairing import check
    return check(ADAPTER_DIR, "bf16", MODEL_DIR.name, MODEL_DIR, allow_mismatch=allow_mismatch)


def up(quant: str, allow_mismatch: bool = False) -> None:
    pairing = pairing_for_up(allow_mismatch)  # raises PairingError before any container starts
    if pairing["mismatch_allowed"]:
        print("WARNING: serving an adapter on a base it was not trained on (exploratory): " + "; ".join(pairing["problems"]))
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    args = ["docker", "run", "-d", "--name", CONTAINER, "--gpus", "all", "--ipc", "host",
            "-p", f"127.0.0.1:{PORT}:8000",  # loopback only; never 0.0.0.0
            "-e", "NVIDIA_DISABLE_REQUIRE=1",  # experiment: CUDA 12.9 image on a 12.6 driver via minor-version compatibility
            "-v", f"{MODEL_DIR}:/model:ro", "-v", f"{ADAPTER_DIR}:/adapters/m1:ro",
            IMAGE, "--model", "/model", "--served-model-name", "base", "--dtype", "bfloat16",
            "--enable-lora", "--lora-modules", "m1=/adapters/m1", "--max-lora-rank", "8", "--max-loras", "1",
            "--max-model-len", "4096", "--gpu-memory-utilization", "0.82", "--limit-mm-per-prompt", '{"image":1}',
            "--mm-processor-kwargs", '{"min_pixels":65536,"max_pixels":786432}', "--seed", "20261113"]
    if quant == "fp8":
        args += ["--quantization", "fp8"]
    subprocess.run(args, check=True)
    deadline = time.time() + 900
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as r:
                if r.status == 200:
                    print("vLLM healthy")
                    return
        except Exception:
            pass
        state = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER], capture_output=True, text=True)
        if state.stdout.strip() != "true":
            logs = subprocess.run(["docker", "logs", "--tail", "40", CONTAINER], capture_output=True, text=True, errors="replace")
            print((logs.stdout + logs.stderr)[-4000:])
            raise SystemExit("container exited before becoming healthy")
        time.sleep(5)
    raise SystemExit("vLLM did not become healthy within 15 min")


def down() -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], check=False)


def _request(model: str, prompt: str, image_path: Path) -> dict:
    data_url = "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode()
    body = {"model": model, "temperature": 0, "max_tokens": MAX_TOKENS, "seed": 20261113,
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_url}},
                                                      {"type": "text", "text": prompt}]}]}
    req = urllib.request.Request(f"http://127.0.0.1:{TARGET['port']}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            payload = json.loads(r.read())
        choice = payload["choices"][0]
        return {"ok": True, "latency_s": time.perf_counter() - start, "raw_response": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"), "prompt_tokens": payload["usage"]["prompt_tokens"],
                "completion_tokens": payload["usage"]["completion_tokens"]}
    except Exception as exc:  # recorded, never dropped — with the HTTP status when there is one (429 queue full, 504 deadline)
        return {"ok": False, "latency_s": time.perf_counter() - start, "error": repr(exc)[:200],
                "http_status": getattr(exc, "code", None)}


def _gpu_mem_mb() -> int | None:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
    try:
        return int(out.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def _fields(record_id: str, raw: str, finish_reason: str | None) -> tuple[int, int]:
    """(correct, scored) fields of one served answer, with the evaluation path's own scorer for the bench's task:
    TRADE_RAW (strict parse, as score_run) or CORD_RAW (fence-stripped parse and positional fields, as cord_eval)."""
    from ..evaluation import parse_for_eval

    pred = {"raw_response": raw, "finish_reason": "length" if finish_reason == "length" else "stop"}
    if TARGET.get("task") == "cord":
        from ..cord import load_gold, manifest_rows
        from ..cord_eval import score_document

        masked = next(r["masked"] for r in manifest_rows("dev") if r["id"] == record_id)
        s = score_document(load_gold(record_id), masked, parse_for_eval(pred, "CORD_RAW", lenient=True))
        return s["strict"][0], s["strict"][1]
    from ..evaluation import score_trade_document

    gold = json.loads((REPO / "data" / "processed" / "trade" / "gold" / f"{record_id}.json").read_text(encoding="utf-8"))
    s = score_trade_document(gold, parse_for_eval(pred, "TRADE_RAW"))
    return sum(c for c, _ in s["fields"].values()), sum(n for _, n in s["fields"].values())


def _server_identity() -> dict:
    """What the server says it is serving (HF server /health: base revision and adapter SHA-256; vLLM: model names), so a
    serving report is tied to a specific adapter, not only to a label (Fable review 5)."""
    out = {}
    for route in ("health", "v1/models"):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{TARGET['port']}/{route}", timeout=10) as resp:
                body = resp.read().decode("utf-8")
            out[route] = json.loads(body) if body.strip() else {}
        except (OSError, ValueError) as exc:
            out[route] = {"error": type(exc).__name__}
    return out


def _offline_adapter(run: str) -> str | None:
    meta = REPO / "artifacts" / "predictions" / run / "run_metadata.json"
    if not meta.exists():
        return None
    return (json.loads(meta.read_text(encoding="utf-8")).get("fingerprint") or {}).get("adapter_sha256")


def _prior_parity(arm: str, doc_ids: list[str], served_sha: str | None) -> tuple[list, list]:
    old = json.loads((REPO / TARGET["parity_from"]).read_text(encoding="utf-8"))
    entry = old["arms"][arm]
    if [r["id"] for r in entry["requests_c1"]] != doc_ids or old.get("adapter", {}).get("served_sha256") != served_sha:
        raise SystemExit("--parity-from report covers other documents or another adapter; run the parity pass instead")
    return entry["parity_rows"], entry["requests_c1"]


def _bench_docs(n_docs: int) -> list:
    from ..vlm.records import cord_records, trade_records

    return (cord_records("dev") if TARGET.get("task") == "cord" else trade_records("standard_role", "dev"))[:n_docs]


def _offline_run(arm: str) -> str:
    """Offline (HF evaluation path) predictions the served answers are compared with, same documents."""
    if TARGET.get("task") == "cord":
        return (TARGET.get("offline") or {}).get(arm) or {"m0": "cord_dev_m0_nf4", "m1": "cord_dev_m1cord_nf4"}[arm]
    return f"{arm}_dev_v1"


def _retrying(request, retries: int = 40, backoff_s: float = 1.0):
    """Client behaviour the bounded queue expects (--retry-429): on HTTP 429 wait (exponential backoff with jitter,
    capped at 8 s) and send again. Latency is end to end from the first attempt, so waiting in the client counts."""
    import random

    def call(model, prompt, image_path):
        start = time.perf_counter()
        for attempt in range(retries + 1):
            r = request(model, prompt, image_path)
            if r.get("http_status") != 429 or attempt == retries:
                return dict(r, attempts=attempt + 1, latency_s=time.perf_counter() - start)
            time.sleep(min(backoff_s * 1.5 ** attempt, 8.0) * (0.5 + random.random()))
        raise AssertionError("unreachable")
    return call


def _load(model: str, docs: list, conc: int, reps: int, duration_s: float | None, c1_raw: dict, request=None) -> dict:
    """One load level. Every answer is kept and scored — not only latency (astra review 3: the old loop counted HTTP
    successes only, so quality under concurrency and truncation were invisible). With duration_s the level runs as a
    sustained load: `conc` requests stay in flight, cycling through the documents, until the time is up."""
    request = request or _request
    if TARGET.get("retry_429"):
        request = _retrying(request, backoff_s=TARGET.get("retry_backoff_s", 1.0))
    lat, mem, codes = [], [], {}
    retries = 0
    correct = scored = truncated = same_as_c1 = answered = 0
    start = time.perf_counter()
    order = [d for _ in range(reps) for d in docs] if not duration_s else None
    sent = 0
    with cf.ThreadPoolExecutor(max_workers=conc) as pool:
        inflight: dict = {}

        def submit_next() -> bool:
            nonlocal sent
            if order is not None:
                if sent >= len(order):
                    return False
                d = order[sent]
            else:
                if time.perf_counter() - start >= duration_s:
                    return False
                d = docs[sent % len(docs)]
            inflight[pool.submit(request, model, d.prompt(), d.image_path)] = d
            sent += 1
            return True

        while len(inflight) < conc and submit_next():
            pass
        while inflight:
            done, _ = cf.wait(list(inflight), return_when=cf.FIRST_COMPLETED)
            for fut in done:
                d = inflight.pop(fut)
                r = fut.result()
                mem.append(_gpu_mem_mb())
                code = r.get("http_status", 200 if r["ok"] else None)
                retries += r.get("attempts", 1) - 1
                codes[str(code)] = codes.get(str(code), 0) + 1
                if r["ok"]:
                    answered += 1
                    lat.append(r["latency_s"])
                    truncated += r.get("finish_reason") == "length"
                    c, n = _fields(d.record_id, r["raw_response"], r.get("finish_reason"))
                    correct, scored = correct + c, scored + n
                    same_as_c1 += (c1_raw.get(d.record_id) or "").strip() == (r["raw_response"] or "").strip()
                submit_next()
    wall = time.perf_counter() - start
    lat.sort()
    return {"requests": sent, "failures": sent - answered, "status_codes": codes, "wall_s": round(wall, 2),
            "client": "retry_429" if TARGET.get("retry_429") else "no_retry", "retries_after_429": retries,
            "sustained_s": duration_s, "docs_per_min": round(60 * answered / wall, 2) if wall else None,
            "p50_s": round(statistics.median(lat), 2) if lat else None,
            "p95_s": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 2) if lat else None,
            "field_accuracy": round(correct / scored, 4) if scored else None, "fields": [correct, scored],
            "truncated": truncated, "identical_to_concurrency1_rate": round(same_as_c1 / answered, 4) if answered else None,
            "gpu_mem_mb_max": max(m for m in mem if m is not None) if any(m is not None for m in mem) else None}


def run(label: str, n_docs: int, warmups: int, reps: int) -> Path:
    docs = _bench_docs(n_docs)
    hf = {}
    for arm in ("m0", "m1"):
        path = REPO / "artifacts" / "predictions" / _offline_run(arm) / "predictions.jsonl"
        if path.exists():
            hf[arm] = {json.loads(l)["id"]: json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}
    result = {"label": label, "task": TARGET.get("task", "trade"), "server_port": TARGET["port"], "docs": [d.record_id for d in docs],
              "max_tokens": MAX_TOKENS, "warmups": warmups, "repetitions": reps,
              "offline_runs": {arm: _offline_run(arm) for arm in ("m0", "m1")}, "server": _server_identity(), "arms": {}}
    health = result["server"].get("health") or {}
    served = (health.get("adapters") or {}).get(TARGET.get("m1_model", "m1")) or health.get("adapter_sha256")
    offline_m1 = _offline_adapter(_offline_run("m1"))
    result["adapter"] = {"m1_served_as": TARGET.get("m1_model", "m1"), "served_sha256": served, "offline_m1_sha256": offline_m1,
                         "same_adapter_as_offline_m1": bool(served) and served == offline_m1}
    for arm, model in (("m0", "base"), ("m1", TARGET.get("m1_model", "m1"))):
        if arm not in TARGET["arms"]:
            continue
        for d in docs[:warmups]:
            _request(model, d.prompt(), d.image_path)
        # parity pass (concurrency 1): same docs as HF dev run. --parity-from reuses the concurrency-1 answers of an
        # earlier report from the SAME server setup (same adapter hash and documents, checked) instead of regenerating them.
        parity, rows = [], []
        prior = _prior_parity(arm, [d.record_id for d in docs], result["adapter"]["served_sha256"]) if TARGET.get("parity_from") else None
        if prior is not None:
            parity, rows = prior
            result["parity_from"] = TARGET["parity_from"]
        for d in ([] if prior is not None else docs):
            r = _request(model, d.prompt(), d.image_path)
            # raw responses are kept: the 2026-11-14 RunPod run dropped them and the M1 field loss under vLLM
            # (exactly 4 fields per document) could then only be inferred from token counts
            rows.append({"id": d.record_id, **r})
            if r["ok"]:
                entry = {"id": d.record_id, "server_fields": list(_fields(d.record_id, r["raw_response"], r["finish_reason"]))}
                if arm in hf and d.record_id in hf[arm]:
                    h = hf[arm][d.record_id]
                    entry["identical_raw_to_hf"] = (h.get("raw_response") or "").strip() == r["raw_response"].strip()
                    entry["hf_fields"] = list(_fields(d.record_id, h.get("raw_response"), h.get("finish_reason")))
                parity.append(entry)
        c1_raw = {row["id"]: row.get("raw_response") for row in rows if row.get("ok")}
        bench = {}
        for conc in TARGET["conc"]:
            bench[str(conc)] = _load(model, docs, conc, reps, TARGET.get("duration_s"), c1_raw)
            print(label, arm, conc, {k: v for k, v in bench[str(conc)].items() if k != "status_codes"}, flush=True)
        vc = sum(p["server_fields"][0] for p in parity)
        vs = sum(p["server_fields"][1] for p in parity)
        hc = sum(p.get("hf_fields", [0, 0])[0] for p in parity)
        hs = sum(p.get("hf_fields", [0, 0])[1] for p in parity)
        result["arms"][arm] = {"parity_rows": parity, "requests_c1": rows,
                               "server_field_accuracy": round(vc / vs, 4) if vs else None,
                               "offline_hf_field_accuracy_same_docs": round(hc / hs, 4) if hs else None,
                               "identical_raw_rate": round(sum(p.get("identical_raw_to_hf", False) for p in parity) / len(parity), 4) if parity else None,
                               "prompt_tokens": sorted({r.get("prompt_tokens") for r in rows if r.get("ok")}),
                               "bench": bench}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{label}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["up", "run", "down"])
    parser.add_argument("--quant", choices=["none", "fp8"], default="none")
    parser.add_argument("--label", default="vllm_bf16")
    parser.add_argument("--docs", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--conc", default="1,2,4,8")
    parser.add_argument("--arms", default="m0,m1", help="which served models to measure: m0 = served name base, m1 = served name m1")
    parser.add_argument("--task", choices=["trade", "cord"], default="trade",
                        help="documents and scorer: own TRADE_RAW dev (default) or CORD v2 dev receipts (CORD_RAW)")
    parser.add_argument("--parity-from", help="reuse the concurrency-1 parity answers of this earlier report (same docs and adapter)")
    parser.add_argument("--retry-429", action="store_true",
                        help="client retries a 429 (queue full) with backoff; latency stays end to end (goodput under overload)")
    parser.add_argument("--m1-model", default="m1",
                        help="served model name for the m1 arm (a multi-LoRA server may serve M1-cord as e.g. 'cord')")
    parser.add_argument("--offline-m1", help="offline prediction run to compare the served m1 with (CORD: default cord_dev_m1cord_nf4)")
    parser.add_argument("--duration", type=float, default=None,
                        help="sustained load: keep each concurrency level busy for this many seconds instead of reps × docs")
    parser.add_argument("--allow-precision-mismatch", action="store_true",
                        help="exploratory only: serve the NF4-trained adapter on the bf16 base (reproduces run 1)")
    args = parser.parse_args()
    TARGET["port"], TARGET["conc"] = args.port, tuple(int(x) for x in args.conc.split(","))
    TARGET["arms"] = tuple(args.arms.split(","))
    TARGET["duration_s"] = args.duration
    TARGET["task"] = args.task
    TARGET["m1_model"] = args.m1_model
    TARGET["retry_429"] = args.retry_429
    TARGET["parity_from"] = args.parity_from
    TARGET["offline"] = {"m1": args.offline_m1} if args.offline_m1 else {}
    if args.command == "up":
        up(args.quant, args.allow_precision_mismatch)
    elif args.command == "down":
        down()
    else:
        print(run(args.label, args.docs, args.warmups, args.reps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
