"""Defect densities and center-of-mass tracking.

Computes hole density h_j(t), particle density p_j(t), spin defect
densities s_j^{(-)}(t) and s_j^{(+)}(t), two-site coarse-grained
densities, and PBC-aware center-of-mass via complex phase method.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DefectResult:
    """Complete defect dynamics for one evolution protocol."""

    tau: np.ndarray                # (n_save,) time points

    # Raw per-site densities
    h_j: np.ndarray                # (n_save, L) hole density (N - N-1)
    s_j: np.ndarray                # (n_save, L) spin defect density (hole)

    # Two-site coarse-grained (L/2 unit cells)
    h_bar: np.ndarray              # (n_save, L/2)
    s_bar: np.ndarray              # (n_save, L/2)

    # Center-of-mass (unwrapped)
    X_h: np.ndarray                # (n_save,)
    X_s: np.ndarray                # (n_save,)
    Z_h: np.ndarray                # (n_save,) complex phase sum
    Z_s: np.ndarray                # (n_save,)

    # Widths (RMS deviation from COM)
    width_h: np.ndarray            # (n_save,)
    width_s: np.ndarray            # (n_save,)

    # Peak positions (argmax of coarse-grained density)
    peak_h: np.ndarray             # (n_save,)
    peak_s: np.ndarray             # (n_save,)

    # Sum checks
    sum_h: np.ndarray              # (n_save,) should = 1
    sum_s: np.ndarray              # (n_save,) should = 1

    # Reference expectations (raw, for diagnostics)
    n_ref: np.ndarray              # (n_save, L) half-filling ⟨n_j⟩
    Sz_ref: np.ndarray             # (n_save, L) half-filling ⟨S^z_j⟩
    n_hole: np.ndarray             # (n_save, L) one-hole ⟨n_j⟩
    Sz_hole: np.ndarray            # (n_save, L) one-hole ⟨S^z_j⟩


@dataclass
class ExtendedDefectResult:
    """Defect dynamics for both hole (N-1) and particle (N+1) sectors."""

    tau: np.ndarray                # (n_save,) time points

    # Hole sector
    hole: DefectResult = field(default=None)  # type: ignore

    # Particle sector
    particle: DefectResult = field(default=None)  # type: ignore

    # Per-site densities for particle sector
    p_j: np.ndarray = field(default=None)  # type: ignore  # (n_save, L)
    s_j_plus: np.ndarray = field(default=None)  # type: ignore  # (n_save, L)

    # Coarse-grained particle densities
    p_bar: np.ndarray = field(default=None)  # type: ignore  # (n_save, L/2)
    s_plus_bar: np.ndarray = field(default=None)  # type: ignore

    # Particle COM
    X_p: np.ndarray = field(default=None)  # type: ignore  # (n_save,)
    X_s_plus: np.ndarray = field(default=None)  # type: ignore  # (n_save,)
    Z_p: np.ndarray = field(default=None)  # type: ignore
    Z_s_plus: np.ndarray = field(default=None)  # type: ignore

    # Particle widths
    width_p: np.ndarray = field(default=None)  # type: ignore
    width_s_plus: np.ndarray = field(default=None)  # type: ignore

    # Particle peak positions
    peak_p: np.ndarray = field(default=None)  # type: ignore
    peak_s_plus: np.ndarray = field(default=None)  # type: ignore

    # Sum checks for particle
    sum_p: np.ndarray = field(default=None)  # type: ignore
    sum_s_plus: np.ndarray = field(default=None)  # type: ignore

    # Reference expectations for particle sector
    n_particle: np.ndarray = field(default=None)  # type: ignore  # (n_save, L)
    Sz_particle: np.ndarray = field(default=None)  # type: ignore


@dataclass
class PumpOddResult:
    """Pump-odd displacements and comparisons."""

    tau: np.ndarray                # (n_save,)

    # Pump-odd displacements
    dX_h_odd: np.ndarray           # (n_save,)
    dX_p_odd: np.ndarray           # (n_save,)
    dX_s_minus_odd: np.ndarray     # (n_save,)
    dX_s_plus_odd: np.ndarray      # (n_save,)

    # Frozen baselines (for subtracting drift)
    X_h_frozen: np.ndarray         # (n_save,)
    X_p_frozen: np.ndarray         # (n_save,)
    X_s_minus_frozen: np.ndarray   # (n_save,)
    X_s_plus_frozen: np.ndarray    # (n_save,)

    # Key comparisons
    hole_vs_particle_diff: np.ndarray      # dX_h_odd + dX_p_odd (should be 0 if symmetric)
    hole_charge_vs_spin_diff: np.ndarray   # dX_h_odd - dX_s_minus_odd
    particle_charge_vs_spin_diff: np.ndarray  # dX_p_odd - dX_s_plus_odd


def compute_hole_density(
    n_ref: np.ndarray,
    n_hole: np.ndarray,
) -> np.ndarray:
    """h_j(t) = ⟨n_j(t)⟩_N - ⟨n_j(t)⟩_{N-1}.

    Since we removed one electron, sum_j h_j = 1.
    """
    return n_ref - n_hole


def compute_spin_defect(
    Sz_ref: np.ndarray,
    Sz_hole: np.ndarray,
) -> np.ndarray:
    """s_j(t) = -2[⟨S^z_j(t)⟩_{N-1} - ⟨S^z_j(t)⟩_N].

    For half-filling, ⟨S^z_j⟩_N = 0, so s_j = -2⟨S^z_j⟩_{N-1}.
    The factor -2 ensures sum_j s_j = 1 (one missing spin-1/2).
    """
    return -2.0 * (Sz_hole - Sz_ref)


def coarse_grain_two_site(
    density: np.ndarray,
) -> np.ndarray:
    """Two-site coarse-graining: ā_ℓ = a_{2ℓ} + a_{2ℓ+1}.

    Parameters
    ----------
    density : np.ndarray, shape (n_save, L)

    Returns
    -------
    np.ndarray, shape (n_save, L/2)
    """
    L = density.shape[1]
    return density[:, 0:L:2] + density[:, 1:L:2]


def compute_com_phase(
    density_bar: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Center-of-mass via complex phase method.

    Z_a(t) = Σ_ℓ ā_ℓ(t) e^{i·2π·ℓ / (L/2)}
    X_a(t) = (L/2)/(2π) · arg(Z_a)  (principal periodic coordinate)

    Parameters
    ----------
    density_bar : np.ndarray, shape (n_save, L/2)
        Coarse-grained defect density.

    Returns
    -------
    Z : np.ndarray, shape (n_save,) — complex phase sum
    X : np.ndarray, shape (n_save,) — COM position in ``[0, n_cells)``
    width : np.ndarray, shape (n_save,) — RMS deviation
    """
    n_save = density_bar.shape[0]
    n_cells = density_bar.shape[1]  # = L/2
    ell = np.arange(n_cells, dtype=np.float64)
    phases = np.exp(2j * np.pi * ell / n_cells)  # (n_cells,)

    Z = density_bar @ phases  # (n_save,)

    # Guard against near-zero |Z|
    abs_Z = np.abs(Z)
    X_raw = np.full(n_save, np.nan)
    valid = abs_Z > 1e-14
    # np.angle returns [-π, π); normalize to [0, n_cells) for consistency
    X_raw[valid] = (np.angle(Z[valid]) * n_cells / (2.0 * np.pi)) % n_cells

    # Keep the principal periodic coordinate.  Applying ``np.unwrap`` to
    # these cell coordinates would use radians as the period and produces
    # incorrect values for trajectories that jump across the boundary.
    X = np.array(X_raw)

    # Width: RMS deviation from COM
    ell_grid = ell[None, :]  # (1, n_cells)
    X_col = X[:, None]  # (n_save, 1)
    delta_ell_sq = np.where(
        np.isfinite(X_col),
        (ell_grid - X_col) ** 2,
        (ell_grid) ** 2,
    )
    width = np.sqrt(np.sum(density_bar * delta_ell_sq, axis=1))

    return Z, X, width


