"""Per-site spin-resolved observables for the RMH pump.

Uses direct Fock-basis bitwise computation — zero extra memory beyond
the state vector.  All density operators are diagonal in the
occupation-number basis.

QuSpin spinful basis encoding (uint32):
  bits  0 … L-1  → down-spin occupation
  bits  L … 2L-1 → up-spin occupation
"""

from __future__ import annotations

import numpy as np


def _measure_single_state(model, psi: np.ndarray):
    """Bitwise extraction of n_up, n_down for a single state vector.

    Returns
    -------
    n_up : np.ndarray, shape (L,)
    n_down : np.ndarray, shape (L,)
    n_total : np.ndarray, shape (L,)
    Sz : np.ndarray, shape (L,)
    """
    L = model.L
    basis_states = model.basis.states  # (dim,), uint32
    prob = np.abs(psi) ** 2  # (dim,)

    down_masks = np.array([1 << j for j in range(L)], dtype=np.uint32)
    up_masks = np.array([1 << (L + j) for j in range(L)], dtype=np.uint32)

    n_down = (basis_states[:, None] & down_masks[None, :]) != 0  # (dim, L)
    n_up = (basis_states[:, None] & up_masks[None, :]) != 0      # (dim, L)

    exp_n_up = np.sum(prob[:, None] * n_up.astype(np.float64), axis=0)
    exp_n_down = np.sum(prob[:, None] * n_down.astype(np.float64), axis=0)
    exp_n_total = exp_n_up + exp_n_down
    exp_Sz = (exp_n_up - exp_n_down) / 2.0

    return exp_n_up, exp_n_down, exp_n_total, exp_Sz


def measure_all_per_site(
    model,
    times: np.ndarray,
    states: list[np.ndarray],
) -> dict:
    """Measure per-site n_up, n_down, n_total, Sz for all saved states.

    Parameters
    ----------
    model : SplitRMHModel
    times : np.ndarray, shape (n_save,)
    states : list[np.ndarray]
        State vectors at each save point.

    Returns
    -------
    dict with keys:
        tau, n_up, n_down, n_total, Sz
        Each value array has shape (n_save, L).
    """
    L = model.L
    n_save = len(states)

    n_up = np.empty((n_save, L))
    n_down = np.empty((n_save, L))
    n_total = np.empty((n_save, L))
    Sz = np.empty((n_save, L))

    for idx, psi in enumerate(states):
        nu, nd, nt, sz = _measure_single_state(model, psi)
        n_up[idx, :] = nu
        n_down[idx, :] = nd
        n_total[idx, :] = nt
        Sz[idx, :] = sz

    return {
        "tau": times,
        "n_up": n_up,
        "n_down": n_down,
        "n_total": n_total,
        "Sz": Sz,
    }
