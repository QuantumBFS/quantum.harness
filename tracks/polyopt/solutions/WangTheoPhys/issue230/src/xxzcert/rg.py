"""Verified linear-algebra primitives for MPS-guided RG compression.

This module constructs the compression maps used by the later RG relaxation.
It intentionally does not claim that projecting a Hamiltonian alone is a
lower-bound method; sound lower bounds require these maps inside an outer
semidefinite relaxation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .model import reduced_density
from .upper import UpperCandidate


@dataclass(frozen=True)
class RGMap:
    block_sites: int
    kept_dimension: int
    isometry: NDArray[np.complex128]
    discarded_weight: float
    isometry_residual: float

    def compress_operator(self, operator: NDArray[np.complex128]) -> NDArray[np.complex128]:
        expected = 1 << self.block_sites
        if operator.shape != (expected, expected):
            raise ValueError("operator dimension does not match RG block")
        return self.isometry.conj().T @ operator @ self.isometry

    def lift_state(self, coarse_state: NDArray[np.complex128]) -> NDArray[np.complex128]:
        if coarse_state.shape != (self.kept_dimension, self.kept_dimension):
            raise ValueError("coarse state dimension mismatch")
        return self.isometry @ coarse_state @ self.isometry.conj().T


def build_density_guided_rg_map(
    candidate: UpperCandidate, block_sites: int, kept_dimension: int
) -> RGMap:
    """Build an isometry from the dominant block-RDM eigenvectors."""
    if block_sites < 1 or block_sites > candidate.sites:
        raise ValueError("invalid RG block size")
    physical_dimension = 1 << block_sites
    if kept_dimension < 1 or kept_dimension > physical_dimension:
        raise ValueError("invalid kept dimension")
    start = (candidate.sites - block_sites) // 2
    keep = tuple(range(start, start + block_sites))
    rho = reduced_density(candidate.state, keep, candidate.sites)
    eigenvalues, eigenvectors = np.linalg.eigh((rho + rho.conj().T) / 2)
    order = np.argsort(eigenvalues)[::-1]
    selected = order[:kept_dimension]
    isometry = np.asarray(eigenvectors[:, selected], dtype=np.complex128)
    retained = float(np.maximum(eigenvalues[selected], 0).sum())
    residual = float(
        np.linalg.norm(
            isometry.conj().T @ isometry - np.eye(kept_dimension), ord=2
        )
    )
    return RGMap(
        block_sites=block_sites,
        kept_dimension=kept_dimension,
        isometry=isometry,
        discarded_weight=max(0.0, 1.0 - retained),
        isometry_residual=residual,
    )


def verify_rg_map(rg_map: RGMap, tolerance: float = 1e-12) -> bool:
    if rg_map.isometry.shape != (
        1 << rg_map.block_sites,
        rg_map.kept_dimension,
    ):
        return False
    gram = rg_map.isometry.conj().T @ rg_map.isometry
    return bool(
        np.linalg.norm(gram - np.eye(rg_map.kept_dimension), ord=2)
        <= tolerance
    )
