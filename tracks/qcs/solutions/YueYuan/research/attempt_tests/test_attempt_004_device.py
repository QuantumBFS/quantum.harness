import pathlib
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import baselines
import device
import pulses
import systems


def test_attempt_004_query_only_device_counts_queries_and_shots():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "small", seed=8)
    oracle = device.QueryOnlyDevice(true_system, seed=9)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=10)

    value = oracle.query(theta, shots=128, seed=11)

    assert isinstance(value, float)
    assert 0.0 <= value <= 1.0
    assert oracle.query_count == 1
    assert oracle.shot_count == 128


def test_attempt_004_device_public_interface_is_strict():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "medium", seed=12)
    oracle = device.QueryOnlyDevice(true_system, seed=13)
    public_names = {name for name in dir(oracle) if not name.startswith("_")}

    assert {"query", "query_count", "shot_count"} <= public_names
    assert "exact_fidelity" not in public_names
    assert "true_system" not in public_names
    assert "hidden_perturbation" not in public_names


def test_attempt_004_noisy_variance_decreases_with_shots():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "large", seed=14)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=15)
    low = []
    high = []
    for seed in range(40):
        low.append(device.QueryOnlyDevice(true_system, seed=seed).query(theta, shots=64, seed=seed))
        high.append(device.QueryOnlyDevice(true_system, seed=seed).query(theta, shots=2048, seed=seed))

    assert np.var(high) < np.var(low)


def test_attempt_004_nelder_mead_uses_only_scalar_objective():
    import optimizers

    calls = []

    def objective(x):
        calls.append(np.asarray(x).copy())
        return float(np.sum((x - np.array([0.2, -0.1])) ** 2))

    result = optimizers.nelder_mead(
        objective,
        np.zeros(2),
        step=0.2,
        max_queries=80,
        bounds=(-1.0, 1.0),
    )

    assert result.best_value < 1e-4
    assert result.queries == len(calls)
    assert result.queries <= 80
    assert len(result.history) == result.queries


def test_attempt_004_nelder_mead_handles_zero_dimensional_search():
    import optimizers

    calls = []

    def objective(x):
        calls.append(np.asarray(x).copy())
        return 0.25

    result = optimizers.nelder_mead(
        objective,
        np.zeros(0),
        step=0.2,
        max_queries=8,
        bounds=(-1.0, 1.0),
    )

    assert result.best_x.shape == (0,)
    assert result.best_value == 0.25
    assert result.queries == 1
    assert len(calls) == 1
    assert len(result.history) == 1


def test_attempt_004_adaptive_hessian_widens_using_query_budget():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "large", seed=16)
    start = np.zeros(config.ONE_QUBIT_X.raw_dim)
    hess = np.eye(config.ONE_QUBIT_X.raw_dim)
    cfg = config.ClosedLoopConfig(
        query_budget=10,
        target_infidelity=1e-6,
        initial_step=0.08,
    )

    record = baselines.run_adaptive_hessian_method(
        model,
        true_system,
        start,
        hess,
        initial_k=0,
        max_k=2,
        shots=64,
        seed=17,
        cfg=cfg,
    )

    assert record.method == "adaptive_hessian_subspace_nelder_mead"
    assert record.k == 2
    assert record.adaptive_initial_k == 0
    assert record.adaptive_final_k == 2
    assert record.adaptive_widened is True
    assert record.query_count <= cfg.query_budget
    assert record.total_shots == record.query_count * 64
