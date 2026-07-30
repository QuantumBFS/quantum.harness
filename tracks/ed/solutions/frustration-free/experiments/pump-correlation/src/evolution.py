"""Time-dependent Krylov-Lanczos evolution for the Rice-Mele-Hubbard pump."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import expm_multiply, eigsh

from .model import SplitRMHModel


@dataclass
class GroundStateResult:
    energy: float
    state: np.ndarray
    residual: float
    converged: bool
    wall_time_s: float


@dataclass
class EvolutionResult:
    times: np.ndarray             # shape (n_save,)
    states: list[np.ndarray]      # list of state vectors at save points
    norm_errors: list[float]      # max |⟨ψ|ψ⟩ - 1| at each step
    wall_time_s: float
    n_steps: int


def compute_ground_state(
    model: SplitRMHModel,
    delta: float,
    Delta: float,
    k: int = 1,
    tol: float = 1e-8,
) -> GroundStateResult:
    """Compute the ground state of H(delta, Delta).

    For L <= 6 (dim <= 5000), uses dense eigh for machine-precision.
    For larger L, tries sparse eigsh first, then falls back to imaginary
    time evolution (expm_multiply) which avoids the eigsh factorization
    bottleneck on large matrices.
    """
    t0 = time.perf_counter()
    dim = model.dim

    if dim <= 5000:
        H = model.hamiltonian_at(delta, Delta).toarray()
        eigenvalues, eigenvectors = np.linalg.eigh(H)
        order = np.argsort(eigenvalues)
        E0 = float(eigenvalues[order[0]].real)
        psi0 = np.asarray(eigenvectors[:, order[0]], dtype=np.complex128)
        psi0 /= np.linalg.norm(psi0)
        Hpsi = H @ psi0
        residual = float(np.linalg.norm(Hpsi - E0 * psi0))
        method = "dense_eigh"
        elapsed = time.perf_counter() - t0
        return GroundStateResult(
            energy=E0, state=psi0, residual=residual,
            converged=residual < 1e-9, wall_time_s=elapsed,
        )

    # Sparse: try eigsh with a timeout-aware approach
    H_sparse = model.hamiltonian_at(delta, Delta)
    try:
        eigenvalues, eigenvectors = eigsh(
            H_sparse, k=1, which="SA", maxiter=5000, tol=1e-6,
        )
        E0 = float(eigenvalues[0].real)
        psi0 = np.asarray(eigenvectors[:, 0], dtype=np.complex128).ravel()
        psi0 /= np.linalg.norm(psi0)
        Hpsi = H_sparse @ psi0
        residual = float(np.linalg.norm(Hpsi - E0 * psi0))
        method = "sparse_eigsh"
    except Exception as e:
        print(f"  eigsh failed ({e}), falling back to imaginary time evolution...")
        # Imaginary time evolution: exp(-H·dβ) repeatedly applied
        rng = np.random.RandomState(42)
        psi = rng.randn(dim) + 1j * rng.randn(dim)
        psi /= np.linalg.norm(psi)

        dbeta = 0.05
        n_ite = 400  # total β = 20
        E_old = float("inf")
        for step in range(n_ite):
            psi = expm_multiply(-dbeta * H_sparse, psi, traceA=0.0)
            psi /= np.linalg.norm(psi)
            if step % 50 == 0 or step == n_ite - 1:
                Hpsi = H_sparse @ psi
                E = float(np.dot(psi.conj(), Hpsi).real)
                de = abs(E - E_old)
                if step % 50 == 0:
                    print(f"    ITE step {step:3d}: E = {E:.6f}  ΔE = {de:.2e}")
                E_old = E
        E0 = E
        psi0 = psi
        residual = float(np.linalg.norm(Hpsi - E0 * psi0))
        method = f"ITE(n={n_ite},dbeta={dbeta})"

    elapsed = time.perf_counter() - t0
    return GroundStateResult(
        energy=E0,
        state=psi0,
        residual=residual,
        converged=residual < 1e-9,
        wall_time_s=elapsed,
    )


def evolve_midpoint_krylov(
    model: SplitRMHModel,
    psi0: np.ndarray,
    T: float,
    dt: float,
    delta_of_tau,
    Delta_of_tau,
    save_interval: float = 0.2,
) -> EvolutionResult:
    """Time evolution via midpoint Krylov method.

    |ψ(τ + dτ)⟩ ≈ exp(-i H(τ + dτ/2) dτ) |ψ(τ)⟩

    Uses scipy.sparse.linalg.expm_multiply with the CSR Hamiltonian
    evaluated at the midpoint of each time step.

    Parameters
    ----------
    model : SplitRMHModel
    psi0 : np.ndarray
        Initial state vector.
    T : float
        Total evolution time.
    dt : float
        Time step.
    delta_of_tau : callable
        Function δ(τ).
    Delta_of_tau : callable
        Function Δ(τ).
    save_interval : float
        Save state every `save_interval` in τ.
    krylov_tol : float
        Tolerance for expm_multiply.

    Returns
    -------
    EvolutionResult
    """
    t0 = time.perf_counter()
    n_steps = int(round(T / dt))
    dim = model.dim

    psi = np.asarray(psi0, dtype=np.complex128).copy()
    norm_errors: list[float] = []

    # save points
    save_times = np.arange(0, T + 1e-12, save_interval)
    if save_times[-1] < T - 1e-12:
        save_times = np.append(save_times, T)
    save_indices = {int(round(t / dt)) for t in save_times}
    save_indices.add(0)

    saved_times: list[float] = [0.0]
    saved_states: list[np.ndarray] = [psi.copy()]

    for m in range(1, n_steps + 1):
        tau_mid = (m - 0.5) * dt
        delta_mid = delta_of_tau(tau_mid)
        Delta_mid = Delta_of_tau(tau_mid)

        H_mid = model.hamiltonian_at(delta_mid, Delta_mid)
        psi = expm_multiply(-1j * dt * H_mid, psi, traceA=0.0)

        # monitor norm
        nrm = float(np.linalg.norm(psi))
        norm_errors.append(abs(nrm - 1.0))
        psi /= nrm

        if m in save_indices:
            saved_times.append(m * dt)
            saved_states.append(psi.copy())

    elapsed = time.perf_counter() - t0
    return EvolutionResult(
        times=np.array(saved_times),
        states=saved_states,
        norm_errors=norm_errors,
        wall_time_s=elapsed,
        n_steps=n_steps,
    )
