"""Spinon-holon relative motion metrics.

Computes overlap O_hs, relative COM distance D_hs, relative distribution
P_hs(r), and relative width ξ_hs from coarse-grained defect densities.

All metrics operate on two-site coarse-grained densities h̄_ℓ, s̄_ℓ
where ℓ indexes unit cells (0 … n_cells-1, n_cells = L/2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .hole import d_pbc


@dataclass
class RelativeMotionResult:
    """Spinon-holon relative motion for one protocol."""

    tau: np.ndarray                # (n_save,) time points
    protocol: str                  # "cw", "ccw", or "frozen"

    # Primary metrics
    O_hs: np.ndarray               # (n_save,) overlap Σ_ℓ h̄_ℓ s̄_ℓ
    D_hs: np.ndarray               # (n_save,) PBC COM distance
    xi_hs: np.ndarray              # (n_save,) width from |P_hs|
    xi_hs_signed: np.ndarray       # (n_save,) width from signed P_hs

    # Full relative distribution
    P_hs: np.ndarray               # (n_save, n_cells) signed P_hs(r, t)

    # Pump-induced changes (None for frozen protocol)
    delta_D_hs: np.ndarray | None = None   # (n_save,)
    delta_xi_hs: np.ndarray | None = None  # (n_save,)


@dataclass
class DeconfinementResult:
    """Complete deconfinement analysis across CW, CCW, frozen."""

    tau: np.ndarray                # (n_save,)

    # Per-protocol results
    cw: RelativeMotionResult
    ccw: RelativeMotionResult
    frozen: RelativeMotionResult

    # CW-CCW odd components
    D_hs_odd: np.ndarray           # (n_save,)
    xi_hs_odd: np.ndarray          # (n_save,)
    O_hs_odd: np.ndarray           # (n_save,)


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------


def compute_overlap(
    h_bar: np.ndarray,
    s_bar: np.ndarray,
) -> np.ndarray:
    """O_hs(t) = Σ_ℓ h̄_ℓ(t) s̄_ℓ(t).

    Parameters
    ----------
    h_bar : np.ndarray, shape (n_save, n_cells)
    s_bar : np.ndarray, shape (n_save, n_cells)

    Returns
    -------
    np.ndarray, shape (n_save,)
    """
    return np.sum(h_bar * s_bar, axis=1)


def compute_relative_distance(
    X_h: np.ndarray,
    X_s: np.ndarray,
    n_cells: int,
) -> np.ndarray:
    """D_hs(t) = d_PBC[X_h(t), X_s(t)].

    Uses PBC-aware minimum distance on the unit-cell ring.

    Parameters
    ----------
    X_h : np.ndarray, shape (n_save,)
        Holon COM position in unit-cell coordinates.
    X_s : np.ndarray, shape (n_save,)
        Spinon COM position in unit-cell coordinates.
    n_cells : int
        Number of unit cells (L/2).

    Returns
    -------
    np.ndarray, shape (n_save,)
    """
    n_save = len(X_h)
    D = np.empty(n_save)
    for i in range(n_save):
        D[i] = d_pbc(float(X_h[i]), float(X_s[i]), n_cells)
    return D


def compute_relative_distribution(
    h_bar: np.ndarray,
    s_bar: np.ndarray,
) -> np.ndarray:
    """P_hs(r, t) = Σ_ℓ h̄_ℓ(t) s̄_{ℓ+r}(t) (circular cross-correlation).

    Parameters
    ----------
    h_bar : np.ndarray, shape (n_save, n_cells)
    s_bar : np.ndarray, shape (n_save, n_cells)

    Returns
    -------
    np.ndarray, shape (n_save, n_cells)
        P_hs[r, t] — signed, no absolute value.
    """
    n_save, n_cells = h_bar.shape
    P = np.empty((n_save, n_cells))
    for r in range(n_cells):
        s_shifted = np.roll(s_bar, -r, axis=1)
        P[:, r] = np.sum(h_bar * s_shifted, axis=1)
    return P


def compute_relative_width(
    P_hs: np.ndarray,
    n_cells: int,
) -> tuple[np.ndarray, np.ndarray]:
    """ξ_hs(t) from absolute and signed P_hs.

    ξ_hs² = Σ_r d_PBC(r, 0)² |P(r)| / Σ_r |P(r)|          (absolute)
    ξ_hs_signed² = Σ_r d_PBC(r, 0)² P(r) / Σ_r P(r)       (signed)

    Parameters
    ----------
    P_hs : np.ndarray, shape (n_save, n_cells)
    n_cells : int

    Returns
    -------
    xi_abs : np.ndarray, shape (n_save,)
    xi_signed : np.ndarray, shape (n_save,)
    """
    n_save = P_hs.shape[0]
    r = np.arange(n_cells, dtype=np.float64)
    # d_PBC(r, 0) for each r
    d_sq = np.array([d_pbc(float(rr), 0.0, n_cells) ** 2 for rr in r])

    xi_abs = np.empty(n_save)
    xi_signed = np.empty(n_save)

    for i in range(n_save):
        P_row = P_hs[i, :]
        P_abs = np.abs(P_row)

        denom_abs = np.sum(P_abs)
        if denom_abs > 1e-30:
            xi_abs[i] = np.sqrt(np.sum(d_sq * P_abs) / denom_abs)
        else:
            xi_abs[i] = 0.0

        denom_signed = np.sum(P_row)
        if abs(denom_signed) > 1e-30:
            xi_signed[i] = np.sqrt(np.sum(d_sq * P_row) / denom_signed)
        else:
            xi_signed[i] = 0.0

    return xi_abs, xi_signed


# ---------------------------------------------------------------------------
# Protocol comparisons
# ---------------------------------------------------------------------------


def compute_delta_pump(
    Q_pump: np.ndarray,
    Q_frozen: np.ndarray,
) -> np.ndarray:
    """δQ^pump(t) = Q^pump(t) - Q^frozen(t)."""
    return Q_pump - Q_frozen


def compute_cw_ccw_odd(
    Q_cw: np.ndarray,
    Q_ccw: np.ndarray,
) -> np.ndarray:
    """Q^odd = (Q^CW - Q^CCW) / 2."""
    return (Q_cw - Q_ccw) / 2.0


# ---------------------------------------------------------------------------
# Master function
# ---------------------------------------------------------------------------


def compute_relative_motion_single(
    tau: np.ndarray,
    h_bar: np.ndarray,
    s_bar: np.ndarray,
    X_h: np.ndarray,
    X_s: np.ndarray,
    n_cells: int,
    protocol: str,
    frozen_result: RelativeMotionResult | None = None,
) -> RelativeMotionResult:
    """Compute all relative motion metrics for a single protocol.

    Parameters
    ----------
    tau : np.ndarray, shape (n_save,)
    h_bar, s_bar : np.ndarray, shape (n_save, n_cells)
    X_h, X_s : np.ndarray, shape (n_save,)
    n_cells : int
    protocol : str
    frozen_result : RelativeMotionResult or None
        If provided, compute δ relative to frozen.

    Returns
    -------
    RelativeMotionResult
    """
    O_hs = compute_overlap(h_bar, s_bar)
    D_hs = compute_relative_distance(X_h, X_s, n_cells)
    P_hs = compute_relative_distribution(h_bar, s_bar)
    xi_hs, xi_hs_signed = compute_relative_width(P_hs, n_cells)

    delta_D = None
    delta_xi = None
    if frozen_result is not None:
        delta_D = compute_delta_pump(D_hs, frozen_result.D_hs)
        delta_xi = compute_delta_pump(xi_hs, frozen_result.xi_hs)

    return RelativeMotionResult(
        tau=tau,
        protocol=protocol,
        O_hs=O_hs,
        D_hs=D_hs,
        xi_hs=xi_hs,
        xi_hs_signed=xi_hs_signed,
        P_hs=P_hs,
        delta_D_hs=delta_D,
        delta_xi_hs=delta_xi,
    )


def compute_deconfinement(
    tau: np.ndarray,
    defect_cw,
    defect_ccw,
    defect_frozen,
) -> DeconfinementResult:
    """Full deconfinement analysis from three DefectResult objects.

    Parameters
    ----------
    tau : np.ndarray, shape (n_save,)
    defect_cw, defect_ccw, defect_frozen : DefectResult
        Defect analysis output for each protocol.

    Returns
    -------
    DeconfinementResult
    """
    n_cells = defect_cw.h_bar.shape[1]

    # Frozen baseline (computed first since cw/ccw need it for delta)
    frozen = compute_relative_motion_single(
        tau=tau,
        h_bar=defect_frozen.h_bar,
        s_bar=defect_frozen.s_bar,
        X_h=defect_frozen.X_h,
        X_s=defect_frozen.X_s,
        n_cells=n_cells,
        protocol="frozen",
        frozen_result=None,
    )

    cw = compute_relative_motion_single(
        tau=tau,
        h_bar=defect_cw.h_bar,
        s_bar=defect_cw.s_bar,
        X_h=defect_cw.X_h,
        X_s=defect_cw.X_s,
        n_cells=n_cells,
        protocol="cw",
        frozen_result=frozen,
    )

    ccw = compute_relative_motion_single(
        tau=tau,
        h_bar=defect_ccw.h_bar,
        s_bar=defect_ccw.s_bar,
        X_h=defect_ccw.X_h,
        X_s=defect_ccw.X_s,
        n_cells=n_cells,
        protocol="ccw",
        frozen_result=frozen,
    )

    # CW-CCW odd components
    D_hs_odd = compute_cw_ccw_odd(cw.D_hs, ccw.D_hs)
    xi_hs_odd = compute_cw_ccw_odd(cw.xi_hs, ccw.xi_hs)
    O_hs_odd = compute_cw_ccw_odd(cw.O_hs, ccw.O_hs)

    return DeconfinementResult(
        tau=tau,
        cw=cw,
        ccw=ccw,
        frozen=frozen,
        D_hs_odd=D_hs_odd,
        xi_hs_odd=xi_hs_odd,
        O_hs_odd=O_hs_odd,
    )
