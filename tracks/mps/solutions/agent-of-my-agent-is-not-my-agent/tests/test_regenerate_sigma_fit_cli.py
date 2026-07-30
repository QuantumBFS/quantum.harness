from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_regeneration_cli_writes_auditable_reduced_fixture(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "regenerate_sigma_fit.py"),
        "--sigma",
        "1.75",
        "--lengths",
        "4",
        "8",
        "--l-max",
        "8",
        "--output-dir",
        str(tmp_path),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((tmp_path / "fit-summary.json").read_text())
    assert summary["primary"]["r_fit"] == 64
    assert len(summary["fits"]) == 7
    assert (tmp_path / "couplings_K24_alpha0.5_rfit64_L8.csv").is_file()


def test_regeneration_cli_supports_primary_only_exploration_fit(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "regenerate_sigma_fit.py"),
            "--sigma",
            "1.75",
            "--lengths",
            "4",
            "--l-max",
            "4",
            "--primary-only",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((tmp_path / "fit-summary.json").read_text())
    assert len(summary["fits"]) == 1
    assert summary["fits"][0]["num_exponentials"] == 24
