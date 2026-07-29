#!/usr/bin/env python3
"""Run one recoverable machine shard of the pre-registered Stage 4 scan."""

from __future__ import annotations

import argparse
from concurrent.futures import as_completed, ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
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
    needs_stable_retry,
    portable_command,
    run_fingerprint,
    validate_run_fingerprint,
    validate_source_revision,
)
from tensor_square.stage4 import (
    BLAS_THREAD_VARIABLES,
    dense_grid,
    EXPERIMENT_ID,
    production_audit,
    replica_specs,
    ReplicaSpec,
    select_shard,
    shard_exit_code,
    Stage4Policy,
    validate_blas_environment,
    validate_budget_plan,
)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
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
        return (
            completed.stdout.strip()
            if completed.returncode == 0
            else "unknown"
        )

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def _run_replica(
    task: tuple[ReplicaSpec, str, str, str, str | None],
) -> dict[str, object]:
    spec, output_dir_text, machine, source_revision, plan_digest = task
    policy = Stage4Policy()
    cell = spec.cell
    output_dir = Path(output_dir_text)
    replica_dir = (
        output_dir
        / "cells"
        / cell.cell_id
        / spec.phase
        / f"replica_{spec.replica:02d}"
    )
    summary_path = replica_dir / "summary.json"
    run_spec: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "cell_id": cell.cell_id,
        "cell_index": cell.index,
        "cohort": cell.cohort,
        "pair_id": cell.pair_id,
        "machine": machine,
        "worker_id": cell.worker_id,
        "phase": spec.phase,
        "replica": spec.replica,
        "seed": spec.seed,
        "config": cell.config.as_dict(),
        "warmup_sweeps": spec.warmup_sweeps,
        "measurement_sweeps": spec.measurement_sweeps,
        "max_measurement_sweeps": (
            policy.max_measurement_sweeps
            if spec.phase == "production"
            else spec.measurement_sweeps
        ),
        "measure_every": spec.measure_every,
        "target_ess_per_replica": (
            policy.target_ess_per_replica
            if spec.phase == "production"
            else None
        ),
        "budget_plan_digest": plan_digest,
        "source_revision": source_revision,
    }
    fingerprint = run_fingerprint(run_spec)
    if summary_path.exists():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        if previous.get("status") in {"COMPLETE", "EARLY_STOP"}:
            validate_run_fingerprint(
                str(previous.get("run_fingerprint", "")),
                fingerprint,
            )
            return previous

    _atomic_json(
        replica_dir / "config.json",
        {"run_spec": run_spec, "run_fingerprint": fingerprint},
    )
    _append_progress(
        replica_dir / "progress.jsonl",
        {
            "event": "start",
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "seed": spec.seed,
        },
    )
    try:
        measurement_sweeps = spec.measurement_sweeps
        audit_history: list[dict[str, object]] = []
        while True:
            total_sweeps = spec.warmup_sweeps + measurement_sweeps
            chain = run_chain(
                cell.config,
                seed=spec.seed,
                warmup_sweeps=spec.warmup_sweeps,
                measurement_sweeps=measurement_sweeps,
                measure_every=spec.measure_every,
                progress_every=max(20, total_sweeps // 20),
                checkpoint_path=replica_dir / "checkpoint" / "chain.npz",
                checkpoint_every=max(40, total_sweeps // 20),
                run_fingerprint=fingerprint,
            )
            if spec.phase == "pilot":
                if needs_stable_retry(chain):
                    raise RuntimeError(
                        "stabilized pilot failed determinant or density audit"
                    )
                final_status = "COMPLETE"
                final_audit: dict[str, object] = {
                    "status": "PASS",
                    "reason": "pilot numerical audit passed",
                }
                break
            final_audit = production_audit(
                chain,
                current_measurement_sweeps=measurement_sweeps,
                policy=policy,
            )
            audit_history.append(dict(final_audit))
            if final_audit["status"] == "EXTEND":
                measurement_sweeps = int(
                    final_audit["next_measurement_sweeps"]
                )
                continue
            final_status = (
                "COMPLETE"
                if final_audit["status"] == "PASS"
                else "EARLY_STOP"
            )
            break
        payload: dict[str, object] = {
            "status": final_status,
            "experiment_id": EXPERIMENT_ID,
            "cell_id": cell.cell_id,
            "cell_index": cell.index,
            "cohort": cell.cohort,
            "pair_id": cell.pair_id,
            "machine": machine,
            "worker_id": cell.worker_id,
            "phase": spec.phase,
            "replica": spec.replica,
            "run_spec": run_spec,
            "run_fingerprint": fingerprint,
            "realized_measurement_sweeps": measurement_sweeps,
            "adaptive_audit_history": audit_history,
            "final_audit": final_audit,
            **chain,
        }
        _atomic_json(summary_path, payload)
        _append_progress(
            replica_dir / "progress.jsonl",
            {
                "event": "complete",
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "acceptance": chain["acceptance"],
                "status": final_status,
            },
        )
        print(
            f"{final_status} {machine} {spec.phase} worker={cell.worker_id} "
            f"{cell.cell_id} replica={spec.replica} "
            f"Q={float(chain['q_combined_mean']):.6f}",
            flush=True,
        )
        return payload
    except Exception as error:
        payload = {
            "status": "ERROR",
            "experiment_id": EXPERIMENT_ID,
            "cell_id": cell.cell_id,
            "cell_index": cell.index,
            "machine": machine,
            "worker_id": cell.worker_id,
            "phase": spec.phase,
            "replica": spec.replica,
            "seed": spec.seed,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        _atomic_json(replica_dir / "error.json", payload)
        _append_progress(
            replica_dir / "progress.jsonl",
            {
                "event": "error",
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": type(error).__name__,
            },
        )
        print(
            f"ERROR {machine} {spec.phase} {cell.cell_id} "
            f"replica={spec.replica} {type(error).__name__}: {error}",
            flush=True,
        )
        return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--machine", required=True, choices=("wsl", "cpu"))
    parser.add_argument("--workers", required=True, type=int)
    parser.add_argument("--phase", required=True, choices=("pilot", "production"))
    parser.add_argument("--budget-plan", type=Path)
    parser.add_argument("--limit-cells", type=int)
    args = parser.parse_args()

    worker_limit = 14 if args.machine == "wsl" else 62
    if not 1 <= args.workers <= worker_limit:
        raise ValueError(
            f"{args.machine} worker count must be in [1, {worker_limit}]"
        )
    blas_environment = {
        name: os.environ.get(name, "") for name in BLAS_THREAD_VARIABLES
    }
    validate_blas_environment(blas_environment)
    policy = Stage4Policy()
    study_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[6]
    git_metadata = _git_metadata(project_root)
    validate_source_revision(
        str(git_metadata["commit"]),
        dirty=bool(git_metadata["dirty"]),
    )
    decisions = None
    plan_digest = None
    if args.phase == "production":
        if args.budget_plan is None:
            raise ValueError("production phase requires --budget-plan")
        plan_bytes = args.budget_plan.read_bytes()
        plan = json.loads(plan_bytes)
        validate_budget_plan(
            plan,
            source_revision=str(git_metadata["commit"]),
            policy=policy,
        )
        decisions = plan["decisions"]
        plan_digest = hashlib.sha256(plan_bytes).hexdigest()

    cells = select_shard(dense_grid(), args.machine)
    if args.limit_cells is not None:
        cells = cells[: args.limit_cells]
    specs = replica_specs(
        cells,
        phase=args.phase,
        policy=policy,
        decisions=decisions,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "phase": args.phase,
        "machine": args.machine,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": portable_command(sys.argv, study_root),
        "grid_cells": len(cells),
        "replica_tasks": len(specs),
        "worker_ids": sorted({cell.worker_id for cell in cells}),
        "max_processes": min(args.workers, len(specs)),
        "blas_threads": blas_environment,
        "policy": asdict(policy),
        "budget_plan_digest": plan_digest,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "git": git_metadata,
    }
    _atomic_json(
        args.output_dir / f"manifest_{args.phase}_{args.machine}.json",
        manifest,
    )

    context = mp.get_context("spawn")
    tasks = [
        (
            spec,
            str(args.output_dir),
            args.machine,
            str(git_metadata["commit"]),
            plan_digest,
        )
        for spec in specs
    ]
    completed: list[dict[str, object]] = []
    if tasks:
        with ProcessPoolExecutor(
            max_workers=min(args.workers, len(tasks)),
            mp_context=context,
        ) as executor:
            futures = [executor.submit(_run_replica, task) for task in tasks]
            for future in as_completed(futures):
                completed.append(future.result())
    errors = [result for result in completed if result["status"] == "ERROR"]
    early_stops = [
        result for result in completed if result["status"] == "EARLY_STOP"
    ]
    shard_summary = {
        "experiment_id": EXPERIMENT_ID,
        "phase": args.phase,
        "machine": args.machine,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "requested": len(tasks),
        "complete": len(completed) - len(errors) - len(early_stops),
        "early_stops": len(early_stops),
        "errors": len(errors),
        "error_replicas": [
            {
                "cell_id": result["cell_id"],
                "replica": result["replica"],
            }
            for result in errors
        ],
    }
    _atomic_json(
        args.output_dir
        / f"shard_summary_{args.phase}_{args.machine}.json",
        shard_summary,
    )
    print(json.dumps(shard_summary, indent=2, sort_keys=True), flush=True)
    exit_code = shard_exit_code(completed)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
