import pathlib
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import dynamics
import open_loop
import pulses
import systems


def test_attempt_004_gradient_matches_finite_difference():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=4)
    jax, _ = config.require_jax()
    loss_fn = lambda x: dynamics.gate_infidelity(x, system)

    analytic = np.asarray(jax.grad(loss_fn)(theta))
    numeric = open_loop.finite_difference_gradient(lambda x: float(loss_fn(x)), theta, step=1e-5)

    assert np.linalg.norm(analytic - numeric) / max(1.0, np.linalg.norm(numeric)) < 2e-4


def test_attempt_004_open_loop_optimization_improves_loss():
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=5)
    cfg = config.OpenLoopConfig(steps=30, learning_rate=0.05, target_infidelity=1e-2, seed_scale=0.0)

    before = float(dynamics.gate_infidelity(start, system))
    result = open_loop.optimize_model_pulse(system, start, cfg)

    assert result.final_infidelity < before
    assert result.final_infidelity <= 1e-2
    assert len(result.history) >= 2
    assert {"step", "loss", "grad_norm"} <= set(result.history[-1])
