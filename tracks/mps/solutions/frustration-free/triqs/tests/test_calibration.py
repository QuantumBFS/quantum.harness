from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy.stats import chi2, t

TRIQS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRIQS_DIR))

from artifacts import canonical_json, sha256_bytes
import calibrate
from calibrate import (
    OBSERVABLES,
    analyze_batch_means,
    analyze_estimator_qualification,
    analyze_warmup,
    build_calibration_plan,
    build_calibration_artifact,
    build_estimator_plan,
    calibration_cluster_commands,
    legendre_reported_values,
    select_cycle_length,
    validate_calibration,
    validate_calibration_plan,
)


def values(base: float) -> dict[str, float]:
    return {name: base + i * 1e-6 for i, name in enumerate(OBSERVABLES)}


def warmup_cells(shift=1e-5, spread=2e-5):
    cells = []
    offsets = tuple(i - 7.5 for i in range(16))
    for level, warmup in enumerate((25000, 50000)):
        for replica, offset in enumerate(offsets):
            cells.append(
                {
                    "cell_kind": "warmup",
                    "warmup_cycles": warmup,
                    "replica": replica,
                    "seed": 820000 + level * 100 + replica,
                    "input_identity": "same",
                    "estimator": "legendre",
                    "values": values(
                        (shift if warmup == 50000 else 0.0) + spread * offset
                    ),
                }
            )
    return cells


def batch_cells(scale=1e-5):
    pattern = (-3.0, -2.0, -1.0, 0.0, 0.0, 1.0, 2.0, 3.0)
    return [
        {
            "cell_kind": "increment",
            "group": group,
            "increment": increment,
            "seed": 822000 + group * 10 + increment,
            "input_identity": "same",
            "estimator": "legendre_direct_increment",
            "warmup_cycles": 50000,
            "measurement_cycles": 62500,
            "values": values(scale * (pattern[increment] + group / 10)),
        }
        for group in range(8)
        for increment in range(8)
    ]


def bindings():
    return {
        "model": {"beta": 16.0, "U": 0.8},
        "meshes": {"n_iw": 2049, "n_tau": 4001},
        "formulas": {"delta": "analytic_semicircle"},
        "source_manifest": {"x": "1" * 64},
        "source_manifest_sha256": "2" * 64,
        "conda_lock_sha256": "3" * 64,
        "environment_yml_sha256": "4" * 64,
        "model_json_sha256": "5" * 64,
    }


def test_warmup_uses_sixteen_independent_replicates_and_welch_interval():
    cells = warmup_cells()
    result = analyze_warmup(cells)["observables"]["n_d"]
    a_values = [c["values"]["n_d"] for c in cells if c["warmup_cycles"] == 25000]
    b_values = [c["values"]["n_d"] for c in cells if c["warmup_cycles"] == 50000]
    se_a = np.std(a_values, ddof=1) / 4
    se_b = np.std(b_values, ddof=1) / 4
    a, b = se_a**2, se_b**2
    df = (a + b) ** 2 / (a**2 / 15 + b**2 / 15)
    q = t.ppf(1 - 0.01 / 16, df)
    assert result["se_delta"] == pytest.approx(math.sqrt(a + b))
    assert result["degrees_of_freedom"] == pytest.approx(df)
    assert result["quantile"] == pytest.approx(q)
    assert result["passed"] is True
    crossing = analyze_warmup(warmup_cells(shift=0, spread=2e-4))
    assert crossing["observables"]["n_d"]["interval"][0] < 0
    assert crossing["observables"]["n_d"]["interval"][1] > 5e-4
    assert crossing["passed"] is False


def test_warmup_zero_variance_is_degenerate():
    cells = warmup_cells(shift=4e-4, spread=0)
    result = analyze_warmup(cells)["observables"]["n_d"]
    assert result["degrees_of_freedom"] == "infinite"
    assert result["interval"] == pytest.approx([4e-4, 4e-4])
    assert result["passed"] is True


def test_cycle_records_empirical_minimum_but_gates_locked_fifty():
    cells = [
        {
            "cell_kind": "cycle",
            "cycle_length": length,
            "replica": replica,
            "seed": 821000 + i * 10 + replica,
            "input_identity": "same",
            "auto_corr_time": 1.0,
            "auto_corr_time_converged": True,
        }
        for i, length in enumerate((10, 25, 50, 100))
        for replica in range(4)
    ]
    result = select_cycle_length(cells)
    assert result["empirical_minimum_cycle_length"] == 10
    assert result["locked_production_cycle_length"] == 50
    assert result["passed"] is True
    for cell in cells:
        if cell["cycle_length"] == 50 and cell["replica"] == 0:
            cell["auto_corr_time_converged"] = False
    changed = select_cycle_length(cells)
    assert changed["empirical_minimum_cycle_length"] == 10
    assert changed["passed"] is False


