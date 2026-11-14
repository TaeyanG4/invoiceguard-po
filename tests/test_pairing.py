"""P15: an adapter is only loaded on the base precision it was trained on (see vlm/pairing.py for the measurement)."""
import json

import pytest

from invoiceguard.vlm import pairing

REV = "89644892e4d85e24eaac8bacfd4f463576704203"


@pytest.fixture
def tmp_path(request):  # repo-local, git-ignored scratch (the sandbox cannot write the system temp dir)
    import shutil
    from pathlib import Path

    d = Path(__file__).resolve().parents[1] / "artifacts" / "test_pairing" / request.node.name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _adapter(tmp_path, name, meta):
    d = tmp_path / name
    d.mkdir()
    if meta is not None:
        (d / "run_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


def test_old_qlora_metadata_is_read_as_nf4(tmp_path):
    d = _adapter(tmp_path, "old", {"base_revision": REV, "config": {"seed": 1},
                                   "env": {"precision": "nf4_double_quant_bf16_compute; vision+lm_head not quantised", "gpu": "X"}})
    assert pairing.adapter_base(d)["precision"] == "nf4"
    assert pairing.check(d, "nf4", REV)["problems"] == []


def test_nf4_adapter_on_bf16_base_is_refused(tmp_path):
    d = _adapter(tmp_path, "q", {"base_revision": REV, "config": {"base_precision": "nf4"}, "env": {}})
    with pytest.raises(pairing.PairingError, match="nf4 base, would be served on a bf16 base"):
        pairing.check(d, "bf16", REV)


def test_explicit_mismatch_flag_is_recorded(tmp_path):
    d = _adapter(tmp_path, "q", {"base_revision": REV, "config": {"base_precision": "nf4"}, "env": {}})
    rec = pairing.check(d, "fp32", REV, allow_mismatch=True)
    assert rec["mismatch_allowed"] is True and rec["problems"]


def test_bf16_lora_pairs_with_bf16_only(tmp_path):
    d = _adapter(tmp_path, "b", {"base_revision": REV, "config": {"base_precision": "bf16"}, "env": {}})
    assert pairing.check(d, "bf16", REV)["problems"] == []
    with pytest.raises(pairing.PairingError):
        pairing.check(d, "nf4", REV)


def test_dequantised_nf4_base_counts_as_nf4(tmp_path):
    d = _adapter(tmp_path, "q", {"base_revision": REV, "config": {"base_precision": "nf4"}, "env": {}})
    base = tmp_path / "deq"
    base.mkdir()
    (base / "merge_metadata.json").write_text(json.dumps({"kind": "nf4_dequantized_bf16_base_only"}), encoding="utf-8")
    assert pairing.check(d, "bf16", REV, model_dir=base)["serving_base_precision"] == "nf4"


def test_missing_metadata_and_other_revision_are_refused(tmp_path):
    with pytest.raises(pairing.PairingError, match="no recorded base precision"):
        pairing.check(_adapter(tmp_path, "none", None), "nf4", REV)
    d = _adapter(tmp_path, "rev", {"base_revision": "0" * 40, "config": {"base_precision": "nf4"}, "env": {}})
    with pytest.raises(pairing.PairingError, match="revision"):
        pairing.check(d, "nf4", REV)


def test_real_frozen_adapter_is_nf4():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    d = repo / "artifacts" / "adapters" / "m1_standard_v1"
    if not (d / "run_metadata.json").exists():
        pytest.skip("frozen adapter not present in this checkout (git-ignored artifacts)")
    assert pairing.adapter_base(d)["precision"] == "nf4"


def test_local_vllm_up_refuses_the_nf4_adapter_on_the_raw_bf16_base(tmp_path, monkeypatch):
    """astra review 2: the old vllm_bench up() path attached the NF4-trained adapter to the raw bf16 checkpoint."""
    from invoiceguard.serving import vllm_bench

    adapter = _adapter(tmp_path, "m1", {"base_revision": REV, "config": {"base_precision": "nf4"}, "env": {}})
    model = tmp_path / REV
    model.mkdir()
    monkeypatch.setattr(vllm_bench, "ADAPTER_DIR", adapter)
    monkeypatch.setattr(vllm_bench, "MODEL_DIR", model)
    started = []
    monkeypatch.setattr(vllm_bench.subprocess, "run", lambda *a, **k: started.append(a))
    with pytest.raises(pairing.PairingError):
        vllm_bench.up("none")
    assert started == []  # refused before any docker command
    assert vllm_bench.pairing_for_up(allow_mismatch=True)["mismatch_allowed"] is True
