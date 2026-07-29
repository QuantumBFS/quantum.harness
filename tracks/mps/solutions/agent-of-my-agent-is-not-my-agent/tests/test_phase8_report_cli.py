import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "report_phase8_scaling.py"


def _write_state(
    root: Path,
    *,
    length: int,
    sector: str,
    gamma: float,
    energy: float,
    discarded_weight: float = 1.0e-10,
) -> None:
    path = root / f"L{length}-{sector}"
    path.mkdir(parents=True)
    raw = {}
    if sector == "even":
        raw = {
            "r_xi": 0.34,
            "xi": 0.34 * length,
            "s_zero": 2.0 * length**0.7,
            "s_k_min": 1.5 * length**0.7,
            "correlations": [1.0, 0.4, 0.3],
        }
    (path / "summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "settings": {
                    "sigma": 1.75,
                    "length": length,
                    "gamma": gamma,
                    "num_exponentials": 24,
                    "alpha": 0.5,
                    "r_fit": 2048,
                    "chi_schedule": [128],
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
                        "requested_chi": 128,
                        "reached_chi": 120,
                        "sweeps": 12,
                        "wall_seconds": 5.0,
                    }
                },
                "raw_observables": raw,
            }
        )
    )


def _run_report(
    decision: Path,
    gap_root: Path,
    uncertainty: Path,
    output: Path,
) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    environment["MPLCONFIGDIR"] = str(output.parent / "mpl")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--decision",
            str(decision),
            "--gap-root",
            str(gap_root),
            "--phase6-uncertainty",
            str(uncertainty),
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_report_separates_effective_z_sensitivities_and_uncertainties(
    tmp_path: Path,
):
    gamma = 1.5609
    decision = tmp_path / "crossing-decision.json"
    decision.write_text(
        json.dumps(
            {
                "status": "resolved",
                "sigma": 1.75,
                "Gamma_endpoints": [1.55, 1.60],
                "differences": [-0.02, 0.03],
                "crossing_resolution": 0.025,
                "Gamma_x_32_64": 1.5679,
                "Gamma_x_64_128": 1.5620,
                "common_field": {
                    "primary": "power",
                    "gap_field": gamma,
                    "power": {
                        "estimate": gamma,
                        "interpretation": "two_point_sensitivity_extrapolation",
                    },
                    "log": {
                        "estimate": 1.552,
                        "interpretation": "two_point_sensitivity_extrapolation",
                    },
                    "spread": 0.0089,
                    "propagated_to_gap_uncertainty": False,
                },
            }
        )
    )
    gap_root = tmp_path / "gaps"
    for length, gap in (
        (16, 0.34),
        (32, 0.20),
        (64, 0.12),
        (96, 0.082),
        (128, 0.065),
    ):
        even_energy = -2.0 * length
        _write_state(
            gap_root,
            length=length,
            sector="even",
            gamma=gamma,
            energy=even_energy,
        )
        _write_state(
            gap_root,
            length=length,
            sector="odd",
            gamma=gamma,
            energy=even_energy + gap,
            discarded_weight=5.49e-8 if length == 64 else 1.0e-10,
        )
    uncertainty = tmp_path / "phase6-analysis.json"
    uncertainty.write_text(
        json.dumps(
            {
                "mpo": {
                    "comparisons": [
                        {
                            "gap": {"absolute": 4.0e-7},
                            "r_xi": {"absolute": -1.0e-6},
                        }
                    ]
                },
                "mps": {
                    "comparisons": [
                        {
                            "gap": {"absolute": 3.0e-9},
                            "r_xi": {"absolute": 5.0e-8},
                            "energy": {
                                "even": {"absolute": -1.5e-8},
                                "odd": {"absolute": -1.2e-8},
                            },
                        }
                    ]
                },
            }
        )
    )
    output = tmp_path / "report"

    completed = _run_report(decision, gap_root, uncertainty, output)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["z"]["z_eff"]["pairs"] == [
        "16_32",
        "32_64",
        "64_96",
        "96_128",
    ]
    assert (
        analysis["z"]["regression"]["power"]["residual_degrees_of_freedom"]
        == 2
    )
    assert (
        analysis["z"]["regression"]["leave_L16_out"]["power"][
            "residual_degrees_of_freedom"
        ]
        == 1
    )
    assert (
        analysis["z"]["regression"]["interpretation"]
        == "deterministic_finite_size_sensitivity_regression"
    )
    assert (
        analysis["z"]["regression"]["shared_gap_correlations_ignored"] is True
    )
    assert (
        analysis["critical_field"]["propagated_to_gap_uncertainty"] is False
    )
    assert analysis["susceptibility_gamma_over_nu"] == "not_measured"
    assert analysis["equal_time_structure_factor"]["role"] == (
        "auxiliary_diagnostic"
    )
    assert set(analysis["uncertainty"]) == {
        "MPO",
        "MPS",
        "finite_size",
        "critical_field_propagation",
        "phase8_acceptance_protocol",
    }
    protocol = analysis["uncertainty"]["phase8_acceptance_protocol"]
    assert protocol["relative_variance_limit"] == 1.0e-10
    assert protocol["discarded_weight_limit"] == 1.0e-7
    assert protocol["changed_after_L64_odd_observation"] is True
    assert analysis["published_comparison"]["z_power"] == 0.91
    assert analysis["published_comparison"]["z_log"] == 0.98
    for name in (
        "crossings.csv",
        "critical-field-sensitivity.csv",
        "gap-diagnostics.csv",
        "z-sensitivity.csv",
        "equal-time-diagnostics.csv",
        "uncertainty-budget.csv",
        "analysis.json",
        "phase8-sigma175.png",
        "phase8-sigma175.pdf",
        "report.md",
    ):
        assert (output / name).stat().st_size > 0
