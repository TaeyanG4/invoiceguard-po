"""Guarded entry point for scoring CORD runs (astra review 3: "cord_eval score/compare has no freeze check and overwrites").

  python -m invoiceguard.cord_score score artifacts/predictions/<run_id>
  python -m invoiceguard.cord_score compare <run_a> <run_b>

cord_eval.py must stay byte-identical to the hash in configs/frozen_cord_v1.json, so the checks live here instead.
For every run that covers cord:test:
* the evaluator files, the CORD prompt and the manifest still hash to the frozen values;
* the run's fingerprint carries the frozen generation settings and a frozen arm/adapter;
* the report is write-once: re-scoring may only reproduce the committed file byte for byte.
Dev runs are scored the same way without the write-once rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from . import cord_eval
from .cord_guard import GENERATION_KEYS, frozen_file_problems

REPO = Path(__file__).resolve().parents[2]
FROZEN_PATH = REPO / "configs" / "frozen_cord_v1.json"
EVAL_DIR = REPO / "reports" / "eval"


class ScoreRefused(RuntimeError):
    pass


def _meta(run: str) -> dict:
    return json.loads((REPO / "artifacts" / "predictions" / run / "run_metadata.json").read_text(encoding="utf-8"))


def freeze_problems(meta: dict, frozen: dict | None = None, repo: Path = REPO) -> list[str]:
    """Why a cord:test run may not be scored under the freeze ([] = fine). Dev-only runs need nothing."""
    if "cord:test" not in (meta.get("sets") or []):
        return []
    if frozen is None:
        if not FROZEN_PATH.exists():
            return ["frozen_cord_config_missing"]
        frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    from .extraction_request import load_prompt

    fp = meta.get("fingerprint") or {}
    problems = frozen_file_problems(frozen, repo)
    problems += [f"run_differs_from_freeze:{k}" for k in GENERATION_KEYS if fp.get(k) != frozen["generation"].get(k)]
    if load_prompt("CORD_RAW")[1] != frozen["cord_prompt_sha256"] or fp.get("cord_prompt_sha256") != frozen["cord_prompt_sha256"]:
        problems.append("prompt_differs_from_freeze")
    manifest = hashlib.sha256((repo / "manifests" / "cord_v2.jsonl").read_bytes()).hexdigest()
    if manifest != frozen["cord_manifest_sha256"] or fp.get("cord_manifest_sha256") != frozen["cord_manifest_sha256"]:
        problems.append("manifest_differs_from_freeze")
    if not any(a["arm"] == fp.get("arm") and a.get("adapter_sha256") == fp.get("adapter_sha256") for a in frozen["arms"].values()):
        problems.append("arm_or_adapter_not_frozen")
    return problems


def write_report(path: Path, report: dict, write_once: bool) -> bool:
    """Write the report as cord_eval does; a write-once report may only be reproduced, never changed."""
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return False  # reproduced exactly
        if write_once:
            raise ScoreRefused(f"{path.name} already exists with different content; a CORD test report is written once")
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def score(run: str) -> Path:
    meta = _meta(run)
    problems = freeze_problems(meta)
    if problems:
        raise ScoreRefused(f"{run}: {problems}")
    path = EVAL_DIR / f"{run}.json"
    write_report(path, cord_eval.score(run), write_once="cord:test" in meta.get("sets", []))
    return path


def compare(run_a: str, run_b: str) -> Path:
    metas = [_meta(run_a), _meta(run_b)]
    problems = [p for m in metas for p in freeze_problems(m)]
    if problems:
        raise ScoreRefused(f"{run_a} vs {run_b}: {problems}")
    path = EVAL_DIR / f"compare_{run_a}__vs__{run_b}.json"
    write_report(path, cord_eval.compare(run_a, run_b), write_once=any("cord:test" in m.get("sets", []) for m in metas))
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score"); s.add_argument("run_dir")
    c = sub.add_parser("compare"); c.add_argument("run_a"); c.add_argument("run_b")
    a = ap.parse_args()
    try:
        path = score(Path(a.run_dir).name) if a.cmd == "score" else compare(a.run_a, a.run_b)
    except ScoreRefused as exc:
        print(f"REFUSED: {exc}")
        return 2
    print(path.relative_to(REPO).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
