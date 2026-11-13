from pathlib import Path

from invoiceguard.dashboard import build_html, collect, parse_kv, parse_task_board

REPO = Path(__file__).resolve().parents[1]


def test_task_board_parsed_from_real_report():
    tasks, gates = parse_task_board((REPO / "reports" / "TASK_BOARD.md").read_text(encoding="utf-8"))
    assert [t["id"] for t in tasks] == [f"T0{i}" for i in range(10)]
    assert [g["id"] for g in gates] == [f"G{i}" for i in range(8)]


def test_approval_form_defaults_to_not_approved():
    kv = parse_kv((REPO / "reports" / "RUNPOD_APPROVAL.md").read_text(encoding="utf-8"))
    assert kv["approved"] == "false" and kv["auto_top_up_authorized"] == "false"


def test_dashboard_escapes_untrusted_text_and_shows_not_run():
    data = collect(REPO / "artifacts" / "does-not-exist" / "junit.xml")
    data["tasks"][0]["evidence"] = "<script>alert(1)</script>"
    page = build_html(data)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "미실행" in page  # model matrix stays not_run without real results
    assert "http://" not in page and "https://" not in page  # self-contained, no external fetches
