"""Time evolution for the pinning experiment.

Supports CW pump, CCW pump, and frozen Hamiltonian modes.
Ground state computed with pinning potentials to localize hole at j0.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import expm_multiply, eigsh

from .model import PinningRMHModel


@dataclass
class GroundStateResult:
    energy: float
    state: np.ndarray
    residual: float
    converged: bool
    wall_time_s: float


@dataclass
class EvolutionResult:
    times: np.ndarray
    states: list[np.ndarray]
    norm_errors: list[float]
    wall_time_s: float
    n_steps: int


def compute_ground_state(
    model: PinningRMHModel,
    delta: float,
    Delta: float,
    V_h: float = 0.0,
    h_s: float = 0.0,
    k: int = 1,
    tol: float = 1e-8,
) -> GroundStateResult:
    """Compute the ground state of H(delta, Delta) + pinning terms.

    Three-tier strategy:
    1. Dense eigh for dim <= 5000
    2. Sparse eigsh for larger dims
    3. Imaginary time evolution fallback
    """
    t0 = time.perf_counter()
    dim = model.dim

    if dim <= 5000:
        H = model.hamiltonian_at(delta, Delta, V_h, h_s).toarray()
        eigenvalues, eigenvectors = np.linalg.eigh(H)
        order = np.argsort(eigenvalues)
        E0 = float(eigenvalues[order[0]].real)
        psi0 = np.asarray(eigenvectors[:, order[0]], dtype=np.complex128)
        psi0 /= np.linalg.norm(psi0)
        Hpsi = H @ psi0
        residual = float(np.linalg.norm(Hpsi - E0 * psi0))
        elapsed = time.perf_counter() - t0
        return GroundStateResult(
            energy=E0, state=psi0, residual=residual,
            converged=residual < 1e-9, wall_time_s=elapsed,
        )

    H_sparse = model.hamiltonian_at(delta, Delta, V_h, h_s)
    try:
        eigenvalues, eigenvectors = eigsh(
            H_sparse, k=1, which="SA", maxiter=5000, tol=1e-6,
        )
        E0 = float(eigenvalues[0].real)
        psi0 = np.asarray(eigenvectors[:, 0], dtype=np.complex128).ravel()
        psi0 /= np.linalg.norm(psi0)
        Hpsi = H_sparse @ psi0
        residual = float(np.linalg.norm(Hpsi - E0 * psi0))
    except Exception as e:
        print(f"  eigsh failed ({e}), falling back to imaginary time evolution...")
        rng = np.random.RandomState(42)
        psi = rng.randn(dim) + 1j * rng.randn(dim)
        psi /= np.linalg.norm(psi)

        dbeta = 0.05
        n_ite = 400
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

    elapsed = time.perf_counter() - t0
    return GroundStateResult(
        energy=E0, state=psi0, residual=residual,
        converged=residual < 1e-9, wall_time_s=elapsed,
    )


def evolve_midpoint_krylov(
    model: PinningRMHModel,
    psi0: np.ndarray,
    T: float,
    dt: float,
    delta_of_tau,
    Delta_of_tau,
    V_h: float = 0.0,
    h_s: float = 0.0,
    save_interval: float = 0.2,
    frozen: bool = False,
) -> EvolutionResult:
    """Midpoint Krylov time evolution with pinning terms.

    Parameters
    ----------
    model : PinningRMHModel
    psi0 : np.ndarray
        Initial state vector.
    T : float
        Total evolution time.
    dt : float
        Time step.
    delta_of_tau, Delta_of_tau : callable
        Pump path functions δ(τ), Δ(τ).  Ignored if frozen=True.
    V_h, h_s : float
        Pinning strengths (constant throughout evolution).
    save_interval : float
        Save state every `save_interval` in τ.
    frozen : bool
        If True, use δ(0), Δ(0) at all times (frozen Hamiltonian).

    Returns
    -------
    EvolutionResult
    """
    t0 = time.perf_counter()
    n_steps = int(round(T / dt))

    if frozen:
        delta0 = float(delta_of_tau(0.0))
        Delta0 = float(Delta_of_tau(0.0))
        H_frozen = model.hamiltonian_at(delta0, Delta0, V_h, h_s)

    psi = np.asarray(psi0, dtype=np.complex128).copy()
    norm_errors: list[float] = []

    save_times = np.arange(0, T + 1e-12, save_interval)
    if save_times[-1] < T - 1e-12:
        save_times = np.append(save_times, T)
    save_indices = {int(round(t / dt)) for t in save_times}
    save_indices.add(0)

    saved_times: list[float] = [0.0]
    saved_states: list[np.ndarray] = [psi.copy()]

    for m in range(1, n_steps + 1):
        if frozen:
            H_mid = H_frozen
        else:
            tau_mid = (m - 0.5) * dt
            delta_mid = delta_of_tau(tau_mid)
            Delta_mid = Delta_of_tau(tau_mid)
            H_mid = model.hamiltonian_at(delta_mid, Delta_mid, V_h, h_s)

        psi = expm_multiply(-1j * dt * H_mid, psi, traceA=0.0)

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
