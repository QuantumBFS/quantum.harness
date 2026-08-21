from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_validation_cli_reports_successful_checks() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "validate_couplings.py"),
            "--length",
            "12",
            "--sigma",
            "1.6",
            "--image-cutoff",
            "1000000",
            "--json",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["length"] == 12
    assert result["sigma"] == 1.6
    assert result["positive"] is True
    assert result["symmetry_residual"] < 1e-14
    assert result["max_direct_relative_error"] < 2e-10
