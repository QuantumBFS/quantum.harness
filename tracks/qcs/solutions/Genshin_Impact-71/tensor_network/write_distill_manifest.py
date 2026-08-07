#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tn_common import atomic_json, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-dir", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--elapsed-seconds", required=True, type=int)
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    args = parser.parse_args()
    root = args.cell_dir.resolve()
    artifacts = []
    for supplied in args.artifact:
        path = supplied.resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"invalid artifact: {path}")
        artifacts.append({
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    manifest = {
        "schema": "occam71-tn-distill-cell-v1",
        "status": "success",
        "job_id": args.job_id,
        "task_id": args.task_id,
        "instance": args.instance,
        "root_seed": 42,
        "elapsed_seconds": args.elapsed_seconds,
        "artifacts": artifacts,
    }
    atomic_json(root / "manifest.json", manifest)
    (root / "SUCCESS").write_text("success\n", encoding="ascii")
    print(json.dumps(manifest, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
