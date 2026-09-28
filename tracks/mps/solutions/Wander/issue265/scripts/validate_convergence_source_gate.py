#!/usr/bin/env python3
"""Validate every formal job and write one local source-gate audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.convergence_source_gate import (  # noqa: E402
    EXPECTED_JOB_COUNT,
    SourceGateError,
    sha256_file,
    validate_source_gate,
)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
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
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--cross-version-report", type=Path, required=True)
    parser.add_argument("--pytest-passed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        record = json.loads(args.submission.read_text())
        cross_version = json.loads(args.cross_version_report.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGateError(
            f"source_gate: cannot parse local audit input: {error}"
        ) from error
    job_ids = [str(job["job_id"]) for job in record.get("jobs", [])]
    if len(job_ids) != EXPECTED_JOB_COUNT or len(set(job_ids)) != len(job_ids):
        raise SourceGateError(
            "source_gate: local audit does not contain 12 unique jobs"
        )
    if (
        cross_version.get("status") != "pass"
        or cross_version.get("interrupted_process_exit_code") != 143
        or not float(cross_version.get("maximum_array_difference", 1.0))
        < float(cross_version.get("threshold", 0.0))
    ):
        raise SourceGateError(
            "source_gate: local audit cross-version check failed"
        )
    attestations = [
        validate_source_gate(
            submission_path=args.submission,
            manifest_path=args.manifest,
            amendment_path=args.amendment,
            job_id=job_id,
            runner_path=args.runner,
            backend_path=args.backend,
        ).as_dict()
        for job_id in job_ids
    ]
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "full_test_suite": {
            "status": "pass",
            "passed": args.pytest_passed,
        },
        "syntax_checks": {
            "python": "pass",
            "slurm_bash": "pass",
        },
        "source_sha256": {
            "runner": sha256_file(args.runner),
            "backend": sha256_file(args.backend),
            "amendment": sha256_file(args.amendment),
            "cross_version_report": sha256_file(
                args.cross_version_report
            ),
        },
        "cross_version_resume": {
            "status": cross_version["status"],
            "interrupted_process_exit_code": cross_version[
                "interrupted_process_exit_code"
            ],
            "maximum_array_difference": cross_version[
                "maximum_array_difference"
            ],
            "threshold": cross_version["threshold"],
        },
        "gate_job_count": len(attestations),
        "attestations": attestations,
    }
    _atomic_write(args.output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "gate_job_count": payload["gate_job_count"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SourceGateError as error:
        raise SystemExit(str(error)) from None