def test_batch_means_pairing_variance_and_seed_guards():
    cells = batch_cells()
    result = analyze_batch_means(cells)
    gate = result["observables"]["n_d"]
    groups = [
        np.array([c["values"]["n_d"] for c in cells if c["group"] == group])
        for group in range(8)
    ]
    differences = [np.mean(group[4:]) - np.mean(group[:4]) for group in groups]
    pooled = sum(7 * np.var(group, ddof=1) for group in groups) / 56
    upper = math.sqrt(56 * pooled / (chi2.ppf(0.01, 56) * 32))
    assert gate["paired_differences"] == pytest.approx(differences)
    assert gate["drift_standard_error"] == pytest.approx(np.std(differences, ddof=1) / math.sqrt(8))
    assert gate["drift_quantile"] == pytest.approx(t.ppf(1 - 0.01 / 16, 7))
    assert gate["variance_degrees_of_freedom"] == 56
    assert gate["production_batch_equivalents"] == 32
    assert gate["pooled_within_group_variance"] == pytest.approx(pooled)
    assert gate["projected_error_upper_99"] == pytest.approx(upper)
    assert "se_decreases" not in canonical_json(result).decode()
    for mutation in ("duplicate", "production", "reconstructed", "mixed", "missing"):
        changed = copy.deepcopy(cells)
        if mutation == "duplicate":
            changed[1]["seed"] = changed[0]["seed"]
        elif mutation == "production":
            changed[0]["seed"] = 810001
        elif mutation == "reconstructed":
            changed[0]["estimator"] = "cumulative_difference"
        elif mutation == "mixed":
            changed[0]["input_identity"] = "other"
        else:
            changed.pop()
        with pytest.raises(ValueError):
            analyze_batch_means(changed)


def accepted_qualification():
    plan = build_estimator_plan(bindings(), n_l=100)
    return analyze_estimator_qualification(
        _qualification_results(identity=plan["payload"]["input_identity"]), plan
    )


def test_plan_is_exact_fresh_112_cell_inventory():
    plan = build_calibration_plan(bindings(), accepted_qualification())
    validate_calibration_plan(plan)
    cells = plan["payload"]["cells"]
    assert [cell["payload"]["cell_index"] for cell in cells] == list(range(112))
    assert [cell["payload"]["cell_kind"] for cell in cells].count("warmup") == 32
    assert [cell["payload"]["cell_kind"] for cell in cells].count("cycle") == 16
    assert [cell["payload"]["cell_kind"] for cell in cells].count("increment") == 64
    assert len({cell["payload"]["seed"] for cell in cells}) == 112
    assert all(cell["payload"]["n_l"] == 100 for cell in cells)
    changed = copy.deepcopy(plan)
    changed["payload"]["cells"][0]["payload"]["seed"] += 1
    changed["payload"]["cells"][0]["sha256"] = sha256_bytes(
        canonical_json(changed["payload"]["cells"][0]["payload"])
    )
    changed["sha256"] = sha256_bytes(canonical_json(changed["payload"]))
    with pytest.raises(ValueError, match="canonical"):
        validate_calibration_plan(changed)


def test_calibration_embeds_and_revalidates_all_results():
    qualification = accepted_qualification()
    plan = build_calibration_plan(bindings(), qualification)
    cells = warmup_cells() + [
        {
            "cell_kind": "cycle",
            "cycle_length": length,
            "replica": replica,
            "seed": 821000 + i * 10 + replica,
            "input_identity": "same",
            "auto_corr_time": 1.0,
            "auto_corr_time_converged": True,
        }
        for i, length in enumerate((10, 25, 50, 100))
        for replica in range(4)
    ] + batch_cells()
    for cell in cells:
        cell["input_identity"] = plan["payload"]["input_identity"]
    results = [
        {"payload": cell, "sha256": sha256_bytes(canonical_json(cell))}
        for cell in cells
    ]
    artifact = build_calibration_artifact(plan, results)
    assert artifact["payload"]["qualification_sha256"] == qualification["sha256"]
    assert artifact["payload"]["status"] == "accepted"
    validate_calibration(artifact, plan)
    artifact["payload"]["analysis"]["batch"]["passed"] = False
    artifact["sha256"] = sha256_bytes(canonical_json(artifact["payload"]))
    with pytest.raises(ValueError):
        validate_calibration(artifact, plan)


def _qualification_results(n_l=100, shift=1e-5, identity="same"):
    truncations = [60, 80, 100] if n_l == 100 else [100, 130, 160]
    results = []
    for replica in range(8):
        payload = {
            "cell_kind": "estimator_qualification",
            "replica": replica,
            "seed": 823000 + replica,
            "input_identity": identity,
            "n_l": n_l,
            "truncations": truncations,
            "truncated_values": {
                str(truncation): values(
                    replica * 2e-5 + (shift if truncation == truncations[-2] else 0)
                )
                for truncation in truncations
            },
        }
        results.append({"payload": payload, "sha256": sha256_bytes(canonical_json(payload))})
    return results


