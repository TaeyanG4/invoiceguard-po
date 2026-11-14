"""Score CORD_RAW runs with the metric fixed in docs/20_DECISIONS_V6.md BEFORE any CORD training or evaluation.

Primary: strict positional field accuracy over gold-present fields (items, sub-items, subtotal/tax/total), NFKC +
whitespace-collapsed exact match; JSON failures and missing rows count as wrong.
Secondary A: format-insensitive accuracy (numeric fields digits only, names casefolded without spaces).
Secondary B: order-free field F1 over (field, strict value) multisets; values the model invents lower precision.
Everything is reported for all documents and for the content-unseen subset (gold not identical to any train doc).
Amendment 1 (docs/20): field scores use the fence-stripped parse (exactly one ```json fence removed, nothing else
repaired), because M0 fences every answer; strict JSON (no fence) is reported separately as the format metric.

Usage (.venv-ml):
  python -I -m invoiceguard.cord_eval score artifacts/predictions/<run_id>
  python -I -m invoiceguard.cord_eval compare <run_a> <run_b>       # paired bootstrap A - B on identical documents
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .cord import load_gold, manifest_rows
from .evaluation import parse_for_eval
from .public_data import nfkc_ws

REPO = Path(__file__).resolve().parents[2]
TASK = "CORD_RAW"
ITEM_FIELDS = ("name", "count", "unit_price", "price")
DOC_FIELDS = ("subtotal", "tax", "total")
NUMERIC = {"count", "unit_price", "price", "subtotal", "tax", "total"}
SEED = 20261113


def strict_norm(v: Any) -> str | None:
    return nfkc_ws(v) if isinstance(v, str) else None


def loose_norm(field: str, v: Any) -> str | None:
    if v is None or isinstance(v, (dict, list, bool)):
        return None
    s = nfkc_ws(str(v))
    if field in NUMERIC:
        return re.sub(r"\D", "", s)
    return re.sub(r"\s+", "", s).casefold()


def _list(obj: Any, key: str) -> list:
    v = obj.get(key) if isinstance(obj, dict) else None
    return [x if isinstance(x, dict) else {} for x in v] if isinstance(v, list) else []


def slots(obj: dict | None) -> list[tuple[tuple, str, Any]]:
    """Every value position of a CORD_RAW object: (position key, field, value)."""
    if not isinstance(obj, dict):
        return []
    out = []
    for i, it in enumerate(_list(obj, "items")):
        for f in ITEM_FIELDS:
            out.append((("item", i, f), f, it.get(f)))
        for j, sub in enumerate(_list(it, "sub_items")):
            for f in ITEM_FIELDS:
                out.append((("sub", i, j, f), f, sub.get(f)))
    for f in DOC_FIELDS:
        out.append((("doc", f), f, obj.get(f)))
    return out


def _masked_keys(masked: list[str]) -> set[tuple]:
    keys = set()
    for path in masked:
        m = re.fullmatch(r"items\[(\d+)\]\.sub_items\[(\d+)\]\.(\w+)", path)
        if m:
            keys.add(("sub", int(m[1]) - 1, int(m[2]) - 1, m[3]))
            continue
        m = re.fullmatch(r"items\[(\d+)\]\.(\w+)", path)
        keys.add(("item", int(m[1]) - 1, m[2]) if m else ("doc", path))
    return keys


def score_document(gold: dict, masked: list[str], parsed) -> dict:
    pred_obj = parsed.obj if parsed.status == "ok" else None
    pred = {k: v for k, _, v in slots(pred_obj)}
    skip = _masked_keys(masked)
    strict, loose = [0, 0], [0, 0]
    by_group: dict[str, list[int]] = {}
    absent_filled = 0
    gold_bag, pred_bag = Counter(), Counter()
    all_strict = True
    for key, field, value in slots(gold):
        if key in skip:
            continue
        p = pred.get(key)
        if value is None:
            absent_filled += p is not None
            continue
        gold_bag[(field, strict_norm(value))] += 1
        ok_s = strict_norm(p) == strict_norm(value)
        ok_l = loose_norm(field, p) is not None and loose_norm(field, p) == loose_norm(field, value)
        strict[0] += ok_s; strict[1] += 1
        loose[0] += ok_l; loose[1] += 1
        group = f"{key[0]}.{field}"
        g = by_group.setdefault(group, [0, 0]); g[0] += ok_s; g[1] += 1
        all_strict &= ok_s
    for key, field, value in slots(pred_obj):
        if key not in skip and strict_norm(value) is not None:
            pred_bag[(field, strict_norm(value))] += 1
    tp = sum((gold_bag & pred_bag).values())
    g_items, p_items = _list(gold, "items"), _list(pred_obj, "items")
    rows_match = len(g_items) == len(p_items) and all(
        len(_list(a, "sub_items")) == len(_list(b, "sub_items")) for a, b in zip(g_items, p_items))
    return {"status": parsed.status, "schema_valid": parsed.schema_valid, "strict": strict, "loose": loose,
            "by_group": by_group, "absent_filled": absent_filled, "f1_counts": [tp, sum(pred_bag.values()), sum(gold_bag.values())],
            "gold_items": len(g_items), "pred_items": len(p_items), "rows_match": rows_match,
            "doc_exact": parsed.status == "ok" and rows_match and all_strict and absent_filled == 0}


def _ratio(a: int, b: int) -> float | None:
    return None if b == 0 else round(a / b, 4)


def f1(tp: int, n_pred: int, n_gold: int) -> dict:
    p, r = (tp / n_pred if n_pred else 0.0), (tp / n_gold if n_gold else 0.0)
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}


def aggregate(docs: list[dict]) -> dict:
    n = len(docs)
    sc, ss = sum(d["strict"][0] for d in docs), sum(d["strict"][1] for d in docs)
    lc, ls = sum(d["loose"][0] for d in docs), sum(d["loose"][1] for d in docs)
    groups: dict[str, list[int]] = {}
    for d in docs:
        for g, (c, s) in d["by_group"].items():
            acc = groups.setdefault(g, [0, 0]); acc[0] += c; acc[1] += s
    tp, npred, ngold = (sum(d["f1_counts"][k] for d in docs) for k in range(3))
    return {"documents": n, "status_counts": dict(Counter(d["status"] for d in docs)),
            "json_valid_rate": _ratio(sum(d["status"] == "ok" for d in docs), n),
            "schema_valid_rate": _ratio(sum(bool(d["schema_valid"]) for d in docs), n),
            "strict_field_accuracy": {"correct": sc, "scored": ss, "accuracy": _ratio(sc, ss)},
            "format_insensitive_accuracy": {"correct": lc, "scored": ls, "accuracy": _ratio(lc, ls)},
            "order_free_f1": f1(tp, npred, ngold) | {"tp": tp, "predicted": npred, "gold": ngold},
            "by_field_strict": {g: {"correct": c, "scored": s, "accuracy": _ratio(c, s)} for g, (c, s) in sorted(groups.items())},
            "absent_fields_filled": sum(d["absent_filled"] for d in docs),
            "row_count_match_rate": _ratio(sum(d["rows_match"] for d in docs), n),
            "doc_exact": _ratio(sum(d["doc_exact"] for d in docs), n)}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_documents(run: str, lenient: bool = False) -> dict[str, list[tuple[dict, dict]]]:
    """{set: [(manifest row, doc score)]} for every expected document of the run's cord sets; missing = failure."""
    run_dir = REPO / "artifacts" / "predictions" / run
    meta = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    preds: dict[str, dict] = {}
    for p in _jsonl(run_dir / "predictions.jsonl"):
        if p["id"] in preds:
            raise SystemExit(f"duplicate prediction id {p['id']} — refusing to score")
        preds[p["id"]] = p
    out = {}
    for spec in meta.get("sets") or []:
        kind, split = spec.split(":", 1)
        if kind != "cord":
            continue
        rows = manifest_rows(split)
        docs = []
        for r in rows:
            p = preds.get(r["id"]) or {"id": r["id"], "generation_status": "missing", "raw_response": None}
            docs.append((r, score_document(load_gold(r["id"]), r["masked"], parse_for_eval(p, TASK, lenient=lenient))))
        out[spec] = docs
    if not out:
        raise SystemExit("run has no cord:* sets")
    return out


