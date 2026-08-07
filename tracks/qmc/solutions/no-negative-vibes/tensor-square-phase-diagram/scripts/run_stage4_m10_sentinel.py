#!/usr/bin/env python3
"""Run one preregistered numerical-only m=10 Stage 4 sentinel."""

from __future__ import annotations

import argparse
from concurrent.futures import as_completed, ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from run_stage4_dense import _atomic_json, _git_metadata, _run_replica
from tensor_square.dqmc import DQMCConfig
from tensor_square.scan import portable_command, validate_source_revision
from tensor_square.stage4 import (
    BLAS_THREAD_VARIABLES,
    DenseCell,
    ReplicaSpec,
    shard_exit_code,
    Stage4Policy,
    validate_blas_environment,
)


SENTINEL_EXPERIMENT_ID = "stage4-m10-numerical-sentinel-20260729-v1"


def _seed(cell_id: str, replica: int, worker_id: int) -> int:
    material = (
        f"{SENTINEL_EXPERIMENT_ID}|{cell_id}|production|"
        f"{replica}|{worker_id}"
    ).encode("utf-8")
    return int.from_bytes(
        hashlib.sha256(material).digest()[:4],
        byteorder="big",
        signed=False,
    )


def _validate_release(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("experiment_id") != SENTINEL_EXPERIMENT_ID:
        raise ValueError("sentinel release experiment_id mismatch")
    selected = payload.get("selected")
    if not isinstance(selected, dict):
        raise ValueError("sentinel release has no selected candidate")
    expected = {
        "sentinel_classification": "ELIGIBLE",
        "inference_scope": "numerical_only",
        "physics_claim_permitted": False,
        "m": 10,
        "beta": 4.0,
        "dt": 0.2,
        "production_replicas": 4,
        "target_ess_per_replica": 40.0,
    }
    if any(selected.get(key) != value for key, value in expected.items()):
        raise ValueError("sentinel release violates the frozen selection gate")
    policy = Stage4Policy()
    warmup = int(selected["initial_warmup_sweeps"])
    measurement = int(selected["initial_measurement_sweeps"])
    if (
        not policy.min_warmup_sweeps
        <= warmup
        <= policy.max_warmup_sweeps
        or not policy.min_measurement_sweeps
        <= measurement
        <= policy.max_measurement_sweeps
    ):
        raise ValueError("sentinel initial budget is outside Stage 4 bounds")
    evidence_digest = str(payload.get("production_evidence_digest", ""))
    if len(evidence_digest) != 64 or any(
        character not in "0123456789abcdef"
        for character in evidence_digest
    ):
        raise ValueError("sentinel production evidence digest is invalid")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--machine", choices=("wsl", "cpu"), default="cpu")
    parser.add_argument("--workers", required=True, type=int)
    args = parser.parse_args()

    worker_limit = 14 if args.machine == "wsl" else 62
    if not 1 <= args.workers <= min(worker_limit, 4):
        raise ValueError("m=10 sentinel workers must be in [1, 4]")
    validate_blas_environment(
        {name: os.environ.get(name, "") for name in BLAS_THREAD_VARIABLES}
    )
    release_bytes = args.release.read_bytes()
    release = json.loads(release_bytes)
    selected = _validate_release(release)
    release_digest = hashlib.sha256(release_bytes).hexdigest()

    study_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[6]
    git_metadata = _git_metadata(project_root)
    validate_source_revision(
        str(git_metadata["commit"]),
        dirty=bool(git_metadata["dirty"]),
    )
    cell_id = (
        "m10_numerical"
        f"_b{int(float(selected['beta'])):02d}"
        f"_g{int(round(100 * float(selected['g_b_over_g_a']))):03d}"
        f"_t{int(round(100 * float(selected['t']))):03d}"
        "_mu000"
    )
    config = DQMCConfig(
        m=10,
        beta=float(selected["beta"]),
        dt=float(selected["dt"]),
        t=float(selected["t"]),
        g_b_over_g_a=float(selected["g_b_over_g_a"]),
        mu=float(selected["mu"]),
        proposal_scale=float(selected["proposal_scale"]),
        stabilize=True,
    )
    first_worker = 0 if args.machine == "wsl" else 14
    specs: list[ReplicaSpec] = []
    for replica in range(int(selected["production_replicas"])):
        worker_id = first_worker + replica
        cell = DenseCell(
            index=replica,
            cell_id=cell_id,
            cohort="m10_numerical_sentinel",
            config=config,
            worker_id=worker_id,
        )
        specs.append(
            ReplicaSpec(
                cell=cell,
                phase="production",
                replica=replica,
                seed=_seed(cell_id, replica, worker_id),
                warmup_sweeps=int(selected["initial_warmup_sweeps"]),
                measurement_sweeps=int(
                    selected["initial_measurement_sweeps"]
                ),
                measure_every=int(selected["measure_every"]),
            )
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": SENTINEL_EXPERIMENT_ID,
        "inference_scope": "numerical_only",
        "physics_claim_permitted": False,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "machine": args.machine,
        "command": portable_command(sys.argv, study_root),
        "release_digest": release_digest,
        "stage4_production_evidence_digest": release[
            "production_evidence_digest"
        ],
        "selected_candidate": selected,
        "replica_tasks": len(specs),
        "max_processes": min(args.workers, len(specs)),
        "blas_threads": {
            name: os.environ[name] for name in BLAS_THREAD_VARIABLES
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "git": git_metadata,
    }
    _atomic_json(args.output_dir / "manifest.json", manifest)
    tasks = [
        (
            spec,
            str(args.output_dir),
            args.machine,
            str(git_metadata["commit"]),
            release_digest,
            SENTINEL_EXPERIMENT_ID,
        )
        for spec in specs
    ]
    completed: list[dict[str, object]] = []
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(tasks)),
        mp_context=context,
    ) as executor:
        futures = [executor.submit(_run_replica, task) for task in tasks]
        for future in as_completed(futures):
            completed.append(future.result())
    errors = [row for row in completed if row["status"] == "ERROR"]
    early_stops = [
        row for row in completed if row["status"] == "EARLY_STOP"
    ]
    summary = {
        "experiment_id": SENTINEL_EXPERIMENT_ID,
        "inference_scope": "numerical_only",
        "physics_claim_permitted": False,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "requested": len(tasks),
        "complete": len(tasks) - len(errors) - len(early_stops),
        "early_stops": len(early_stops),
        "errors": len(errors),
        "error_replicas": [
            int(row["replica"]) for row in errors
        ],
    }
    _atomic_json(args.output_dir / "shard_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    exit_code = shard_exit_code(completed)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
