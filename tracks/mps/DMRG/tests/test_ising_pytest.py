from __future__ import annotations

import itertools

import numpy as np

from vmcrg_ref.ising import (
    delta_hamiltonian,
    ising_hamiltonian,
    periodic_neighbors,
)


def brute_force_hamiltonian(spins: np.ndarray, coupling: float) -> float:
    length = spins.shape[0]
    bond_sum = 0
    for x, y in itertools.product(range(length), repeat=2):
        bond_sum += int(spins[x, y] * spins[(x + 1) % length, y])
        bond_sum += int(spins[x, y] * spins[x, (y + 1) % length])
    return -coupling * bond_sum


def test_periodic_neighbors() -> None:
    assert periodic_neighbors(0, 0, 4) == ((3, 0), (1, 0), (0, 3), (0, 1))
    assert periodic_neighbors(3, 2, 4) == ((2, 2), (0, 2), (3, 1), (3, 3))


def test_ising_energy_against_bruteforce() -> None:
    rng = np.random.default_rng(20260801)
    for length in (2, 3, 4):
        spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length, length))
        assert ising_hamiltonian(spins, 0.436) == brute_force_hamiltonian(
            spins, 0.436
        )


def test_delta_energy_matches_full_recompute() -> None:
    rng = np.random.default_rng(20260802)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(7, 7))
    before = ising_hamiltonian(spins, 0.436)
    for x, y in ((0, 0), (3, 4), (6, 6)):
        delta = delta_hamiltonian(spins, x, y, 0.436)
        trial = spins.copy()
        trial[x, y] *= -1
        assert abs((ising_hamiltonian(trial, 0.436) - before) - delta) < 1e-12
