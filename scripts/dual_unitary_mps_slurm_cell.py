#!/usr/bin/env python3
"""Run one dual-unitary MPS trajectory as a resumable Slurm array cell."""

from __future__ import annotations

import os

for _name in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

try:
    from dual_unitary_mps import run_mps_trajectory
except ImportError:
    from scripts.dual_unitary_mps import run_mps_trajectory


WIDTHS = (8, 10, 12, 14, 16)
CHI_BY_WIDTH = {
    8: (16,),
    10: (24, 32),
    12: (48, 64, 96),
    14: (64, 96, 128, 192),
    16: (96, 128, 192, 256),
}
SAMPLES_PER_POINT = 400


@dataclass(frozen=True)
class CellResult:
    result_path: Path
    manifest_path: Path
    resumed: bool


def _write_json_atomic(value, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trajectory_seed(base_seed: int, L: int, sample: int) -> int:
    """Return a common-random-number seed shared by all chi at fixed L/sample."""
    sequence = np.random.SeedSequence([base_seed, L, sample, 0xD0A1])
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def write_production_spec(path: Path, run_id: str) -> dict:
    path = Path(path)
    settings = {
        "p": 0.14,
        "cutoff": 1e-12,
        "base_seed": 12220260730,
        "burn_in_multiplier": 32,
        "record_multiplier": 256,
        "samples_per_point": SAMPLES_PER_POINT,
    }
    cells = []
    for L in WIDTHS:
        for chi in CHI_BY_WIDTH[L]:
            for sample in range(SAMPLES_PER_POINT):
                cells.append(
                    {
                        "cell_id": f"L{L:02d}-chi{chi:03d}-s{sample:03d}",
                        "params": {
                            "L": L,
                            "chi": chi,
                            "sample_index": sample,
                            "seed": _trajectory_seed(
                                settings["base_seed"], L, sample
                            ),
                        },
                    }
                )
    submission_batches = [[] for _ in range(SAMPLES_PER_POINT)]
    for selector, cell in enumerate(cells, start=1):
        sample = int(cell["params"]["sample_index"])
        submission_batches[sample].append(selector)
    spec = {
        "schema_version": 1,
        "run_id": run_id,
        "run_dir": f"results/{run_id}",
        "settings": settings,
        "provenance": {
            "ensemble": "dual-Haar dual-unitary gates",
            "boundary": "periodic physical ring via explicit SWAP network",
            "measurement": "independent z projection with Born sampling",
        },
        "cells": cells,
        # One batch per sample index gives every Slurm task exactly one
        # trajectory from each (L, chi) point.  The 400 tasks are therefore
        # workload-balanced and stay below the cluster's per-user submit cap.
        "submission_batches": submission_batches,
    }
    _write_json_atomic(spec, path)
    return spec


def _select_cell(run_spec: Mapping, selector: int) -> dict:
    cells = list(run_spec.get("cells", ()))
    if selector < 1 or selector > len(cells):
        raise ValueError("cell selector must be one-based and within the run spec")
    return dict(cells[selector - 1])


def _entropy_density_slope(record: Mapping) -> float:
    cumulative = np.asarray(record["cumulative_record_cost"], dtype=float)
    times = np.arange(1, cumulative.size + 1, dtype=float)
    design = np.column_stack((np.ones_like(times), times))
    coefficients, _, _, _ = np.linalg.lstsq(
        design, cumulative / int(record["L"]), rcond=None
    )
    return float(coefficients[1])


def run_cell(
    run_spec: Mapping,
    selector: int,
    trajectory_runner=run_mps_trajectory,
) -> CellResult:
    cell = _select_cell(run_spec, int(selector))
    settings = dict(run_spec["settings"])
    params = dict(cell["params"])
    cell_dir = Path(run_spec["run_dir"]) / "cells" / cell["cell_id"]
    result_path = cell_dir / "result.json"
    manifest_path = cell_dir / "manifest.json"

    if result_path.is_file() and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("status") == "success"
            and manifest.get("artifact_sha256") == _sha256(result_path)
        ):
            return CellResult(result_path, manifest_path, True)

    L = int(params["L"])
    burn_in_steps = int(settings["burn_in_multiplier"]) * L
    record_steps = int(settings["record_multiplier"]) * L
    total_steps = burn_in_steps + record_steps
    print(
        f"start {cell['cell_id']} L={L} chi={params['chi']} "
        f"steps={total_steps} seed={params['seed']}",
        flush=True,
    )
    record = dict(
        trajectory_runner(
            L=L,
            p=float(settings["p"]),
            chi=int(params["chi"]),
            seed=int(params["seed"]),
            burn_in_steps=burn_in_steps,
            record_steps=record_steps,
            cutoff=float(settings["cutoff"]),
            progress_every=max(1, total_steps // 25),
        )
    )
    record.update(
        {
            "run_id": run_spec["run_id"],
            "cell_id": cell["cell_id"],
            "sample_index": int(params.get("sample_index", 0)),
        }
    )
    slope = _entropy_density_slope(record)
    _write_json_atomic(record, result_path)
    manifest = {
        "status": "success",
        "run_id": run_spec["run_id"],
        "cell_id": cell["cell_id"],
        "L": L,
        "chi": int(params["chi"]),
        "seed": int(params["seed"]),
        "sample_index": int(params.get("sample_index", 0)),
        "burn_in_steps": burn_in_steps,
        "record_steps": record_steps,
        "entropy_density_slope": slope,
        "discarded_weight_sum": float(record["discarded_weight_sum"]),
        "discarded_weight_rate": float(record["discarded_weight_sum"])
        / max(1, int(record["split_count"])),
        "runtime_seconds": float(record["runtime_seconds"]),
        "artifact": result_path.name,
        "artifact_sha256": _sha256(result_path),
    }
    _write_json_atomic(manifest, manifest_path)
    print(
        f"complete {cell['cell_id']} f={slope:.10f} "
        f"runtime={record['runtime_seconds']:.1f}s",
        flush=True,
    )
    return CellResult(result_path, manifest_path, False)


def run_batch(
    run_spec: Mapping,
    batch_selector: int,
    trajectory_runner=run_mps_trajectory,
) -> list[CellResult]:
    batches = list(run_spec.get("submission_batches", ()))
    if batch_selector < 1 or batch_selector > len(batches):
        raise ValueError("batch selector must be one-based and within the run spec")
    selectors = list(batches[batch_selector - 1])
    print(
        f"batch {batch_selector}/{len(batches)} cells={len(selectors)}",
        flush=True,
    )
    return [
        run_cell(run_spec, int(selector), trajectory_runner=trajectory_runner)
        for selector in selectors
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-spec", type=Path)
    parser.add_argument("--run-id", default="dual-unitary-mps-20260730")
    args = parser.parse_args(argv)
    if args.write_spec:
        spec = write_production_spec(args.write_spec, args.run_id)
        print(f"wrote {args.write_spec} with {len(spec['cells'])} cells")
        return 0

    spec_path = os.environ.get("HARNESS_RUN_SPEC")
    selector = os.environ.get(
        "SLURM_ARRAY_TASK_ID", os.environ.get("HARNESS_CELL_INDEX")
    )
    if not spec_path or not selector:
        raise SystemExit(
            "HARNESS_RUN_SPEC and SLURM_ARRAY_TASK_ID are required"
        )
    with Path(spec_path).open(encoding="utf-8") as handle:
        run_spec = json.load(handle)
    if os.environ.get("HARNESS_BATCH_MODE", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        run_batch(run_spec, int(selector))
    else:
        run_cell(run_spec, int(selector))
    return 0


if __name__ == "__main__":
    sys.exit(main())