def compute_peak_position(
    density_bar: np.ndarray,
) -> np.ndarray:
    """Peak position = argmax of coarse-grained density.

    Returns
    -------
    np.ndarray, shape (n_save,)
    """
    return np.argmax(density_bar, axis=1).astype(np.float64)


def compute_all_defects(
    obs_ref: dict,
    obs_hole: dict,
) -> DefectResult:
    """Full pipeline: hole/spin densities, coarse-graining, COM.

    Parameters
    ----------
    obs_ref : dict
        Output of measure_all_per_site for half-filling sector.
    obs_hole : dict
        Output of measure_all_per_site for one-hole sector.

    Returns
    -------
    DefectResult
    """
    tau = obs_ref["tau"]
    n_ref = obs_ref["n_total"]
    Sz_ref = obs_ref["Sz"]
    n_hole = obs_hole["n_total"]
    Sz_hole = obs_hole["Sz"]

    h_j = compute_hole_density(n_ref, n_hole)
    s_j = compute_spin_defect(Sz_ref, Sz_hole)

    h_bar = coarse_grain_two_site(h_j)
    s_bar = coarse_grain_two_site(s_j)

    Z_h, X_h, width_h = compute_com_phase(h_bar)
    Z_s, X_s, width_s = compute_com_phase(s_bar)

    peak_h = compute_peak_position(h_bar)
    peak_s = compute_peak_position(s_bar)

    sum_h = np.sum(h_j, axis=1)
    sum_s = np.sum(s_j, axis=1)

    return DefectResult(
        tau=tau,
        h_j=h_j, s_j=s_j,
        h_bar=h_bar, s_bar=s_bar,
        X_h=X_h, X_s=X_s,
        Z_h=Z_h, Z_s=Z_s,
        width_h=width_h, width_s=width_s,
        peak_h=peak_h, peak_s=peak_s,
        sum_h=sum_h, sum_s=sum_s,
        n_ref=n_ref, Sz_ref=Sz_ref,
        n_hole=n_hole, Sz_hole=Sz_hole,
    )


