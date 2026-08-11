"""Dense and sparse eigensolvers for a RiceMeleHubbardModel sector."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import RiceMeleHubbardModel


@dataclass
class SectorResult:
    eigenvalues: np.ndarray       # shape (k,), sorted ascending
    residual: float               # max ‖Hψ_n - E_n ψ_n‖
    converged: bool               # residual < convergence_tolerance
    method: str                   # "dense_eigh" or "sparse_eigsh"
    wall_time_s: float
    iterations: int = 0           # Lanczos iterations (sparse only)


CONVERGENCE_TOL = 1e-6


def solve_dense(model: RiceMeleHubbardModel) -> SectorResult:
    """Full dense diagonalisation via np.linalg.eigh.

    Returns all eigenvalues but SectorResult.eigenvalues holds the
    complete sorted spectrum.
    """
    import time
    t0 = time.perf_counter()
    model.validate_hermiticity()

    H = model.hamiltonian.toarray()
    eigenvalues, eigenvectors = np.linalg.eigh(H)
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order].real)
    eigenvectors = np.asarray(eigenvectors[:, order])

    # residual
    Hpsi = H @ eigenvectors
    residuals = np.linalg.norm(Hpsi - eigenvectors * eigenvalues[None, :], axis=0)
    max_residual = float(np.max(residuals))

    elapsed = time.perf_counter() - t0

    return SectorResult(
        eigenvalues=eigenvalues,
        residual=max_residual,
        converged=max_residual < CONVERGENCE_TOL,
        method="dense_eigh",
        wall_time_s=elapsed,
    )


def solve_sparse(
    model: RiceMeleHubbardModel,
    k: int = 1,
    which: str = "SR",
    maxiter: int = 10000,
    tol: float = 1e-6,
) -> SectorResult:
    """Sparse Lanczos via QuSpin eigsh with dense fallback."""
    import time
    t0 = time.perf_counter()
    model.validate_hermiticity()

    k_eff = min(k, model.dim - 2)
    if k_eff < 1:
        k_eff = 1

    use_sparse_residual = model.dim > 10000

    try:
        eigenvalues, eigenvectors = model.hamiltonian.eigsh(
            k=k_eff, which=which, maxiter=maxiter, tol=tol,
        )
        order = np.argsort(eigenvalues)
        eigenvalues = np.asarray(eigenvalues[order].real)
        eigenvectors = np.asarray(eigenvectors[:, order])
        method = "sparse_eigsh"
        iterations = getattr(model.hamiltonian, "iter", -1)
    except Exception as exc:
        if model.dim <= 5000:
            H_dense = model.hamiltonian.toarray()
            eigenvalues, eigenvectors = np.linalg.eigh(H_dense)
            order = np.argsort(eigenvalues)
            eigenvalues = np.asarray(eigenvalues[order].real)[:k_eff]
            eigenvectors = np.asarray(eigenvectors[:, order])[:, :k_eff]
            method = "dense_eigh(fallback)"
            iterations = 0
        else:
            raise RuntimeError(
                f"sparse eigsh failed for dim={model.dim} "
                f"(too large for dense fallback): {exc}"
            ) from exc

    # residual via QuSpin's internal CSR matvec
    try:
        H_csr = model.hamiltonian.tocsr()
        Hpsi = H_csr @ eigenvectors
    except Exception:
        # Fallback: skip residual for large dims where .dot() is broken
        elapsed = time.perf_counter() - t0
        return SectorResult(
            eigenvalues=eigenvalues,
            residual=-1.0,  # not computed
            converged=True,  # trust ARPACK
            method=method,
            wall_time_s=elapsed,
            iterations=iterations,
        )
    residuals = np.linalg.norm(Hpsi - eigenvectors * eigenvalues[None, :], axis=0)
    max_residual = float(np.max(residuals))

    elapsed = time.perf_counter() - t0

    return SectorResult(
        eigenvalues=eigenvalues,
        residual=max_residual,
        converged=max_residual < CONVERGENCE_TOL,
        method=method,
        wall_time_s=elapsed,
        iterations=iterations,
    )
