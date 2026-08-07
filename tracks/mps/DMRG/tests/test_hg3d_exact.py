from __future__ import annotations

import itertools

import numpy as np
import pytest

import spinglass3d.exact as exact_module
from spinglass3d.exact import enumerate_l2, transfer_l3
from spinglass3d.model import EABonds


def _fixed_l2_bonds() -> EABonds:
    values = np.array(
        [
            1,
            -1,
            1,
            1,
            1,
            -1,
            -1,
            1,
            1,
            1,
            -1,
            -1,
            1,
            1,
            1,
            -1,
            -1,
            1,
            -1,
            1,
            -1,
            1,
            -1,
            1,
        ],
        dtype=np.int8,
    ).reshape(2, 2, 2, 3)
    return EABonds(values)


def _direct_energies(states: np.ndarray, bonds: EABonds) -> np.ndarray:
    length = bonds.length
    result = np.empty(states.shape[0], dtype=np.int64)
    for state_index, state in enumerate(states):
        total = 0
        for x, y, z in itertools.product(range(length), repeat=3):
            for axis in range(3):
                neighbor = [x, y, z]
                neighbor[axis] = (neighbor[axis] + 1) % length
                total -= (
                    int(bonds.values[x, y, z, axis])
                    * int(state[x, y, z])
                    * int(state[tuple(neighbor)])
                )
        result[state_index] = total
    return result


def test_l2_enumeration_matches_independent_state_sum() -> None:
    beta = 0.73
    bonds = _fixed_l2_bonds()
    record = enumerate_l2(beta, bonds)

    assert record.states.shape == (256, 2, 2, 2)
    assert np.unique(record.states.reshape(256, -1), axis=0).shape[0] == 256
    reference_energies = _direct_energies(record.states, bonds)
    log_weights = -beta * reference_energies.astype(np.float64)
    shift = float(np.max(log_weights))
    weights = np.exp(log_weights - shift)
    probabilities = weights / weights.sum()

    np.testing.assert_array_equal(record.energies, reference_energies)
    np.testing.assert_allclose(
        record.probabilities,
        probabilities,
        atol=2e-14,
        rtol=0.0,
    )
    assert record.partition_function == pytest.approx(
        float(np.exp(shift) * weights.sum()), rel=2e-14
    )
    assert record.partition_derivative == pytest.approx(
        float(np.sum(-reference_energies * np.exp(log_weights))), rel=2e-14
    )
    expected_energy = float(probabilities @ reference_energies)
    expected_heat_capacity = beta**2 * float(
        probabilities @ (reference_energies.astype(np.float64) ** 2)
        - expected_energy**2
    )
    assert record.energy == pytest.approx(expected_energy, abs=2e-14, rel=0.0)
    assert record.heat_capacity == pytest.approx(
        expected_heat_capacity,
        abs=2e-13,
        rel=0.0,
    )

    flat = record.states.reshape(256, -1).astype(np.float64)
    expected_two_point = flat.T @ (probabilities[:, None] * flat)
    np.testing.assert_allclose(
        record.two_point,
        expected_two_point,
        atol=2e-14,
        rtol=0.0,
    )
    overlap = flat @ flat.T / 8.0
    pair_probability = probabilities[:, None] * probabilities[None, :]
    assert record.q2 == pytest.approx(
        float(np.sum(pair_probability * overlap**2)), abs=2e-14, rel=0.0
    )
    assert record.q4 == pytest.approx(
        float(np.sum(pair_probability * overlap**4)), abs=2e-14, rel=0.0
    )


