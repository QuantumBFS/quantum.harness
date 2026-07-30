from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lrtfim.fit_protocol import regenerate_sigma_fits
from scripts.run_phase6_cell import _normalize_fit_summary


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase2_fit_summary_is_accepted_as_locked_primary() -> None:
    summary = _normalize_fit_summary(
        {
            "K": 24,
            "p": 2.75,
            "r_fit": 2048,
            "min_rate_scale": 0.5,
            "lambdas": [0.9],
            "coefficients": [1.0],
            "infinite_kernel": {
                "max_relative_error": 1e-5,
                "rms_relative_error": 1e-6,
            },
        }
    )
    assert summary["sigma"] == 1.75
    assert summary["primary"] == {
        "num_exponentials": 24,
        "alpha": 0.5,
        "r_fit": 2048,
    }
    assert summary["fits"][0]["kernel_max_relative_error"] == 1e-5


def test_small_cell_preserves_raw_observables_and_resumes(tmp_path: Path) -> None:
    fit_path = tmp_path / "fit-summary.json"
    fit_path.write_text(
        json.dumps(
            regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4),
            indent=2,
        )
        + "\n"
    )
    output = tmp_path / "cell"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_phase6_cell.py"),
        "--fit-summary",
        str(fit_path),
        "--length",
        "4",
        "--gamma",
        "1.56",
        "--chi",
        "16",
        "--max-sweeps",
        "12",
        "--output-dir",
        str(output),
    ]
    first = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert first.returncode == 0, first.stderr
    manifest_path = output / "manifest.json"
    before = manifest_path.read_text()
    manifest = json.loads(before)
    assert manifest["status"] == "success"
    raw = manifest["raw_observables"]
    assert len(raw["correlations"]) == 4
    assert raw["s_zero"] > 0.0
    assert raw["s_k_min"] > 0.0
    assert raw["xi"] > 0.0
    assert raw["r_xi"] == raw["xi"] / 4
    assert (output / "correlations.csv").is_file()

    second = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert second.returncode == 0, second.stderr
    assert "reusing successful cell" in second.stdout
    assert manifest_path.read_text() == before
