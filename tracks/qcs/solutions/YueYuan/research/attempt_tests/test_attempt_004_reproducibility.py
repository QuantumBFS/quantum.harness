import pathlib
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import baselines
import config
import device
import hessian
import open_loop
import pulses
import systems


def _prepared_one_qubit(seed=0):
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=seed)
    opt = open_loop.optimize_model_pulse(
        system,
        start,
        config.OpenLoopConfig(
            steps=25,
            learning_rate=0.05,
            target_infidelity=1e-2,
            seed_scale=0.0,
        ),
    )
    hess = hessian.dense_hessian(system, opt.theta)
    true_system = device.build_true_system(system, "small", seed=seed)
    return system, true_system, opt, hess


def test_attempt_004_random_subspace_is_orthonormal_and_reproducible():
    first = baselines.random_subspace(raw_dim=16, k=3, seed=2)
    second = baselines.random_subspace(raw_dim=16, k=3, seed=2)

    assert np.allclose(first, second)
    assert np.max(np.abs(first.T @ first - np.eye(3))) < 1e-10


def test_attempt_004_model_only_and_hessian_records_are_reproducible():
    system, true_system, opt, hess = _prepared_one_qubit(seed=3)
    closed = config.ClosedLoopConfig(query_budget=40, target_infidelity=1e-3, initial_step=0.08)
    record_a = baselines.run_model_only(system, true_system, opt.theta, shots=128, seed=4)
    record_b = baselines.run_model_only(system, true_system, opt.theta, shots=128, seed=4)
    hessian_record = baselines.run_subspace_method(
        method="hessian_subspace_nelder_mead",
        system=system,
        true_system=true_system,
        start_theta=opt.theta,
        hessian_matrix=hess,
        k=3,
        shots=128,
        seed=4,
        cfg=closed,
    )

    assert record_a == record_b
    assert record_a.method == "model_only"
    assert hessian_record.method == "hessian_subspace_nelder_mead"
    assert hessian_record.query_count <= closed.query_budget
    assert hessian_record.total_shots <= closed.query_budget * 128
