#!/usr/bin/env python3
"""Run one resumable fixed-gamma scan selected from the deadline manifest."""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from run_campaign_cell import atomic_json, slurm_memory_mb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=int)
    parser.add_argument(
        "--manifest", type=Path, default=Path("results/deadline_gap_scan_manifest.json")
    )
    parser.add_argument("--results", type=Path, default=Path("results/deadline_gap_scans"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    force = args.force or os.environ.get("ISSUE92_FORCE", "0") == "1"
    manifest = json.loads(args.manifest.read_text())
    cells = manifest["cells"]
    if not 0 <= args.index < len(cells):
        parser.error(f"index must be in [0,{len(cells)-1}]")
    cell = cells[args.index]
    required_cpus = int(cell["requested_cpus"])
    allocated_cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", required_cpus))
    if allocated_cpus < required_cpus:
        raise RuntimeError(f"{cell['id']} requests {required_cpus} CPUs, got {allocated_cpus}")
    allocated_memory = os.environ.get("SLURM_MEM_PER_NODE")
    allocated_memory_mb = None
    if allocated_memory is not None:
        allocated_memory_mb = slurm_memory_mb(allocated_memory)
        required_memory_mb = int(cell["requested_memory_gb"]) * 1024
        if allocated_memory_mb < required_memory_mb:
            raise RuntimeError(
                f"{cell['id']} requests {required_memory_mb} MiB, got {allocated_memory_mb}"
            )
    output = args.results / f"{cell['id']}.json"
    if output.exists() and not force:
        existing = json.loads(output.read_text())
        if existing.get("status") == "COMPLETE":
            print(f"skip completed {cell['id']}", flush=True)
            return
    args.results.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=args.results, delete=False) as handle:
        json.dump(cell, handle)
        handle.write("\n")
        input_path = Path(handle.name)
    command = [
        "julia",
        "--project=julia",
        "julia/scripts/run_fixed_gamma_scan.jl",
        str(input_path),
        str(output),
    ]
    environment = os.environ.copy()
    environment.setdefault("JULIA_NUM_THREADS", str(allocated_cpus))
    if force:
        environment["ISSUE92_FORCE"] = "1"
    print(f"run {cell['id']}", flush=True)
    started = time.monotonic()
    attempt_status = "ERROR"
    try:
        subprocess.run(command, check=True, env=environment)
        attempt_status = "COMPLETE"
    finally:
        input_path.unlink(missing_ok=True)
        if output.exists():
            payload = json.loads(output.read_text())
            payload["runner"] = {
                "attempt_status": attempt_status,
                "wall_seconds": time.monotonic() - started,
                "max_rss_gb": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024**2,
                "allocated_cpus": allocated_cpus,
                "allocated_memory_gb": (
                    allocated_memory_mb / 1024 if allocated_memory_mb is not None else None
                ),
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "slurm_array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID"),
                "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
            }
            atomic_json(output, payload)


if __name__ == "__main__":
    main()
