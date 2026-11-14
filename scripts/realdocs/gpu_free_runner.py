"""Run a list of local GPU jobs only while this PC is otherwise not using the GPU (user decision 2026-11-15:
"Local, when PC is free").

Why: on Windows (WDDM) a 16 GB card shared with a game or overlay spills the trainer into system memory — measured
5.9 s/step -> 110-354 s/step on 2026-11-15 (handoff.md). So each job waits until the GPU is free, and a job that meets
contention while running is stopped and started again later:
* training restarts from step 0 (it saves only at the end, so nothing half-written is kept);
* inference resumes where it stopped (infer.py appends to the same run id and skips finished documents).

Free  = GPU memory in use < FREE_MB and no other process (except the desktop compositor and Claude's own window)
        using more than FOREIGN_UTIL % of a 3D engine, for FREE_CHECKS checks in a row.
Busy while running = (memory > SPILL_MB and (foreign 3D use or slow steps)) or slow steps for SLOW_CHECKS checks.

CPU-only (no torch import) on purpose, so it never opens a CUDA context of its own.
Usage (.venv): python scripts/realdocs/gpu_free_runner.py cord_r5_r6
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY_ML = str(REPO / ".venv-ml" / "Scripts" / "python.exe")
LOG = REPO / "artifacts" / "logs" / "gpu_runner.log"
FREE_MB, SPILL_MB = 2500, 15000
FOREIGN_UTIL = 15.0
FREE_CHECKS, CHECK_S = 3, 60
SLOW_TRAIN_S_PER_IT, SLOW_INFER_S_PER_DOC, SLOW_CHECKS = 15.0, 60.0, 6
# The trainer itself can grow past 16 GB through the CUDA caching allocator (seen 2026-11-15: python held ~15 GB at
# 354 s/step). These settings make the allocator release cached blocks early; they change memory reuse, not the math.
ALLOC_CONF = "garbage_collection_threshold:0.6,max_split_size_mb:256"
# Hard cap on the trainer's pool (12 of 16 GB; the run peaks at ~7 GB allocated): the allocator then frees cache
# instead of growing into shared memory when a desktop app holds a few hundred MB (train.py reads this variable).
MEM_FRACTION = "0.75"
# The trainer reserves nearly the whole 16 GB soon after loading (measured ~15.9 GB within a minute, 2026-11-15), so a
# running game leaves too little memory even when idle in a menu: these processes mean "not free" while they exist.
BUSY_PROCESSES = {"osu!", "leagueclient", "league of legends", "valorant", "valorant-win64-shipping"}
IGNORED = {"python", "dwm", "claude", "msedgewebview2", "explorer", "csrss", "system", "idle"}


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def gpu_mem_mb() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return int(out[0]) if out else 0


def foreign_3d_util() -> dict[str, float]:
    """3D-engine utilization per process name, excluding our own python and the desktop."""
    ps = ("$s=(Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples;"
          "$s | Where-Object { $_.CookedValue -gt 1 } | ForEach-Object { $p=($_.InstanceName -split '_')[1];"
          "$n=(Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName; \"$n`t$($_.CookedValue)\" }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    use: dict[str, float] = {}
    for line in out.splitlines():
        if "\t" in line:
            name, val = line.split("\t", 1)
            if name and name.lower() not in IGNORED:
                use[name] = use.get(name, 0.0) + float(val)
    return use


def running_busy_processes() -> list[str]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Process).ProcessName"],
                         capture_output=True, text=True).stdout
    return sorted({n.strip() for n in out.splitlines() if n.strip().lower() in BUSY_PROCESSES})


def is_contended() -> tuple[bool, str]:
    use = foreign_3d_util()
    busy: dict[str, object] = {k: round(v, 1) for k, v in use.items() if v > FOREIGN_UTIL}
    for name in running_busy_processes():
        busy.setdefault(name, "running")
    return bool(busy), json.dumps(busy)


def wait_until_free() -> None:
    streak = 0
    while streak < FREE_CHECKS:
        mem = gpu_mem_mb()
        busy, who = is_contended()
        if mem < FREE_MB and not busy:
            streak += 1
        else:
            if streak or mem >= FREE_MB or busy:
                log(f"waiting: gpu {mem} MiB, other GPU use {who}")
            streak = 0
        time.sleep(CHECK_S)


def last_rate(unit_log: Path, kind: str, start_offset: int = 0) -> float | None:
    """Speed from THIS attempt's output only (bytes after start_offset); earlier attempts are ignored."""
    if not unit_log.exists():
        return None
    tail = unit_log.read_bytes()[start_offset:][-4000:].decode("utf-8", "replace").replace("\r", "\n")
    if kind == "train":
        m = re.findall(r"([\d.]+)s/it", tail)
        return float(m[-1]) if m else None
    m = re.findall(r"(\d+)/(\d+) done, elapsed (\d+)s", tail)
    if len(m) >= 2:
        (a, _, ta), (b, _, tb) = m[-2], m[-1]
        return (int(tb) - int(ta)) / max(1, int(b) - int(a))
    return None


