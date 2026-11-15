"""Review screen in a real headless browser (Fable review 6: the screen's JavaScript had no automated test).

A real HTTP server (uvicorn, loopback, free port) serves the API + screen with a scripted TEST_DOUBLE extractor; headless
Chrome/Chromium loads `/#case=<id>`, runs review.js (fetches the case over HTTP, builds the table and findings) and dumps the
DOM. Skips when no Chrome/Chromium is installed (GitHub's ubuntu runners have google-chrome). CPU only.
"""
import json
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

uvicorn = pytest.importorskip("uvicorn")

from invoiceguard.app.api import create_app  # noqa: E402

from test_app import BASE, INVOICE, PO, Scripted, png_bytes  # noqa: E402

CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
              "C:/Program Files/Google/Chrome/Application/chrome.exe",
              "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"]


def _browser() -> str | None:
    for c in CANDIDATES:
        found = shutil.which(c) or (c if Path(c).exists() else None)
        if found:
            return found
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _call(url: str, data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _multipart(fields: dict, file_bytes: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="x.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                 + file_bytes + b"\r\n")
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


@pytest.mark.skipif(_browser() is None, reason="no Chrome/Chromium/Edge installed")
def test_review_screen_renders_a_case_from_the_api_in_a_real_browser():
    root = BASE / uuid.uuid4().hex
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(root / "db.sqlite", root / "uploads", Scripted(json.dumps(INVOICE))),
                                           host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        _call(base + "/api/purchase-orders", json.dumps(PO).encode(), {"Content-Type": "application/json"})
        body, ctype = _multipart({"po_id": PO["po_id"], "po_version": str(PO["po_version"])}, png_bytes())
        case_id = _call(base + "/api/cases", body, {"Content-Type": ctype})["case_id"]
        extracted = _call(base + f"/api/cases/{case_id}/extract", json.dumps({"expected_version": 0}).encode(),
                          {"Content-Type": "application/json"})
        profile = root / "browser-profile"
        out = subprocess.run([_browser(), "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}",
                              "--virtual-time-budget=8000", "--dump-dom", f"{base}/#case={case_id}"],
                             capture_output=True, text=True, encoding="utf-8", timeout=90)
        dom = out.stdout
        assert "InvoiceGuard 검수" in dom, out.stderr[-500:]
        assert case_id in dom                                    # the case header was rendered by review.js
        assert f'data-row="{len(INVOICE["items"])}"' in dom      # one editable table row per extracted item
        state_label = {"needs_review": "검토 필요", "matched_candidate": "일치 후보"}[extracted["state"]]
        assert state_label in dom and "버전 1" in dom            # state pill and version from GET /api/cases/{id}
        assert "추출 이력" in dom and "TEST_DOUBLE" in dom        # run history from the API
        assert "발주서 대사 결과" in dom
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        shutil.rmtree(root, ignore_errors=True)
