"""Field-level regression gate over committed scoring reports (Fable review 3/4: "no CI gate with per-field drop limits").

  python -m invoiceguard.regression_gate            # check every pair in configs/regression_gate.json; exit 1 on a violation

A field FAILS when, on the same set, the new run's strict accuracy is more than MAX_DROP below the baseline's AND it got
at least MIN_FIELDS fewer fields right (so one document flipping on a 24-document set does not count as a regression).
The rule is fixed in configs/regression_gate.json before looking at the per-field numbers; a pair can list fields whose
drop is known and accepted, each with its reason, so an accepted regression stays visible instead of being hidden.

Works on the committed reports in reports/eval/ (no predictions, gold or GPU needed), so it runs in CI. Reports come
from score_run (synthetic sets: sets.<set>.strict.fields) or cord_eval/cord_score (CORD: sets.<set>.all.by_field_strict).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "regression_gate.json"


def _fields(report: dict, set_name: str) -> dict[str, dict]:
    s = report["sets"][set_name]
    if "strict" in s:
        return s["strict"]["fields"]
    return s["all"]["by_field_strict"]


def check_pair(new: dict, base: dict, sets: list[str], max_drop: float, min_fields: int,
               accepted: dict[str, str] | None = None) -> list[dict]:
    """Per-field violations of `new` against `base` on the given sets (accepted ones are returned with their reason)."""
    out = []
    for set_name in sets:
        nf, bf = _fields(new, set_name), _fields(base, set_name)
        for field, b in bf.items():
            n = nf.get(field)
            if not n or not b.get("scored") or not n.get("scored"):
                continue
            drop = b["correct"] / b["scored"] - n["correct"] / n["scored"]
            lost = b["correct"] - n["correct"] if b["scored"] == n["scored"] else round(drop * b["scored"])
            if drop > max_drop and lost >= min_fields:
                key = f"{set_name}|{field}"
                out.append({"set": set_name, "field": field, "base": round(b["correct"] / b["scored"], 4),
                            "new": round(n["correct"] / n["scored"], 4), "drop": round(drop, 4), "fields_lost": lost,
                            "accepted": (accepted or {}).get(key)})
    return out


def run(config_path: Path = CONFIG, eval_dir: Path = REPO / "reports" / "eval") -> list[dict]:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    results = []
    for pair in cfg["pairs"]:
        new = json.loads((eval_dir / f"{pair['new']}.json").read_text(encoding="utf-8"))
        base = json.loads((eval_dir / f"{pair['base']}.json").read_text(encoding="utf-8"))
        for v in check_pair(new, base, pair["sets"], cfg["max_drop"], cfg["min_fields"], pair.get("accepted")):
            results.append({"pair": f"{pair['new']} vs {pair['base']}"} | v)
    return results


def main() -> int:
    results = run()
    for r in results:
        tag = f"accepted: {r['accepted']}" if r["accepted"] else "FAIL"
        print(f"{tag}  {r['pair']}  {r['set']} {r['field']}: {r['base']} -> {r['new']} (-{r['drop']}, {r['fields_lost']} fields)")
    failing = [r for r in results if not r["accepted"]]
    print(f"regression gate: {len(failing)} failing, {len(results) - len(failing)} accepted")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