# ---------------------------------------------------------------------------
# Particle sector defect densities
# ---------------------------------------------------------------------------


def compute_particle_density(
    n_ref: np.ndarray,
    n_particle: np.ndarray,
) -> np.ndarray:
    """p_j(t) = ⟨n_j(t)⟩_{N+1} - ⟨n_j(t)⟩_N.

    Since we added one electron, sum_j p_j = 1.
    """
    return n_particle - n_ref


def compute_particle_spin(
    Sz_ref: np.ndarray,
    Sz_particle: np.ndarray,
) -> np.ndarray:
    """s_j^{(+)}(t) = 2[⟨S^z_j(t)⟩_{N+1} - ⟨S^z_j(t)⟩_N].

    The factor 2 ensures sum_j s_j^{(+)} = 1 (one extra spin-1/2).
    """
    return 2.0 * (Sz_particle - Sz_ref)


def _defect_pipeline(n_ref, Sz_ref, n_ex, Sz_ex):
    """Common pipeline: density, spin defect, coarse-graining, COM.

    Returns dict with all computed quantities.
    """
    density = n_ref - n_ex  # hole convention: h_j = n_ref - n_hole
    spin_defect = -2.0 * (Sz_ex - Sz_ref)  # s_j = -2(Sz_ex - Sz_ref)

    d_bar = coarse_grain_two_site(density)
    s_bar = coarse_grain_two_site(spin_defect)

    Z_d, X_d, width_d = compute_com_phase(d_bar)
    Z_s, X_s, width_s = compute_com_phase(s_bar)

    peak_d = compute_peak_position(d_bar)
    peak_s = compute_peak_position(s_bar)

    sum_d = np.sum(density, axis=1)
    sum_s = np.sum(spin_defect, axis=1)

    return {
        "density": density,
        "spin_defect": spin_defect,
        "d_bar": d_bar,
        "s_bar": s_bar,
        "Z_d": Z_d, "X_d": X_d, "width_d": width_d,
        "Z_s": Z_s, "X_s": X_s, "width_s": width_s,
        "peak_d": peak_d, "peak_s": peak_s,
        "sum_d": sum_d, "sum_s": sum_s,
    }