def kill_tree(proc: subprocess.Popen) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    proc.wait(timeout=60)


def run_unit(name: str, kind: str, cmd: list[str]) -> str:
    """'done', 'contended' or 'failed'."""
    unit_log = REPO / "artifacts" / "logs" / f"unit_{name}.log"
    log(f"start {name}: {' '.join(cmd[2:])}")
    start_offset = unit_log.stat().st_size if unit_log.exists() else 0
    with unit_log.open("ab") as out:
        env = os.environ | {"PYTORCH_CUDA_ALLOC_CONF": ALLOC_CONF, "INVOICEGUARD_CUDA_MEM_FRACTION": MEM_FRACTION}
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT, env=env)
    slow, checks = 0, 0
    while proc.poll() is None:
        time.sleep(30)
        if proc.poll() is not None:
            break
        mem = gpu_mem_mb()
        busy, who = is_contended()
        rate = last_rate(unit_log, kind, start_offset)
        limit = SLOW_TRAIN_S_PER_IT if kind == "train" else SLOW_INFER_S_PER_DOC
        slow = slow + 1 if rate is not None and rate > limit else 0
        checks += 1
        if checks % 10 == 0:  # every 5 min: memory and speed, to tell allocator growth from outside contention
            log(f"  {name}: gpu {mem} MiB, rate {rate}, other GPU use {who}")
        # stop for a real competitor (busy process while memory is full) or sustained slowness of this attempt;
        # a nearly full card alone is normal for this trainer
        if (busy and mem > SPILL_MB) or slow >= SLOW_CHECKS:
            log(f"contention in {name}: gpu {mem} MiB, rate {rate}, other GPU use {who} -> stop and wait")
            kill_tree(proc)
            return "contended"
    log(f"{name} exited {proc.returncode}")
    return "done" if proc.returncode == 0 else "failed"


def done(kind: str, out: str) -> bool:
    if kind == "train":
        return (REPO / "artifacts" / "adapters" / out / "adapter_model.safetensors").exists()
    meta = REPO / "artifacts" / "predictions" / out / "run_metadata.json"
    return meta.exists() and "finished" in json.loads(meta.read_text(encoding="utf-8"))


def plan_cord_r5_r6() -> list[tuple[str, str, str, list[str]]]:
    """docs/20 amendments 2 and 3: two more M1-cord seeds and the unit-price up-weight run, each evaluated on CORD dev."""
    units = []
    for run, data, seed in (("m1_cord_s20261114", "all_plus_cord", "20261114"), ("m1_cord_s20261115", "all_plus_cord", "20261115"),
                            ("m1_cord_up_v1", "all_plus_cord_up", "20261113")):
        units.append((f"train_{run}", "train", run, [PY_ML, "-m", "invoiceguard.vlm.train", "--profile", "standard", "--data", data,
                                                       "--max-steps", "240", "--seed", seed, "--run-id", run]))
        pred = {"m1_cord_up_v1": "cord_dev_m1cordup_nf4"}.get(run, f"cord_dev_{run.replace('m1_cord_', 'm1cord_')}_nf4")
        units.append((f"dev_{run}", "infer", pred, [PY_ML, "-m", "invoiceguard.vlm.infer", "--arm", "m1", "--adapter",
                                                     f"artifacts/adapters/{run}", "--set", "cord:dev", "--batch-size", "1",
                                                     "--run-id", pred]))
    return units


PLANS = {"cord_r5_r6": plan_cord_r5_r6}


def main() -> int:
    units = PLANS[sys.argv[1]]()
    log(f"plan {sys.argv[1]}: {[u[0] for u in units]}")
    for name, kind, out, cmd in units:
        attempts = 0
        while not done(kind, out):
            wait_until_free()
            attempts += 1
            result = run_unit(name, kind, cmd)
            if result == "failed" and not done(kind, out):
                log(f"ABORT: {name} failed (see artifacts/logs/unit_{name}.log)")
                return 1
            if attempts >= 60:
                log(f"ABORT: {name} contended 60 times")
                return 2
        log(f"{name} complete")
    log("ALL DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
