#!/usr/bin/env python3
"""Dry-assemble one unique hierarchy level and preserve resource evidence."""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import tempfile
import time
from pathlib import Path


def slurm_memory_mb(value: str) -> int:
    """Parse Slurm memory environment values; a bare number is in MiB."""
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("empty Slurm memory value")
    factors = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024**2}
    suffix = normalized[-1]
    if suffix in factors:
        return int(float(normalized[:-1]) * factors[suffix])
    return int(normalized)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=int)
    parser.add_argument(
        "--manifest", type=Path, default=Path("results/dry_level_manifest.json")
    )
    parser.add_argument("--results", type=Path)
    parser.add_argument("--build-model", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    levels = manifest["levels"]
    if not 0 <= args.index < len(levels):
        parser.error(f"index must be in [0,{len(levels)-1}]")
    level = levels[args.index]
    results_directory = args.results or Path(
        "results/dry_models" if args.build_model else "results/dry_levels"
    )
    output = results_directory / f"{level['id']}.json"
    if output.exists() and not args.force:
        existing = json.loads(output.read_text())
        if existing.get("status") == "COMPLETE":
            print(f"skip completed {level['id']}", flush=True)
            return

    allocated_cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", level["requested_cpus"]))
    if allocated_cpus < int(level["requested_cpus"]):
        raise RuntimeError(
            f"{level['id']} requests {level['requested_cpus']} CPUs but allocation has "
            f"{allocated_cpus}"
        )
    allocated_memory = os.environ.get("SLURM_MEM_PER_NODE")
    if allocated_memory is not None:
        allocated_memory_mb = slurm_memory_mb(allocated_memory)
        required_memory_mb = int(level["requested_memory_gb"]) * 1024
        if allocated_memory_mb < required_memory_mb:
            raise RuntimeError(
                f"{level['id']} requests {required_memory_mb} MiB but allocation has "
                f"{allocated_memory_mb} MiB"
            )

    results_directory.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.setdefault("JULIA_NUM_THREADS", str(allocated_cpus))
    if args.build_model:
        environment["ISSUE92_DRY_BUILD_MODEL"] = "1"
    started = time.monotonic()
    mode = "model" if args.build_model else "assembly"
    print(f"dry {mode} {args.index}: {level['id']}", flush=True)
    try:
        with tempfile.TemporaryDirectory(dir=results_directory) as directory:
            temporary_directory = Path(directory)
            spec_path = temporary_directory / "spec.json"
            raw_output = temporary_directory / "level.json"
            spec_path.write_text(json.dumps(level, indent=2, sort_keys=True) + "\n")
            subprocess.run(
                [
                    "julia", "--project=julia", "julia/scripts/dry_assemble.jl",
                    str(level["graph_path"]), str(spec_path), str(raw_output),
                ],
                check=True,
                env=environment,
            )
            metadata = json.loads(raw_output.read_text())
        max_rss_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        payload = {
            "status": "COMPLETE",
            "mode": mode,
            "dry_level": level,
            "level": metadata,
            "runner": {
                "wall_seconds": time.monotonic() - started,
                "max_rss_gb": max_rss_kb / 1024**2,
                "allocated_cpus": allocated_cpus,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
            },
        }
        atomic_json(output, payload)
        print(
            f"complete {mode} {level['id']}: "
            f"max_rss_gb={payload['runner']['max_rss_gb']:.3f}",
            flush=True,
        )
    except Exception as error:
        atomic_json(
            output,
            {
                "status": "ERROR",
                "mode": mode,
                "dry_level": level,
                "reason": f"{type(error).__name__}: {error}",
                "runner": {
                    "wall_seconds": time.monotonic() - started,
                    "allocated_cpus": allocated_cpus,
                    "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                    "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
                },
            },
        )
        raise


if __name__ == "__main__":
    main()
