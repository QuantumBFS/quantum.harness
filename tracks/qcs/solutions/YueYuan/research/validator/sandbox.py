from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from schema import error


def run_candidate_if_needed(candidate_dir: Path, timeout_seconds: float) -> list[dict]:
    submission = candidate_dir / "submission.json"
    if submission.exists():
        return []

    runner = candidate_dir / "run_candidate.py"
    if not runner.exists():
        return [error("missing_submission", "candidate must provide submission.json or run_candidate.py")]

    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        result = subprocess.run(
            [sys.executable, str(runner)],
            cwd=candidate_dir,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return [
            error(
                "candidate_timeout",
                "candidate exceeded validator wall-clock budget",
                timeout_seconds=timeout_seconds,
            )
        ]

    if result.returncode != 0:
        return [
            error(
                "candidate_failed",
                "candidate runner exited nonzero",
                returncode=result.returncode,
                stderr=result.stderr[-1200:],
            )
        ]
    if not submission.exists():
        return [error("missing_submission", "candidate runner did not create submission.json")]
    return []