def test_l2_infinite_temperature_overlap_moments_are_analytic() -> None:
    record = enumerate_l2(0.0, _fixed_l2_bonds())
    np.testing.assert_allclose(
        record.probabilities,
        np.full(256, 1.0 / 256.0),
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(record.two_point, np.eye(8), atol=0.0, rtol=0.0)
    assert record.energy == 0.0
    assert record.heat_capacity == 0.0
    assert record.q2 == pytest.approx(1.0 / 8.0, abs=0.0, rel=0.0)
    assert record.q4 == pytest.approx(11.0 / 256.0, abs=0.0, rel=0.0)


def test_l2_large_beta_keeps_normalized_observables_when_raw_z_overflows() -> None:
    record = enumerate_l2(100.0, _fixed_l2_bonds())
    assert np.isinf(record.partition_function)
    assert np.isfinite(record.log_partition)
    assert np.isfinite(record.energy)
    assert np.isfinite(record.heat_capacity)
    assert np.all(np.isfinite(record.probabilities))
    assert float(record.probabilities.sum()) == pytest.approx(
        1.0,
        abs=2e-15,
        rel=0.0,
    )


def test_generic_layer_transfer_matches_l2_direct_enumeration() -> None:
    beta = 0.41
    bonds = _fixed_l2_bonds()
    direct = enumerate_l2(beta, bonds)
    transfer = exact_module._transfer_layers(beta, bonds)
    assert transfer.length == 2
    assert transfer.partition_function == pytest.approx(
        direct.partition_function, rel=2e-11
    )
    assert transfer.partition_derivative == pytest.approx(
        direct.partition_derivative, rel=2e-11, abs=2e-11
    )
    assert transfer.energy == pytest.approx(
        direct.energy,
        abs=2e-11,
        rel=0.0,
    )


def test_l3_transfer_has_exact_beta_zero_partition() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072904))
    record = transfer_l3(0.0, bonds)
    assert record.length == 3
    assert record.partition_function == float(2**27)
    assert record.log_partition == pytest.approx(
        27.0 * np.log(2.0),
        abs=2e-14,
        rel=0.0,
    )
    assert record.partition_derivative == pytest.approx(
        0.0,
        abs=2e-8,
        rel=0.0,
    )
    assert record.energy == pytest.approx(0.0, abs=2e-14, rel=0.0)


def test_l3_energy_matches_log_partition_derivative() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072905))
    beta = 0.37
    epsilon = 1.0e-5
    center = transfer_l3(beta, bonds)
    plus = transfer_l3(beta + epsilon, bonds)
    minus = transfer_l3(beta - epsilon, bonds)
    finite_difference = (plus.log_partition - minus.log_partition) / (
        2.0 * epsilon
    )
    assert -center.energy == pytest.approx(
        finite_difference,
        abs=2e-7,
        rel=0.0,
    )
    assert center.partition_derivative / center.partition_function == pytest.approx(
        -center.energy,
        abs=2e-13,
        rel=0.0,
    )


def test_l3_log_domain_fallback_matches_fast_transfer() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072905))
    beta = 0.37
    fast = transfer_l3(beta, bonds)
    states = exact_module._layer_states(3)
    log_partition, mean_energy = exact_module._log_domain_transfer(
        beta,
        bonds,
        states,
    )
    assert log_partition == pytest.approx(
        fast.log_partition,
        abs=2e-11,
        rel=0.0,
    )
    assert mean_energy == pytest.approx(fast.energy, abs=2e-11, rel=0.0)


@pytest.mark.parametrize("beta", (12.0, 14.0, 100.0, 200.0))
def test_l3_low_temperature_transfer_remains_log_stable(beta: float) -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072905))
    record = transfer_l3(beta, bonds)
    assert np.isfinite(record.log_partition)
    assert np.isfinite(record.energy)
    assert -81.0 <= record.energy <= 81.0
    if np.isfinite(record.partition_function):
        assert record.partition_function > 0.0


def test_exact_oracles_are_strict_about_lattice_and_beta() -> None:
    l2 = _fixed_l2_bonds()
    l3 = EABonds.sample(3, np.random.default_rng(2026072906))
    with pytest.raises(ValueError, match="L=2"):
        enumerate_l2(0.4, l3)
    with pytest.raises(ValueError, match="L=3"):
        transfer_l3(0.4, l2)
    with pytest.raises(ValueError, match="beta"):
        enumerate_l2(-0.1, l2)
    with pytest.raises(ValueError, match="beta"):
        transfer_l3(np.inf, l3)
