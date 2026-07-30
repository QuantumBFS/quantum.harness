"""Tests for exact-state Haar circuit gate operations."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_transfer.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_transfer", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_transfer"] = module
    spec.loader.exec_module(module)
    return module


def _dense_apply(state, gate, sites, L):
    q0, q1 = sites
    out = np.zeros_like(state)
    for source in range(1 << L):
        bits = [(source >> (L - 1 - q)) & 1 for q in range(L)]
        local_in = 2 * bits[q0] + bits[q1]
        for local_out in range(4):
            target_bits = bits.copy()
            target_bits[q0], target_bits[q1] = divmod(local_out, 2)
            target = sum(bit << (L - 1 - q) for q, bit in enumerate(target_bits))
            out[target] += gate[local_out, local_in] * state[source]
    return out


def test_layer_pairs_include_periodic_odd_gate():
    """Catches a missing periodic pair in an odd brickwork layer."""
    module = _load_module()
    assert module.layer_pairs(6, 0) == ((0, 1), (2, 3), (4, 5))
    assert module.layer_pairs(6, 1) == ((1, 2), (3, 4), (5, 0))


@pytest.mark.parametrize("sites", [(0, 1), (1, 2), (3, 0)])
def test_local_gate_matches_dense_oracle(sites):
    """Catches wrong tensor axes or local basis order for any gate pair."""
    module = _load_module()
    rng = np.random.default_rng(17)
    state = module.global_haar_state(4, rng)
    gate = module.haar_unitary_4(rng)
    expected = _dense_apply(state, gate, sites, 4)
    module.apply_two_qubit_gate_inplace(state, gate, sites, 4)
    np.testing.assert_allclose(state, expected, rtol=2e-13, atol=2e-13)


def test_haar_unitarity_and_low_moment():
    """Catches non-unitary sampling or a biased Haar gate distribution."""
    module = _load_module()
    rng = np.random.default_rng(41)
    values = []
    for _ in range(2000):
        gate = module.haar_unitary_4(rng)
        np.testing.assert_allclose(gate.conj().T @ gate, np.eye(4), atol=5e-13)
        values.append(abs(gate[0, 0]) ** 2)
    assert abs(np.mean(values) - 0.25) < 0.015


def test_haar_low_moments_are_left_unitary_invariant():
    """Catches QR phase handling that breaks left-unitary Haar invariance."""
    module = _load_module()
    rng = np.random.default_rng(43)
    fixed = module.haar_unitary_4(np.random.default_rng(99))
    raw, rotated = [], []
    for _ in range(3000):
        gate = module.haar_unitary_4(rng)
        raw.append([abs(gate[0, 0])**2, abs(gate[0, 0])**4])
        transformed = fixed @ gate
        rotated.append([abs(transformed[0, 0])**2,
                        abs(transformed[0, 0])**4])
    np.testing.assert_allclose(np.mean(raw, axis=0), [.25, .1], atol=.015)
    np.testing.assert_allclose(np.mean(rotated, axis=0), [.25, .1], atol=.015)
    np.testing.assert_allclose(np.mean(raw, axis=0),
                               np.mean(rotated, axis=0), atol=.015)


@pytest.mark.parametrize("factory", ["global_haar_state", "product_haar_state"])
def test_initial_states_are_normalized_complex128(factory):
    """Catches real-valued or unnormalized exact-state initialization."""
    module = _load_module()
    state = getattr(module, factory)(5, np.random.default_rng(7))
    assert state.shape == (32,)
    assert state.dtype == np.complex128
    np.testing.assert_allclose(np.vdot(state, state).real, 1.0, atol=3e-14)


def test_measurement_probability_and_post_state():
    """Catches incorrectly normalized or non-projective Z measurements."""
    module = _load_module()
    state = np.array([np.sqrt(0.8), 0.0, np.sqrt(0.2), 0.0], dtype=np.complex128)
    outcome, probability = module.measure_z_inplace(
        state, site=0, L=2, rng=np.random.default_rng(3))
    assert probability == pytest.approx(0.8 if outcome == 0 else 0.2)
    assert np.vdot(state, state).real == pytest.approx(1.0, abs=2e-14)
    assert np.linalg.norm(state.reshape(2, 2)[1 - outcome]) == pytest.approx(0.0)


def test_empirical_born_frequency():
    """Catches outcome sampling that is not weighted by Born probabilities."""
    module = _load_module()
    outcomes = []
    for seed in range(3000):
        state = np.array([np.sqrt(0.7), np.sqrt(0.3)], dtype=np.complex128)
        outcomes.append(module.measure_z_inplace(
            state, 0, 1, np.random.default_rng(seed))[0])
    assert abs(np.mean(outcomes) - 0.3) < 0.025


def test_even_odd_period_matches_dense_oracle(monkeypatch):
    """Catches a gate-layer composition that misses periodic odd pairs."""
    module = _load_module()
    rng = np.random.default_rng(9)
    state = module.global_haar_state(4, rng)
    gates = [module.haar_unitary_4(rng) for _ in range(4)]
    expected = state.copy()
    for gate, pair in zip(gates, ((0, 1), (2, 3), (1, 2), (3, 0))):
        expected = _dense_apply(expected, gate, pair, 4)
    iterator = iter(gates)
    monkeypatch.setattr(module, "haar_unitary_4", lambda ignored: next(iterator))
    module.apply_gate_layer(state, 4, 0, rng)
    module.apply_gate_layer(state, 4, 1, rng)
    np.testing.assert_allclose(state, expected, atol=3e-13)


def test_measured_basis_state_has_zero_cost():
    """Catches assigning entropy cost to a deterministic measurement."""
    module = _load_module()
    state = np.array([0, 0, 1, 0], dtype=np.complex128)
    result = module.apply_measurement_layer(
        state, L=2, p=1.0, rng=np.random.default_rng(5), accumulate_cost=True)
    assert result["attempted"] == 2
    assert result["cost"] == pytest.approx(0.0)


@pytest.mark.parametrize("family", ["global_haar", "product"])
def test_trajectory_is_reproducible_and_p_zero_has_zero_cost(family):
    """Catches nondeterministic trajectories or costs without measurements."""
    module = _load_module()
    kwargs = dict(L=4, p=0.0, seed=73, initial_family=family,
                  burn_in_steps=3, record_steps=5)
    first = module.run_trajectory(**kwargs)
    second = module.run_trajectory(**kwargs)
    assert first["record_cost"] == 0.0
    assert first["attempted_measurements"] == 0
    assert first["cumulative_record_cost"] == [0.0] * 5
    for key in first.keys() - {"runtime_seconds"}:
        assert first[key] == second[key]
