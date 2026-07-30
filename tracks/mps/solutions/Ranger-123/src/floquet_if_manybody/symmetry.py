"""Exact Hilbert-space symmetry sectors for N=2 and N=3."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .operators import ComplexMatrix, swap_operator


@dataclass(frozen=True)
class Sector:
    name: str
    isometry: ComplexMatrix

    def __post_init__(self) -> None:
        gram = self.isometry.conj().T @ self.isometry
        if not np.allclose(gram, np.eye(gram.shape[0]), atol=1e-13):
            raise ValueError(f"{self.name} isometry is not orthonormal")

    @property
    def dimension(self) -> int:
        return int(self.isometry.shape[1])


def _eigenspace(operator: ComplexMatrix, eigenvalue: float, name: str) -> Sector:
    values, vectors = np.linalg.eigh(operator)
    selected = vectors[:, np.isclose(values, eigenvalue, atol=1e-12)]
    return Sector(name, selected)


def n2_sectors() -> tuple[Sector, Sector]:
    swap = swap_operator(0, 1, 2)
    singlet = _eigenspace(swap, -1, "singlet")
    triplet = _eigenspace(swap, +1, "triplet")
    return singlet, triplet


def n3_reflection_sectors() -> tuple[Sector, Sector]:
    reflection = swap_operator(0, 2, 3)
    odd = _eigenspace(reflection, -1, "odd")
    even = _eigenspace(reflection, +1, "even")
    return odd, even


def project(operator: ComplexMatrix, sector: Sector) -> ComplexMatrix:
    if operator.shape[0] != sector.isometry.shape[0]:
        raise ValueError("operator and sector dimensions do not match")
    return sector.isometry.conj().T @ operator @ sector.isometry


def cross_project(
    operator: ComplexMatrix, left: Sector, right: Sector
) -> NDArray[np.complex128]:
    return left.isometry.conj().T @ operator @ right.isometry


def sector_residual(operator: ComplexMatrix, sector: Sector) -> float:
    identity = np.eye(operator.shape[0], dtype=np.complex128)
    projector = sector.isometry @ sector.isometry.conj().T
    return float(np.linalg.norm((identity - projector) @ operator @ sector.isometry))
