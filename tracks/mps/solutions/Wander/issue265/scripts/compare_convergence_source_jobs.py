#!/usr/bin/env python3
"""Compare all formal J2=0 convergence jobs under old and current helpers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import tenpy_research_backend as current_backend  # noqa: E402
from src.convergence_source_gate import (  # noqa: E402
    EXPECTED_JOB_COUNT,
    SourceGateError,
    sha256_file,
)


def _load_original_backend(path: Path) -> ModuleType:
    module_name = "src._first_slice_tenpy_research_backend"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SourceGateError(
            "source_gate: cannot load recovered backend"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def compare_jobs(
    *,
    manifest_path: Path,
    original_runner_path: Path,
    original_backend_path: Path,
    current_runner_path: Path,
    current_backend_path: Path,
) -> dict[str, Any]:
    """Return exact numerical/grid/hash comparisons for twelve jobs."""

    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGateError(
            f"source_gate: cannot parse manifest: {error}"
        ) from error
    jobs = [
        job
        for job in manifest.get("jobs", [])
        if job.get("stage") == "convergence"
    ]
    if len(jobs) != EXPECTED_JOB_COUNT:
        raise SourceGateError(
            f"source_gate: expected 12 convergence jobs, found {len(jobs)}"
        )
    old_backend = _load_original_backend(original_backend_path)
    comparisons: list[dict[str, Any]] = []
    for job in jobs:
        old_numerics = old_backend.resolve_numerics(job)
        new_numerics = current_backend.resolve_numerics(job)
        old_times = old_backend.output_times(old_numerics)
        new_times = current_backend.output_times(new_numerics)
        old_job_sha256 = old_backend.canonical_job_sha256(
            job,
            old_numerics,
        )
        new_job_sha256 = current_backend.canonical_job_sha256(
            job,
            new_numerics,
        )
        numerics_exact = old_numerics == new_numerics
        time_grid_exact = bool(
            old_times.dtype == new_times.dtype
            and np.array_equal(old_times, new_times)
        )
        canonical_exact = old_job_sha256 == new_job_sha256
        status = (
            "pass"
            if numerics_exact and time_grid_exact and canonical_exact
            else "fail"
        )
        comparisons.append(
            {
                "job_id": str(job["job_id"]),
                "status": status,
                "numerics_exact": numerics_exact,
                "old_numerics": old_numerics,
                "current_numerics": new_numerics,
                "time_grid_exact": time_grid_exact,
                "time_grid_points": int(old_times.size),
                "time_grid_start": float(old_times[0]),
                "time_grid_end": float(old_times[-1]),
                "canonical_job_sha256_exact": canonical_exact,
                "original_canonical_job_sha256": old_job_sha256,
                "current_canonical_job_sha256": new_job_sha256,
            }
        )
    passed = all(item["status"] == "pass" for item in comparisons)
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if passed else "fail",
        "manifest_sha256": sha256_file(manifest_path),
        "original_runner_sha256": sha256_file(original_runner_path),
        "original_backend_sha256": sha256_file(original_backend_path),
        "current_runner_sha256": sha256_file(current_runner_path),
        "current_backend_sha256": sha256_file(current_backend_path),
        "job_count": len(comparisons),
        "jobs": comparisons,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--original-runner", type=Path, required=True)
    parser.add_argument("--original-backend", type=Path, required=True)
    parser.add_argument("--current-runner", type=Path, required=True)
    parser.add_argument("--current-backend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_jobs(
        manifest_path=args.manifest,
        original_runner_path=args.original_runner,
        original_backend_path=args.original_backend,
        current_runner_path=args.current_runner,
        current_backend_path=args.current_backend,
    )
    _atomic_write(args.output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "job_count": result["job_count"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    if result["status"] != "pass":
        raise SystemExit("source_gate: all-job comparison failed")


if __name__ == "__main__":
    try:
        main()
    except SourceGateError as error:
        raise SystemExit(str(error)) from None
