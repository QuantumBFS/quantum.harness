"""Run and exactly validate the frozen initial cost-sensitivity matrix."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .confirmation_run import (
    FROZEN_CANDIDATE_COMMIT,
    FROZEN_CANDIDATE_TREE_SHA256,
    _run_one,
    _validate_one,
)
from .dev_validator import _candidate_tree_sha256
from .sensitivity import load_sensitivity_matrix


RUN_SCHEMA = "q66-cost-sensitivity-initial-run-v1"
GROUP_SCHEMA = "q66-cost-sensitivity-initial-group-v1"


class SensitivityRunError(RuntimeError):
    """Raised when cost-sensitivity execution or exact replay is incomplete."""


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


def _worker_count(value: int, allocated: int, name: str) -> int:
    if not 1 <= value <= allocated:
        raise SensitivityRunError(
            f"{name} workers must be inside [1,{allocated}], got {value}"
        )
    return value


def run_initial_sensitivity(
    *,
    matrix_path: Path,
    candidate_root: Path,
    output_root: Path,
    simulation_workers: int,
    validation_workers: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise SensitivityRunError("cost sensitivity must execute inside Slurm")
    if os.environ.get("SLURM_ARRAY_TASK_ID") is not None:
        raise SensitivityRunError("initial cost sensitivity must be one job")
    if output_root.name != slurm_job_id:
        raise SensitivityRunError("cost-sensitivity output differs from Slurm job")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    simulation_workers = _worker_count(
        simulation_workers, allocated, "simulation"
    )
    validation_workers = _worker_count(
        validation_workers, allocated, "validation"
    )
    if not 1 <= timeout_seconds <= 10_800:
        raise SensitivityRunError("per-cell timeout must be inside [1,10800]")

    matrix_path = matrix_path.resolve(strict=True)
    candidate_root = candidate_root.resolve(strict=True)
    matrix = load_sensitivity_matrix(matrix_path)
    candidate_tree_sha256 = _candidate_tree_sha256(candidate_root)
    if (
        matrix["source_commit"] != FROZEN_CANDIDATE_COMMIT
        or candidate_tree_sha256 != FROZEN_CANDIDATE_TREE_SHA256
    ):
        raise SensitivityRunError("cost-sensitivity candidate identity changed")
    if output_root.exists():
        raise SensitivityRunError(f"cost-sensitivity output exists: {output_root}")
    staging = output_root.with_name(f".{output_root.name}.staging")
    if staging.exists():
        raise SensitivityRunError(f"cost-sensitivity staging exists: {staging}")
    staging.mkdir(parents=True)
    matrix_copy = staging / "cost-sensitivity-matrix.json"
    matrix_copy.write_bytes(matrix_path.read_bytes())
    matrix_sha256 = _sha256(matrix_copy)

    tasks = []
    ordered = []
    for group in matrix["groups"]:
        group_index = int(group["group_index"])
        group_root = staging / f"group-{group_index:02d}"
        group_root.mkdir()
        for request_value in group["requests"]:
            run_id = str(request_value["run_id"])
            request_path = group_root / f"{run_id}.request.json"
            _canonical_json(request_path, request_value)
            run_root = group_root / run_id
            tasks.append(
                (candidate_root, request_path, run_root, timeout_seconds)
            )
            ordered.append((request_value, request_path, run_root))

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=simulation_workers
    ) as executor:
        evidence = list(executor.map(_run_one, tasks))
    if _candidate_tree_sha256(candidate_root) != candidate_tree_sha256:
        raise SensitivityRunError("cost-sensitivity candidate source mutated")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=validation_workers
    ) as executor:
        validation = list(executor.map(_validate_one, [row[2] for row in ordered]))
    if len(evidence) != 192 or len(validation) != 192:
        raise SensitivityRunError("cost sensitivity did not return all 192 cells")

    group_summaries = []
    for group in matrix["groups"]:
        group_index = int(group["group_index"])
        start = group_index * 4
        stop = start + 4
        group_evidence = evidence[start:stop]
        group_validation = validation[start:stop]
        expected_ids = [request["run_id"] for request in group["requests"]]
        if [row["run_id"] for row in group_evidence] != expected_ids or [
            row["run_id"] for row in group_validation
        ] != expected_ids:
            raise SensitivityRunError("cost-sensitivity result order changed")
        if len({row["shot_id_sha256"] for row in group_validation}) != 1:
            raise SensitivityRunError("cost-sensitivity paired shot IDs differ")
        manifest = {
            "schema_version": GROUP_SCHEMA,
            "slurm_job_id": slurm_job_id,
            "matrix_sha256": matrix_sha256,
            "group_index": group_index,
            "physical_key": group["physical_key"],
            "reload_configuration_id": group["reload_configuration_id"],
            "reload": group["reload"],
            "baseline_reference": group["baseline_reference"],
            "runs": group_evidence,
            "validation": group_validation,
        }
        path = staging / f"group-{group_index:02d}/group-manifest.json"
        _canonical_json(path, manifest)
        group_summaries.append(
            {
                "group_index": group_index,
                "group_manifest": str(path.relative_to(staging)),
                "group_manifest_sha256": _sha256(path),
                "logical_failures": [
                    int(row["logical_failures"]) for row in group_validation
                ],
            }
        )

    summary_path = staging / "run-summary.json"
    summary = {
        "schema_version": RUN_SCHEMA,
        "status": "initial-cost-sensitivity-complete",
        "slurm_job_id": slurm_job_id,
        "matrix": matrix_copy.name,
        "matrix_sha256": matrix_sha256,
        "candidate_root": str(candidate_root),
        "candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "candidate_tree_sha256": candidate_tree_sha256,
        "simulation_workers": simulation_workers,
        "validation_workers": validation_workers,
        "per_cell_timeout_seconds": timeout_seconds,
        "groups": group_summaries,
        "group_count": 48,
        "cell_count": 192,
        "total_shots": 3_840_000,
        "validation": "exact-replay-passed-for-every-run",
        "claims_authorized": False,
        "note": "Initial cost sensitivity requires preregistered stopping analysis.",
    }
    _canonical_json(summary_path, summary)
    root_paths = [
        matrix_copy,
        summary_path,
        *[
            staging / str(group["group_manifest"])
            for group in group_summaries
        ],
    ]
    (staging / "result-checksums.sha256").write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(staging).as_posix()}\n"
            for path in sorted(root_paths)
        ),
        encoding="ascii",
    )
    staging.rename(output_root)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--simulation-workers", type=int, required=True)
    parser.add_argument("--validation-workers", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=10_800)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_initial_sensitivity(
        matrix_path=args.matrix,
        candidate_root=args.candidate_root,
        output_root=args.output_root,
        simulation_workers=args.simulation_workers,
        validation_workers=args.validation_workers,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
