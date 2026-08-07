from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.model import EABonds, energy
from spinglass3d.tempering import (
    BiasedPairLadder,
    SingleReplicaLadder,
    TemperatureGrid,
    UnbiasedOverlapPT,
    enumerate_l2_pt_transition,
    swap_delta,
)


def _fixed_l2_bonds() -> EABonds:
    values = np.array(
        [1, -1, 1, 1, 1, -1, -1, 1, 1, 1, -1, -1,
         1, 1, 1, -1, -1, 1, -1, 1, -1, 1, -1, 1],
        dtype=np.int8,
    ).reshape(2, 2, 2, 3)
    return EABonds(values)


def test_general_biased_swap_delta() -> None:
    delta = swap_delta(
        beta_m=0.7,
        beta_n=1.1,
        energy_m=-12.0,
        energy_n=-4.0,
        bias_m_xm=2.0,
        bias_m_xn=3.5,
        bias_n_xm=-1.0,
        bias_n_xn=0.25,
    )
    expected = 1.1 * -12.0 + 0.7 * -4.0 - 0.7 * -12.0 - 1.1 * -4.0
    expected += -1.0 + 3.5 - 2.0 - 0.25
    assert delta == pytest.approx(expected, abs=2e-15, rel=0.0)


def test_l2_transition_matrix_obeys_detailed_balance() -> None:
    transition, stationary = enumerate_l2_pt_transition(0.8, _fixed_l2_bonds())
    flux = stationary[:, None] * transition
    np.testing.assert_allclose(flux, flux.T, atol=2e-13, rtol=2e-13)
    np.testing.assert_allclose(transition.sum(axis=1), 1.0, atol=2e-14, rtol=0.0)


def test_temperature_grid_is_strict_and_labeled() -> None:
    grid = TemperatureGrid(np.array([0.4, 0.7, 1.1]))
    np.testing.assert_array_equal(grid.betas, np.array([0.4, 0.7, 1.1]))
    np.testing.assert_allclose(grid.temperatures, 1.0 / grid.betas, rtol=0.0)
    assert len(grid.labels) == 3
    with pytest.raises(ValueError, match="increasing"):
        TemperatureGrid(np.array([0.4, 0.4, 1.1]))


def test_unbiased_overlap_pt_has_independent_ladders_and_exact_energy_cache() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072917))
    grid = TemperatureGrid(np.array([0.35, 0.6, 0.9]))
    left = SingleReplicaLadder.random(bonds, grid, seed=100)
    right = SingleReplicaLadder.random(bonds, grid, seed=200)
    pt = UnbiasedOverlapPT(left, right)
    assert not np.shares_memory(left.spins, right.spins)
    assert left.local_rng is not right.local_rng
    assert left.swap_rng is not right.swap_rng
    pt.run_sweeps(4)
    for ladder in (left, right):
        for index in range(len(grid.betas)):
            assert ladder.energies[index] == energy(ladder.spins[index], bonds)
        assert len(ladder.position_history) == 5
        assert ladder.local_attempts > 0
    pairs = pt.measure_pairs()
    assert len(pairs) == 3
    assert all(not np.shares_memory(pair.a, pair.b) for pair in pairs)


def test_shared_bias_swap_reduces_to_physical_energy_exchange() -> None:
    beta_m, beta_n = 0.5, 1.0
    energy_m, energy_n = -10.0, -4.0
    bias_m, bias_n = 0.7, -0.2
    actual = swap_delta(
        beta_m=beta_m,
        beta_n=beta_n,
        energy_m=energy_m,
        energy_n=energy_n,
        bias_m_xm=bias_m,
        bias_m_xn=bias_n,
        bias_n_xm=bias_m,
        bias_n_xn=bias_n,
    )
    expected = (beta_m - beta_n) * (energy_n - energy_m)
    assert actual == pytest.approx(expected, abs=2e-15, rel=0.0)


def test_biased_pair_uses_random_sequential_updates_and_global_q_flip() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072918))
    grid = TemperatureGrid(np.array([0.4, 0.8]))

    def even_bias(a: np.ndarray, b: np.ndarray) -> float:
        overlap = float(np.sum(a * b, dtype=np.int64))
        return 0.05 * overlap**2 / a.size

    ladder = BiasedPairLadder.random(
        bonds,
        grid,
        bias_energy=even_bias,
        seed=300,
    )
    assert ladder.update_mode == "random_sequential"
    before_a = ladder.spins_a[0].copy()
    before_energy = ladder.energies[0]
    before_bias = ladder.bias_values[0]
    assert ladder.attempt_global_q_flip(0, replica="a") is True
    np.testing.assert_array_equal(ladder.spins_a[0], -before_a)
    assert ladder.energies[0] == before_energy
    assert ladder.bias_values[0] == pytest.approx(before_bias, abs=2e-13, rel=0.0)
    ladder.run_sweeps(3)
    assert len(ladder.position_history) == 4
    assert ladder.local_attempts > 0
    assert ladder.global_flip_attempts == 4
    for index in range(len(grid.betas)):
        expected = energy(ladder.spins_a[index], bonds) + energy(
            ladder.spins_b[index], bonds
        )
        assert ladder.energies[index] == expected
        assert ladder.bias_values[index] == pytest.approx(
            even_bias(ladder.spins_a[index], ladder.spins_b[index]),
            abs=2e-13,
            rel=0.0,
        )


def test_fixed_seed_trajectories_are_reproducible() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072919))
    grid = TemperatureGrid(np.array([0.4, 0.7, 1.0]))
    first = SingleReplicaLadder.random(bonds, grid, seed=400)
    second = SingleReplicaLadder.random(bonds, grid, seed=400)
    first.run_sweeps(5)
    second.run_sweeps(5)
    np.testing.assert_array_equal(first.spins, second.spins)
    np.testing.assert_array_equal(first.energies, second.energies)
    np.testing.assert_array_equal(first.replica_ids, second.replica_ids)
