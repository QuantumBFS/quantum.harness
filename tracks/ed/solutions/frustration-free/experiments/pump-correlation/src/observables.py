"""Charge and spin correlation observables for the RMH pump.

Uses direct Fock-basis computation (bitwise) — zero extra memory beyond
the state vector.  All density-density operators are diagonal in the
occupation-number basis, so the expectation is simply:

    ⟨ψ| O |ψ⟩ = Σ_α |ψ_α|² O(α)

where O(α) reads the bits of the basis integers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import SplitRMHModel


@dataclass
class CorrelationResult:
    tau: np.ndarray              # shape (n_save,)
    C_spin: np.ndarray           # shape (n_save,) — spatially averaged
    C_charge: np.ndarray         # shape (n_save,)
    bond_spin: np.ndarray        # shape (n_save, L) — per-bond
    bond_charge: np.ndarray      # shape (n_save, L)
    norm_errors: list[float]


def measure_correlations(
    model: SplitRMHModel,
    times: np.ndarray,
    states: list[np.ndarray],
    norm_errors: list[float],
) -> CorrelationResult:
    """Measure charge and spin correlations directly from Fock basis.

    Uses bitwise extraction of occupation numbers from QuSpin's basis
    state integers.  This avoids building any operator matrices and
    uses zero extra memory — safe for L = 12, 14.
    """
    L = model.L
    n_save = len(states)
    basis_states = model.basis.states  # shape (dim,), dtype uint32 — encodes both spins
    dim = len(basis_states)

    # QuSpin spinful basis encoding:
    #   bits  0 … L-1  → down-spin occupation
    #   bits  L … 2L-1 → up-spin occupation

    # Pre-compute bit masks for all sites
    down_masks = np.array([1 << j for j in range(L)], dtype=basis_states.dtype)   # (L,)
    up_masks = np.array([1 << (L + j) for j in range(L)], dtype=basis_states.dtype)  # (L,)

    bond_spin = np.empty((n_save, L))
    bond_charge = np.empty((n_save, L))
    C_spin = np.empty(n_save)
    C_charge = np.empty(n_save)

    for t_idx, psi in enumerate(states):
        prob = np.abs(psi) ** 2  # shape (dim,)

        # Extract up/down occupations: (dim, L)
        n_down = (basis_states[:, None] & down_masks[None, :]) != 0
        n_up = (basis_states[:, None] & up_masks[None, :]) != 0
        n_total = n_up.astype(np.float64) + n_down.astype(np.float64)  # (dim, L)

        # n_j n_{j+1} for all bonds (including boundary via roll)
        n_neighbor = np.roll(n_total, -1, axis=1)
        nn_expect = np.sum(prob[:, None] * n_total * n_neighbor, axis=0)

        # S_j^z = (n↑ - n↓) / 2,  c_S = 4 <S_j^z S_{j+1}^z> = <(n↑-n↓)_j (n↑-n↓)_{j+1}>
        sz = n_up.astype(np.float64) - n_down.astype(np.float64)
        sz_neighbor = np.roll(sz, -1, axis=1)
        szsz_expect = np.sum(prob[:, None] * sz * sz_neighbor, axis=0)

        bond_spin[t_idx, :] = szsz_expect
        bond_charge[t_idx, :] = nn_expect
        C_spin[t_idx] = np.mean(bond_spin[t_idx, :])
        C_charge[t_idx] = np.mean(bond_charge[t_idx, :])

    return CorrelationResult(
        tau=times,
        C_spin=C_spin,
        C_charge=C_charge,
        bond_spin=bond_spin,
        bond_charge=bond_charge,
        norm_errors=norm_errors,
    )
