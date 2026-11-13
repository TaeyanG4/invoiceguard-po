"""Leak-free grouping and deterministic split assignment (shared by public and own data)."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def stable_key(seed: str | int, *parts: str) -> str:
    return hashlib.sha256("|".join([str(seed), *parts]).encode("utf-8")).hexdigest()


def group_documents(rows: Iterable[dict[str, Any]], id_field: str, link_fields: list[str]) -> dict[str, str]:
    """Return {document_id: group_id}; documents sharing ANY link value are connected."""
    uf = UnionFind()
    rows = list(rows)
    for row in rows:
        doc = f"doc::{row[id_field]}"
        uf.find(doc)
        for field in link_fields:
            value = row.get(field)
            if value:
                uf.union(doc, f"{field}::{value}")
    members: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        members[uf.find(f"doc::{row[id_field]}")].append(row[id_field])
    group_of: dict[str, str] = {}
    for docs in members.values():
        unique = sorted(set(docs))
        gid = "g_" + hashlib.sha256("\n".join(unique).encode("utf-8")).hexdigest()[:16]
        for doc in unique:
            group_of[doc] = gid
    return group_of


def assign_ratio(group_ids: Iterable[str], seed: str | int, names: list[str], ratios: list[float]) -> dict[str, str]:
    """Deterministically order groups by seeded hash and cut by cumulative ratio."""
    ordered = sorted(set(group_ids), key=lambda g: stable_key(seed, "split", g))
    total = len(ordered)
    cuts, acc = [], 0.0
    for ratio in ratios[:-1]:
        acc += ratio
        cuts.append(round(acc * total))
    assignment: dict[str, str] = {}
    for index, gid in enumerate(ordered):
        bucket = sum(index >= c for c in cuts)
        assignment[gid] = names[bucket]
    return assignment


def find_leaks(rows: Iterable[dict[str, Any]], split_field: str, keys: list[str]) -> dict[str, list[str]]:
    """For each key, list values that occur in more than one split. Empty lists == no leakage."""
    seen: dict[str, dict[str, set]] = {k: defaultdict(set) for k in keys}
    for row in rows:
        split = row.get(split_field)
        if split is None:
            continue
        for key in keys:
            value = row.get(key)
            if value is not None:
                seen[key][value].add(split)
    return {k: sorted(v for v, s in vals.items() if len(s) > 1) for k, vals in seen.items()}
