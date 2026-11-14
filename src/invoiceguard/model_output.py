"""Strict parsing of raw VLM responses (shared by evaluator and product API).

The primary path accepts exactly one JSON object (surrounding whitespace allowed). Truncated
or fenced output is NOT repaired on the primary path. An optional, separately reported
"fence_strip" repair exists and must never be mixed into primary metrics.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

REPO = Path(__file__).resolve().parents[2]
_SCHEMAS = {
    "TRADE_RAW": json.loads((REPO / "schemas" / "extraction.schema.json").read_text(encoding="utf-8")),
    "PUBLIC_CANONICAL": json.loads((REPO / "schemas" / "public_extraction.schema.json").read_text(encoding="utf-8")),
    "CORD_RAW": json.loads((REPO / "schemas" / "cord_extraction.schema.json").read_text(encoding="utf-8")),
}
_FENCE = re.compile(r"^\s*```(?:json)?\s*\n(?P<body>.*)\n\s*```\s*$", re.DOTALL)

# generation statuses recorded by the inference runner
GENERATION_FAILURES = ("timeout", "oom", "error", "cancelled", "interrupted")


@dataclass
class ParsedOutput:
    status: str           # ok | empty | json_invalid | not_object | truncated | <generation failure>
    obj: dict[str, Any] | None
    schema_valid: bool
    schema_errors: list[str]
    row_index_valid: bool
    repair: str | None = None  # only set on the lenient path


def _row_index_valid(obj: dict[str, Any]) -> bool:
    items = obj.get("items")
    if not isinstance(items, list):
        return False
    return [it.get("row_index") if isinstance(it, dict) else None for it in items] == list(range(1, len(items) + 1))


def parse_response(text: str | None, task: str, generation_status: str = "ok",
                   finish_reason: str | None = None, lenient: bool = False) -> ParsedOutput:
    if task not in _SCHEMAS:
        raise ValueError(f"unknown task {task}")
    if generation_status != "ok":
        return ParsedOutput(generation_status, None, False, [], False)
    if finish_reason == "length":  # hit max_new_tokens: never patched into success
        return ParsedOutput("truncated", None, False, [], False)
    if text is None or not text.strip():
        return ParsedOutput("empty", None, False, [], False)
    repair = None
    body = text
    if lenient:
        match = _FENCE.match(text)
        if match:
            body, repair = match.group("body"), "fence_strip"
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        return ParsedOutput("json_invalid", None, False, [], False, repair)
    if not isinstance(obj, dict):
        return ParsedOutput("not_object", None, False, [], False, repair)
    validator = jsonschema.Draft202012Validator(_SCHEMAS[task])
    errors = sorted(f"{list(e.path)}: {e.message}"[:200] for e in validator.iter_errors(obj))
    return ParsedOutput("ok", obj, not errors, errors, _row_index_valid(obj), repair)
