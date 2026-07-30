"""Spin, multiplet, and helicity-resolved observables."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import linalg, sparse
from scipy.sparse import linalg as sparse_linalg

from .angular_momentum import angular_momentum_lowering, l2_operator
from .basis import FockBasis
from .hamiltonian import build_hamiltonian
from .interactions import PairTable
from .rotation_equivariance import rotation_equivariance_error


@dataclass(frozen=True)
class MultipletReport:
    total_l: int
    m_values: tuple[int, ...]
    energies: tuple[float, ...]
    l2_expectations: tuple[float, ...]
    energy_spread: float
    rotation_equivariance_error: float


def multiplet_report(
    highest_basis: FockBasis,
    highest_vector: np.ndarray,
    total_l: int,
    pair_table: PairTable,
) -> MultipletReport:
    """Generate an SO(3) multiplet by repeated exact lowering."""

    if highest_basis.two_lz != 2 * total_l:
        raise ValueError("input must be the M=L highest-weight sector")
    basis = highest_basis
    vector = np.asarray(highest_vector, dtype=np.complex128)
    vector /= np.linalg.norm(vector)
    energies: list[float] = []
    l2_values: list[float] = []
    m_values: list[int] = []
    bases: list[FockBasis] = []
    vectors: list[np.ndarray] = []

    for m in range(total_l, -total_l - 1, -1):
        hamiltonian = build_hamiltonian(basis, pair_table)
        energies.append(float(np.real(vector.conjugate() @ (hamiltonian @ vector))))
        l2 = l2_operator(basis)
        l2_values.append(float(np.real(vector.conjugate() @ (l2 @ vector))))
        m_values.append(m)
        bases.append(basis)
        vectors.append(vector.copy())
        if m == -total_l:
            break
        target = FockBasis(basis.system, basis.two_lz - 2)
        lowering = angular_momentum_lowering(basis, target)
        vector = lowering @ vector
        expected_norm = np.sqrt((total_l + m) * (total_l - m + 1))
        vector /= expected_norm
        basis = target

    spread = max(energies) - min(energies)
    rotation_error = rotation_equivariance_error(bases, vectors, total_l)
    return MultipletReport(
        total_l,
        tuple(m_values),
        tuple(energies),
        tuple(l2_values),
        spread,
        rotation_error,
    )


def transition_weight(initial: np.ndarray, final: np.ndarray, operator) -> float:
    """Return |<final|operator|initial>|^2 for a supplied metric operator."""

    amplitude = np.asarray(final).conjugate() @ (operator @ np.asarray(initial))
    return float(abs(amplitude) ** 2)


def chirality_ratio(bright_weight: float, dark_weight: float) -> float:
    """Return bright/dark weight, using infinity for an exactly dark channel."""

    if bright_weight < 0.0 or dark_weight < 0.0:
        raise ValueError("spectral weights must be non-negative")
    if dark_weight == 0.0:
        return float("inf") if bright_weight > 0.0 else 0.0
    return bright_weight / dark_weight
