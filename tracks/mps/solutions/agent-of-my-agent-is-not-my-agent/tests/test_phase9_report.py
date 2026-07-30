from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import csv

import matplotlib.pyplot as plt
import pytest

from lrtfim.phase9_protocol import (
    GAMMA_NN,
    MEAN_FIELD_BENCHMARKS,
    MEAN_FIELD_SIZES,
    NN_SIZES,
)
from scripts.report_phase9_validation import (
    _mean_field_power_panel_data,
    _panel_status_text,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "report_phase9_validation.py"


def test_plot_panel_distinguishes_excluded_mpo_bias_from_unresolved():
    assert _panel_status_text({"status": "excluded_mpo_bias"}) == (
        "excluded: MPO bias"
    )
    assert _panel_status_text({"status": "unresolved"}) == "unresolved"


def test_mean_field_power_panel_uses_effective_size_correction():
    branch = {
        "gap_scaling": {
            "z_eff": {
                "effective_lengths": [22.0, 45.0, 78.0],
                "values": [0.39, 0.37, 0.35],
            },
            "correction_sensitivity": {
                "power": {
                    "estimate": 1.0 / 3.0,
                    "coefficient": 1.25,
                }
            },
        }
    }

    panel = _mean_field_power_panel_data(branch)

    assert panel["effective_lengths"].tolist() == [22.0, 45.0, 78.0]
    assert panel["z_eff"].tolist() == [0.39, 0.37, 0.35]
    assert panel["z_power"] == pytest.approx(1.0 / 3.0)
    assert panel["fit_values"] == pytest.approx(
        panel["z_power"] + 1.25 / panel["fit_lengths"]
    )
    assert panel["fit_lengths"][0] == pytest.approx(22.0)
    assert panel["fit_lengths"][-1] > 78.0


def _write_summary(
    root: Path,
    length: int,
    gamma: float,
    sector: str,
    energy: float,
    *,
    sigma: float | None = None,
    r_xi: float | None = None,
    discarded: float = 1.0e-9,
) -> None:
    directory = root / f"L{length}_G{gamma:g}_{sector}"
    directory.mkdir(parents=True)
    raw = {} if r_xi is None else {"r_xi": r_xi}
    (directory / "summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "settings": {
                    "sigma": sigma,
                    "length": length,
                    "gamma": gamma,
                    "sectors": [sector],
                    "max_sweeps": 30,
                },
                "direct": {
                    sector: {
                        "energy": energy,
                        "variance": 1.0e-12,
                        "discarded_weight": discarded,
                        "reached_chi": 64,
                        "sweeps": 12,
                        "wall_seconds": 1.0,
                    }
                },
                "fit": {
                    "K": 24,
                    "alpha": 0.5,
                    "r_fit": 2048,
                    "fit_hash": "fixture-fit-hash",
                },
                "mpo": {
                    "pruned": True,
                    "active_channels": [0, 1],
                    "chi": 6,
                    "approximate_compression": False,
                },
                "code_hash": "fixture-code-hash",
                "raw_observables": raw,
            }
        )
        + "\n"
    )


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    nn = tmp_path / "nn"
    mean_field = tmp_path / "mean-field"
    for length in NN_SIZES:
        for gamma in GAMMA_NN:
            _write_summary(
                nn,
                length,
                gamma,
                "even",
                -float(length),
                sigma=None,
                r_xi=0.5 + (gamma - 1.0) * length / 16.0,
            )
            _write_summary(
                nn,
                length,
                gamma,
                "odd",
                -float(length) + 1.0 / length,
                sigma=None,
            )
    for benchmark in MEAN_FIELD_BENCHMARKS:
        for length in MEAN_FIELD_SIZES:
            even = -2.0 * length
            _write_summary(
                mean_field,
                length,
                benchmark["Gamma"],
                "even",
                even,
                sigma=benchmark["sigma"],
            )
            _write_summary(
                mean_field,
                length,
                benchmark["Gamma"],
                "odd",
                even + length ** (-benchmark["expected_z"]),
                sigma=benchmark["sigma"],
            )
    return nn, mean_field


