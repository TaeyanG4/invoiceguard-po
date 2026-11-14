import re
import shutil
from pathlib import Path

from invoiceguard import readme_figures as rf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "artifacts" / "test_readme_figures"  # git-ignored; never the system temp dir


def test_figures_are_drawn_from_the_recorded_results():
    shutil.rmtree(OUT, ignore_errors=True)
    try:
        written = rf.build(OUT)
        assert sorted(p.name for p in written) == sorted(f"{n}-{m}.svg" for n in ("final-accuracy", "paired-diff", "training-loss")
                                                         for m in ("light", "dark"))
        finals = rf.load_finals()
        assert set(finals) == {"b0", "m0", "m1"}
        acc = (OUT / "final-accuracy-light.svg").read_text(encoding="utf-8")
        for arm, run in finals.items():
            for key, *_ in rf.SETS:
                assert f"{run['headline'][key]['fields_acc']:.3f}" in acc, (arm, key)
        diff = rf.load_compare("m1", "m0")["sets"]["trade:test"]
        assert f"{diff['field_acc_diff']:+.3f}" in (OUT / "paired-diff-dark.svg").read_text(encoding="utf-8")
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


def test_readme_links_point_to_existing_files():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    targets = set(re.findall(r'(?:\]\(|srcset="|src=")((?:docs|reports|src|configs|\.github)/[^)"#\s]+)', readme))
    assert targets, "README has no local links"
    missing = sorted(t for t in targets if not (REPO / t).exists())
    assert not missing, missing