def compute_all_defects_extended(
    obs_ref: dict,
    obs_hole: dict,
    obs_particle: dict,
):
    """Full pipeline for both hole and particle sectors.

    Parameters
    ----------
    obs_ref : dict
        Output of measure_all_per_site for half-filling sector.
    obs_hole : dict
        Output of measure_all_per_site for one-hole sector (N-1).
    obs_particle : dict
        Output of measure_all_per_site for one-particle sector (N+1).

    Returns
    -------
    ExtendedDefectResult
    """
    tau = obs_ref["tau"]
    n_ref = obs_ref["n_total"]
    Sz_ref = obs_ref["Sz"]

    # --- Hole sector ---
    hole_defect = compute_all_defects(obs_ref, obs_hole)

    # --- Particle sector ---
    n_particle = obs_particle["n_total"]
    Sz_particle = obs_particle["Sz"]

    p_j = compute_particle_density(n_ref, n_particle)
    s_j_plus = compute_particle_spin(Sz_ref, Sz_particle)

    p_bar = coarse_grain_two_site(p_j)
    s_plus_bar = coarse_grain_two_site(s_j_plus)

    Z_p, X_p, width_p = compute_com_phase(p_bar)
    Z_s_plus, X_s_plus, width_s_plus = compute_com_phase(s_plus_bar)

    peak_p = compute_peak_position(p_bar)
    peak_s_plus = compute_peak_position(s_plus_bar)

    sum_p = np.sum(p_j, axis=1)
    sum_s_plus = np.sum(s_j_plus, axis=1)

    return ExtendedDefectResult(
        tau=tau,
        hole=hole_defect,
        particle=None,  # not a full DefectResult; fields stored directly
        p_j=p_j,
        s_j_plus=s_j_plus,
        p_bar=p_bar,
        s_plus_bar=s_plus_bar,
        X_p=X_p,
        X_s_plus=X_s_plus,
        Z_p=Z_p,
        Z_s_plus=Z_s_plus,
        width_p=width_p,
        width_s_plus=width_s_plus,
        peak_p=peak_p,
        peak_s_plus=peak_s_plus,
        sum_p=sum_p,
        sum_s_plus=sum_s_plus,
        n_particle=n_particle,
        Sz_particle=Sz_particle,
    )


def compute_pump_odd(
    tau: np.ndarray,
    X_cw: dict,
    X_ccw: dict,
    X_frozen: dict,
) -> PumpOddResult:
    """Compute pump-odd displacements from CW, CCW, and frozen COM data.

    Parameters
    ----------
    tau : np.ndarray, shape (n_save,)
    X_cw : dict with keys "X_h", "X_s", "X_p", "X_s_plus"
    X_ccw : dict with keys "X_h", "X_s", "X_p", "X_s_plus"
    X_frozen : dict with keys "X_h", "X_s", "X_p", "X_s_plus"

    Returns
    -------
    PumpOddResult
    """
    dX_h_odd = (X_cw["X_h"] - X_ccw["X_h"]) / 2.0
    dX_p_odd = (X_cw["X_p"] - X_ccw["X_p"]) / 2.0
    dX_s_minus_odd = (X_cw["X_s"] - X_ccw["X_s"]) / 2.0
    dX_s_plus_odd = (X_cw["X_s_plus"] - X_ccw["X_s_plus"]) / 2.0

    return PumpOddResult(
        tau=tau,
        dX_h_odd=dX_h_odd,
        dX_p_odd=dX_p_odd,
        dX_s_minus_odd=dX_s_minus_odd,
        dX_s_plus_odd=dX_s_plus_odd,
        X_h_frozen=X_frozen["X_h"],
        X_p_frozen=X_frozen["X_p"],
        X_s_minus_frozen=X_frozen["X_s"],
        X_s_plus_frozen=X_frozen["X_s_plus"],
        hole_vs_particle_diff=dX_h_odd + dX_p_odd,
        hole_charge_vs_spin_diff=dX_h_odd - dX_s_minus_odd,
        particle_charge_vs_spin_diff=dX_p_odd - dX_s_plus_odd,
    )