def score(run: str) -> dict:
    meta = json.loads((REPO / "artifacts" / "predictions" / run / "run_metadata.json").read_text(encoding="utf-8"))
    strict_docs, fenced_docs = run_documents(run), run_documents(run, lenient=True)
    report = {"run_id": run, "contract": "docs/20_DECISIONS_V6.md (CORD_RAW, pre-registered)",
              "fingerprint": meta.get("fingerprint"), "wall_seconds": meta.get("wall_seconds"),
              "peak_vram_gb": meta.get("peak_vram_gb"), "env": meta.get("env"), "sets": {}}
    for spec, docs in fenced_docs.items():  # primary: fence-stripped parse (docs/20 amendment 1)
        unseen = [d for r, d in docs if not r.get("content_seen_in_train")]
        report["sets"][spec] = {"all": aggregate([d for _, d in docs]), "content_unseen": aggregate(unseen),
                                "strict_json_no_repair_all": aggregate([d for _, d in strict_docs[spec]]),
                                "fence_stripped_documents": sum(d["status"] == "ok" for _, d in docs)
                                - sum(d["status"] == "ok" for _, d in strict_docs[spec])}
    return report


def _paired(a: list[tuple[dict, dict]], b: list[tuple[dict, dict]], iterations: int = 2000) -> dict:
    clusters: dict[str, list[int]] = {}
    for i, (r, _) in enumerate(a):
        clusters.setdefault(r["gold_sha256"], []).append(i)  # identical answers resample together
    keys = sorted(clusters)

    def stats(idx: list[int]) -> tuple[float, float, float, float]:
        def acc(docs, k):
            c = sum(docs[i][1][k][0] for i in idx); s = sum(docs[i][1][k][1] for i in idx)
            return c / s if s else 0.0

        def f(docs):
            tp, npred, ngold = (sum(docs[i][1]["f1_counts"][k] for i in idx) for k in range(3))
            return f1(tp, npred, ngold)["f1"]

        de = (sum(a[i][1]["doc_exact"] for i in idx) - sum(b[i][1]["doc_exact"] for i in idx)) / len(idx)
        return acc(a, "strict") - acc(b, "strict"), acc(a, "loose") - acc(b, "loose"), f(a) - f(b), de

    point = stats(list(range(len(a))))
    rng = random.Random(SEED)
    samples = [stats([i for _ in keys for i in clusters[rng.choice(keys)]]) for _ in range(iterations)]
    lo, hi = int(0.025 * (iterations - 1)), int(0.975 * (iterations - 1))
    out = {"n_docs": len(a), "n_clusters": len(keys)}
    for k, name in enumerate(("strict_field_accuracy", "format_insensitive_accuracy", "order_free_f1", "doc_exact")):
        vals = sorted(s[k] for s in samples)
        out[name] = {"diff": round(point[k], 4), "ci95": [round(vals[lo], 4), round(vals[hi], 4)]}
    return out


