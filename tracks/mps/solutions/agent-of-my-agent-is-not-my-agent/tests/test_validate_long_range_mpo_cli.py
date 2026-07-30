from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cli_writes_three_layer_profiles_and_plots(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    environment["MPLCONFIGDIR"] = str(tmp_path / "matplotlib")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "validate_long_range_mpo.py"),
        "--lengths",
        "4",
        "--gammas",
        "1.2",
        "--k",
        "4",
        "--r-fit",
        "32",
        "--alpha",
        "0.5",
        "--chi-max",
        "16",
        "--max-sweeps",
        "12",
        "--output-dir",
        str(tmp_path / "output"),
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
    output = tmp_path / "output"
    summary = json.loads((output / "summary.json").read_text())
    assert len(summary["cells"]) == 1
    assert set(summary["cells"][0]["layers"]) == {
        "exact_pair_ed",
        "compact_mpo_ed",
        "compact_mpo_dmrg",
    }
    assert (output / "summary.csv").is_file()
    assert (output / "cell_L4_Gamma1.2.json").is_file()
    assert (output / "coupling_L4.csv").is_file()
    assert (output / "correlations_L4_Gamma1.2.csv").is_file()
    assert (output / "coupling_error.png").is_file()
    assert (output / "observable_errors.png").is_file()

    resumed = subprocess.run(
        command[:-2]
        + [
            "--gammas",
            "1.2",
            "1.3",
            "--resume",
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert resumed.returncode == 0, resumed.stderr
    resumed_summary = json.loads((output / "summary.json").read_text())
    assert len(resumed_summary["cells"]) == 2
