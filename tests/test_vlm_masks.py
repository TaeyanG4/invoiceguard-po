"""M01 regression: loss mask on the expanded image-token sequence (runs only in .venv-ml with the pinned processor)."""
import json

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("torchvision")

from invoiceguard.vlm import MODEL_DIR  # noqa: E402

pytestmark = pytest.mark.skipif(not (MODEL_DIR / "tokenizer.json").exists(), reason="pinned processor files not downloaded")


@pytest.fixture(scope="module")
def processor():
    from invoiceguard.vlm.sft import load_processor

    return load_processor()


def _trade_record():
    from invoiceguard.vlm.records import trade_records

    records = trade_records()
    if not records or not records[0].image_path.exists():
        pytest.skip("trade data not generated")
    return records[0]


def test_m01_answer_only_loss_on_expanded_tokens(processor):
    from invoiceguard.vlm.sft import IGNORE, encode

    rec = _trade_record()
    enc = encode(processor, rec.image(), rec.prompt(), rec.answer)
    assert enc.check_errors == []
    assert enc.n_answer > 0 and enc.n_image_tokens > 0
    trained = enc.labels != IGNORE
    image_id = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
    assert not bool((enc.batch["input_ids"][0][trained] == image_id).any())
    assert processor.tokenizer.decode(enc.batch["input_ids"][0][trained]) == rec.answer + "<|im_end|>"


def test_corrupted_answer_alignment_is_detected(processor):
    """If the trained span would not decode to the gold answer, encode() must report it (no silent pass)."""
    from invoiceguard.vlm.sft import encode

    rec = _trade_record()
    enc = encode(processor, rec.image(), rec.prompt(), rec.answer)
    enc.labels[: enc.n_prompt + 1] = -100  # simulate an off-by-one mask
    trained_text = processor.tokenizer.decode(enc.batch["input_ids"][0][enc.labels != -100])
    assert trained_text != rec.answer + "<|im_end|>"


def test_answer_is_compact_json_matching_gold(processor):
    rec = _trade_record()
    obj = json.loads(rec.answer)
    assert obj["schema_version"] == "1.0" and "\n" not in rec.answer
