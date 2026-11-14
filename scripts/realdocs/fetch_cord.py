"""Download CORD v2 (real Indonesian receipt photos with labels, CC BY 4.0) at a pinned revision and verify every file.

Source: https://huggingface.co/datasets/naver-clova-ix/cord-v2 (the official copy; the Kaggle mirror is labelled GPL-2).
Download approved by the user on 2026-11-14 ("내려받기 승인"), about 2.31 GB.

Files land in data/raw/cord-v2/<revision>/ (git-ignored). Each parquet's SHA256 is checked against the LFS hash that
the Hub reports for that revision. A small evidence file with sizes, hashes and elapsed time is written to
reports/realdocs/cord_fetch.json (committed; contains no images or labels).

Usage: python -I scripts/realdocs/fetch_cord.py
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = "naver-clova-ix/cord-v2"
REVISION = "7f0115a4b758a71d6473b8d085751692da2fef98"
ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "raw" / "cord-v2" / REVISION
EVIDENCE = ROOT / "reports" / "realdocs" / "cord_fetch.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    from huggingface_hub import HfApi, hf_hub_download

    info = HfApi().dataset_info(REPO, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        raise SystemExit(f"revision mismatch: {info.sha}")
    license_ = (info.card_data or {}).get("license")
    DEST.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    files = []
    for s in sorted(info.siblings, key=lambda x: x.rfilename):
        if not s.rfilename.endswith(".parquet"):
            continue
        expected = s.lfs.sha256 if s.lfs else None
        t = time.time()
        local = Path(hf_hub_download(REPO, s.rfilename, repo_type="dataset", revision=REVISION, local_dir=str(DEST)))
        got = sha256(local)
        ok = got == expected
        files.append({"file": s.rfilename, "bytes": local.stat().st_size, "sha256": got, "hub_sha256": expected,
                      "ok": ok, "seconds": round(time.time() - t, 1)})
        print(json.dumps(files[-1]), flush=True)
        if not ok:
            raise SystemExit(f"hash mismatch for {s.rfilename}")
    out = {"repo": REPO, "revision": REVISION, "license": license_, "source": f"https://huggingface.co/datasets/{REPO}",
           "approved_by_user": "2026-11-14", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "total_bytes": sum(f["bytes"] for f in files), "total_seconds": round(time.time() - t0, 1),
           "all_ok": all(f["ok"] for f in files), "files": files, "local_dir": str(DEST.relative_to(ROOT)).replace("\\", "/")}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    (DEST / "manifest.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"total_bytes": out["total_bytes"], "total_seconds": out["total_seconds"], "all_ok": out["all_ok"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
