from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_cli_writes_diagnostics_and_plot(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "benchmark_tfim.py"),
        "--lengths",
        "4",
        "--chi-max",
        "16",
        "--max-sweeps",
        "12",
        "--output-dir",
        str(tmp_path),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["model"]["gamma"] == 1.0
    assert summary["sizes"][0]["length_times_gap"] > 0.0
    assert summary["sizes"][0]["excited_targeting"]["overlap"] < 1.0e-10
    assert (tmp_path / "benchmark.csv").is_file()
    assert (tmp_path / "tfim_critical_gap.png").is_file()