def _run(nn: Path, mean_field: Path, output: Path):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--nn-root",
            str(nn),
            "--mean-field-root",
            str(mean_field),
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_report_builds_resolved_z_only_validation_outputs(tmp_path: Path):
    nn, mean_field = _fixtures(tmp_path)
    output = tmp_path / "report"

    completed = _run(nn, mean_field, output)

    assert completed.returncode == 0, completed.stderr
    assert "No artists with labels" not in completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["nearest_neighbor"]["status"] == "complete"
    assert analysis["nearest_neighbor"]["precision_z_claim"] is False
    assert analysis["mean_field"]["sigma_2over3"]["status"] == "complete"
    assert analysis["mean_field"]["sigma_0p4"]["status"] == "excluded_mpo_bias"
    assert analysis["mean_field"]["sigma_0p4"]["dmrg_run"] is False
    assert analysis["mean_field"]["sigma_2over3"]["reported_exponents"] == ["z"]
    provenance = analysis["mean_field"]["sigma_2over3"]["mpo_provenance"]
    assert provenance["fit"] == {
        "K": 24,
        "alpha": 0.5,
        "r_fit": 2048,
        "fit_hash": "fixture-fit-hash",
    }
    assert provenance["mpo"]["pruned"] is True
    assert provenance["mpo"]["approximate_compression"] is False
    correction = analysis["mean_field"]["sigma_2over3"]["gap_scaling"][
        "correction_sensitivity"
    ]
    assert correction["power"]["estimate"] == pytest.approx(1.0 / 3.0)
    assert correction["log"]["estimate"] == pytest.approx(1.0 / 3.0)
    assert correction["length_convention"] == "L_eff=sqrt(L1*L2)"
    assert correction["interpretation"] == (
        "finite_size_sensitivity_estimates_not_statistical_extrapolations"
    )
    assert analysis["mean_field"]["sigma_2over3"]["gap_scaling"][
        "direct"
    ]["exponent"] == pytest.approx(1.0 / 3.0)
    assert analysis["sigma_2_gamma"]["classification"] == (
        "finite_size_crossing_comparison"
    )
    rendered = (output / "report.md").read_text()
    assert "not a precision reproduction" in rendered
    assert "### Nearest-neighbor limit" in rendered
    assert "Gamma_x(16,32)=1.000000" in rendered
    assert "16_32: 1.000000" in rendered
    assert "Simple three-size estimate: z=1.000000" in rendered
    assert "18/18 cells pass the nominal convergence gates" in rendered
    assert "## Track B readiness checklist" in rendered
    assert "external published benchmark" in rendered
    assert "does not independently determine" in rendered
    assert "z=0.333333" in rendered
    assert "z_power=0.333333" in rendered
    assert "z_log=0.333333" in rendered
    assert "not statistically reliable extrapolations" in rendered
    assert "gap-based pairwise effective dynamical exponents" in rendered
    assert "QMC aspect-ratio tuning procedure" in rendered
    assert "qualitative_consistency" not in rendered
    assert "beta/nu" not in rendered
    assert "gamma/nu" in rendered
    assert "not measured" in rendered
    assert (output / "nn-gaps.csv").is_file()
    assert (output / "mean-field-sigma-2over3-gaps.csv").is_file()
    with (output / "mean-field-sigma-2over3-gaps.csv").open() as stream:
        fields = csv.DictReader(stream).fieldnames
    assert fields is not None
    assert {
        "even_reached_chi",
        "odd_reached_chi",
        "even_sweeps",
        "odd_sweeps",
        "even_wall_seconds",
        "odd_wall_seconds",
    }.issubset(fields)
    assert not (output / "mean-field-sigma-0p4-gaps.csv").exists()
    assert (output / "validation-gaps.png").is_file()
    assert (output / "validation-gaps.pdf").is_file()
    image = plt.imread(output / "validation-gaps.png")
    aspect_ratio = image.shape[1] / image.shape[0]
    assert 1.8 < aspect_ratio < 2.8


def test_report_marks_invalid_branch_unresolved_without_refinement(
    tmp_path: Path,
):
    nn, mean_field = _fixtures(tmp_path)
    odd = next(mean_field.glob("L96_G3.673_odd/summary.json"))
    summary = json.loads(odd.read_text())
    summary["direct"]["odd"]["energy"] = -300.0
    odd.write_text(json.dumps(summary))
    output = tmp_path / "report"

    completed = _run(nn, mean_field, output)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["nearest_neighbor"]["status"] == "complete"
    assert analysis["mean_field"]["sigma_2over3"]["status"] == "unresolved"
    assert analysis["mean_field"]["sigma_0p4"]["status"] == "excluded_mpo_bias"
    assert "refinement_command" not in json.dumps(analysis)


def test_report_labels_variance_flags_as_qualitative_consistency(
    tmp_path: Path,
):
    nn, mean_field = _fixtures(tmp_path)
    even = next(mean_field.glob("L64_G3.673_even/summary.json"))
    summary = json.loads(even.read_text())
    summary["direct"]["even"]["variance"] = 1.0e-4
    even.write_text(json.dumps(summary))
    output = tmp_path / "report"

    completed = _run(nn, mean_field, output)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads((output / "analysis.json").read_text())
    branch = analysis["mean_field"]["sigma_2over3"]
    assert branch["status"] == "complete_with_warnings"
    assert branch["assessment"] == (
        "qualitative_consistency_with_convergence_warnings"
    )
    assert "qualitative_consistency_with_convergence_warnings" in (
        output / "report.md"
    ).read_text()


def test_report_records_nn_diagnostic_warning_without_precision_claim(
    tmp_path: Path,
):
    nn, mean_field = _fixtures(tmp_path)
    even = next(nn.glob("L64_G1_even/summary.json"))
    summary = json.loads(even.read_text())
    summary["direct"]["even"]["variance"] = 1.0e-6
    even.write_text(json.dumps(summary))
    output = tmp_path / "report"

    completed = _run(nn, mean_field, output)

    assert completed.returncode == 0, completed.stderr
    rendered = (output / "report.md").read_text()
    assert "17/18 cells pass the nominal convergence gates" in rendered
    assert "L=64, Gamma=1, even: relative_variance" in rendered
    assert "not a high-precision thermodynamic extrapolation" in rendered
