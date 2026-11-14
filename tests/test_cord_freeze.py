"""CORD single-test-run integrity (docs/20 "동결"), CPU only.

1. The committed results were produced under the freeze: evaluator files, prompt and manifest still hash to the
   values in configs/frozen_cord_v1.json, and every committed CORD test report matches a frozen arm and the frozen
   generation settings, once per arm. A later edit to the scorer fails CI instead of silently changing the verdict.
2. The run guard (cord_guard.py) refuses a second test run per arm even if the prediction folder was renamed or
   deleted, and a finished test run id cannot be reused for another set.
"""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from invoiceguard import cord_guard

REPO = Path(__file__).resolve().parents[1]
FROZEN = json.loads((REPO / "configs" / "frozen_cord_v1.json").read_text(encoding="utf-8"))


def test_scorer_prompt_and_manifest_are_still_the_frozen_files():
    from invoiceguard.extraction_request import load_prompt

    assert cord_guard.frozen_file_problems(FROZEN) == []
    assert load_prompt("CORD_RAW")[1] == FROZEN["cord_prompt_sha256"]
    assert hashlib.sha256((REPO / "manifests" / "cord_v2.jsonl").read_bytes()).hexdigest() == FROZEN["cord_manifest_sha256"]


def test_committed_test_reports_are_one_per_frozen_arm_under_the_frozen_settings():
    arms = {(a["arm"], a["adapter_sha256"]): name for name, a in FROZEN["arms"].items()}
    seen = []
    for path in sorted((REPO / "reports" / "eval").glob("cord_*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if "cord:test" not in report.get("sets", {}):
            continue
        fp = report["fingerprint"]
        assert (fp["arm"], fp.get("adapter_sha256")) in arms, path.name
        assert {k: fp.get(k) for k in FROZEN["generation"]} == FROZEN["generation"], path.name
        assert fp["cord_prompt_sha256"] == FROZEN["cord_prompt_sha256"] and fp["cord_manifest_sha256"] == FROZEN["cord_manifest_sha256"]
        seen.append(arms[(fp["arm"], fp.get("adapter_sha256"))])
    assert len(seen) == len(set(seen)), f"an arm has more than one CORD test report: {seen}"


@pytest.fixture
def fake_repo(request):
    root = REPO / "artifacts" / "test_cord_guard" / request.node.name
    shutil.rmtree(root, ignore_errors=True)
    for rel in ("configs", "artifacts/predictions", "reports/eval", "src"):
        (root / rel).mkdir(parents=True)
    (root / "src" / "scorer.py").write_text("print('frozen scorer')\n", encoding="utf-8")
    frozen = {"generation": {k: 1 for k in cord_guard.GENERATION_KEYS}, "cord_prompt_sha256": "p", "cord_manifest_sha256": "m",
              "evaluator_sha256": {"src/scorer.py": hashlib.sha256((root / "src" / "scorer.py").read_bytes()).hexdigest()},
              "arms": {"M1_cord": {"arm": "m1", "adapter_sha256": "A"}}}
    (root / "configs" / "frozen_cord_v1.json").write_text(json.dumps(frozen), encoding="utf-8")
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _fp():
    return {"arm": "m1", "adapter_sha256": "A", "cord_prompt_sha256": "p", "cord_manifest_sha256": "m",
            **{k: 1 for k in cord_guard.GENERATION_KEYS}}


def _ran_test(root, run_id):
    d = root / "artifacts" / "predictions" / run_id
    d.mkdir()
    (d / "run_metadata.json").write_text(json.dumps({"run_id": run_id, "sets": ["cord:test"], "fingerprint": _fp()}), encoding="utf-8")
    (root / "reports" / "eval" / f"cord_{run_id}.json").write_text(  # scoring reports are named cord_<run>.json
        json.dumps({"run_id": run_id, "fingerprint": _fp(), "sets": {"cord:test": {}}}), encoding="utf-8")
    return d


def test_first_test_run_is_allowed(fake_repo):
    assert cord_guard.check_cord_frozen(_fp(), "t1", repo=fake_repo) == []


def test_second_test_run_is_refused_even_after_deleting_the_predictions(fake_repo):
    d = _ran_test(fake_repo, "t1")
    assert any(e.startswith("cord_test_already_run") for e in cord_guard.check_cord_frozen(_fp(), "t2", repo=fake_repo))
    shutil.rmtree(d)  # the committed scoring report still blocks it — also under the original run id
    for run_id in ("t2", "t1"):
        assert any(e.startswith("cord_test_already_scored") for e in cord_guard.check_cord_frozen(_fp(), run_id, repo=fake_repo))


def test_resuming_the_same_present_run_is_allowed(fake_repo):
    _ran_test(fake_repo, "t1")
    assert cord_guard.check_cord_frozen(_fp(), "t1", repo=fake_repo) == []


def test_edited_scorer_and_unfrozen_adapter_are_refused(fake_repo):
    (fake_repo / "src" / "scorer.py").write_text("print('changed after the freeze')\n", encoding="utf-8")
    errors = cord_guard.check_cord_frozen(_fp() | {"adapter_sha256": "B"}, "t1", repo=fake_repo)
    assert "frozen_mismatch:evaluator:src/scorer.py" in errors and "arm_or_adapter_not_frozen" in errors


def test_a_finished_test_run_id_cannot_be_reused_for_dev(fake_repo):
    d = _ran_test(fake_repo, "t1")
    assert cord_guard.check_run_sets(d / "run_metadata.json", ["cord:dev"])  # problem text, not None
    assert cord_guard.check_run_sets(d / "run_metadata.json", ["cord:test"]) is None
