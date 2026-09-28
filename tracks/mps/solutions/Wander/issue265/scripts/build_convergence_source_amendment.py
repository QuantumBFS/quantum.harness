#!/usr/bin/env python3
"""Build the immutable source-equivalence amendment for convergence slices."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.convergence_source_gate import (  # noqa: E402
    EXPECTED_JOB_COUNT,
    SourceGateError,
    canonical_sha256,
    sha256_file,
    submission_identity,
)


REMOTE_ROOT = Path(
    "/work/share/giggleliu/cfys01/kharkov_burgers_20260729"
)
REMOTE_SUBMISSION = REMOTE_ROOT / "jobs" / "convergence_submission.json"
REMOTE_MANIFEST = (
    REMOTE_ROOT
    / "source"
    / "results_research_program"
    / "manifest.json"
)


def _load_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGateError(
            f"source_gate: cannot parse {label}: {error}"
        ) from error
    if not isinstance(value, Mapping):
        raise SourceGateError(
            f"source_gate: {label} is not an object"
        )
    return value


def _job_ids(values: Any, label: str) -> set[str]:
    if not isinstance(values, list):
        raise SourceGateError(
            f"source_gate: {label} jobs are not a list"
        )
    result = {str(value.get("job_id")) for value in values if isinstance(value, Mapping)}
    if len(result) != len(values):
        raise SourceGateError(
            f"source_gate: {label} has duplicate or malformed job IDs"
        )
    return result


def _relative_artifact(path: Path, output_path: Path) -> str:
    try:
        return str(path.resolve().relative_to(output_path.resolve().parent))
    except ValueError as error:
        raise SourceGateError(
            "source_gate: recovered sources must be inside the evidence directory"
        ) from error


def build_amendment(
    *,
    submission_path: Path,
    manifest_path: Path,
    original_runner_path: Path,
    original_backend_path: Path,
    current_runner_path: Path,
    current_backend_path: Path,
    all_job_report_path: Path,
    resume_report_path: Path,
    output_path: Path,
    submission_reference: str = str(REMOTE_SUBMISSION),
    manifest_reference: str = str(REMOTE_MANIFEST),
    created_at: str | None = None,
) -> dict[str, Any]:
    """Validate raw reports and return a frozen amendment."""

    record = _load_json(submission_path, "submission record")
    manifest = _load_json(manifest_path, "manifest")
    all_jobs = _load_json(all_job_report_path, "all-job report")
    resume = _load_json(resume_report_path, "cross-version resume report")

    if record.get("submission_complete") is not True:
        raise SourceGateError(
            "source_gate: submission record is incomplete"
        )
    submitted_ids = _job_ids(record.get("jobs"), "submission")
    if len(submitted_ids) != EXPECTED_JOB_COUNT:
        raise SourceGateError(
            "source_gate: expected exactly 12 submitted jobs"
        )
    manifest_convergence = [
        job
        for job in manifest.get("jobs", [])
        if isinstance(job, Mapping) and job.get("stage") == "convergence"
    ]
    manifest_ids = _job_ids(
        manifest_convergence,
        "manifest convergence",
    )
    if manifest_ids != submitted_ids:
        raise SourceGateError(
            "source_gate: submission/manifest convergence job set mismatch"
        )
    for job in manifest_convergence:
        condition = job.get("condition")
        if not isinstance(condition, Mapping):
            raise SourceGateError(
                "source_gate: manifest convergence condition is malformed"
            )
        try:
            j2 = float(condition.get("j2", 0.0))
        except (TypeError, ValueError) as error:
            raise SourceGateError(
                "source_gate: convergence J2 is invalid"
            ) from error
        if abs(j2) > 1e-15:
            raise SourceGateError(
                "source_gate: convergence job has nonzero J2"
            )

    manifest_sha256 = sha256_file(manifest_path)
    if record.get("manifest_sha256") != manifest_sha256:
        raise SourceGateError(
            "source_gate: authoritative manifest hash mismatch"
        )
    original_runner_sha256 = sha256_file(original_runner_path)
    original_backend_sha256 = sha256_file(original_backend_path)
    current_runner_sha256 = sha256_file(current_runner_path)
    current_backend_sha256 = sha256_file(current_backend_path)
    if record.get("runner_sha256") != original_runner_sha256:
        raise SourceGateError(
            "source_gate: recovered runner does not match first slice"
        )

    if all_jobs.get("status") != "pass":
        raise SourceGateError(
            "source_gate: all-job report status is not pass"
        )
    compared_ids = _job_ids(
        all_jobs.get("jobs"),
        "all-job report",
    )
    if compared_ids != submitted_ids:
        raise SourceGateError(
            "source_gate: all-job report does not cover exactly 12 jobs"
        )
    for raw_item in all_jobs["jobs"]:
        item = dict(raw_item)
        if (
            item.get("status") != "pass"
            or item.get("numerics_exact") is not True
            or item.get("time_grid_exact") is not True
            or item.get("time_grid_points") != 1001
            or item.get("canonical_job_sha256_exact") is not True
        ):
            raise SourceGateError(
                "source_gate: all-job report contains a failed comparison"
            )
    expected_source_hashes = {
        "original_runner_sha256": original_runner_sha256,
        "original_backend_sha256": original_backend_sha256,
        "current_runner_sha256": current_runner_sha256,
        "current_backend_sha256": current_backend_sha256,
    }
    for key, expected in expected_source_hashes.items():
        if all_jobs.get(key) != expected:
            raise SourceGateError(
                f"source_gate: all-job report {key} mismatch"
            )

    threshold = float(resume.get("threshold", 1e-13))
    maximum = float(resume.get("maximum_array_difference", float("inf")))
    if resume.get("status") != "pass":
        raise SourceGateError(
            "source_gate: cross-version resume report status is not pass"
        )
    if resume.get("interrupted_process_exit_code") != 143:
        raise SourceGateError(
            "source_gate: cross-version interruption was not exit 143"
        )
    if threshold <= 0.0 or maximum < 0.0 or not maximum < threshold:
        raise SourceGateError(
            "source_gate: cross-version resume exceeds threshold"
        )
    for key, expected in expected_source_hashes.items():
        if resume.get(key) != expected:
            raise SourceGateError(
                f"source_gate: cross-version report {key} mismatch"
            )

    normalized_jobs = sorted(
        (dict(item) for item in all_jobs["jobs"]),
        key=lambda item: str(item["job_id"]),
    )
    amendment = {
        "schema_version": 1,
        "created_at": created_at
        or datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "submission": {
            "path": submission_reference,
            "identity_sha256": canonical_sha256(
                submission_identity(record)
            ),
        },
        "manifest": {
            "path": manifest_reference,
            "sha256": manifest_sha256,
        },
        "original_source": {
            "runner_sha256": original_runner_sha256,
            "backend_sha256": original_backend_sha256,
        },
        "recovered_artifacts": [
            {
                "role": "first_slice_runner",
                "path": _relative_artifact(
                    original_runner_path,
                    output_path,
                ),
                "sha256": original_runner_sha256,
            },
            {
                "role": "first_slice_backend",
                "path": _relative_artifact(
                    original_backend_path,
                    output_path,
                ),
                "sha256": original_backend_sha256,
            },
        ],
        "allowed_source_pairs": [
            {
                "pair_id": "first_slice",
                "runner_sha256": original_runner_sha256,
                "backend_sha256": original_backend_sha256,
            },
            {
                "pair_id": "j2_extended_j2zero_validated",
                "runner_sha256": current_runner_sha256,
                "backend_sha256": current_backend_sha256,
            },
        ],
        "environment": dict(resume.get("environment", {})),
        "all_job_equivalence": {
            "status": "pass",
            "expected_job_count": EXPECTED_JOB_COUNT,
            "jobs": normalized_jobs,
            "raw_report_sha256": sha256_file(all_job_report_path),
        },
        "cross_version_resume": {
            **dict(resume),
            "threshold": threshold,
            "maximum_array_difference": maximum,
            "raw_report_sha256": sha256_file(resume_report_path),
        },
    }
    return amendment


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--original-runner", type=Path, required=True)
    parser.add_argument("--original-backend", type=Path, required=True)
    parser.add_argument("--current-runner", type=Path, required=True)
    parser.add_argument("--current-backend", type=Path, required=True)
    parser.add_argument("--all-job-report", type=Path, required=True)
    parser.add_argument("--resume-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--submission-reference",
        default=str(REMOTE_SUBMISSION),
    )
    parser.add_argument(
        "--manifest-reference",
        default=str(REMOTE_MANIFEST),
    )
    args = parser.parse_args()
    amendment = build_amendment(
        submission_path=args.submission,
        manifest_path=args.manifest,
        original_runner_path=args.original_runner,
        original_backend_path=args.original_backend,
        current_runner_path=args.current_runner,
        current_backend_path=args.current_backend,
        all_job_report_path=args.all_job_report,
        resume_report_path=args.resume_report,
        output_path=args.output,
        submission_reference=args.submission_reference,
        manifest_reference=args.manifest_reference,
    )
    _atomic_write(args.output, amendment)
    print(
        json.dumps(
            {
                "status": amendment["status"],
                "output": str(args.output),
                "submission_identity_sha256": amendment["submission"][
                    "identity_sha256"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SourceGateError as error:
        raise SystemExit(str(error)) from None
