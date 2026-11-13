"""Check the as-delivered package against MANIFEST.json; no writes or network calls.

Run BEFORE editing or running validators that rewrite reports. A later mismatch
may simply mean the package was legitimately edited, not that its app is broken.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    errors: list[str] = []
    for entry in manifest['files']:
        relative = Path(entry['path'])
        path = (root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(root.resolve()):
            errors.append(f'unsafe path: {entry["path"]}')
            continue
        if not path.is_file():
            errors.append(f'missing: {entry["path"]}')
            continue
        raw = path.read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            errors.append(f'changed: {entry["path"]}')
    for error in errors:
        print(error)
    print(f'{"PASS" if not errors else "CHANGED/FAILED"}: {len(manifest["files"])} listed files; archive integrity only')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
