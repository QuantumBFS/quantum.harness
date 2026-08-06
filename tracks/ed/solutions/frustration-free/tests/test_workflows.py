from __future__ import annotations

import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from src.io_utils import (
    deterministic_grid_filename,
    load_yaml,
    save_chern_grid,
    save_scan_summary,
)
from src.model import ModelParameters
from src.workflows import (
    BenchmarkConfig,
    ScanConfig,
    run_benchmark,
    scan_u,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/tmp/challenge36-quspin-venv/bin/python")


def test_yaml_loader_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text("model:\n  L: 4\n  L: 6\n")

    with pytest.raises(ValueError, match="duplicate YAML key"):
        load_yaml(path)


def test_deterministic_grid_filename_encodes_all_physical_parameters():
    first = deterministic_grid_filename(
        ModelParameters(L=4, U=0.0),
        n_theta=5,
        n_phi=5,
    )
    second = deterministic_grid_filename(
        ModelParameters(L=4, U=0.0, Delta0=2.5),
        n_theta=5,
        n_phi=5,
    )
    nearby_u = deterministic_grid_filename(
        ModelParameters(L=4, U=4e-7),
        n_theta=5,
        n_phi=5,
    )

    assert first.endswith(".npz")
    assert "L4" in first
    assert "U_p0d000000" in first
    assert "Ntheta5_Nphi5" in first
    assert first != second
    assert first != nearby_u


def test_scan_u_reuses_nested_vertices_and_persists_reusable_states(tmp_path):
    config = ScanConfig(
        model=ModelParameters(L=4),
        grid_sizes=(5, 10),
    )

    records = scan_u([0.0], config)
    coarse, fine = records
    grid_path = save_chern_grid(fine, tmp_path)
    json_path, csv_path = save_scan_summary(records, tmp_path)

    assert coarse.result.new_diagonalizations == 25
    assert fine.result.new_diagonalizations == 75
    assert fine.result.fhs.chern_integer == 2
    with np.load(grid_path) as saved:
        assert {
            "ground_states",
            "berry_flux",
            "ground_state_energies",
            "first_excited_energies",
            "gaps",
            "hermiticity_errors",
            "parameters_json",
            "basis_fingerprint",
        } <= set(saved.files)
        np.testing.assert_allclose(saved["ground_states"], fine.result.states)
        parameters = json.loads(str(saved["parameters_json"]))
        assert parameters["U"] == 0.0
        assert str(saved["basis_fingerprint"]) == fine.result.basis_fingerprint
        assert len(str(saved["basis_fingerprint"])) == 64
    assert json.loads(json_path.read_text())[1]["N_theta"] == 10
    assert csv_path.read_text().splitlines()[0].startswith("L,U,t")


def test_benchmark_workflow_returns_all_four_observables():
    config = BenchmarkConfig(
        model=ModelParameters(L=4),
        chern_grid=5,
        gap_grids=(3, 6),
        polarization_points=20,
        period=2.0,
        time_steps=80,
    )

    result = run_benchmark(config)

    assert result["C_MB"] == pytest.approx(2.0, abs=1e-10)
    assert result["Delta_min"] == pytest.approx(3.6, abs=1e-10)
    assert result["Q_adiabatic"] == pytest.approx(2.0, abs=1e-8)
    assert np.isfinite(result["Q_real_time"])
    assert result["norm_error"] < 1e-12
    assert result["conventions"]["torus_order"] == "theta,phi"


def test_unified_benchmark_cli_prints_one_json_document(tmp_path):
    config_path = tmp_path / "benchmark.yaml"
    config_path.write_text(
        """
model:
  L: 10
  t: 1.0
  delta0: 0.9
  Delta0: 3.0
  U: 0.0
  N_up: 5
  N_down: 5
benchmark:
  chern_grid: 5
  gap_grids: [3, 6]
  polarization_points: 20
  period: 1.0
  time_steps: 40
scan:
  grid_sizes: [5]
  U_values: [0.0]
output_dir: results
""".lstrip()
    )

    completed = subprocess.run(
        [
            str(PYTHON),
            str(PROJECT_ROOT / "scripts" / "run.py"),
            "benchmark",
            "--config",
            str(config_path),
            "--L",
            "4",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert set(("C_MB", "Delta_min", "Q_adiabatic", "Q_real_time")) <= set(
        payload
    )
    assert completed.stderr == ""


def test_slurm_wrapper_does_not_require_a_preexisting_log_directory():
    script = (PROJECT_ROOT / "cluster" / "scan_u.slurm").read_text()
    output_line = next(
        line for line in script.splitlines() if line.startswith("#SBATCH --output=")
    )
    error_line = next(
        line for line in script.splitlines() if line.startswith("#SBATCH --error=")
    )

    assert "/" not in output_line.removeprefix("#SBATCH --output=")
    assert "/" not in error_line.removeprefix("#SBATCH --error=")
    assert '"$@"' in script
