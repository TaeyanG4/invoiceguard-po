"""Field-level regression gate (Fable review 3/4) on the committed scoring reports, CPU only."""
import json
from pathlib import Path

from invoiceguard import regression_gate as rg

REPO = Path(__file__).resolve().parents[1]


def test_committed_reports_pass_the_gate_and_every_acceptance_is_still_needed():
    results = rg.run()
    assert [r for r in results if not r["accepted"]] == []  # a new field regression fails CI
    cfg = json.loads(rg.CONFIG.read_text(encoding="utf-8"))
    accepted = {(p["new"], key) for p in cfg["pairs"] for key in (p.get("accepted") or {})}
    found = {(r["pair"].split(" vs ")[0], f"{r['set']}|{r['field']}") for r in results}
    assert accepted == found  # no stale acceptance that would hide nothing (or something else)


def _report(fields):
    return {"sets": {"s": {"strict": {"fields": {k: {"correct": c, "scored": n} for k, (c, n) in fields.items()}}}}}


def test_rule_needs_both_a_large_drop_and_several_lost_fields():
    base = _report({"a": (24, 24), "b": (20, 20), "c": (95, 100)})
    new = _report({"a": (22, 24), "b": (17, 20), "c": (91, 100)})
    out = {v["field"]: v for v in rg.check_pair(new, base, ["s"], max_drop=0.05, min_fields=3)}
    assert "a" not in out                         # -0.083 but only 2 fields: one or two documents flipping
    assert out["b"]["fields_lost"] == 3 and out["b"]["accepted"] is None
    assert "c" not in out                         # 4 fields but only -0.04


def test_an_acceptance_covers_only_the_counts_it_was_pinned_to():
    """astra review 5: a name-only acceptance let the same field fall further without failing."""
    base = _report({"b": (20, 20)})
    pin = {"s|b": {"reason": "known drop", "base": [20, 20], "new": [17, 20]}}
    same = rg.check_pair(_report({"b": (17, 20)}), base, ["s"], 0.05, 3, pin)
    assert same[0]["accepted"] == "known drop" and "problem" not in same[0]
    worse = rg.check_pair(_report({"b": (15, 20)}), base, ["s"], 0.05, 3, pin)
    assert worse[0]["accepted"] is None and worse[0]["problem"] == "accepted_counts_changed"
    name_only = rg.check_pair(_report({"b": (17, 20)}), base, ["s"], 0.05, 3, {"s|b": "known drop"})
    assert name_only[0]["accepted"] is None


def test_a_field_or_set_missing_from_the_new_report_fails():
    base = _report({"a": (10, 10), "b": (5, 5)})
    out = rg.check_pair(_report({"a": (10, 10), "b": (0, 0)}), base, ["s"], 0.05, 3)
    assert [(v["field"], v["problem"]) for v in out] == [("b", "field_missing_in_new")]
    out = rg.check_pair(_report({"a": (10, 10)}), base, ["s", "other"], 0.05, 3)
    assert {(v["field"], v["problem"]) for v in out} == {("b", "field_missing_in_new"), ("*", "set_missing")}
