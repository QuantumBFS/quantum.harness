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


@dataclass(frozen=True)
class MultipletReport:
    total_l: int
    m_values: tuple[int, ...]
    energies: tuple[float, ...]
    l2_expectations: tuple[float, ...]
    energy_spread: float
    rotation_equivariance_error: float


def _rotation_equivariance_error(
    bases: list[FockBasis], vectors: list[np.ndarray], total_l: int
) -> float:
    """Check a generic-axis rotation against the exact spin-L representation."""

    dimensions = [basis.dimension for basis in bases]
    offsets = np.cumsum([0, *dimensions])
    total_dimension = int(offsets[-1])
    n_members = 2 * total_l + 1
    embedding = np.zeros((total_dimension, n_members), dtype=np.complex128)
    for column, vector in enumerate(vectors):
        embedding[offsets[column] : offsets[column + 1], column] = vector

    lowering = sparse.lil_matrix(
        (total_dimension, total_dimension), dtype=np.complex128
    )
    for column in range(n_members - 1):
        block = angular_momentum_lowering(bases[column], bases[column + 1])
        lowering[
            offsets[column + 1] : offsets[column + 2],
            offsets[column] : offsets[column + 1],
        ] = block
    lowering = lowering.tocsr()
    raising = lowering.getH()
    m_values = np.arange(total_l, -total_l - 1, -1, dtype=float)
    actual_z = sparse.diags(
        np.concatenate(
            [np.full(dimension, m) for dimension, m in zip(dimensions, m_values)]
        ),
        format="csr",
    )
    actual_x = 0.5 * (raising + lowering)
    actual_y = -0.5j * (raising - lowering)

    spin_lowering = np.zeros((n_members, n_members), dtype=np.complex128)
    for column, m in enumerate(m_values[:-1]):
        spin_lowering[column + 1, column] = np.sqrt(
            (total_l + m) * (total_l - m + 1)
        )
    spin_raising = spin_lowering.conjugate().T
    spin_x = 0.5 * (spin_raising + spin_lowering)
    spin_y = -0.5j * (spin_raising - spin_lowering)
    spin_z = np.diag(m_values)

    axis = np.asarray([1.0, 2.0, 3.0])
    axis /= np.linalg.norm(axis)
    angle = 0.371
    actual_generator = axis[0] * actual_x + axis[1] * actual_y + axis[2] * actual_z
    spin_generator = axis[0] * spin_x + axis[1] * spin_y + axis[2] * spin_z
    coefficients = np.arange(1, n_members + 1) + 1j * np.arange(n_members, 0, -1)
    coefficients = coefficients / np.linalg.norm(coefficients)
    rotated_actual = sparse_linalg.expm_multiply(
        -1j * angle * actual_generator, embedding @ coefficients
    )
    rotated_expected = embedding @ (
        linalg.expm(-1j * angle * spin_generator) @ coefficients
    )
    return float(np.linalg.norm(rotated_actual - rotated_expected))


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
    rotation_error = _rotation_equivariance_error(bases, vectors, total_l)
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
