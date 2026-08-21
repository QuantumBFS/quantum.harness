from __future__ import annotations

import numpy as np


def site_index(x: int, y: int, ly: int) -> int:
    return x * ly + y


def obc_bonds(lx: int, ly: int) -> tuple[tuple[int, int], ...]:
    horizontal = tuple(
        (site_index(x, y, ly), site_index(x + 1, y, ly))
        for x in range(lx - 1)
        for y in range(ly)
    )
    vertical = tuple(
        (site_index(x, y, ly), site_index(x, y + 1, ly))
        for x in range(lx)
        for y in range(ly - 1)
    )
    return horizontal + vertical


def tfim_dense(lx: int, ly: int, *, j: float, h: float) -> np.ndarray:
    nsites = lx * ly
    if nsites > 9:
        raise ValueError("dense oracle is restricted to at most 9 sites")
    dim = 1 << nsites
    matrix = np.zeros((dim, dim), dtype=np.float64)
    bonds = obc_bonds(lx, ly)
    for state in range(dim):
        spins = tuple(1 if state & (1 << i) else -1 for i in range(nsites))
        matrix[state, state] = -j * sum(
            spins[i] * spins[k] for i, k in bonds
        )
        for i in range(nsites):
            matrix[state ^ (1 << i), state] -= h
    return matrix


def global_spin_flip(nsites: int) -> np.ndarray:
    dim = 1 << nsites
    mask = dim - 1
    matrix = np.zeros((dim, dim), dtype=np.float64)
    for state in range(dim):
        matrix[state ^ mask, state] = 1.0
    return matrix
