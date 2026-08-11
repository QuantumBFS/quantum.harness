"""Exact critical transverse-field Ising Casimir calibration."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .fits import CasimirFit, casimir_gls


def critical_ground_energy(lengths: ArrayLike) -> NDArray[np.float64]:
    r"""Return the Neveu--Schwarz vacuum energy for even periodic widths."""

    sizes = np.asarray(lengths, dtype=int)
    if np.any(sizes < 2) or np.any(sizes % 2):
        raise ValueError("critical Ising benchmark requires even L >= 2")
    return -2.0 / np.sin(np.pi / (2.0 * sizes))


def fit_clean_ising(
    lengths: ArrayLike, *, velocity: float = 2.0
) -> CasimirFit:
    """Fit the exact vacuum energies with the declared sound velocity."""

    if velocity <= 0.0:
        raise ValueError("velocity must be positive")
    sizes = np.asarray(lengths, dtype=float)
    energies = critical_ground_energy(sizes.astype(int))
    covariance = np.eye(sizes.size) * 1e-20
    return casimir_gls(
        sizes,
        energies,
        covariance,
        alpha=velocity,
        include_l3=True,
    )
