from __future__ import annotations

import itertools

import numpy as np
import pytest

from spinglass3d.model import EABonds, delta_energy, energy, three_color_sites


def _scalar_energy(spins: np.ndarray, bonds: EABonds) -> int:
    length = spins.shape[0]
    total = 0
    for x, y, z in itertools.product(range(length), repeat=3):
        for axis in range(3):
            neighbor = [x, y, z]
            neighbor[axis] = (neighbor[axis] + 1) % length
            total -= (
                int(bonds.values[x, y, z, axis])
                * int(spins[x, y, z])
                * int(spins[tuple(neighbor)])
            )
    return total


def test_cubic_energy_matches_scalar_bond_sum() -> None:
    rng = np.random.default_rng(2026072901)
    for length in (2, 3, 6):
        bonds = EABonds.sample(length, rng)
        spins = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(length, length, length),
        )
        assert energy(spins, bonds) == _scalar_energy(spins, bonds)


def test_local_delta_matches_total_energy() -> None:
    rng = np.random.default_rng(11)
    bonds = EABonds.sample(6, rng)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(6, 6, 6))
    before = energy(spins, bonds)
    for site in np.ndindex(spins.shape):
        delta = delta_energy(spins, bonds, site)
        flipped = spins.copy()
        flipped[site] *= -1
        assert energy(flipped, bonds) - before == delta


def test_iid_generator_does_not_force_exact_half() -> None:
    bonds = EABonds.sample(45, np.random.default_rng(17))
    assert bonds.values.dtype == np.int8
    assert bonds.values.shape == (45, 45, 45, 3)
    assert bonds.values.size == 273_375
    assert set(np.unique(bonds.values)) == {-1, 1}
    assert np.count_nonzero(bonds.values == 1) != bonds.values.size // 2


def test_bonds_own_a_read_only_validated_copy() -> None:
    source = np.ones((2, 2, 2, 3), dtype=np.int64)
    bonds = EABonds(source)
    source[0, 0, 0, 0] = -1
    assert bonds.values[0, 0, 0, 0] == 1
    with pytest.raises(ValueError, match="read-only"):
        bonds.values[0, 0, 0, 0] = -1

    with pytest.raises(ValueError, match="shape"):
        EABonds(np.ones((2, 2, 3), dtype=np.int8))
    malformed = np.ones((2, 2, 2, 3), dtype=np.int8)
    malformed[0, 0, 0, 0] = 0
    with pytest.raises(ValueError, match=r"-1 and \+1"):
        EABonds(malformed)


@pytest.mark.parametrize("length", (3, 6, 9, 12, 15, 18, 24, 27, 45))
def test_three_color_sites_partition_periodic_edges(length: int) -> None:
    colors = three_color_sites(length)
    assert len(colors) == 3
    assert all(color.dtype == np.int64 for color in colors)
    combined = np.concatenate(colors, axis=0)
    assert combined.shape == (length**3, 3)
    assert np.unique(combined, axis=0).shape[0] == length**3

    color_of = np.empty((length, length, length), dtype=np.int8)
    for color, sites in enumerate(colors):
        color_of[tuple(sites.T)] = color
    for axis in range(3):
        assert np.all(color_of != np.roll(color_of, -1, axis=axis))


def test_model_interfaces_reject_incompatible_inputs() -> None:
    bonds = EABonds.sample(3, np.random.default_rng(2026072902))
    with pytest.raises(ValueError, match="shape"):
        energy(np.ones((3, 3, 2), dtype=np.int8), bonds)
    spins = np.ones((3, 3, 3), dtype=np.int8)
    spins[0, 0, 0] = 0
    with pytest.raises(ValueError, match=r"-1 and \+1"):
        energy(spins, bonds)
    with pytest.raises(ValueError, match="site"):
        delta_energy(np.ones((3, 3, 3), dtype=np.int8), bonds, (3, 0, 0))
    with pytest.raises(ValueError, match="divisible by three"):
        three_color_sites(4)
    with pytest.raises(ValueError, match="at least"):
        EABonds.sample(1, np.random.default_rng(2026072903))
