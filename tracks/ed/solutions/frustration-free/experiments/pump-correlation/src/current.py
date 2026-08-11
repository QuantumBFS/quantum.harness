"""Bond current operators and diagnostics for the RMH pump.

J_j(τ) = -i t_j(τ) Σ_σ (c†_{jσ}c_{j+1,σ} - c†_{j+1,σ}c_{jσ})

where t_j(τ) = 1 + (-1)^j δ(τ).

Split for O(1) per-timestep evaluation:
  J_j(τ) = J_j^(0) + δ(τ) · J_j^(1)

Boundary bond (L−1, 0) includes twist phase e^{iϑ} (ϑ = 0 for PBC, π for APBC),
matching the Hamiltonian boundary convention exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from quspin.operators import hamiltonian

from .model import SplitRMHModel


@dataclass
class CurrentResult:
    """All current diagnostics for one pump cycle."""

    tau: np.ndarray               # shape (n_save,)
    tau_over_T: np.ndarray        # shape (n_save,)
    phi: np.ndarray               # 2π τ / T, for φ-axis plots
    bond_current: np.ndarray      # shape (n_save, L) — J_j(τ)
    current_mean: np.ndarray      # shape (n_save,) — J(τ) = (1/L) Σ J_j
    current_even: np.ndarray      # shape (n_save,) — (2/L) Σ_{j even} J_j
    current_odd: np.ndarray       # shape (n_save,) — (2/L) Σ_{j odd} J_j
    scaled_current: np.ndarray    # J(φ) = (T/2π) J(τ)
    scaled_current_even: np.ndarray
    scaled_current_odd: np.ndarray
    Q: np.ndarray                 # Q(τ) = ∫_0^τ J(τ') dτ'
    Q_even: np.ndarray
    Q_odd: np.ndarray
    Q_cycle: float                # Q(T)
    density_by_site: np.ndarray   # shape (n_save, L) — ⟨n_j⟩(τ)
    continuity_residual: float    # max |d⟨n_j⟩/dτ - (J_{j-1} - J_j)|


# ---------------------------------------------------------------------------
# Operator construction
# ---------------------------------------------------------------------------


def _build_current_operators(model: SplitRMHModel):
    """Build (J0_ops, J1_ops) lists of QuSpin hamiltonian objects.

    J0_ops[j] = J_j^(0)  (coefficient for t=1 part)
    J1_ops[j] = J_j^(1)  (coefficient for t=(-1)^j part)

    Each is a 2-spin-component QuSpin hamiltonian with "+-|" (up)
    and "|+-" (down) terms. check_herm=False because we explicitly
    include both c†c and its conjugate with the correct coefficients.
    """
    L = model.L
    anti = model.antiperiodic
    twist = -1.0 if anti else 1.0  # e^{iϑ}

    J0_ops: list = []
    J1_ops: list = []

    for j in range(L):
        jp1 = (j + 1) % L
        is_boundary = (j == L - 1)

        if is_boundary:
            # Boundary bond: J = -i t (e^{iϑ} c†_{L-1} c_0 - e^{-iϑ} c†_0 c_{L-1})
            # With ϑ=π: e^{iπ}=e^{-iπ}=-1, giving +i for (L-1,0), -i for (0,L-1)
            phase_fwd = twist       # e^{iϑ}
            phase_bwd = twist       # e^{-iϑ} = e^{iϑ} for ϑ∈{0,π}
        else:
            phase_fwd = 1.0
            phase_bwd = 1.0

        sign_j = float((-1) ** j)

        # --- J^(0): t=1 part ---
        # coeff for (j, j+1): -i * 1 * e^{iϑ}
        # coeff for (j+1, j): +i * 1 * e^{-iϑ}
        c0_fwd = -1j * phase_fwd
        c0_bwd = 1j * phase_bwd

        J0 = hamiltonian(
            [
                ["+-|", [[c0_fwd, j, jp1], [c0_bwd, jp1, j]]],
                ["|+-", [[c0_fwd, j, jp1], [c0_bwd, jp1, j]]],
            ],
            [],
            basis=model.basis,
            dtype=np.complex128,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )
        J0_ops.append(J0)

        # --- J^(1): δ part, coefficient × (-1)^j ---
        # coeff for (j, j+1): -i * (-1)^j * e^{iϑ}
        # coeff for (j+1, j): +i * (-1)^j * e^{-iϑ}
        c1_fwd = -1j * sign_j * phase_fwd
        c1_bwd = 1j * sign_j * phase_bwd

        J1 = hamiltonian(
            [
                ["+-|", [[c1_fwd, j, jp1], [c1_bwd, jp1, j]]],
                ["|+-", [[c1_fwd, j, jp1], [c1_bwd, jp1, j]]],
            ],
            [],
            basis=model.basis,
            dtype=np.complex128,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )
        J1_ops.append(J1)

    return J0_ops, J1_ops


def _build_density_operators(model: SplitRMHModel):
    """Build one QuSpin hamiltonian per site for ⟨n_j⟩ = ⟨n_{j↑}⟩ + ⟨n_{j↓}⟩."""
    L = model.L
    n_ops: list = []
    for j in range(L):
        op = hamiltonian(
            [["n|", [[1.0, j]]], ["|n", [[1.0, j]]]],
            [],
            basis=model.basis,
            dtype=np.float64,
            check_herm=False,
            check_symm=False,
            check_pcon=False,
        )
        n_ops.append(op)
    return n_ops


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def measure_currents(
    model: SplitRMHModel,
    times: np.ndarray,
    states: list[np.ndarray],
    delta_of_tau,
) -> CurrentResult:
    """Measure bond currents, cumulative transport, and continuity for all
    saved time points.

    Parameters
    ----------
    model : SplitRMHModel
    times : np.ndarray, shape (n_save,)
        Time values τ at which states were saved.
    states : list[np.ndarray]
        State vectors |ψ(τ)⟩ at each save point.
    delta_of_tau : callable
        δ(τ) function.

    Returns
    -------
    CurrentResult
    """
    L = model.L
    n_save = len(states)
    T = times[-1]

    J0_ops, J1_ops = _build_current_operators(model)
    n_ops = _build_density_operators(model)

    bond_current = np.empty((n_save, L))
    density = np.empty((n_save, L))

    for t_idx, psi in enumerate(states):
        psi_conj = psi.conj()
        delta = delta_of_tau(times[t_idx])

        for j in range(L):
            exp_J0 = float(np.dot(psi_conj, J0_ops[j].dot(psi)).real)
            exp_J1 = float(np.dot(psi_conj, J1_ops[j].dot(psi)).real)
            bond_current[t_idx, j] = exp_J0 + delta * exp_J1

            exp_n = float(np.dot(psi_conj, n_ops[j].dot(psi)).real)
            density[t_idx, j] = exp_n

    # --- Spatial averages ---
    current_mean = np.mean(bond_current, axis=1)  # (1/L) Σ J_j

    even_idx = np.arange(0, L, 2)
    odd_idx = np.arange(1, L, 2)
    # np.mean over L/2 elements already gives (2/L) Σ
    current_even = np.mean(bond_current[:, even_idx], axis=1)
    current_odd = np.mean(bond_current[:, odd_idx], axis=1)

    # --- Scaled current J(φ) = (T/2π) J(τ) ---
    factor = T / (2.0 * np.pi)
    scaled_current = factor * current_mean
    scaled_current_even = factor * current_even
    scaled_current_odd = factor * current_odd

    # --- Trapezoidal integration ---
    Q = _cumulative_trapezoid(times, current_mean)
    Q_even = _cumulative_trapezoid(times, current_even)
    Q_odd = _cumulative_trapezoid(times, current_odd)
    Q_cycle = float(Q[-1])

    # --- Continuity equation check ---
    continuity_residual = _check_continuity(times, density, bond_current)

    return CurrentResult(
        tau=times,
        tau_over_T=times / T,
        phi=2.0 * np.pi * times / T,
        bond_current=bond_current,
        current_mean=current_mean,
        current_even=current_even,
        current_odd=current_odd,
        scaled_current=scaled_current,
        scaled_current_even=scaled_current_even,
        scaled_current_odd=scaled_current_odd,
        Q=Q,
        Q_even=Q_even,
        Q_odd=Q_odd,
        Q_cycle=Q_cycle,
        density_by_site=density,
        continuity_residual=continuity_residual,
    )


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


def _cumulative_trapezoid(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integration: Q_k = ∫_{x_0}^{x_k} y(x) dx."""
    n = len(x)
    Q = np.zeros(n)
    for k in range(1, n):
        Q[k] = Q[k - 1] + 0.5 * (y[k] + y[k - 1]) * (x[k] - x[k - 1])
    return Q


# ---------------------------------------------------------------------------
# Continuity equation
# ---------------------------------------------------------------------------


def _check_continuity(
    times: np.ndarray,
    density: np.ndarray,         # (n_save, L)
    bond_current: np.ndarray,    # (n_save, L)
) -> float:
    """Verify d⟨n_j⟩/dτ = J_{j-1} - J_j.

    Uses central differences for d⟨n_j⟩/dτ.
    Returns max absolute residual over all (j, τ).
    """
    n_save, L = density.shape

    # Central difference for interior time points
    residual_max = 0.0

    for t_idx in range(1, n_save - 1):
        dtau = times[t_idx + 1] - times[t_idx - 1]
        if dtau == 0:
            continue
        for j in range(L):
            # d⟨n_j⟩/dτ via central difference
            dn_dtau = (density[t_idx + 1, j] - density[t_idx - 1, j]) / dtau

            # Divergence: J_{j-1} - J_j  (inflow - outflow)
            j_prev = (j - 1) % L
            div_J = bond_current[t_idx, j_prev] - bond_current[t_idx, j]

            res = abs(dn_dtau - div_J)
            if res > residual_max:
                residual_max = res

    return float(residual_max)
