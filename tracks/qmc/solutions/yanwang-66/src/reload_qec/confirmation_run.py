"""Run and exactly validate the frozen initial confirmation matrix."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from .confirmation import load_confirmation_matrix
from .config import SimulationRequest
from .dev_validator import _candidate_tree_sha256, _run_candidate
from .validate_artifacts import validate_run


RUN_SCHEMA = "q66-confirmation-initial-run-v1"
GROUP_SCHEMA = "q66-confirmation-initial-group-v1"
FROZEN_CANDIDATE_COMMIT = "0a73ba334a4b85403634e710f3d768ef8831d16d"
FROZEN_CANDIDATE_TREE_SHA256 = (
    "829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482"
)


class ConfirmationRunError(RuntimeError):
    """Raised when confirmation execution or exact validation is incomplete."""


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


def _run_one(value: tuple[Path, Path, Path, int]) -> dict[str, Any]:
    candidate_root, request_path, run_root, timeout_seconds = value
    request = SimulationRequest.load(request_path)
    result = _run_candidate(
        candidate_root=candidate_root,
        request_path=request_path,
        run_root=run_root,
        timeout_seconds=timeout_seconds,
    )
    stdout = result.pop("stdout")
    stderr = result.pop("stderr")
    stdout_path = request_path.with_suffix(".stdout")
    stderr_path = request_path.with_suffix(".stderr")
    runner_path = request_path.with_suffix(".runner.json")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    if result["timed_out"] or result["return_code"] != 0:
        raise ConfirmationRunError(
            f"confirmation candidate failed for {request.run_id}: "
            f"return_code={result['return_code']}, timed_out={result['timed_out']}"
        )
    cleanup = result["process_cleanup"]
    if cleanup["background_processes_detected"] or not cleanup[
        "process_group_cleared"
    ]:
        raise ConfirmationRunError(
            f"confirmation candidate left a process for {request.run_id}"
        )
    evidence = {
        **result,
        "run_id": request.run_id,
        "request_sha256": _sha256(request_path),
        "stdout_sha256": _sha256(stdout_path),
        "stderr_sha256": _sha256(stderr_path),
    }
    _canonical_json(runner_path, evidence)
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="ascii"))
    if (
        manifest.get("status") != "completed"
        or manifest.get("run_id") != request.run_id
        or manifest.get("request") != request.as_dict()
    ):
        raise ConfirmationRunError(
            f"confirmation manifest identity mismatch for {request.run_id}"
        )
    return {
        "run_id": request.run_id,
        "request": request_path.name,
        "request_sha256": evidence["request_sha256"],
        "runner": runner_path.name,
        "runner_sha256": _sha256(runner_path),
        "run_checksums_sha256": _sha256(run_root / "checksums.sha256"),
    }


def _validate_one(run_root: Path) -> dict[str, Any]:
    run = validate_run(run_root)
    logical_failure = np.ascontiguousarray(run.labels["logical_failure"])
    shot_id = np.ascontiguousarray(run.labels["shot_id"])
    aggregate = run.manifest["aggregate"]
    return {
        "run_id": run.request.run_id,
        "shots": run.request.shots,
        "shot_start": run.request.shot_start,
        "shot_id_sha256": hashlib.sha256(shot_id.tobytes()).hexdigest(),
        "logical_failure_sha256": hashlib.sha256(
            logical_failure.tobytes()
        ).hexdigest(),
        "logical_failures": int(aggregate["logical_failures"]),
        "catastrophic_shots": int(aggregate["catastrophic_shots"]),
        "reload_requests": int(aggregate["reload_requests"]),
        "reload_successes": int(aggregate["reload_successes"]),
        "missing_site_boundaries": int(aggregate["missing_site_boundaries"]),
        "validation": "exact-replay-passed",
    }


def _worker_count(value: int, allocated: int, name: str) -> int:
    if value < 1 or value > allocated:
        raise ConfirmationRunError(
            f"{name} workers must be inside [1,{allocated}], got {value}"
        )
    return value


def run_initial_confirmation(
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
        raise ConfirmationRunError("confirmation must execute inside Slurm")
    if os.environ.get("SLURM_ARRAY_TASK_ID") is not None:
        raise ConfirmationRunError("initial confirmation must be one consolidated job")
    if output_root.name != slurm_job_id:
        raise ConfirmationRunError("confirmation output root differs from Slurm job ID")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if allocated < 1:
        raise ConfirmationRunError("Slurm CPU allocation is missing")
    simulation_workers = _worker_count(
        simulation_workers, allocated, "simulation"
    )
    validation_workers = _worker_count(
        validation_workers, allocated, "validation"
    )
    if timeout_seconds < 1 or timeout_seconds > 10_800:
        raise ConfirmationRunError("per-cell timeout must be inside [1,10800]")

    matrix_path = matrix_path.resolve(strict=True)
    candidate_root = candidate_root.resolve(strict=True)
    matrix = load_confirmation_matrix(matrix_path)
    if matrix["source_commit"] != FROZEN_CANDIDATE_COMMIT:
        raise ConfirmationRunError("confirmation matrix changed candidate commit")
    candidate_tree_sha256 = _candidate_tree_sha256(candidate_root)
    if candidate_tree_sha256 != FROZEN_CANDIDATE_TREE_SHA256:
        raise ConfirmationRunError("confirmation candidate tree hash mismatch")
    if output_root.exists():
        raise ConfirmationRunError(f"confirmation output already exists: {output_root}")
    staging = output_root.with_name(f".{output_root.name}.staging")
    if staging.exists():
        raise ConfirmationRunError(f"confirmation staging already exists: {staging}")
    staging.mkdir(parents=True)
    matrix_copy = staging / "confirmation-matrix.json"
    shutil.copyfile(matrix_path, matrix_copy)
    matrix_sha256 = _sha256(matrix_copy)

    tasks: list[tuple[Path, Path, Path, int]] = []
    ordered_runs: list[tuple[int, dict[str, Any], Path, Path]] = []
    for group in matrix["groups"]:
        group_index = int(group["group_index"])
        group_root = staging / f"group-{group_index:02d}"
        group_root.mkdir()
        for request_value in group["requests"]:
            request = SimulationRequest.from_dict(request_value)
            request_path = group_root / f"{request.run_id}.request.json"
            _canonical_json(request_path, request.as_dict())
            run_root = group_root / request.run_id
            tasks.append(
                (candidate_root, request_path, run_root, timeout_seconds)
            )
            ordered_runs.append((group_index, request_value, request_path, run_root))

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=simulation_workers
    ) as executor:
        run_evidence = list(executor.map(_run_one, tasks))
    if _candidate_tree_sha256(candidate_root) != candidate_tree_sha256:
        raise ConfirmationRunError("confirmation candidate source tree mutated")

    run_roots = [value[3] for value in ordered_runs]
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=validation_workers
    ) as executor:
        validation_rows = list(executor.map(_validate_one, run_roots))
    if len(run_evidence) != 40 or len(validation_rows) != 40:
        raise ConfirmationRunError("confirmation did not return all 40 cells")

    groups = []
    for group in matrix["groups"]:
        group_index = int(group["group_index"])
        start = group_index * 5
        stop = start + 5
        evidence = run_evidence[start:stop]
        validation = validation_rows[start:stop]
        expected_ids = [request["run_id"] for request in group["requests"]]
        if [row["run_id"] for row in evidence] != expected_ids or [
            row["run_id"] for row in validation
        ] != expected_ids:
            raise ConfirmationRunError("confirmation result order changed")
        if len({row["shot_id_sha256"] for row in validation}) != 1:
            raise ConfirmationRunError("confirmation paired shot IDs differ")
        group_manifest = {
            "schema_version": GROUP_SCHEMA,
            "slurm_job_id": slurm_job_id,
            "matrix_sha256": matrix_sha256,
            "group_index": group_index,
            "physical_key": group["physical_key"],
            "runs": evidence,
            "validation": validation,
        }
        group_path = staging / f"group-{group_index:02d}/group-manifest.json"
        _canonical_json(group_path, group_manifest)
        groups.append(
            {
                "group_index": group_index,
                "group_manifest": str(group_path.relative_to(staging)),
                "group_manifest_sha256": _sha256(group_path),
                "logical_failures": [
                    int(row["logical_failures"]) for row in validation
                ],
            }
        )

    summary_path = staging / "run-summary.json"
    summary = {
        "schema_version": RUN_SCHEMA,
        "status": "initial-confirmation-complete",
        "slurm_job_id": slurm_job_id,
        "matrix": matrix_copy.name,
        "matrix_sha256": matrix_sha256,
        "candidate_root": str(candidate_root),
        "candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "candidate_tree_sha256": candidate_tree_sha256,
        "simulation_workers": simulation_workers,
        "validation_workers": validation_workers,
        "per_cell_timeout_seconds": timeout_seconds,
        "groups": groups,
        "group_count": 8,
        "cell_count": 40,
        "total_shots": 800_000,
        "validation": "exact-replay-passed-for-every-run",
        "claims_authorized": False,
        "note": "Initial confirmation requires preregistered stopping analysis.",
        "artifacts": [
            matrix_copy.name,
            summary_path.name,
            "result-checksums.sha256",
        ],
    }
    _canonical_json(summary_path, summary)
    root_paths = [
        matrix_copy,
        summary_path,
        *[
            staging / str(group["group_manifest"])
            for group in groups
        ],
    ]
    checksum_text = "".join(
        f"{_sha256(path)}  {path.relative_to(staging).as_posix()}\n"
        for path in sorted(root_paths)
    )
    (staging / "result-checksums.sha256").write_text(
        checksum_text, encoding="ascii"
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
    parser.add_argument("--timeout-seconds", type=int, default=7_200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_initial_confirmation(
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
