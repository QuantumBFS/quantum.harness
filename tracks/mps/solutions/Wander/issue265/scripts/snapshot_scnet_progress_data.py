#!/usr/bin/env python3
"""Create a hash manifest for an already copied, read-only SCNet snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(paths: list[Path], root: Path) -> dict:
    records = []
    for path in sorted((p.resolve() for p in paths), key=str):
        if not path.is_file():
            raise FileNotFoundError(path)
        stat = path.stat()
        records.append(
            {
                "path": str(path.relative_to(root.resolve())),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = [p for p in args.root.rglob("*") if p.is_file()]
    manifest = build_manifest(files, args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()

