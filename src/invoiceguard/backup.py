"""T09: inventory + copy + hash-verified restore check of the artifacts that are NOT in git.

  python -m invoiceguard.backup --dest <folder outside the repo>

Covers adapters (smoke, M1 v1, M1 v2), every prediction run (raw responses first-class), training reports.
Writes reports/backup_inventory.json (paths relative to the repo, sha256, bytes) and verifies every copied file by
re-hashing the copy. Weights of the public base model are re-downloadable and are not copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = ["artifacts/adapters", "artifacts/predictions"]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", required=True)
    args = parser.parse_args()
    dest = Path(args.dest).resolve()
    if dest == REPO or REPO in dest.parents:
        raise SystemExit("backup destination must be outside the repository")
    files = sorted(p for src in SOURCES for p in (REPO / src).rglob("*") if p.is_file())
    inventory, mismatches = [], []
    for path in files:
        rel = path.relative_to(REPO).as_posix()
        digest = _sha(path)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if _sha(target) != digest:
            mismatches.append(rel)
        inventory.append({"path": rel, "bytes": path.stat().st_size, "sha256": digest})
    report = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "destination_kind": "local folder outside repo",
              "files": len(inventory), "total_bytes": sum(f["bytes"] for f in inventory),
              "restore_hash_check": "pass" if not mismatches else "fail", "mismatches": mismatches,
              "note": "base model weights are re-downloadable at the pinned revision and are not copied",
              "inventory": inventory}
    (REPO / "reports" / "backup_inventory.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: report[k] for k in ("files", "total_bytes", "restore_hash_check")}))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
