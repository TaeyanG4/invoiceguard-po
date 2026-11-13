"""Completion-only encoding with VERIFIED loss masks on the expanded image-token batch (docs/15 C).

Not a prompt-length estimate: the prompt is tokenised together with the same image and must be an
exact token prefix of the full conversation. Everything up to and including the generation prompt is
-100; the answer JSON plus the closing <|im_end|> are trained; anything after <|im_end|> is -100.
Records are never truncated; over-budget records are reported, not cut.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from . import MODEL_DIR

MAX_PIXELS = 786_432       # configs/project.yaml model.max_pixels
MIN_PIXELS = 65_536        # processor default shortest_edge
SEQUENCE_BUDGET = 6_144    # training.sequence_budget
MAX_NEW_TOKENS = 1_536     # model.max_new_tokens
IGNORE = -100


def load_processor(model_dir=MODEL_DIR):
    from transformers import AutoProcessor

    processor = AutoProcessor.from_pretrained(str(model_dir))
    processor.image_processor.size = {"shortest_edge": MIN_PIXELS, "longest_edge": MAX_PIXELS}
    return processor


def user_messages(prompt: str) -> list[dict]:
    return [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]


@dataclass
class Encoded:
    batch: dict
    labels: torch.Tensor
    n_prompt: int
    n_answer: int
    n_image_tokens: int
    n_total: int
    check_errors: list


def encode(processor, image, prompt: str, answer: str) -> Encoded:
    tok = processor.tokenizer
    user = user_messages(prompt)
    full = user + [{"role": "assistant", "content": [{"type": "text", "text": answer}]}]
    prompt_text = processor.apply_chat_template(user, tokenize=False, add_generation_prompt=True)
    full_text = processor.apply_chat_template(full, tokenize=False, add_generation_prompt=False)
    errors = []
    if not full_text.startswith(prompt_text):
        errors.append("chat_template_prompt_not_text_prefix")
    enc_full = processor(text=[full_text], images=[image], return_tensors="pt")
    enc_prompt = processor(text=[prompt_text], images=[image], return_tensors="pt")
    ids, pids = enc_full["input_ids"][0], enc_prompt["input_ids"][0]
    n_prompt = len(pids)
    if len(ids) <= n_prompt or not torch.equal(ids[:n_prompt], pids):
        errors.append("prompt_not_token_prefix_of_full_sequence")
    labels = ids.clone()
    labels[:n_prompt] = IGNORE
    im_end = tok.convert_tokens_to_ids("<|im_end|>")
    tail = (ids[n_prompt:] == im_end).nonzero()
    if len(tail) == 0:
        errors.append("no_im_end_after_answer")
    else:
        labels[n_prompt + int(tail[0]) + 1:] = IGNORE
    trained = labels != IGNORE
    image_token = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
    special_ids = {image_token, tok.convert_tokens_to_ids("<|vision_start|>"), tok.convert_tokens_to_ids("<|vision_end|>")}
    if any(int(t) in special_ids for t in ids[trained]):
        errors.append("image_or_vision_token_unmasked")
    if tok.pad_token_id is not None and tok.pad_token_id != im_end and bool((ids[trained] == tok.pad_token_id).any()):
        errors.append("pad_token_unmasked")
    decoded = tok.decode(ids[trained], skip_special_tokens=False)
    if decoded != answer + "<|im_end|>":
        errors.append("trained_span_decode_mismatch")
    if int(trained.sum()) == 0:
        errors.append("zero_answer_tokens")
    n_image = int((ids == image_token).sum())
    grid = enc_full["image_grid_thw"][0]
    expected_image_tokens = int(grid.prod()) // (processor.image_processor.merge_size ** 2)
    if n_image != expected_image_tokens:
        errors.append(f"image_tokens_{n_image}_ne_grid_{expected_image_tokens}")
    if len(ids) > SEQUENCE_BUDGET:
        errors.append("over_sequence_budget")
    if int(trained.sum()) > MAX_NEW_TOKENS:
        errors.append("answer_over_max_new_tokens")
    return Encoded(dict(enc_full), labels, n_prompt, int(trained.sum()), n_image, len(ids), errors)
