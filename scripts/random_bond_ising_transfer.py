#!/usr/bin/env python3
"""Matrix-free spin-basis row transfers for the bimodal random-bond Ising model."""

import math

import numpy as np


def nishimori_coupling(p):
    """Return K on the Nishimori line for Pr(J=-1)=p."""
    p = float(p)
    if not 0.0 < p < 0.5:
        raise ValueError("p must satisfy 0 < p < 0.5")
    return 0.5 * math.log((1.0 - p) / p)


def periodic_spin_products(L):
    """Return sigma_i sigma_(i+1) for every bit-encoded periodic row."""
    L = int(L)
    if L < 2:
        raise ValueError("L must be at least 2")
    states = np.arange(1 << L, dtype=np.uint64)
    products = np.empty((L, states.size), dtype=np.int8)
    for site in range(L):
        neighbor = (site + 1) % L
        different = ((states >> site) ^ (states >> neighbor)) & 1
        products[site] = 1 - 2 * different.astype(np.int8)
    return products


class RandomBondRowTransfer:
    """Apply one fixed-disorder transfer row without forming its dense matrix."""

    def __init__(self, L, coupling):
        self.L = int(L)
        self.spin_products = periodic_spin_products(self.L)
        self.dimension = 1 << self.L
        self.coupling = float(coupling)
        if not math.isfinite(self.coupling):
            raise ValueError("coupling must be finite")

    def apply(self, vector, horizontal_bonds, vertical_bonds):
        """Return T(horizontal_bonds, vertical_bonds) @ vector."""
        vector = np.asarray(vector, dtype=np.float64)
        horizontal_bonds = np.asarray(horizontal_bonds, dtype=np.int8)
        vertical_bonds = np.asarray(vertical_bonds, dtype=np.int8)
        if vector.shape != (self.dimension,):
            raise ValueError("vector has the wrong dimension")
        if horizontal_bonds.shape != (self.L,) or vertical_bonds.shape != (self.L,):
            raise ValueError("bond arrays must have shape (L,)")
        if not np.all(np.isin(horizontal_bonds, (-1, 1))) or not np.all(
            np.isin(vertical_bonds, (-1, 1))
        ):
            raise ValueError("bond signs must be +/-1")

        source = vector.copy()
        target = np.empty_like(source)
        for site, sign in enumerate(vertical_bonds):
            parallel = math.exp(self.coupling * int(sign))
            antiparallel = math.exp(-self.coupling * int(sign))
            stride = 1 << site
            source_blocks = source.reshape(-1, 2, stride)
            target_blocks = target.reshape(-1, 2, stride)
            lower = source_blocks[:, 0, :]
            upper = source_blocks[:, 1, :]
            target_blocks[:, 0, :] = parallel * lower + antiparallel * upper
            target_blocks[:, 1, :] = antiparallel * lower + parallel * upper
            source, target = target, source

        horizontal_energy = horizontal_bonds @ self.spin_products
        source *= np.exp(self.coupling * horizontal_energy)
        return source
