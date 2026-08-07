from __future__ import annotations

import numpy as np

from .ising import validate_spins


def block_sums(spins: np.ndarray, block_size: int = 3) -> np.ndarray:
    validate_spins(spins)
    length = spins.shape[0]
    if block_size <= 0 or block_size % 2 == 0:
        raise ValueError("block_size must be a positive odd integer")
    if length % block_size != 0:
        raise ValueError("lattice length must be divisible by block_size")
    coarse = length // block_size
    reshaped = spins.reshape(coarse, block_size, coarse, block_size)
    return reshaped.sum(axis=(1, 3), dtype=np.int64)


def block_majority(spins: np.ndarray, block_size: int = 3) -> np.ndarray:
    sums = block_sums(spins, block_size)
    if np.any(sums == 0):
        raise AssertionError("odd blocks cannot have a tied majority")
    return np.where(sums > 0, 1, -1).astype(np.int8)
