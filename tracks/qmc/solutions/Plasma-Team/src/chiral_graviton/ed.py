"""Symmetry-resolved exact diagonalization for the chiral-graviton gap."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import linalg, sparse
from scipy.sparse import linalg as sparse_linalg

from .angular_momentum import highest_weight_basis, l2_operator
from .basis import FockBasis, SphereSystem
from .hamiltonian import build_hamiltonian, relative_hermiticity_error
from .interactions import (
    PairTable,
    coulomb_pseudopotentials,
    pair_matrix_elements,
    v1_pseudopotentials,
)


@dataclass(frozen=True)
class FixedLSpectrum:
    total_l: int
    energy: float
    vector: np.ndarray
    basis: FockBasis
    highest_weight_map: np.ndarray
    residual_norm: float
    l2_expectation: float


@dataclass(frozen=True)
class GapResult:
    n_electrons: int
    two_q: int
    interaction: str
    e_l0: float
    e_l2: float
    gap: float
    l2_excited: float
    residual_l0: float
    residual_l2: float
    dimension_lz0: int
    dimension_lz2: int
    energy_unit: str = "e^2/(epsilon*l_B)"

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def interaction_pair_table(system: SphereSystem, interaction: str) -> PairTable:
    if interaction == "v1":
        pseudo = v1_pseudopotentials(system.two_q)
    elif interaction == "coulomb":
        pseudo = coulomb_pseudopotentials(system.two_q)
    else:
        raise ValueError(f"unknown interaction: {interaction}")
    return pair_matrix_elements(system.two_q, pseudo)


def _smallest_eigenpair(matrix: np.ndarray | sparse.spmatrix) -> tuple[float, np.ndarray]:
    dimension = matrix.shape[0]
    if dimension == 0:
        raise ValueError("CG002: empty total-L sector")
    if dimension <= 64 or not sparse.issparse(matrix):
        dense = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
        values, vectors = linalg.eigh(dense, subset_by_index=(0, 0))
        return float(values[0]), np.asarray(vectors[:, 0])
    values, vectors = sparse_linalg.eigsh(matrix, k=1, which="SA", tol=1e-11)
    return float(values[0]), np.asarray(vectors[:, 0])


def solve_fixed_l(
    system: SphereSystem,
    total_l: int,
    interaction: str = "coulomb",
    *,
    pair_table: PairTable | None = None,
    projection_threshold: int = 2500,
) -> FixedLSpectrum:
    """Solve the lowest state of exact total angular momentum ``total_l``."""

    if total_l < 0:
        raise ValueError("total_l must be non-negative")
    basis = FockBasis(system, two_lz=2 * total_l)
    if basis.dimension == 0:
        raise ValueError("CG002: requested Lz sector is empty")
    table = pair_table or interaction_pair_table(system, interaction)
    hamiltonian = build_hamiltonian(basis, table)
    hermiticity = relative_hermiticity_error(hamiltonian)
    if hermiticity > 1e-10:
        raise ValueError(f"CG003: Hamiltonian Hermiticity error {hermiticity:.3e}")

    l2 = l2_operator(basis)
    if basis.dimension <= projection_threshold:
        highest = highest_weight_basis(basis)
        projected = highest.T @ (hamiltonian @ highest)
        projected = 0.5 * (projected + projected.T)
        energy, reduced_vector = _smallest_eigenpair(projected)
        vector = highest @ reduced_vector
        vector /= np.linalg.norm(vector)
    else:
        # Dense null-space construction scales cubically and becomes the ED
        # bottleneck near N=8. In the M=L sector no total angular momentum
        # below L is present, so adding a positive L^2 penalty selects the
        # desired irrep without changing its physical energy.
        target_l2 = float(total_l * (total_l + 1))
        identity = sparse.identity(basis.dimension, dtype=np.float64, format="csr")
        penalty_strength = 10.0
        effective = hamiltonian + penalty_strength * (l2 - target_l2 * identity)
        _, vector = _smallest_eigenpair(effective)
        vector /= np.linalg.norm(vector)
        energy = float(vector @ (hamiltonian @ vector))
        highest = np.empty((basis.dimension, 0), dtype=np.float64)
    residual = float(np.linalg.norm(hamiltonian @ vector - energy * vector))
    l2_expectation = float(np.real(vector.conjugate() @ (l2 @ vector)))
    if abs(l2_expectation - total_l * (total_l + 1)) > 1e-7:
        raise ValueError(
            f"CG004: fixed-L solver returned <L^2>={l2_expectation:.12g} for L={total_l}"
        )
    return FixedLSpectrum(
        total_l=total_l,
        energy=energy,
        vector=vector,
        basis=basis,
        highest_weight_map=highest,
        residual_norm=residual,
        l2_expectation=l2_expectation,
    )


def neutral_gap(system: SphereSystem, interaction: str = "coulomb") -> GapResult:
    """Compute E(L=2)-E(L=0) with a shared interaction table."""

    pair_table = interaction_pair_table(system, interaction)
    ground = solve_fixed_l(system, 0, interaction, pair_table=pair_table)
    graviton = solve_fixed_l(system, 2, interaction, pair_table=pair_table)
    return GapResult(
        n_electrons=system.n_electrons,
        two_q=system.two_q,
        interaction=interaction,
        e_l0=ground.energy,
        e_l2=graviton.energy,
        gap=graviton.energy - ground.energy,
        l2_excited=graviton.l2_expectation,
        residual_l0=ground.residual_norm,
        residual_l2=graviton.residual_norm,
        dimension_lz0=ground.basis.dimension,
        dimension_lz2=graviton.basis.dimension,
    )
