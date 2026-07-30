"""Midpoint Krylov-Lanczos time evolution and light ground-state solver."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import expm_multiply

from .model_split import SplitRMHModel


@dataclass
class EvolutionResult:
    psi_final: np.ndarray
    max_norm_error: float
    n_steps: int
    wall_time_s: float


@dataclass
class GroundStateResult:
    energy: float
    state: np.ndarray
    residual: float
    converged: bool
    wall_time_s: float
    method: str


def solve_ground_state(
    model=None,  # RiceMeleHubbardModel (for L<=6) or None (for large L)
    k: int = 1,
    which: str = "SA",
    maxiter: int = 200000,
    tol: float = 1e-8,
    convergence_tol: float = 1e-9,
    # Raw parameters for large-L direct construction (avoids toarray() OOM):
    L: int | None = None,
    delta: float = 0.0,
    Delta: float = 0.0,
    U: float = 0.0,
    t: float = 1.0,
) -> GroundStateResult:
    """Ground-state solver safe for all L.

    For L <= 6 (dim <= 5000): pass a RiceMeleHubbardModel — uses dense eigh.
    For L >= 8: pass raw (L, delta, Delta, U) — builds scipy CSR matrix
    directly, NEVER calls toarray(), safe for dim > 60000.
    """
    t0 = time.perf_counter()

    if model is not None:
        dim = model.dim
    else:
        from math import comb
        n = L // 2
        dim = comb(L, n) ** 2

    # Dense eigh for small dim (L <= 6) — exact, machine-precision
    if model is not None and dim <= 5000:
        model.validate_hermiticity()
        H = model.hamiltonian.toarray()
        eigenvalues, eigenvectors = np.linalg.eigh(H)
        order = np.argsort(eigenvalues)
        eigenvalues = np.asarray(eigenvalues[order].real)
        eigenvectors = np.asarray(eigenvectors[:, order])

        E0 = float(eigenvalues[0])
        psi0 = np.asarray(eigenvectors[:, 0], dtype=np.complex128)
        psi0 /= np.linalg.norm(psi0)

        Hpsi = H @ psi0
        residual = float(np.linalg.norm(Hpsi - E0 * psi0))

        elapsed = time.perf_counter() - t0
        return GroundStateResult(
            energy=E0, state=psi0, residual=residual,
            converged=residual < convergence_tol,
            wall_time_s=elapsed, method="dense_eigh",
        )

    # Large dim (L >= 8): build scipy CSR via QuSpin internal _static
    from scipy.sparse.linalg import eigsh
    if model is None:
        H_sparse = _build_rmh_sparse(L=L, delta=delta, Delta=Delta, U=U, t=t)
    else:
        from scipy.sparse import csr_matrix
        H_sparse = csr_matrix(model.hamiltonian.toarray())
    dim = H_sparse.shape[0]

    eigenvalues, eigenvectors = eigsh(
        H_sparse, k=min(k, dim - 2), which=which, maxiter=maxiter, tol=tol,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order].real)
    eigenvectors = np.asarray(eigenvectors[:, order])

    E0 = float(eigenvalues[0])
    psi0 = np.asarray(eigenvectors[:, 0], dtype=np.complex128).ravel()
    psi0 /= np.linalg.norm(psi0)

    # residual via sparse matvec
    Hpsi = H_sparse @ psi0
    residual = float(np.linalg.norm(Hpsi - E0 * psi0))

    elapsed = time.perf_counter() - t0

    return GroundStateResult(
        energy=E0,
        state=psi0,
        residual=residual,
        converged=residual < convergence_tol,
        wall_time_s=elapsed,
        method="sparse_eigsh",
    )


def _build_rmh_sparse(
    L: int, delta: float, Delta: float, U: float, t: float = 1.0,
):
    """Build RMH Hamiltonian as scipy CSR matrix via QuSpin _static.

    Uses QuSpin to construct the operator then extracts the internal
    CSR matrix — avoids the .dot() version-specific bug.
    """
    from quspin.basis import spinful_fermion_basis_1d
    from quspin.operators import hamiltonian as qs_hamiltonian

    n = L // 2
    basis = spinful_fermion_basis_1d(L, Nf=(n, n))

    up_hopping: list = []
    down_hopping: list = []

    for j in range(L - 1):
        coeff = -(t + ((-1) ** j) * delta)
        up_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])
        down_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])

    boundary_coeff = -(t + ((-1) ** L) * delta)
    up_hopping.extend([[boundary_coeff, L - 1, 0], [boundary_coeff, 0, L - 1]])
    down_hopping.extend([[boundary_coeff, L - 1, 0], [boundary_coeff, 0, L - 1]])

    onsite = [[Delta * ((-1) ** j), j] for j in range(L)]

    static: list = [
        ["+-|", up_hopping],
        ["|+-", down_hopping],
        ["n|", onsite],
        ["|n", onsite],
    ]
    if U != 0.0:
        static.append(["n|n", [[U, j, j] for j in range(L)]])

    H_qs = qs_hamiltonian(
        static, [], basis=basis, dtype=np.complex128,
        check_herm=False, check_symm=False, check_pcon=False,
    )
    return H_qs._static  # scipy CSR matrix


def evolve_midpoint(
    split_model: SplitRMHModel,
    psi0: np.ndarray,
    T: float,
    dt: float,
    delta0: float = 0.5,
) -> EvolutionResult:
    """Midpoint Krylov-Lanczos time evolution under cosine ramp δ(t).

    δ(t) = −δ₀ cos(π t / T),  0 ≤ t ≤ T

    Uses scipy.sparse.linalg.expm_multiply with CSR matrices from
    SplitRMHModel.sparse_at() — avoids QuSpin .dot() version bug.
    """
    t0 = time.perf_counter()
    dim = split_model.dim
    n_steps = int(round(T / dt))

    psi = np.asarray(psi0, dtype=np.complex128).copy()
    norm_errors: list[float] = []

    for m in range(n_steps):
        t_mid = (m + 0.5) * dt
        delta_mid = -delta0 * np.cos(np.pi * t_mid / T)

        H_sparse = split_model.sparse_at(delta_mid)
        psi = expm_multiply(-1j * dt * H_sparse, psi, traceA=0.0)

        nrm = float(np.linalg.norm(psi))
        norm_errors.append(abs(nrm - 1.0))
        psi /= nrm

    elapsed = time.perf_counter() - t0
    max_err = max(norm_errors) if norm_errors else 0.0

    return EvolutionResult(
        psi_final=psi,
        max_norm_error=max_err,
        n_steps=n_steps,
        wall_time_s=elapsed,
    )
