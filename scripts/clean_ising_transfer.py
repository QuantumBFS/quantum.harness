#!/usr/bin/env python3
"""Exact matrix-free row transfer operator for the clean 2D Ising model."""

import math

import numpy as np
from scipy.sparse.linalg import LinearOperator


def critical_coupling():
    """Return the isotropic square-lattice Ising critical coupling."""
    return 0.5 * math.log(1.0 + math.sqrt(2.0))


def _periodic_row_energies(L):
    """Return sum_i sigma_i sigma_(i+1) for every bit-encoded row."""
    states = np.arange(1 << L, dtype=np.uint64)
    domain_walls = np.zeros(states.size, dtype=np.int16)
    for site in range(L):
        neighbor = (site + 1) % L
        different = ((states >> site) ^ (states >> neighbor)) & 1
        domain_walls += different.astype(np.int16)
    return L - 2 * domain_walls


class IsingTransferOperator(LinearOperator):
    """Symmetric clean-Ising transfer operator without dense materialization."""

    def __init__(self, L, kx, ktau):
        if L < 2:
            raise ValueError("L must be at least 2")
        self.L = int(L)
        self.dimension = 1 << self.L
        self.kx = float(kx)
        self.ktau = float(ktau)

        row_energies = _periodic_row_energies(self.L)
        self._dhalf = np.exp(0.5 * self.kx * row_energies)
        self._parallel = math.exp(self.ktau)
        self._antiparallel = math.exp(-self.ktau)
        super().__init__(dtype=np.dtype(np.float64), shape=(self.dimension, self.dimension))

    def _matvec(self, vector):
        vector = np.asarray(vector, dtype=np.float64)
        source = self._dhalf * vector
        target = np.empty_like(source)

        for site in range(self.L):
            stride = 1 << site
            source_blocks = source.reshape(-1, 2, stride)
            target_blocks = target.reshape(-1, 2, stride)
            lower = source_blocks[:, 0, :]
            upper = source_blocks[:, 1, :]
            target_blocks[:, 0, :] = (
                self._parallel * lower + self._antiparallel * upper
            )
            target_blocks[:, 1, :] = (
                self._antiparallel * lower + self._parallel * upper
            )
            source, target = target, source

        source *= self._dhalf
        return source
