from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import RiceMeleModel


@dataclass(frozen=True)
class DiagonalizationResult:
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    orthogonality_error: float
    maximum_residual: float


def diagonalize_full(
    model: RiceMeleModel,
    tolerance: float = 1e-10,
) -> DiagonalizationResult:
    """Compute and validate the complete Hermitian eigensystem."""
    eigenvalues, eigenvectors = model.hamiltonian.eigh()
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order].real)
    eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.complex128)

    identity = np.eye(eigenvectors.shape[1], dtype=np.complex128)
    orthogonality_error = float(
        np.max(np.abs(eigenvectors.conj().T @ eigenvectors - identity))
    )
    matrix = model.hamiltonian.toarray()
    residual_matrix = matrix @ eigenvectors - eigenvectors * eigenvalues[None, :]
    maximum_residual = float(np.max(np.linalg.norm(residual_matrix, axis=0)))
    if orthogonality_error >= tolerance:
        raise RuntimeError(
            f"eigenvectors are not orthonormal: error={orthogonality_error:.3e}"
        )
    if maximum_residual >= tolerance:
        raise RuntimeError(f"eigenproblem residual is too large: error={maximum_residual:.3e}")

    eigenvalues.setflags(write=False)
    eigenvectors.setflags(write=False)

    return DiagonalizationResult(
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        orthogonality_error=orthogonality_error,
        maximum_residual=maximum_residual,
    )