def compare(run_a: str, run_b: str) -> dict:
    da, db = run_documents(run_a, lenient=True), run_documents(run_b, lenient=True)  # docs/20 amendment 1
    if set(da) != set(db):
        raise SystemExit(f"runs cover different sets: {sorted(da)} vs {sorted(db)}")
    out = {"a": run_a, "b": run_b, "parse": "fence-stripped (one ```json fence removed, no other repair)",
           "method": "document-paired bootstrap 2000 (seed 20261113), clusters = identical gold, A minus B",
           "criteria": "docs/20_DECISIONS_V6.md", "sets": {}}
    for spec in sorted(da):
        if [r["id"] for r, _ in da[spec]] != [r["id"] for r, _ in db[spec]]:
            raise SystemExit("runs do not cover identical documents")
        unseen = [i for i, (r, _) in enumerate(da[spec]) if not r.get("content_seen_in_train")]
        out["sets"][spec] = {"all": _paired(da[spec], db[spec]),
                             "content_unseen": _paired([da[spec][i] for i in unseen], [db[spec][i] for i in unseen])}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score"); s.add_argument("run_dir")
    c = sub.add_parser("compare"); c.add_argument("run_a"); c.add_argument("run_b")
    args = ap.parse_args()
    (REPO / "reports" / "eval").mkdir(parents=True, exist_ok=True)
    if args.cmd == "score":
        run = Path(args.run_dir).name
        out = score(run)
        path = REPO / "reports" / "eval" / f"{run}.json"
        summary = {spec: {"field_acc": v["all"]["strict_field_accuracy"]["accuracy"],
                          "format_insensitive_acc": v["all"]["format_insensitive_accuracy"]["accuracy"],
                          "order_free_f1": v["all"]["order_free_f1"]["f1"], "json_ok_after_fence_strip": v["all"]["json_valid_rate"],
                          "strict_json_rate": v["strict_json_no_repair_all"]["json_valid_rate"],
                          "unseen_field_acc": v["content_unseen"]["strict_field_accuracy"]["accuracy"]}
                   for spec, v in out["sets"].items()}
    else:
        out = compare(args.run_a, args.run_b)
        path = REPO / "reports" / "eval" / f"compare_{args.run_a}__vs__{args.run_b}.json"
        summary = out["sets"]
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
