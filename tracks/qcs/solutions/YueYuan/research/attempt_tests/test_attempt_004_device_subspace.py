import json
import pathlib
import subprocess
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import baselines
import device
import device_subspace
import pulses
import systems


def test_attempt_004_residual_directions_are_orthonormal_and_residual():
    existing = np.eye(5, 2)
    directions = device_subspace.random_residual_directions(
        raw_dim=5,
        existing_basis=existing,
        count=3,
        seed=12,
    )

    assert directions.shape == (5, 3)
    assert np.allclose(directions.T @ directions, np.eye(3), atol=1e-10)
    assert np.allclose(existing.T @ directions, np.zeros((2, 3)), atol=1e-10)


def _one_qubit_probe_context(seed=21):
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "small", seed=seed)
    oracle = device.QueryOnlyDevice(true_system, seed=seed + 1)
    center = pulses.initial_pulse(config.ONE_QUBIT_X, seed=seed + 2)
    existing = np.eye(config.ONE_QUBIT_X.raw_dim, 2)
    return oracle, center, existing


def test_attempt_004_device_subspace_probe_counts_queries_and_shots():
    oracle, center, existing = _one_qubit_probe_context()
    cfg = device_subspace.ProbeConfig(
        direction_count=3,
        append_count=2,
        step=0.02,
        repeats=2,
        min_positive_curvature=-1e9,
    )

    result = device_subspace.estimate_device_subspace(
        oracle,
        config.ONE_QUBIT_X,
        center,
        existing,
        shots=32,
        seed=33,
        cfg=cfg,
    )

    assert result.query_count == 13
    assert result.shot_count == 13 * 32
    assert oracle.query_count == 13
    assert oracle.shot_count == 13 * 32
    assert result.curvatures.shape == (3,)
    assert result.basis.shape == (config.ONE_QUBIT_X.raw_dim, 2)
    assert result.selected_count == 2
    assert np.allclose(result.basis.T @ result.basis, np.eye(2), atol=1e-10)


def test_attempt_004_device_informed_method_respects_budget_and_records_probe():
    model = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=41)
    hess = np.eye(config.ONE_QUBIT_X.raw_dim)
    true_system = device.build_true_system(model, "medium", seed=42)
    closed_cfg = config.ClosedLoopConfig(
        query_budget=36,
        target_infidelity=1e-3,
        initial_step=0.05,
    )
    probe_cfg = device_subspace.ProbeConfig(
        direction_count=4,
        append_count=2,
        step=0.03,
        repeats=1,
        min_positive_curvature=-1e9,
    )

    record = baselines.run_device_informed_adaptive_hessian_method(
        model,
        true_system,
        start,
        hess,
        initial_k=2,
        max_k=5,
        shots=64,
        seed=43,
        cfg=closed_cfg,
        probe_cfg=probe_cfg,
    )

    assert record.method == "device_informed_adaptive_hessian_nelder_mead"
    assert record.query_count <= closed_cfg.query_budget
    assert record.total_shots == record.query_count * 64
    assert record.device_probe_attempted is True
    assert record.device_probe_directions_tested == 4
    assert record.device_probe_directions_selected <= 2
    assert record.device_probe_query_count == 1 + 2 * 4
    assert record.device_probe_shot_count == record.device_probe_query_count * 64
    assert record.adaptive_initial_k == 2
    assert record.adaptive_final_k >= 2


def test_attempt_004_device_informed_focus_runner_emits_new_method(tmp_path):
    out_dir = tmp_path / "device_focus"
    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_device_informed_focus.py"),
            "--out",
            str(out_dir),
            "--fast",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in (out_dir / "runs.jsonl").read_text().splitlines()]
    assert "device_informed_adaptive_hessian_nelder_mead" in {row["method"] for row in rows}
    assert (out_dir / "summary_tables" / "device_informed_summary.csv").exists()
    assert (out_dir / "summary_tables" / "device_informed_recovery.csv").exists()
    assert (out_dir / "figures" / "device_informed_recovery.png").exists()
