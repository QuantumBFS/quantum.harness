from __future__ import annotations

import copy
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
from calibrate import (
    OBSERVABLES,
    analyze_batch_means,
    analyze_warmup,
    build_calibration_plan,
    build_calibration_artifact,
    calibration_cluster_commands,
    select_cycle_length,
    validate_calibration,
    validate_calibration_plan,
)


def values(base: float) -> dict[str, float]:
    return {name: base + i * 1e-6 for i, name in enumerate(OBSERVABLES)}


def warmup_cells(shift=1e-5, spread=2e-5):
    cells = []
    offsets = (-3.0, -1.0, 1.0, 3.0)
    for level, warmup in enumerate((12500, 25000, 50000)):
        for replica, offset in enumerate(offsets):
            cells.append(
                {
                    "cell_kind": "warmup",
                    "warmup_cycles": warmup,
                    "replica": replica,
                    "seed": 820000 + level * 10 + replica,
                    "input_identity": "same",
                    "estimator": "direct",
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
            "estimator": "direct_increment",
            "warmup_cycles": 50000,
            "measurement_cycles": 62500,
            "values": values(scale * (pattern[increment] + group / 10)),
        }
        for group in range(4)
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


def test_warmup_uses_independent_welch_interval_and_equivalence():
    cells = warmup_cells()
    result = analyze_warmup(cells)["observables"]["n_d"]
    a_values = [c["values"]["n_d"] for c in cells if c["warmup_cycles"] == 25000]
    b_values = [c["values"]["n_d"] for c in cells if c["warmup_cycles"] == 50000]
    se_a = np.std(a_values, ddof=1) / 2
    se_b = np.std(b_values, ddof=1) / 2
    a, b = se_a**2, se_b**2
    df = (a + b) ** 2 / (a**2 / 3 + b**2 / 3)
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


def test_cycle_selection_fails_closed_if_smallest_is_not_fifty():
    cells = [
        {
            "cell_kind": "cycle",
            "cycle_length": length,
            "replica": replica,
            "seed": 821000 + i * 10 + replica,
            "input_identity": "same",
            "auto_corr_time": 5.0 if length >= 50 else 5.1,
            "auto_corr_time_converged": length >= 50,
        }
        for i, length in enumerate((10, 25, 50, 100))
        for replica in range(4)
    ]
    assert select_cycle_length(cells)["passed"] is True
    for cell in cells:
        if cell["cycle_length"] == 25:
            cell["auto_corr_time"] = 5.0
            cell["auto_corr_time_converged"] = True
    changed = select_cycle_length(cells)
    assert changed["selected_cycle_length"] == 25
    assert changed["passed"] is False


def test_batch_means_pairing_variance_and_seed_guards():
    cells = batch_cells()
    result = analyze_batch_means(cells)
    gate = result["observables"]["n_d"]
    groups = [
        np.array([c["values"]["n_d"] for c in cells if c["group"] == group])
        for group in range(4)
    ]
    differences = [np.mean(group[4:]) - np.mean(group[:4]) for group in groups]
    pooled = sum(7 * np.var(group, ddof=1) for group in groups) / 28
    upper = math.sqrt(28 * pooled / (chi2.ppf(0.01, 28) * 64))
    assert gate["paired_differences"] == pytest.approx(differences)
    assert gate["drift_standard_error"] == pytest.approx(np.std(differences, ddof=1) / 2)
    assert gate["drift_quantile"] == pytest.approx(t.ppf(1 - 0.01 / 16, 3))
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


def test_plan_is_exact_sixty_hash_bound_cells():
    plan = build_calibration_plan(bindings())
    validate_calibration_plan(plan)
    cells = plan["payload"]["cells"]
    assert [cell["payload"]["cell_index"] for cell in cells] == list(range(60))
    assert [cell["payload"]["cell_kind"] for cell in cells].count("warmup") == 12
    assert [cell["payload"]["cell_kind"] for cell in cells].count("cycle") == 16
    assert [cell["payload"]["cell_kind"] for cell in cells].count("increment") == 32
    assert len({cell["payload"]["seed"] for cell in cells}) == 60
    changed = copy.deepcopy(plan)
    changed["payload"]["cells"][0]["payload"]["seed"] += 1
    changed["payload"]["cells"][0]["sha256"] = sha256_bytes(
        canonical_json(changed["payload"]["cells"][0]["payload"])
    )
    changed["sha256"] = sha256_bytes(canonical_json(changed["payload"]))
    with pytest.raises(ValueError, match="canonical"):
        validate_calibration_plan(changed)


def test_calibration_embeds_and_revalidates_all_results():
    plan = build_calibration_plan(bindings())
    cells = warmup_cells() + [
        {
            "cell_kind": "cycle",
            "cycle_length": length,
            "replica": replica,
            "seed": 821000 + i * 10 + replica,
            "input_identity": "same",
            "auto_corr_time": 5.0 if length >= 50 else 5.1,
            "auto_corr_time_converged": length >= 50,
        }
        for i, length in enumerate((10, 25, 50, 100))
        for replica in range(4)
    ] + batch_cells()
    results = [
        {"payload": cell, "sha256": sha256_bytes(canonical_json(cell))}
        for cell in cells
    ]
    analysis = {
        "warmup": analyze_warmup(cells[:12]),
        "cycle": select_cycle_length(cells[12:28]),
        "batch": analyze_batch_means(cells[28:]),
    }
    artifact = build_calibration_artifact(plan, results)
    assert artifact["payload"]["analysis"] == analysis
    assert artifact["payload"]["status"] == "accepted"
    validate_calibration(artifact, plan)
    artifact["payload"]["analysis"]["batch"]["passed"] = False
    artifact["sha256"] = sha256_bytes(canonical_json(artifact["payload"]))
    with pytest.raises(ValueError):
        validate_calibration(artifact, plan)


def test_calibration_cluster_commands_and_wrapper_are_serial_offline(tmp_path):
    commands = calibration_cluster_commands(
        Path("/opt/micromamba"),
        Path("/opt/triqs"),
        Path("/data/plan.json"),
        Path("/data/run"),
    )
    assert "--array=0-59 --ntasks=1 --cpus-per-task=1" in commands["array"]
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
    assert args[:5] == ["run", "--offline", "--prefix", "/opt/triqs", "python"]
    assert args[-2:] == ["--cell-index", "7"]
    for name, value in (
        ("SLURM_ARRAY_TASK_ID", "60"),
        ("SLURM_NTASKS", "2"),
        ("OMP_NUM_THREADS", "2"),
        ("CTHYB_CAL_PLAN", "relative"),
    ):
        changed = dict(env)
        changed[name] = value
        assert subprocess.run([str(wrapper)], env=changed).returncode != 0
