#!/usr/bin/env python3
"""Run one recoverable machine shard of the approved Stage 3 coarse grid."""

from __future__ import annotations

import argparse
from concurrent.futures import as_completed, ProcessPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback

import numpy as np
import scipy

from tensor_square.dqmc import run_chain
from tensor_square.scan import (
    coarse_grid,
    deterministic_seed,
    EXPERIMENT_ID,
    needs_stable_retry,
    portable_command,
    run_fingerprint,
    ScanCell,
    select_shard,
    validate_run_fingerprint,
    validate_source_revision,
)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_progress(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _git_metadata(project_root: Path) -> dict[str, object]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() if completed.returncode == 0 else "unknown"

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def _run_cell(
    task: tuple[ScanCell, str, str, int, int, int, str],
) -> dict[str, object]:
    (
        cell,
        output_dir_text,
        machine,
        warmup,
        measurement,
        measure_every,
        source_revision,
    ) = task
    output_dir = Path(output_dir_text)
    cell_dir = output_dir / "cells" / cell.cell_id
    summary_path = cell_dir / "summary.json"
    seed = deterministic_seed(EXPERIMENT_ID, cell.cell_id, cell.worker_id)
    run_spec: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "cell_id": cell.cell_id,
        "cell_index": cell.index,
        "machine": machine,
        "worker_id": cell.worker_id,
        "seed": seed,
        "config": cell.config.as_dict(),
        "warmup_sweeps": warmup,
        "measurement_sweeps": measurement,
        "measure_every": measure_every,
        "source_revision": source_revision,
    }
    fingerprint = run_fingerprint(run_spec)
    if summary_path.exists():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        if previous.get("status") == "COMPLETE":
            try:
                validate_run_fingerprint(
                    str(previous.get("run_fingerprint", "")),
                    fingerprint,
                )
            except ValueError as error:
                payload = {
                    "status": "ERROR",
                    "experiment_id": EXPERIMENT_ID,
                    "cell_id": cell.cell_id,
                    "cell_index": cell.index,
                    "machine": machine,
                    "worker_id": cell.worker_id,
                    "seed": seed,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
                _atomic_json(cell_dir / "error.json", payload)
                return payload
            return previous

    config_payload = {
        "run_spec": run_spec,
        "run_fingerprint": fingerprint,
    }
    _atomic_json(cell_dir / "config.json", config_payload)
    _append_progress(
        cell_dir / "progress.jsonl",
        {
            "event": "start",
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "seed": seed,
        },
    )
    try:
        checkpoint_dir = cell_dir / "checkpoint"
        chain = run_chain(
            cell.config,
            seed=seed,
            warmup_sweeps=warmup,
            measurement_sweeps=measurement,
            measure_every=measure_every,
            progress_every=warmup + measurement,
            checkpoint_path=checkpoint_dir / "chain.npz",
            checkpoint_every=max(20, (warmup + measurement) // 3),
            run_fingerprint=fingerprint,
        )
        initial_audit = None
        if not bool(chain["stabilized"]) and needs_stable_retry(chain):
            initial_audit = {
                "direct_sign_mean": chain["direct_sign_mean"],
                "direct_sign_min": chain["direct_sign_min"],
                "weight_log_error_mean": chain["weight_log_error_mean"],
                "weight_log_error_max": chain["weight_log_error_max"],
                "density_mean": chain["density_mean"],
                "density_min": chain["density_min"],
                "density_max": chain["density_max"],
            }
            stable_config = replace(cell.config, stabilize=True)
            chain = run_chain(
                stable_config,
                seed=seed,
                warmup_sweeps=warmup,
                measurement_sweeps=measurement,
                measure_every=measure_every,
                progress_every=warmup + measurement,
                checkpoint_path=checkpoint_dir / "chain_stable.npz",
                checkpoint_every=max(20, (warmup + measurement) // 3),
                run_fingerprint=fingerprint,
            )
        payload: dict[str, object] = {
            "status": "COMPLETE",
            "experiment_id": EXPERIMENT_ID,
            "cell_id": cell.cell_id,
            "cell_index": cell.index,
            "machine": machine,
            "worker_id": cell.worker_id,
            "stability_retry": initial_audit is not None,
            "initial_audit": initial_audit,
            "run_spec": run_spec,
            "run_fingerprint": fingerprint,
            **chain,
        }
        _atomic_json(summary_path, payload)
        _append_progress(
            cell_dir / "progress.jsonl",
            {
                "event": "complete",
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "acceptance": chain["acceptance"],
                "stabilized": chain["stabilized"],
            },
        )
        print(
            f"COMPLETE {machine} worker={cell.worker_id} {cell.cell_id} "
            f"E={float(chain['energy_mean']):.6f} "
            f"Q={float(chain['q_combined_mean']):.6f}",
            flush=True,
        )
        return payload
    except Exception as error:  # keep independent cells independent
        payload = {
            "status": "ERROR",
            "experiment_id": EXPERIMENT_ID,
            "cell_id": cell.cell_id,
            "cell_index": cell.index,
            "machine": machine,
            "worker_id": cell.worker_id,
            "seed": seed,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        _atomic_json(cell_dir / "error.json", payload)
        _append_progress(
            cell_dir / "progress.jsonl",
            {
                "event": "error",
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": type(error).__name__,
            },
        )
        print(
            f"ERROR {machine} worker={cell.worker_id} {cell.cell_id} "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--machine", required=True, choices=("wsl", "cpu"))
    parser.add_argument("--workers", required=True, type=int)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--measurement", type=int, default=80)
    parser.add_argument("--measure-every", type=int, default=2)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    worker_limit = 14 if args.machine == "wsl" else 62
    if not 1 <= args.workers <= worker_limit:
        raise ValueError(
            f"{args.machine} worker count must be in [1, {worker_limit}]"
        )
    if args.warmup < 0 or args.measurement <= 0 or args.measure_every <= 0:
        raise ValueError("sweep counts must be positive (warmup may be zero)")

    cells = select_shard(coarse_grid(), args.machine)
    if args.limit is not None:
        cells = cells[: args.limit]
    study_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[6]
    git_metadata = _git_metadata(project_root)
    validate_source_revision(
        str(git_metadata["commit"]),
        dirty=bool(git_metadata["dirty"]),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "machine": args.machine,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": portable_command(sys.argv, study_root),
        "grid_cells": len(cells),
        "full_grid_cells": len(coarse_grid()),
        "worker_ids": sorted({cell.worker_id for cell in cells}),
        "max_processes": min(args.workers, len(cells)),
        "blas_threads": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "seed_rule": "uint32_be(SHA256(experiment_id|cell_id|worker_id)[:4])",
        "grid": {
            "m": [4, 6, 8],
            "beta": [2.0, 4.0, 8.0],
            "dt": 0.2,
            "g_b_over_g_a": [0.0, 0.25, 0.5, 1.0, 2.0],
            "t": [0.0, 0.25, 0.5, 1.0, 2.0],
            "mu": [-1.5, 0.0, 1.5],
            "stabilized_beta": [4.0, 8.0],
        },
        "sweeps": {
            "warmup": args.warmup,
            "measurement": args.measurement,
            "measure_every": args.measure_every,
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "git": git_metadata,
    }
    _atomic_json(
        args.output_dir / f"manifest_{args.machine}.json",
        manifest,
    )

    context = mp.get_context("spawn")
    tasks = [
        (
            cell,
            str(args.output_dir),
            args.machine,
            args.warmup,
            args.measurement,
            args.measure_every,
            str(git_metadata["commit"]),
        )
        for cell in cells
    ]
    completed: list[dict[str, object]] = []
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(tasks)),
        mp_context=context,
    ) as executor:
        futures = [executor.submit(_run_cell, task) for task in tasks]
        for future in as_completed(futures):
            completed.append(future.result())
    errors = [result for result in completed if result["status"] != "COMPLETE"]
    shard_summary = {
        "experiment_id": EXPERIMENT_ID,
        "machine": args.machine,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "requested": len(tasks),
        "complete": len(completed) - len(errors),
        "errors": len(errors),
        "error_cells": [result["cell_id"] for result in errors],
    }
    _atomic_json(
        args.output_dir / f"shard_summary_{args.machine}.json",
        shard_summary,
    )
    print(json.dumps(shard_summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
