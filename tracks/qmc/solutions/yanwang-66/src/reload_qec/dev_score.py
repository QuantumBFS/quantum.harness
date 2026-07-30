"""Aggregate exact-replay-passed public validator cell timings."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any

from .config import SimulationRequest
from .dev_matrix import MATRIX_SCHEMA
from .dev_validator import RUNNER_SCHEMA
from .sandbox import MAX_ADDRESS_SPACE_BYTES, SANDBOX_SCHEMA


SCORE_SCHEMA = "q66-dev-validator-score-v1"
MAX_RSS_KIB = 16 * 1024 * 1024


class DevScoreError(ValueError):
    """Raised when runner evidence is incomplete or inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def aggregate_score(
    *, matrix_path: Path, results_root: Path, out_path: Path
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise DevScoreError("development scoring must run inside Slurm")
    matrix_sha256 = _sha256(matrix_path)
    matrix = json.loads(matrix_path.read_text(encoding="ascii"))
    if matrix.get("schema_version") != MATRIX_SCHEMA:
        raise DevScoreError("development matrix schema mismatch")
    cells = matrix.get("cells")
    if not isinstance(cells, list) or len(cells) != 16:
        raise DevScoreError("development matrix is not the frozen 16 cells")
    expected_entries = {f"cell-{index:02d}" for index in range(16)}
    actual_entries = {path.name for path in results_root.iterdir()}
    if actual_entries != expected_entries:
        raise DevScoreError("validator result cells are incomplete or extra")

    candidate_ids: set[str] = set()
    candidate_tree_hashes: set[str] = set()
    rows = []
    seconds_by_distance: dict[int, list[float]] = {3: [], 5: []}
    shots_by_distance = {3: 0, 5: 0}
    for cell_index, cell in enumerate(cells):
        request = SimulationRequest.from_dict(cell["request"])
        report_path = (
            results_root / f"cell-{cell_index:02d}" / "runner-report.json"
        )
        report = json.loads(report_path.read_text(encoding="ascii"))
        if report.get("schema_version") != RUNNER_SCHEMA:
            raise DevScoreError(f"runner schema mismatch for cell {cell_index}")
        if report.get("status") != "passed":
            raise DevScoreError(f"runner rejected cell {cell_index}")
        if report.get("cell_index") != cell_index:
            raise DevScoreError(f"runner cell identity mismatch for {cell_index}")
        if report.get("workload_id") != cell["workload_id"]:
            raise DevScoreError(f"runner workload mismatch for cell {cell_index}")
        if report.get("matrix_sha256") != matrix_sha256:
            raise DevScoreError(f"runner matrix hash mismatch for cell {cell_index}")
        if report.get("slurm_array_job_id") != results_root.name:
            raise DevScoreError(f"runner array job mismatch for cell {cell_index}")
        if report.get("slurm_array_task_id") != str(cell_index):
            raise DevScoreError(f"runner array task mismatch for cell {cell_index}")
        sandbox = report.get("sandbox")
        if sandbox != {
            "schema_version": SANDBOX_SCHEMA,
            "network_isolation": "seccomp-bpf-errno-eperm",
            "process_group_isolation": "seccomp-bpf-errno-eperm",
            "no_new_privs": 1,
            "seccomp_mode": 2,
            "setpgid_errno": 1,
            "setsid_errno": 1,
            "socket_errno": 1,
            "address_space_limit_bytes": MAX_ADDRESS_SPACE_BYTES,
        }:
            raise DevScoreError(f"sandbox evidence mismatch for cell {cell_index}")
        if report.get("filesystem_guard") != (
            "candidate-tree-sha256-before-and-after-every-run"
        ):
            raise DevScoreError(f"filesystem guard mismatch for cell {cell_index}")
        candidate_ids.add(str(report.get("candidate_id")))
        candidate_tree_hashes.add(str(report.get("candidate_tree_sha256")))
        runs = report.get("runs")
        if not isinstance(runs, list) or len(runs) != 4:
            raise DevScoreError(f"runner repetition count mismatch for cell {cell_index}")
        timed_seconds = []
        validator_seconds = []
        peak_rss_kib = 0
        for repetition, run in enumerate(runs):
            expected_role = "warmup" if repetition == 0 else "timed"
            if (
                run.get("repetition") != repetition
                or run.get("timing_role") != expected_role
                or run.get("run_id")
                != f"{request.run_id}-repeat-{repetition}"
                or run.get("shot_start") != repetition * request.shots
                or run.get("shots") != request.shots
                or run.get("validation") != "exact-replay-passed"
                or run.get("return_code") != 0
                or run.get("timed_out") is not False
                or run.get("process_cleanup")
                != {
                    "background_processes_detected": False,
                    "background_process_ids": [],
                    "background_process_signals": [],
                    "process_group_cleared": True,
                }
            ):
                raise DevScoreError(
                    f"invalid runner evidence in cell {cell_index}, repeat {repetition}"
                )
            candidate_seconds = float(run["candidate_wall_seconds"])
            replay_seconds = float(run["validator_wall_seconds"])
            rss_kib = int(run["children_max_rss_kib"])
            if (
                not math.isfinite(candidate_seconds)
                or candidate_seconds <= 0.0
                or not math.isfinite(replay_seconds)
                or replay_seconds <= 0.0
                or rss_kib <= 0
                or rss_kib > MAX_RSS_KIB
            ):
                raise DevScoreError(
                    f"invalid time/RSS in cell {cell_index}, repeat {repetition}"
                )
            peak_rss_kib = max(peak_rss_kib, rss_kib)
            if repetition > 0:
                timed_seconds.append(candidate_seconds)
                validator_seconds.append(replay_seconds)
        median_seconds = float(statistics.median(timed_seconds))
        median_validator_seconds = float(statistics.median(validator_seconds))
        seconds_by_distance[request.distance].append(median_seconds)
        shots_by_distance[request.distance] += request.shots
        rows.append(
            {
                "cell_index": cell_index,
                "workload_id": cell["workload_id"],
                "run_id": request.run_id,
                "distance": request.distance,
                "shots": request.shots,
                "median_candidate_seconds": median_seconds,
                "median_validator_seconds": median_validator_seconds,
                "peak_children_rss_kib": peak_rss_kib,
            }
        )
    if len(candidate_ids) != 1 or len(candidate_tree_hashes) != 1:
        raise DevScoreError("validator cells used different candidate identities")

    throughput = {
        distance: shots_by_distance[distance] / sum(seconds_by_distance[distance])
        for distance in (3, 5)
    }
    score = math.sqrt(throughput[3] * throughput[5])
    report = {
        "schema_version": SCORE_SCHEMA,
        "status": "passed",
        "slurm_job_id": slurm_job_id,
        "matrix": str(matrix_path),
        "matrix_sha256": matrix_sha256,
        "results_root": str(results_root),
        "candidate_id": candidate_ids.pop(),
        "candidate_tree_sha256": candidate_tree_hashes.pop(),
        "validated_shots_d3": shots_by_distance[3],
        "validated_shots_d5": shots_by_distance[5],
        "q3": throughput[3],
        "q5": throughput[5],
        "score": score,
        "cells": rows,
    }
    if out_path.exists():
        raise DevScoreError(f"score output already exists: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _canonical_json(out_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = aggregate_score(
        matrix_path=args.matrix,
        results_root=args.results_root,
        out_path=args.out,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
