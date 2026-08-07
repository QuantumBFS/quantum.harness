#!/usr/bin/env python3
"""Run one self-dual Born trajectory cell and write auditable JSON/CSV."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--replica", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--burnin-rows", type=int, required=True)
    parser.add_argument("--measurement-rows", type=int, required=True)
    parser.add_argument("--block-rows", type=int, required=True)
    parser.add_argument("--qr-interval", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    source_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source_root / "src"))
    from borncritical.selfdual import run_selfdual_trajectory

    status = "success"
    return_code = 0
    error: dict[str, str] | None = None
    try:
        result = run_selfdual_trajectory(
            size=args.size,
            replica=args.replica,
            seed=args.seed,
            burnin_rows=args.burnin_rows,
            measurement_rows=args.measurement_rows,
            block_rows=args.block_rows,
            qr_interval=args.qr_interval,
        )
        payload = result.to_dict()
        atomic_json(output / "observables.json", payload)
        checksum = hashlib.sha256(
            (output / "observables.json").read_bytes()
        ).hexdigest()
    except Exception as exception:
        status = "failed"
        return_code = 1
        checksum = ""
        error = {
            "type": type(exception).__name__,
            "message": str(exception),
        }

    manifest: dict[str, object] = {
        "schema_version": 1,
        "stage": "stage4-selfdual",
        "status": status,
        "return_code": return_code,
        "started_at": started,
        "finished_at": utc_now(),
        "hostname": socket.gethostname(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
        "parameters": {
            "size": args.size,
            "replica": args.replica,
            "seed": args.seed,
            "burnin_rows": args.burnin_rows,
            "measurement_rows": args.measurement_rows,
            "block_rows": args.block_rows,
            "qr_interval": args.qr_interval,
        },
        "observables_sha256": checksum or None,
        "error": error,
    }
    atomic_json(output / "manifest.json", manifest)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
