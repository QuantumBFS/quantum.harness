import pathlib
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
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
