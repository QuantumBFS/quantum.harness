from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "report_phase9_sigma18_z.py"


def _write_state(
    root: Path,
    length: int,
    sector: str,
    energy: float,
) -> None:
    directory = root / f"L{length}_{sector}"
    directory.mkdir(parents=True)
    (directory / "summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "settings": {
                    "sigma": 1.8,
                    "length": length,
                    "gamma": 1.5288,
                    "sectors": [sector],
                    "max_sweeps": 30,
                },
                "direct": {
                    sector: {
                        "energy": energy,
                        "variance": 1.0e-12,
                        "discarded_weight": 1.0e-10,
                        "reached_chi": 128,
                        "sweeps": 12,
                        "wall_seconds": 1.0,
                    }
                },
                "fit": {
                    "K": 24,
                    "alpha": 0.5,
                    "r_fit": 2048,
                    "fit_hash": "sigma18-fit",
                },
                "mpo": {
                    "pruned": True,
                    "active_channels": [0, 1],
                    "chi": 6,
                    "approximate_compression": False,
                },
                "code_hash": "test-code",
            }
        )
        + "\n"
    )


def test_sigma18_report_writes_fixed_field_gap_validation(tmp_path: Path):
    root = tmp_path / "cells"
    for length in (16, 32, 64, 96, 128):
        even = -2.0 * length
        _write_state(root, length, "even", even)
        _write_state(root, length, "odd", even + length ** (-0.95))
    output = tmp_path / "report"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    environment["MPLCONFIGDIR"] = str(tmp_path / "matplotlib")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary-root",
            str(root),
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["Gamma"] == pytest.approx(1.5288)
    assert analysis["field_role"] == "external_published_benchmark"
    assert analysis["gap_scaling"]["z_eff"]["values"] == pytest.approx(
        [0.95] * 4
    )
    assert analysis["gap_scaling"]["correction_sensitivity"]["power"][
        "estimate"
    ] == pytest.approx(0.95)
    assert analysis["gap_scaling"]["correction_sensitivity"]["log"][
        "estimate"
    ] == pytest.approx(0.95)
    rendered = (output / "report.md").read_text()
    assert "does not independently determine Gamma_c" in rendered
    assert "validation comparison only" in rendered
    assert "precision reproduction" in rendered
    normalized = " ".join(rendered.split()).lower()
    assert "gap-based pairwise effective dynamical exponents" in normalized
    assert "qmc aspect-ratio tuning procedure" in normalized
    assert (output / "gaps.csv").is_file()
    assert (output / "gap-scaling.png").is_file()
    assert (output / "gap-scaling.pdf").is_file()
