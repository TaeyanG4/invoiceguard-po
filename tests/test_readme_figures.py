import re
import shutil
from pathlib import Path

import pytest

from invoiceguard import readme_figures as rf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "artifacts" / "test_readme_figures"  # git-ignored; never the system temp dir
NAMES = ("final-accuracy", "paired-diff", "training-loss", "runpod-loss")


def test_figures_are_drawn_from_the_recorded_results():
    shutil.rmtree(OUT, ignore_errors=True)
    try:
        written = rf.build(OUT)
        expected = {f"{n}{infix}-{m}.svg" for n in NAMES for infix in rf.LANGS.values() for m in ("light", "dark")}
        assert {p.name for p in written} == expected and len(expected) == 16
        cmp = rf._json(REPO / "reports" / "runpod" / "train_compare.json")
        for name in ("runpod-loss-light.svg", "runpod-loss-ko-dark.svg"):
            assert f"{cmp['max_abs_step_diff']:.4f}" in (OUT / name).read_text(encoding="utf-8")
        finals = rf.load_finals()
        assert set(finals) == {"b0", "m0", "m1"}
        for name in ("final-accuracy-light.svg", "final-accuracy-ko-dark.svg"):
            acc = (OUT / name).read_text(encoding="utf-8")
            for arm, run in finals.items():
                for key in rf.SET_KEYS:
                    assert f"{run['headline'][key]['fields_acc']:.3f}" in acc, (name, arm, key)
        diff = rf.load_compare("m1", "m0")["sets"]["trade:test"]
        for name in ("paired-diff-dark.svg", "paired-diff-ko-light.svg"):
            assert f"{diff['field_acc_diff']:+.3f}" in (OUT / name).read_text(encoding="utf-8")
        assert "Own test" in (OUT / "final-accuracy-light.svg").read_text(encoding="utf-8")
        assert "자체 test" in (OUT / "final-accuracy-ko-light.svg").read_text(encoding="utf-8")
        for path in written:
            svg = path.read_text(encoding="utf-8")
            assert svg.startswith("<svg") and "<script" not in svg and "href" not in svg
            assert re.findall(r"https?://[^\"]+", svg) == ["http://www.w3.org/2000/svg"]
    finally:
        shutil.rmtree(OUT, ignore_errors=True)


def test_committed_figures_match_a_fresh_build():
    shutil.rmtree(OUT, ignore_errors=True)
    try:
        for path in rf.build(OUT):
            committed = REPO / "docs" / "images" / path.name
            assert committed.read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), path.name
    finally:
        shutil.rmtree(OUT, ignore_errors=True)


@pytest.mark.parametrize("readme, other, chart_infix", [("README.md", "README.ko.md", ""), ("README.ko.md", "README.md", "-ko")])
def test_readme_links_point_to_existing_files(readme, other, chart_infix):
    text = (REPO / readme).read_text(encoding="utf-8")
    assert f"]({other})" in text  # language switch at the top
    targets = set(re.findall(r'(?:\]\(|srcset="|src=")((?:docs|reports|src|configs|prompts|\.github)/[^)"#\s]+)', text))
    assert targets, "README has no local links"
    missing = sorted(t for t in targets if not (REPO / t).exists())
    assert not missing, missing
    charts = re.findall(r"docs/images/([a-z-]+)-(?:light|dark)\.svg", text)
    assert charts and all(c.endswith(chart_infix) or not chart_infix and not c.endswith("-ko") for c in charts), charts


def test_readme_field_tables_match_the_final_scoring_files():
    from invoiceguard import readme_tables as rt

    assert rt.apply(check=True) == []  # README blocks equal a fresh build from reports/eval/*_final_*.json
    finals = rf.load_finals()
    sku = finals["m1"]["sets"]["trade:test"]["strict"]["fields"]["sku_raw"]
    for name in ("README.md", "README.ko.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert f"{sku['accuracy']:.3f}" in text and f"{sku['correct']}/{sku['scored']}" in text


def test_readme_cord_tables_match_the_cord_scoring_files():
    from invoiceguard import readme_cord as rc

    assert rc.apply(check=True) == []  # README CORD blocks equal a fresh build from reports/eval/cord_*.json
    for name in ("README.md", "README.ko.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        for stage in rc.STAGES:
            for _, arm in rc.ARMS:
                sc = rc.score(stage, arm)
                if sc is not None:  # every produced number is in the README
                    acc = sc["all"]["strict_field_accuracy"]
                    assert f"{acc['correct']:,}/{acc['scored']:,}" in text


def test_readme_cord_leaves_unrun_results_blank(monkeypatch):
    from invoiceguard import readme_cord as rc

    real_score = rc.score
    monkeypatch.setattr(rc, "score", lambda stage, arm: None if stage == "test" else real_score(stage, arm))
    monkeypatch.setattr(rc, "compare", lambda stage, a, b: None)
    test_row = next(line for line in rc.summary_block("en").splitlines() if line.startswith("| test"))
    assert test_row.count(rc.DASH) == 3 and not any(ch.isdigit() for ch in test_row.split("|", 2)[2])
    metric_rows = [line for line in rc.metrics_block("ko").splitlines() if line.startswith("| ") and "지표" not in line]
    assert all(line.rstrip(" |").endswith("— | — | —") for line in metric_rows)  # the three test columns
    assert rc.criteria_block("ko").count("| — |") >= 2  # no verdict without the comparison file
