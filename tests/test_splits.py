import json
from pathlib import Path

import pytest

from invoiceguard.splits import assign_ratio, find_leaks, group_documents

REPO = Path(__file__).resolve().parents[1]


def test_transitive_grouping_links_shared_content_and_images():
    docs = [
        {"id": "a", "content": "c1", "img": "i1"},
        {"id": "b", "content": "c1", "img": "i2"},   # same content as a
        {"id": "c", "content": "c3", "img": "i2"},   # same image as b -> transitively a
        {"id": "d", "content": "c4", "img": "i4"},
    ]
    groups = group_documents(docs, "id", ["content", "img"])
    assert groups["a"] == groups["b"] == groups["c"]
    assert groups["d"] != groups["a"]


def test_assign_ratio_is_deterministic_and_complete():
    gids = [f"g{i}" for i in range(80)]
    a = assign_ratio(gids, 1, ["train", "dev", "test"], [0.75, 0.125, 0.125])
    b = assign_ratio(reversed(gids), 1, ["train", "dev", "test"], [0.75, 0.125, 0.125])
    assert a == b
    counts = {k: list(a.values()).count(k) for k in ("train", "dev", "test")}
    assert counts == {"train": 60, "dev": 10, "test": 10}


def test_find_leaks_detects_cross_split_values():
    rows = [{"split": "train", "k": "x"}, {"split": "test", "k": "x"}, {"split": "test", "k": "y"}]
    assert find_leaks(rows, "split", ["k"]) == {"k": ["x"]}


MANIFEST = REPO / "manifests" / "public_canonical_v1.jsonl"


@pytest.mark.skipif(not MANIFEST.exists(), reason="public manifest not built (needs local data)")
def test_d04_public_manifest_has_no_leakage():
    from invoiceguard.public_manifest import check

    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines()]
    result = check(rows)
    assert result["pass"], result


@pytest.mark.skipif(not MANIFEST.exists(), reason="public manifest not built (needs local data)")
def test_d06_manifest_contains_no_label_values_or_po():
    first = json.loads(MANIFEST.read_text(encoding="utf-8").splitlines()[0])
    forbidden = {"line_items", "quantity", "unit_price", "amount", "description", "po", "image", "po_id"}
    assert not forbidden & set(first)
