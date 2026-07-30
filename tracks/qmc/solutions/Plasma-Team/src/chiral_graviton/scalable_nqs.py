"""Sparse, certified SO(3) projection for enumerated neural quantum states.

The original :mod:`chiral_graviton.nqs` implementation constructs an explicit
dense basis for ``ker(L_+)``.  This module implements the same orthogonal
projector without constructing that basis.  For ``A=L_+`` it applies

    P = I - A^T (A A^T)^(-1) A

with sparse matrix-vector products and conjugate gradients.
In the ``M=L`` sector, ``A`` is onto the ``M=L+1`` sector (each latter SO(3)
irrep has a nonzero lowering partner), so ``A A^T`` is positive definite.
Consequently the expression above is exactly the projector onto total angular
momentum ``L`` in exact arithmetic.

This removes the quadratic/cubic storage/work of a dense null-space
factorization.  It deliberately does *not* claim to remove fixed-M Fock-space
enumeration: amplitudes and exact iid |psi|^2 sampling still scale with that
sector's dimension.  It is therefore an N=8--9 bridge, not a thermodynamic-VMC
sampler.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse import linalg as sparse_linalg

from .angular_momentum import angular_momentum_raising
from .basis import FockBasis, SphereSystem
from .ed import interaction_pair_table
from .hamiltonian import build_hamiltonian
from .nqs import SharedProjectedMLP


@dataclass(frozen=True)
class ProjectionCertificate:
    """Numerical certificate for one highest-weight projection.

    For a normalized vector in ``M=L``, ``raising_residual**2`` is exactly
    ``<L^2>-L(L+1)`` (up to floating-point roundoff), rather than merely a
    heuristic symmetry score.
    """

    raising_residual: float
    l2_excess: float
    cg_iterations: int
    refinement_steps: int


class SparseHighestWeightProjector:
    """Orthogonal ``ker(L_+)`` projector with no dense highest-weight basis."""

    def __init__(
        self,
        source: FockBasis,
        *,
        solver_tolerance: float = 2e-13,
        certificate_tolerance: float = 2e-10,
        max_refinements: int = 3,
    ) -> None:
        if source.two_lz < 0:
            raise ValueError("highest-weight projection requires M>=0")
        if solver_tolerance <= 0.0 or certificate_tolerance <= 0.0:
            raise ValueError("projection tolerances must be positive")
        if max_refinements < 1:
            raise ValueError("max_refinements must be positive")

        self.source = source
        self.target = FockBasis(source.system, source.two_lz + 2)
        self.raising = angular_momentum_raising(source, self.target)
        self.solver_tolerance = float(solver_tolerance)
        self.certificate_tolerance = float(certificate_tolerance)
        self.max_refinements = int(max_refinements)

        # Representation theory gives rank(A)=dim(target) for M>=0.  Checking
        # dimensions catches requests for an empty highest-weight sector.
        self.kernel_dimension = source.dimension - self.target.dimension
        if self.kernel_dimension <= 0:
            raise ValueError("requested total-L highest-weight sector is empty")

        if self.target.dimension:
            shape = (self.target.dimension, self.target.dimension)
            self._normal = sparse_linalg.LinearOperator(
                shape,
                matvec=lambda value: self.raising @ (self.raising.T @ value),
                rmatvec=lambda value: self.raising @ (self.raising.T @ value),
                dtype=np.float64,
            )
        else:
            self._normal = None

        # In exact arithmetic CG terminates after at most the number of
        # distinct J sectors, bounded by the maximum many-body L plus one.
        n = source.system.n_electrons
        two_q = source.system.two_q
        maximum_l = (n * two_q - n * (n - 1)) // 2
        total_l = source.two_lz // 2
        self.max_iterations = max(64, 4 * (maximum_l - total_l + 1))

    @property
    def sparse_storage_bytes(self) -> int:
        """Bytes occupied by the CSR representation of L_+ (approximately)."""

        matrix = self.raising
        return int(matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes)

    @property
    def avoided_dense_basis_bytes(self) -> int:
        """Bytes an explicit float64 null-space basis would require."""

        return int(8 * self.source.dimension * self.kernel_dimension)

    def project_with_certificate(
        self, raw_vector: np.ndarray
    ) -> tuple[np.ndarray, ProjectionCertificate]:
        """Project a vector and return a directly checkable symmetry certificate."""

        vector = np.asarray(raw_vector, dtype=np.float64)
        if vector.shape != (self.source.dimension,):
            raise ValueError("raw vector has the wrong shape")
        if not np.all(np.isfinite(vector)):
            raise ValueError("raw vector contains non-finite values")
        if self.target.dimension == 0:
            return vector.copy(), ProjectionCertificate(0.0, 0.0, 0, 0)

        projected = vector.copy()
        total_iterations = 0
        refinements = 0
        for refinements in range(1, self.max_refinements + 1):
            right_hand_side = np.asarray(self.raising @ projected).ravel()
            projected_norm = float(np.linalg.norm(projected))
            residual = float(np.linalg.norm(right_hand_side)) / max(projected_norm, 1e-300)
            if residual <= self.certificate_tolerance:
                refinements -= 1
                break

            iteration_count = 0

            def count_iteration(_: np.ndarray) -> None:
                nonlocal iteration_count
                iteration_count += 1

            solution, info = sparse_linalg.cg(
                self._normal,
                right_hand_side,
                rtol=self.solver_tolerance,
                atol=0.0,
                maxiter=self.max_iterations,
                callback=count_iteration,
            )
            total_iterations += iteration_count
            if info != 0:
                raise FloatingPointError(
                    f"sparse highest-weight projection CG failed (info={info})"
                )
            projected -= np.asarray(self.raising.T @ solution).ravel()

        norm = float(np.linalg.norm(projected))
        raising_residual = (
            float(np.linalg.norm(self.raising @ projected) / norm) if norm > 0.0 else 0.0
        )
        if raising_residual > self.certificate_tolerance:
            raise FloatingPointError(
                "uncertified highest-weight projection: "
                f"||L_+ psi||/||psi||={raising_residual:.3e}"
            )
        certificate = ProjectionCertificate(
            raising_residual=raising_residual,
            l2_excess=raising_residual**2,
            cg_iterations=total_iterations,
            refinement_steps=refinements,
        )
        return projected, certificate

    def project(self, raw_vector: np.ndarray) -> np.ndarray:
        """Apply the certified orthogonal projector."""

        return self.project_with_certificate(raw_vector)[0]


@dataclass(frozen=True)
class SparseProjectedSector:
    """One fixed-M sector using a sparse highest-weight projector."""

    total_l: int
    basis: FockBasis
    hamiltonian: sparse.csr_matrix
    projector: SparseHighestWeightProjector
    features: np.ndarray

    @classmethod
    def build(
        cls,
        system: SphereSystem,
        total_l: int,
        interaction: str,
        *,
        pair_table=None,
        solver_tolerance: float = 2e-13,
        certificate_tolerance: float = 2e-10,
    ) -> SparseProjectedSector:
        basis = FockBasis(system, two_lz=2 * total_l)
        projector = SparseHighestWeightProjector(
            basis,
            solver_tolerance=solver_tolerance,
            certificate_tolerance=certificate_tolerance,
        )
        table = pair_table or interaction_pair_table(system, interaction)
        hamiltonian = build_hamiltonian(basis, table)
        occupancy = basis.occupancy_matrix()
        features = occupancy - system.n_electrons / system.n_orbitals
        return cls(total_l, basis, hamiltonian, projector, features)

    def project(self, raw_vector: np.ndarray) -> np.ndarray:
        return self.projector.project(raw_vector)


class SparseProjectedMLP(SharedProjectedMLP):
    """Shared MLP with certified sparse SO(3) projection.

    The neural ansatz and analytic variational gradient are inherited from
    :class:`SharedProjectedMLP`; only the dense null-space representation is
    replaced.  No ED eigenvector enters initialization, projection, or
    optimization.
    """

    @classmethod
    def build(
        cls,
        system: SphereSystem,
        interaction: str = "coulomb",
        *,
        hidden_width: int = 24,
        seed: int = 1729,
        solver_tolerance: float = 2e-13,
        certificate_tolerance: float = 2e-10,
    ) -> SparseProjectedMLP:
        table = interaction_pair_table(system, interaction)
        ground = SparseProjectedSector.build(
            system,
            0,
            interaction,
            pair_table=table,
            solver_tolerance=solver_tolerance,
            certificate_tolerance=certificate_tolerance,
        )
        graviton = SparseProjectedSector.build(
            system,
            2,
            interaction,
            pair_table=table,
            solver_tolerance=solver_tolerance,
            certificate_tolerance=certificate_tolerance,
        )
        return cls(ground, graviton, hidden_width=hidden_width, seed=seed)

    def projection_certificate(
        self, parameters: np.ndarray, total_l: int
    ) -> ProjectionCertificate:
        """Certify the projected neural vector without using L^2 diagonalization."""

        weights, bias, heads = self._unpack(parameters)
        sector = self.sectors[total_l]
        hidden = np.tanh(sector.features @ weights.T + bias)
        head_weights, head_bias = heads[total_l]
        raw = hidden @ head_weights + head_bias
        _, certificate = sector.projector.project_with_certificate(raw)
        return certificate
