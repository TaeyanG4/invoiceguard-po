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
    for rel in ("configs", "artifacts/predictions", "reports/eval", "src", "manifests"):
        (root / rel).mkdir(parents=True)
    (root / "manifests" / "cord_v2.jsonl").write_text("{}\n", encoding="utf-8")
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


def _ran_test(root, run_id, finished=True, scored=True):
    d = root / "artifacts" / "predictions" / run_id
    d.mkdir()
    meta = {"run_id": run_id, "sets": ["cord:test"], "fingerprint": _fp()} | ({"finished": "2026-11-15T01:00:00"} if finished else {})
    (d / "run_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    if scored:
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


def test_only_an_interrupted_unscored_run_may_resume(fake_repo):
    _ran_test(fake_repo, "t1", finished=False, scored=False)  # crashed half way: resuming the same run id is allowed
    assert cord_guard.check_cord_frozen(_fp(), "t1", repo=fake_repo) == []


def test_a_finished_or_scored_run_cannot_resume_to_regenerate_lost_predictions(fake_repo):
    """astra review 3: losing predictions.jsonl of a completed run must not let the same run id generate again."""
    _ran_test(fake_repo, "t1", finished=True, scored=False)
    assert "cord_test_run_finished:t1" in cord_guard.check_cord_frozen(_fp(), "t1", repo=fake_repo)
    (fake_repo / "artifacts" / "predictions" / "t1" / "run_metadata.json").unlink()
    _ran_test_report_only = fake_repo / "reports" / "eval" / "cord_t1.json"
    _ran_test_report_only.write_text(json.dumps({"run_id": "t1", "fingerprint": _fp(), "sets": {"cord:test": {}}}), encoding="utf-8")
    assert "cord_test_already_scored:cord_t1.json" in cord_guard.check_cord_frozen(_fp(), "t1", repo=fake_repo)


def test_guarded_scoring_refuses_a_changed_scorer_and_a_changed_report(fake_repo, monkeypatch):
    """astra review 3: scoring itself checks the freeze; a test report is write-once (re-scoring may only reproduce it)."""
    from invoiceguard import cord_score

    frozen = json.loads((fake_repo / "configs" / "frozen_cord_v1.json").read_text(encoding="utf-8"))
    meta = {"sets": ["cord:test"], "fingerprint": _fp()}
    (fake_repo / "src" / "scorer.py").write_text("print('edited after the freeze')\n", encoding="utf-8")
    assert "frozen_mismatch:evaluator:src/scorer.py" in cord_score.freeze_problems(meta, frozen, repo=fake_repo)
    assert cord_score.freeze_problems({"sets": ["cord:dev"], "fingerprint": {}}, frozen, repo=fake_repo) == []
    report = fake_repo / "reports" / "eval" / "cord_t9.json"
    assert cord_score.write_report(report, {"a": 1}, write_once=True) is True
    assert cord_score.write_report(report, {"a": 1}, write_once=True) is False  # identical re-score
    with pytest.raises(cord_score.ScoreRefused):
        cord_score.write_report(report, {"a": 2}, write_once=True)
    assert cord_score.write_report(report, {"a": 2}, write_once=False) is True  # dev reports may be refreshed


def test_edited_scorer_and_unfrozen_adapter_are_refused(fake_repo):
    (fake_repo / "src" / "scorer.py").write_text("print('changed after the freeze')\n", encoding="utf-8")
    errors = cord_guard.check_cord_frozen(_fp() | {"adapter_sha256": "B"}, "t1", repo=fake_repo)
    assert "frozen_mismatch:evaluator:src/scorer.py" in errors and "arm_or_adapter_not_frozen" in errors


def test_a_finished_test_run_id_cannot_be_reused_for_dev(fake_repo):
    d = _ran_test(fake_repo, "t1")
    assert cord_guard.check_run_sets(d / "run_metadata.json", ["cord:dev"])  # problem text, not None
    assert cord_guard.check_run_sets(d / "run_metadata.json", ["cord:test"]) is None


def test_scorer_dependencies_are_pinned_to_the_freeze_commit(fake_repo):
    """astra review 4: evaluation.py / public_data.py etc. decide the score too, so they are pinned like the evaluator."""
    deps = json.loads((REPO / "configs" / "frozen_cord_v1_deps.json").read_text(encoding="utf-8"))
    for rel, digest in deps["dependency_sha256"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    assert deps["freeze_commit"].startswith(FROZEN["git_commit"][:7])
    # a changed dependency is refused like a changed evaluator
    (fake_repo / "src" / "dep.py").write_bytes(b"x = 1\n")  # bytes: no newline translation on Windows
    (fake_repo / "configs" / "frozen_cord_v1_deps.json").write_text(json.dumps(
        {"dependency_sha256": {"src/dep.py": hashlib.sha256(b"x = 1\n").hexdigest()}}), encoding="utf-8")
    frozen = json.loads((fake_repo / "configs" / "frozen_cord_v1.json").read_text(encoding="utf-8"))
    assert cord_guard.frozen_file_problems(frozen, fake_repo) == []
    (fake_repo / "src" / "dep.py").write_bytes(b"x = 2\n")
    assert cord_guard.frozen_file_problems(frozen, fake_repo) == ["frozen_mismatch:dependency:src/dep.py"]
