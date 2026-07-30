#!/usr/bin/env python3
"""Check the frozen source amendment before a convergence slice runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.convergence_source_gate import (  # noqa: E402
    SourceGateError,
    validate_source_gate,
)


REMOTE_ROOT = Path(
    "/work/share/giggleliu/cfys01/kharkov_burgers_20260729"
)
REMOTE_SOURCE = REMOTE_ROOT / "source"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument(
        "--submission",
        type=Path,
        default=REMOTE_ROOT / "jobs" / "convergence_submission.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REMOTE_SOURCE / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--amendment",
        type=Path,
        default=(
            REMOTE_SOURCE
            / "results_research_program"
            / "hpc"
            / "convergence_source_20260729"
            / "amendment.json"
        ),
    )
    parser.add_argument(
        "--runner",
        type=Path,
        default=REMOTE_SOURCE / "scripts" / "run_tenpy_research_job.py",
    )
    parser.add_argument(
        "--backend",
        type=Path,
        default=REMOTE_SOURCE / "src" / "tenpy_research_backend.py",
    )
    args = parser.parse_args()
    attestation = validate_source_gate(
        submission_path=args.submission,
        manifest_path=args.manifest,
        amendment_path=args.amendment,
        job_id=args.job_id,
        runner_path=args.runner,
        backend_path=args.backend,
    )
    print(
        json.dumps(
            attestation.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SourceGateError as error:
        raise SystemExit(str(error)) from None
