#!/usr/bin/env python3
"""Matrix-free spin-basis row transfers for the bimodal random-bond Ising model."""

import math
import time

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


def sample_bond_signs(rng, L, p):
    """Sample independent +/-1 bonds using p as the antiferromagnetic fraction."""
    return np.where(rng.random(int(L)) < float(p), -1, 1).astype(np.int8)


def run_random_strip(
    L,
    p,
    seed,
    burn_in,
    retained_rows,
    block_length,
    progress=True,
):
    """Estimate the leading Lyapunov exponent of an IID random transfer strip."""
    L = int(L)
    burn_in = int(burn_in)
    retained_rows = int(retained_rows)
    block_length = int(block_length)
    if burn_in < 0 or retained_rows <= 0 or block_length <= 0:
        raise ValueError("row counts must be positive and burn_in nonnegative")
    if retained_rows % block_length:
        raise ValueError("retained_rows must be a multiple of block_length")

    coupling = nishimori_coupling(p)
    operator = RandomBondRowTransfer(L, coupling)
    rng = np.random.default_rng(seed)
    vector = np.ones(operator.dimension, dtype=np.float64)
    vector /= np.linalg.norm(vector)
    block_means = []
    block_sum = 0.0
    retained = 0
    started = time.perf_counter()

    for row in range(burn_in + retained_rows):
        horizontal = sample_bond_signs(rng, L, p)
        vertical = sample_bond_signs(rng, L, p)
        vector = operator.apply(vector, horizontal, vertical)
        norm = float(np.linalg.norm(vector))
        if not math.isfinite(norm) or norm <= 0.0:
            raise RuntimeError(f"invalid transfer norm at row {row}")
        vector /= norm
        if row < burn_in:
            continue

        block_sum += math.log(norm)
        retained += 1
        if retained % block_length == 0:
            block_means.append(block_sum / block_length)
            block_sum = 0.0
            if progress:
                print(
                    f"L={L}: block={len(block_means)}, "
                    f"Lambda0={np.mean(block_means):.10f}",
                    flush=True,
                )

    runtime_seconds = time.perf_counter() - started
    blocks = np.asarray(block_means, dtype=float)
    lyapunov = float(np.mean(blocks))
    lyapunov_se = (
        float(np.std(blocks, ddof=1) / math.sqrt(len(blocks)))
        if len(blocks) > 1
        else math.nan
    )
    return {
        "L": L,
        "p": float(p),
        "coupling": coupling,
        "seed": int(seed),
        "burn_in": burn_in,
        "retained_rows": retained_rows,
        "block_length": block_length,
        "block_log_norm_means": blocks,
        "lyapunov": lyapunov,
        "lyapunov_se": lyapunov_se,
        "free_energy": -lyapunov / L,
        "free_energy_se": lyapunov_se / L,
        "runtime_seconds": runtime_seconds,
        "rows_per_second": (burn_in + retained_rows) / runtime_seconds,
    }