def test_legendre_reconstruction_and_qualification_bias_gate():
    coefficients = np.zeros(100)
    coefficients[0] = 16.0
    reconstructed = legendre_reported_values(
        coefficients, beta=16.0, tau=[4.0, 8.0, 12.0], truncation=100
    )
    assert reconstructed == pytest.approx([1.0, 1.0, 1.0])

    plan = build_estimator_plan(bindings(), n_l=100)
    identity = plan["payload"]["input_identity"]
    result = analyze_estimator_qualification(
        _qualification_results(identity=identity), plan
    )
    assert result["payload"]["status"] == "accepted"
    assert result["payload"]["qualified_n_l"] == 100
    gate = result["payload"]["analysis"]["observables"]["G_up_4"]
    assert gate["degrees_of_freedom"] == 7
    assert gate["equivalence_bound"] == 2.5e-4
    failed = analyze_estimator_qualification(
        _qualification_results(shift=3e-4, identity=identity), plan
    )
    assert failed["payload"]["status"] == "failed"


def test_estimator_plan_has_eight_unique_nonproduction_seeds():
    plan = build_estimator_plan(bindings(), n_l=100)
    cells = plan["payload"]["cells"]
    assert len(cells) == 8
    assert [cell["payload"]["cell_index"] for cell in cells] == list(range(8))
    assert len({cell["payload"]["seed"] for cell in cells}) == 8
    assert all(cell["payload"]["warmup_cycles"] == 50000 for cell in cells)
    assert all(cell["payload"]["measurement_cycles"] == 1_000_000 for cell in cells)
    assert all(cell["payload"]["cycle_length"] == 50 for cell in cells)
    assert all(cell["payload"]["truncations"] == [60, 80, 100] for cell in cells)


def test_summary_schema_names_estimator_artifacts():
    schema = json.loads((TRIQS_DIR / "cthyb-summary.schema.json").read_text())
    artifact_types = schema["properties"]["payload"]["properties"]["artifact_type"][
        "enum"
    ]
    assert "cthyb_estimator_plan" in artifact_types
    assert "cthyb_estimator_qualification" in artifact_types


def test_result_values_preserve_actual_convergence_and_raw_coefficients(monkeypatch):
    class Operator:
        def __init__(self, name):
            self.name = name

        def __mul__(self, other):
            return Operator(f"{self.name}*{other.name}")

    monkeypatch.setattr(
        calibrate.run_chain, "_number_operator", lambda spin, orbital: Operator(spin)
    )
    monkeypatch.setattr(
        calibrate.run_chain,
        "_trace_rho_op",
        lambda density, operator, diagonalization: {
            "up": 0.5,
            "down": 0.5,
            "up*down": 0.1,
        }[operator.name],
    )

    class Block:
        def __init__(self):
            self.data = np.zeros((100, 1, 1), dtype=np.complex128)
            self.data[0, 0, 0] = -8.0

    solver = type(
        "Solver",
        (),
        {
            "density_matrix": object(),
            "h_loc_diagonalization": object(),
            "G_l": {"up": Block(), "down": Block()},
            "auto_corr_time_converged": False,
        },
    )()
    payload = {
        "model": {"beta": 16.0},
        "meshes": {"reported_tau": [0.0, 4.0, 8.0, 12.0, 16.0]},
    }
    result = calibrate._result_values(solver, payload, [60, 80, 100])
    assert result["auto_corr_time_converged"] is False
    assert len(result["legendre_coefficients"]["up"]["real"]) == 100
    assert result["values"]["G_up_4"] == pytest.approx(-0.5)


def test_calibration_cluster_commands_and_wrapper_are_serial_offline(tmp_path):
    commands = calibration_cluster_commands(
        Path("/opt/micromamba"),
        Path("/opt/triqs"),
        Path("/data/plan.json"),
        Path("/data/run"),
    )
    assert "--array=0-111 --ntasks=1 --cpus-per-task=1" in commands["array"]
    assert "OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,MKL_NUM_THREADS=1" in commands["array"]
    assert all("--offline" in value for key, value in commands.items() if key != "array")

    fake = tmp_path / "micromamba"
    log = tmp_path / "args"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$LOG\"\n", encoding="utf-8")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "CTHYB_MICROMAMBA": str(fake),
        "CTHYB_ENV": "/opt/triqs",
        "CTHYB_CAL_PLAN": "/data/plan.json",
        "CTHYB_CAL_RUN": "/data/run",
        "CTHYB_SOURCE": "/src",
        "SLURM_ARRAY_TASK_ID": "7",
        "SLURM_NTASKS": "1",
        "SLURM_CPUS_PER_TASK": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "LOG": str(log),
    }
    wrapper = TRIQS_DIR / "cthyb_calibration_slurm_array.sh"
    subprocess.run([str(wrapper)], env=env, check=True)
    args = log.read_text().splitlines()
    assert args[:5] == ["--offline", "run", "--prefix", "/opt/triqs", "python"]
    assert args[5] == "/src/calibrate.py"
    assert args[-2:] == ["--cell-index", "7"]
    for name, value in (
        ("SLURM_ARRAY_TASK_ID", "112"),
        ("SLURM_NTASKS", "2"),
        ("OMP_NUM_THREADS", "2"),
        ("CTHYB_CAL_PLAN", "relative"),
    ):
        changed = dict(env)
        changed[name] = value
        assert subprocess.run([str(wrapper)], env=changed).returncode != 0
