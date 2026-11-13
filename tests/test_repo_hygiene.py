"""Weights, keys, fonts and raw data must never be tracked by git (CLAUDE.md: keep them out of repo/release).

scripts/verify_claude_pack.py scans the whole working tree, so git-ignored local assets (models/, artifacts/,
.venv-ml/) make it fail locally; this test checks what would actually be published.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = (".pem", ".key", ".safetensors", ".pt", ".bin", ".ttf", ".otf", ".woff", ".woff2", ".parquet",
                      ".sqlite", ".env")
FORBIDDEN_DIRS = ("data/", "models/", "artifacts/", ".venv", "secrets/")


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(), reason="git repo not available")
def test_no_weights_keys_fonts_or_raw_data_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
    bad = [p for p in tracked if p.lower().endswith(FORBIDDEN_SUFFIXES) or p.startswith(FORBIDDEN_DIRS)]
    assert bad == []
