import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "report_phase8_field_sensitivity.py"


def _write_state(
    root: Path,
    *,
    length: int,
    sector: str,
    energy: float,
    chi: int = 128,
    discarded_weight: float = 1.0e-10,
) -> None:
    path = root / f"L{length}-{sector}-chi{chi}"
    path.mkdir(parents=True)
    (path / "summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "settings": {
                    "sigma": 1.75,
                    "length": length,
                    "gamma": 1.5609,
                    "num_exponentials": 24,
                    "alpha": 0.5,
                    "r_fit": 2048,
                    "chi_schedule": [chi],
                    "max_sweeps": 30,
                    "sectors": [sector],
                    "direct_only": True,
                },
                "mpo": {
                    "pruned": True,
                    "approximate_compression": False,
                },
                "direct": {
                    sector: {
                        "energy": energy,
                        "variance": 1.0e-10,
                        "discarded_weight": discarded_weight,
                        "requested_chi": chi,
                        "reached_chi": chi,
                        "sweeps": 12,
                        "wall_seconds": 4.0,
                    }
                },
                "code_hash": "synthetic-code",
                "fit": {"fit_hash": "synthetic-fit"},
            }
        )
    )


def test_report_compares_external_and_self_consistent_fields(tmp_path: Path):
    lengths = [16, 32, 64, 96, 128]
    previous_gaps = [0.30, 0.18, 0.11, 0.085, 0.072]
    st_gaps = [2.4 * length ** (-0.92) for length in lengths]
    previous = tmp_path / "power-analysis.json"
    previous.write_text(
        json.dumps(
            {
                "sigma": 1.75,
                "critical_field": {"gap_field": 1.5738504887054727},
                "gaps": {
                    str(length): gap
                    for length, gap in zip(lengths, previous_gaps)
                },
                "z": {
                    "regression": {
                        "power": {"estimate": 0.58},
                        "log": {"estimate": 0.22},
                    }
                },
                "published_comparison": {
                    "z_power": 0.91,
                    "z_log": 0.98,
                    "url": "https://arxiv.org/abs/2305.14121",
                },
            }
        )
    )
    root = tmp_path / "st"
    for length, gap in zip(lengths, st_gaps):
        even = -2.0 * length
        _write_state(root, length=length, sector="even", energy=even)
        _write_state(
            root,
            length=length,
            sector="odd",
            energy=even + gap + (1.0e-6 if length == 96 else 0.0),
            discarded_weight=2.0e-7 if length == 96 else 1.0e-10,
        )
        if length == 96:
            _write_state(
                root,
                length=length,
                sector="odd",
                energy=even + gap,
                chi=256,
            )
    output = tmp_path / "report"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    environment["MPLCONFIGDIR"] = str(tmp_path / "mpl")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--st-root",
            str(root),
            "--power-analysis",
            str(previous),
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
    assert analysis["branches"]["self_consistent_crossing_field"]["Gamma"] == (
        1.5738504887054727
    )
    external = analysis["branches"]["external_published_field"]
    assert external["Gamma"] == 1.5609
    assert external["direct_gap_power_law"]["exponent"] == pytest.approx(0.92)
    assert external["selected_chi"]["96"]["odd"] == 256
    assert external["chi128_baselines"]["96"]["odd"]["accepted"] is False
    assert len(analysis["z_eff_comparison"]) == 4
    assert analysis["interpretation"]["field_selected_by_outcome"] is False
    for name in (
        "gaps-comparison.csv",
        "z-eff-comparison.csv",
        "fit-comparison.csv",
        "refinement-diagnostics.csv",
        "analysis.json",
        "phase8-field-sensitivity.png",
        "phase8-field-sensitivity.pdf",
        "report.md",
    ):
        assert (output / name).stat().st_size > 0
