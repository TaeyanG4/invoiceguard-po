"""Build a step-by-step timeline (start, end, duration) of a RunPod run from its logs, so elapsed time is recorded
from evidence rather than memory (user 2026-11-14: "걸리는 시간도 잘 기록하도록해").

Inputs: the run's log folder (copied from /workspace/logs), whose orchestration logs contain "== <step> HH:MM:SS"
lines (UTC), plus optional fixed events given on the command line (e.g. Pod creation and deletion times).
Output: a Markdown table in KST with durations, and the same rows as JSON.

Usage: python scripts/runpod/timeline.py <logs-dir> --date 2026-11-14 --event "11:49:38|Pod created" ... \
         --out-md reports/runpod2/timeline.md --out-json reports/runpod2/timeline.json
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

STEP = re.compile(r"^== (?P<label>.+?) (?P<t>\d\d:\d\d:\d\d)\s*$")
ORDER = ("run2.log", "teacher_run.log", "p14.log", "teacher8b_run.log")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs")
    ap.add_argument("--date", required=True, help="UTC date of the run, YYYY-MM-DD")
    ap.add_argument("--event", action="append", default=[], help='"HH:MM:SS|label" in UTC, added to the timeline')
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    a = ap.parse_args()
    events = []
    for e in a.event:
        t, label = e.split("|", 1)
        events.append((t, label, "manual"))
    for name in ORDER:
        p = Path(a.logs) / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = STEP.match(line.strip())
            if m:
                events.append((m["t"], m["label"], name))
    events.sort(key=lambda x: x[0])
    rows, kst = [], timedelta(hours=9)
    for i, (t, label, src) in enumerate(events):
        start = datetime.fromisoformat(f"{a.date}T{t}")
        nxt = datetime.fromisoformat(f"{a.date}T{events[i + 1][0]}") if i + 1 < len(events) else None
        rows.append({"utc": t, "kst": (start + kst).strftime("%H:%M:%S"), "event": label, "source": src,
                     "until_next_s": int((nxt - start).total_seconds()) if nxt else None})
    first = datetime.fromisoformat(f"{a.date}T{events[0][0]}")
    last = datetime.fromisoformat(f"{a.date}T{events[-1][0]}")
    lines = ["| KST | UTC | event | until next event | source |", "|---|---|---|---:|---|"]
    for r in rows:
        dur = f"{r['until_next_s'] // 60}m {r['until_next_s'] % 60:02d}s" if r["until_next_s"] is not None else ""
        lines.append(f"| {r['kst']} | {r['utc']} | {r['event']} | {dur} | {r['source']} |")
    total = int((last - first).total_seconds())
    lines.append(f"\nFirst to last event: {total // 3600}h {total % 3600 // 60:02d}m {total % 60:02d}s.")
    Path(a.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    Path(a.out_json).write_text(json.dumps({"date_utc": a.date, "rows": rows, "total_s": total}, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
