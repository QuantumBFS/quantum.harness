from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.linalg
import scipy.sparse as sp

from .model import obc_bonds
from .symmetry_ed import sector_basis


@dataclass(frozen=True)
class SectorSpectrum:
    eigenvalues: np.ndarray
    matrix_dimension: int
    recovered_dimension: int
    spectral_multiplicity: int
    hermiticity_residual: float


def tfim_sparse(l: int, *, j: float, h: float) -> sp.csr_matrix:
    nsites = l * l
    dimension = 1 << nsites
    bonds = obc_bonds(l, l)
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for state in range(dimension):
        diagonal = 0.0
        for left, right in bonds:
            same = ((state >> left) & 1) == ((state >> right) & 1)
            diagonal += -j if same else j
        rows.append(state)
        columns.append(state)
        values.append(diagonal)
        for site in range(nsites):
            rows.append(state ^ (1 << site))
            columns.append(state)
            values.append(-h)
    return sp.csr_matrix(
        (values, (rows, columns)),
        shape=(dimension, dimension),
    )


def _validated_symmetric(
    projected: np.ndarray,
) -> tuple[np.ndarray, float]:
    scale = max(float(np.linalg.norm(projected)), 1.0)
    residual = float(np.linalg.norm(projected - projected.T) / scale)
    if not np.isfinite(residual) or residual > 1e-12:
        raise FloatingPointError(
            f"non-Hermitian sector projection: {residual}"
        )
    return 0.5 * (projected + projected.T), residual


def sector_matrix(
    l: int,
    *,
    j: float,
    h: float,
    irrep: str,
    parity: int,
    e_reflection: int = 1,
):
    basis = sector_basis(
        l,
        irrep,
        parity,
        e_reflection=e_reflection,
    )
    projected = (
        basis.q.T @ tfim_sparse(l, j=j, h=h) @ basis.q
    ).toarray()
    matrix, residual = _validated_symmetric(projected)
    return matrix, basis, residual


def sector_eigenvalues(
    l: int,
    *,
    j: float,
    h: float,
    irrep: str,
    parity: int,
    e_reflection: int = 1,
) -> SectorSpectrum:
    matrix, basis, residual = sector_matrix(
        l,
        j=j,
        h=h,
        irrep=irrep,
        parity=parity,
        e_reflection=e_reflection,
    )
    eigenvalues = scipy.linalg.eigvalsh(
        matrix,
        overwrite_a=True,
        check_finite=False,
        driver="evd",
    )
    if not np.isfinite(eigenvalues).all():
        raise FloatingPointError("eigensolver returned non-finite values")
    return SectorSpectrum(
        eigenvalues,
        matrix.shape[0],
        basis.recovered_dimension,
        basis.spectral_multiplicity,
        residual,
    )
