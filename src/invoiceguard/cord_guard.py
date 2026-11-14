"""Torch-free guards for the single CORD test run (docs/20 "동결"), shared by vlm/infer.py and the CPU tests.

What they enforce before any cord:test generation (astra / Fable review 2 found the old guard too weak):
* the frozen generation settings, CORD prompt, manifest AND evaluator files (cord_eval.py, cord.py, model_output.py)
  still hash to the values in configs/frozen_cord_v1.json;
* the arm and adapter are one of the frozen arms;
* that arm has not run cord:test before — checked against the run metadata of every prediction folder AND against the
  committed scoring reports (reports/eval/cord_*.json), so deleting or renaming a prediction folder does not reopen it;
* an existing run id keeps the sets it was created with (a finished test run id cannot be reused for cord:dev, which
  used to overwrite its metadata and erase the record that test had run).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FROZEN_CORD = REPO / "configs" / "frozen_cord_v1.json"
GENERATION_KEYS = ("model_revision", "max_pixels", "max_new_tokens", "do_sample", "precision", "batch_size", "padding_side")


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _same_arm(fp: dict, other: dict) -> bool:
    return other.get("arm") == fp.get("arm") and other.get("adapter_sha256") == fp.get("adapter_sha256")


def frozen_file_problems(frozen: dict, repo: Path = REPO) -> list[str]:
    """Evaluator files must be byte-identical to the freeze (they decide the verdict)."""
    return [f"frozen_mismatch:evaluator:{rel}" for rel, digest in (frozen.get("evaluator_sha256") or {}).items()
            if _sha(repo / rel) != digest]


def check_cord_frozen(fp: dict, run_id: str | None, repo: Path = REPO, frozen_path: Path | None = None) -> list[str]:
    frozen_path = frozen_path or repo / "configs" / "frozen_cord_v1.json"
    if not frozen_path.exists():
        return ["frozen_cord_config_missing"]
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    errors = [f"frozen_mismatch:{k}" for k in GENERATION_KEYS if frozen["generation"].get(k) != fp.get(k)]
    for key in ("cord_prompt_sha256", "cord_manifest_sha256"):
        if frozen[key] != fp.get(key):
            errors.append(f"frozen_mismatch:{key}")
    errors += frozen_file_problems(frozen, repo)
    if not any(a["arm"] == fp["arm"] and a.get("adapter_sha256") == fp.get("adapter_sha256") for a in frozen["arms"].values()):
        errors.append("arm_or_adapter_not_frozen")
    for meta_path in (repo / "artifacts" / "predictions").glob("*/run_metadata.json"):
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if "cord:test" not in (old.get("sets") or []) or not _same_arm(fp, old.get("fingerprint") or {}):
            continue
        if old.get("run_id") != run_id:
            errors.append(f"cord_test_already_run:{old.get('run_id')}")
        elif "finished" in old:  # the same run already completed: resuming would regenerate lost predictions (astra review 3)
            errors.append(f"cord_test_run_finished:{run_id}")
    for report in (repo / "reports" / "eval").glob("cord_*.json"):
        data = json.loads(report.read_text(encoding="utf-8"))
        if "cord:test" in (data.get("sets") or {}) and _same_arm(fp, data.get("fingerprint") or {}):
            errors.append(f"cord_test_already_scored:{report.name}")  # once scored, never again — under any run id
    return errors


def check_run_sets(meta_path: Path, sets: list[str]) -> str | None:
    """A run id keeps the sets it was created with; resuming the same sets is fine."""
    if not meta_path.exists():
        return None
    old = json.loads(meta_path.read_text(encoding="utf-8"))
    if sorted(old.get("sets") or []) != sorted(sets):
        return f"run id exists with sets {old.get('sets')}, refusing to change them to {sets}; use a new run id"
    return None
