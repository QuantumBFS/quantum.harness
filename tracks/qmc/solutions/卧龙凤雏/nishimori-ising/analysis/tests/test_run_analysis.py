import json
import csv
import statistics

import pytest

from analysis.run_analysis import analyze_run
from analysis.tests.helpers import create_synthetic_run


def test_analysis_writes_data_gates_and_six_plots(tmp_path):
    run_dir = create_synthetic_run(tmp_path / "run")
    summary = analyze_run(run_dir, bootstrap_samples=128, bootstrap_seed=464)

    assert summary["primary_fit"]["central_charge"] == pytest.approx(
        0.464, abs=1.0e-10
    )
    with (run_dir / "processed" / "central_charge_bootstrap.csv").open() as handle:
        bootstrap_mean = statistics.mean(
            float(row["c_lmin4"]) for row in csv.DictReader(handle)
        )
    assert summary["central_charge"] == pytest.approx(bootstrap_mean, abs=1.0e-15)
    assert summary["central_charge_ci95"][0] < 0.464
    assert summary["central_charge_ci95"][1] > 0.464
    assert len(summary["gates"]["gates"]) == 9
    assert len(list((run_dir / "figures").glob("*.png"))) == 6
    assert (run_dir / "processed" / "free_energy.csv").is_file()
    assert (run_dir / "processed" / "central_charge_bootstrap.csv").is_file()

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["python_version"]
    assert manifest["analysis_elapsed_s"] > 0.0
    assert "figure-free_energy_fit" in manifest["artifact_sha256"]
