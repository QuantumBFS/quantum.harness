"""Validated eigensolvers, exact-coordinate caching, and gap scans."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

import numpy as np
from scipy.sparse.linalg import ArpackNoConvergence

from .model import RiceMeleHubbardModel


HERMITICITY_TOLERANCE = 1e-12
RESIDUAL_TOLERANCE = 1e-8
EIGSH_TOLERANCE = 1e-10
EIGSH_MAXITER = (100000, 200000)
EIGSH_NCV = (64, 160)


def _hermiticity_error(sparse_matrix) -> float:
    antihermitian = sparse_matrix - sparse_matrix.getH()
    return float(np.max(np.abs(antihermitian.data))) if antihermitian.nnz else 0.0


def _residual_limit(energies: tuple[float, float]) -> float:
    scale = max(1.0, *(abs(float(energy)) for energy in energies))
    return RESIDUAL_TOLERANCE * scale


def _sparse_low_energy(model_hamiltonian, dimension: int):
    last_error: ArpackNoConvergence | None = None
    for requested_ncv, maxiter in zip(EIGSH_NCV, EIGSH_MAXITER):
        ncv = min(dimension - 1, requested_ncv)
        try:
            return model_hamiltonian.eigsh(
                k=2,
                which="SA",
                ncv=ncv,
                maxiter=maxiter,
                tol=EIGSH_TOLERANCE,
            )
        except ArpackNoConvergence as error:
            last_error = error
    assert last_error is not None
    raise last_error


@dataclass(frozen=True)
class FullEigensystem:
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    residuals: np.ndarray
    orthogonality_error: float
    hermiticity_error: float


def diagonalize_full(model_hamiltonian) -> FullEigensystem:
    """Fully diagonalize a validated Hermitian QuSpin Hamiltonian."""
    sparse_matrix = model_hamiltonian.tocsr()
    hermiticity_error = _hermiticity_error(sparse_matrix)
    if hermiticity_error >= HERMITICITY_TOLERANCE:
        raise RuntimeError(
            f"Hamiltonian is not Hermitian: error={hermiticity_error:.3e}"
        )
    matrix = model_hamiltonian.toarray()
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    residual_matrix = matrix @ eigenvectors - eigenvectors * eigenvalues[None, :]
    residuals = np.linalg.norm(residual_matrix, axis=0)
    identity = np.eye(eigenvectors.shape[1])
    orthogonality_error = float(
        np.max(np.abs(eigenvectors.conj().T @ eigenvectors - identity))
    )
    return FullEigensystem(
        eigenvalues=np.asarray(eigenvalues.real),
        eigenvectors=np.asarray(eigenvectors, dtype=np.complex128),
        residuals=np.asarray(residuals),
        orthogonality_error=orthogonality_error,
        hermiticity_error=hermiticity_error,
    )


@dataclass(frozen=True)
class LowEnergyVertex:
    state: np.ndarray
    excited_state: np.ndarray | None
    energies: tuple[float, float]
    gap: float
    hermiticity_error: float
    residual: float
    ground_state_residual: float
    first_excited_residual: float


@dataclass(frozen=True)
class GapGridResult:
    N_theta: int
    N_phi: int
    e0: np.ndarray
    e1: np.ndarray
    gaps: np.ndarray
    minimum_gap: float
    theta_at_minimum: float
    phi_at_minimum: float
    maximum_hermiticity_error: float
    maximum_residual: float
    new_diagonalizations: int
    total_diagonalizations: int


class EDEngine:
    """Low-energy ED with one shared basis and exact periodic cache keys."""

    def __init__(self, model: RiceMeleHubbardModel) -> None:
        model.validate_basis()
        self.model = model
        self._cache: dict[tuple[Fraction, Fraction], LowEnergyVertex] = {}
        self._diagonalization_count = 0

    @property
    def basis(self):
        return self.model.basis

    @property
    def diagonalization_count(self) -> int:
        return self._diagonalization_count

    @property
    def cached_vertex_count(self) -> int:
        return len(self._cache)

    def seed_vertex(
        self,
        theta: Fraction,
        phi: Fraction,
        *,
        state: np.ndarray,
        energies: tuple[float, float],
        hermiticity_error: float,
        residual: float,
    ) -> None:
        """Seed one externally validated vertex without counting a solve."""
        if not isinstance(theta, Fraction) or not isinstance(phi, Fraction):
            raise TypeError("theta and phi cache coordinates must be Fractions")
        key = (theta % 1, phi % 1)
        if key in self._cache:
            raise ValueError(f"vertex {key} is already cached")
        vector = np.asarray(state, dtype=np.complex128)
        if vector.shape != (self.basis.Ns,) or not np.all(np.isfinite(vector)):
            raise ValueError("seed state has an invalid shape or non-finite values")
        if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-10):
            raise ValueError("seed state is not normalized")
        e0, e1 = (float(value) for value in energies)
        if not np.isfinite((e0, e1)).all() or e1 < e0:
            raise ValueError("seed energies must be finite and ordered")
        hermiticity_error = float(hermiticity_error)
        residual = float(residual)
        if not np.isfinite(hermiticity_error) or hermiticity_error >= HERMITICITY_TOLERANCE:
            raise ValueError("seed Hermiticity error exceeds tolerance")
        if not np.isfinite(residual) or residual >= _residual_limit((e0, e1)):
            raise ValueError("seed eigensolver residual exceeds tolerance")
        self._cache[key] = LowEnergyVertex(
            state=vector.copy(),
            excited_state=None,
            energies=(e0, e1),
            gap=e1 - e0,
            hermiticity_error=hermiticity_error,
            residual=residual,
            ground_state_residual=residual,
            first_excited_residual=residual,
        )

    def vertex(self, theta: Fraction, phi: Fraction) -> LowEnergyVertex:
        """Return the cached two lowest states at exact torus coordinates."""
        if not isinstance(theta, Fraction) or not isinstance(phi, Fraction):
            raise TypeError("theta and phi cache coordinates must be Fractions")
        key = (theta % 1, phi % 1)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        theta_value = 2.0 * np.pi * float(key[0])
        phi_value = 2.0 * np.pi * float(key[1])
        model_hamiltonian = self.model.hamiltonian(phi_value, theta_value)
        sparse_matrix = model_hamiltonian.tocsr()
        hermiticity_error = _hermiticity_error(sparse_matrix)
        if hermiticity_error >= HERMITICITY_TOLERANCE:
            raise RuntimeError(
                f"Hamiltonian is not Hermitian: error={hermiticity_error:.3e}"
            )

        try:
            energies, vectors = _sparse_low_energy(
                model_hamiltonian,
                self.basis.Ns,
            )
            order = np.argsort(energies.real)
            energies = np.asarray(energies[order].real)
            state = np.asarray(vectors[:, order[0]], dtype=np.complex128)
            excited_state = np.asarray(vectors[:, order[1]], dtype=np.complex128)
        except Exception as error:
            if self.basis.Ns > 1000:
                raise RuntimeError(
                    f"sparse eigensolver failed for Hilbert dimension {self.basis.Ns}"
                ) from error
            energies, vectors = np.linalg.eigh(model_hamiltonian.toarray())
            energies = np.asarray(energies[:2].real)
            state = np.asarray(vectors[:, 0], dtype=np.complex128)
            excited_state = np.asarray(vectors[:, 1], dtype=np.complex128)

        state /= np.linalg.norm(state)
        excited_state /= np.linalg.norm(excited_state)
        e0, e1 = float(energies[0]), float(energies[1])
        ground_residual = float(np.linalg.norm(sparse_matrix @ state - e0 * state))
        excited_residual = float(
            np.linalg.norm(sparse_matrix @ excited_state - e1 * excited_state)
        )
        residual = max(ground_residual, excited_residual)
        residual_limit = _residual_limit((e0, e1))
        if residual >= residual_limit:
            raise RuntimeError(
                "eigensolver residual is too large: "
                f"{residual:.3e} >= {residual_limit:.3e}"
            )

        result = LowEnergyVertex(
            state=state,
            excited_state=excited_state,
            energies=(e0, e1),
            gap=e1 - e0,
            hermiticity_error=hermiticity_error,
            residual=residual,
            ground_state_residual=ground_residual,
            first_excited_residual=excited_residual,
        )
        self._cache[key] = result
        self._diagonalization_count += 1
        return result

    def scan_gap_grid(self, N_theta: int, N_phi: int) -> GapGridResult:
        if N_theta < 2 or N_phi < 2:
            raise ValueError("grid dimensions must be at least 2")
        before = self.diagonalization_count
        e0 = np.empty((N_theta, N_phi), dtype=np.float64)
        e1 = np.empty_like(e0)
        hermiticity = np.empty_like(e0)
        residuals = np.empty_like(e0)
        for theta_index in range(N_theta):
            for phi_index in range(N_phi):
                vertex = self.vertex(
                    Fraction(theta_index, N_theta),
                    Fraction(phi_index, N_phi),
                )
                e0[theta_index, phi_index] = vertex.energies[0]
                e1[theta_index, phi_index] = vertex.energies[1]
                hermiticity[theta_index, phi_index] = vertex.hermiticity_error
                residuals[theta_index, phi_index] = vertex.residual

        gaps = e1 - e0
        minimum_index = np.unravel_index(np.argmin(gaps), gaps.shape)
        return GapGridResult(
            N_theta=N_theta,
            N_phi=N_phi,
            e0=e0,
            e1=e1,
            gaps=gaps,
            minimum_gap=float(gaps[minimum_index]),
            theta_at_minimum=2.0 * np.pi * minimum_index[0] / N_theta,
            phi_at_minimum=2.0 * np.pi * minimum_index[1] / N_phi,
            maximum_hermiticity_error=float(np.max(hermiticity)),
            maximum_residual=float(np.max(residuals)),
            new_diagonalizations=self.diagonalization_count - before,
            total_diagonalizations=self.diagonalization_count,
        )

    def scan_nested_gaps(self, sizes: Sequence[int]) -> list[GapGridResult]:
        if not sizes:
            raise ValueError("at least one grid size is required")
        grid_sizes = [int(size) for size in sizes]
        for coarse, fine in zip(grid_sizes, grid_sizes[1:]):
            if fine <= coarse or fine % coarse:
                raise ValueError(
                    "each nested grid must be an increasing integer multiple"
                )
        return [self.scan_gap_grid(size, size) for size in grid_sizes]
