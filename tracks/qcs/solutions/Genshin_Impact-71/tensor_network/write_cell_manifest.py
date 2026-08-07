#!/usr/bin/env python3
"""Atomically close one independent Slurm cell after all artifacts exist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tn_common import atomic_json, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-dir", required=True, type=Path)
    parser.add_argument("--kind", required=True, choices=("rank", "mps"))
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--order", required=True)
    parser.add_argument("--bond", type=int)
    parser.add_argument("--elapsed-seconds", required=True, type=int)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    args = parser.parse_args()
    cell = args.cell_dir.resolve()
    artifacts = []
    for supplied in args.artifact:
        path = supplied.resolve()
        if cell not in path.parents:
            raise ValueError(f"artifact escapes cell directory: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        artifacts.append(
            {
                "path": str(path.relative_to(cell)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema": "occam71-tn-full-cell-v1",
        "status": "success",
        "kind": args.kind,
        "job_id": args.job_id,
        "task_id": args.task_id,
        "instance": args.instance,
        "order": args.order,
        "bond": args.bond,
        "root_seed": 42,
        "elapsed_seconds": args.elapsed_seconds,
        "input_sha256": args.input_sha256,
        "artifacts": artifacts,
    }
    atomic_json(cell / "manifest.json", manifest)
    (cell / "SUCCESS").write_text("success\n", encoding="ascii")
    print(json.dumps(manifest, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
