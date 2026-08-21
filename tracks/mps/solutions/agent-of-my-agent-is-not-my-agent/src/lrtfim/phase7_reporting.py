"""Pure analysis helpers for the deadline-focused Phase 7 report."""

from __future__ import annotations

import math

import numpy as np


def interpolate_endpoint_value(
    gamma_left: float,
    gamma_right: float,
    value_left: float,
    value_right: float,
    gamma_target: float,
) -> float:
    """Linearly interpolate an endpoint observable to ``gamma_target``."""
    if gamma_right <= gamma_left:
        raise ValueError("Gamma endpoints must be strictly increasing")
    if not gamma_left <= gamma_target <= gamma_right:
        raise ValueError("target Gamma lies outside the endpoint interval")
    fraction = (gamma_target - gamma_left) / (gamma_right - gamma_left)
    return float(value_left + fraction * (value_right - value_left))


def z_eff_from_gaps(delta_small: float, delta_large: float) -> float:
    """Return the gap-based pairwise effective exponent for doubled L."""
    if delta_small <= 0.0 or delta_large <= 0.0:
        raise ValueError("gaps must be positive")
    return float(math.log(delta_small / delta_large) / math.log(2.0))


def two_size_power_exponent(
    value_small: float,
    value_large: float,
    *,
    size_ratio: float,
) -> float:
    """Return ``log(value_large/value_small) / log(size_ratio)``."""
    if value_small <= 0.0 or value_large <= 0.0 or size_ratio <= 1.0:
        raise ValueError("values must be positive and size_ratio must exceed 1")
    return float(
        math.log(value_large / value_small) / math.log(size_ratio)
    )


def convergence_flags(
    state: dict,
    *,
    max_sweeps: int,
    relative_variance_threshold: float = 1.0e-10,
    discarded_weight_threshold: float = 1.0e-8,
) -> list[str]:
    """Apply the preregistered state-level convergence flags."""
    relative_variance = state["variance"] / max(state["energy"] ** 2, 1.0)
    flags = []
    if relative_variance > relative_variance_threshold:
        flags.append("relative_variance")
    if state["discarded_weight"] > discarded_weight_threshold:
        flags.append("discarded_weight")
    if state["sweeps"] >= max_sweeps:
        flags.append("sweep_cap")
    return flags


def endpoint_chi_validation(
    *,
    r_small,
    r_large_chi64,
    r_large_chi128,
    threshold: float,
) -> dict:
    """Audit endpoint R_xi shifts and the crossing sign structure."""
    small = np.asarray(r_small, dtype=float)
    low = np.asarray(r_large_chi64, dtype=float)
    high = np.asarray(r_large_chi128, dtype=float)
    if small.shape != (2,) or low.shape != (2,) or high.shape != (2,):
        raise ValueError("exactly two endpoint values are required")
    shifts = high - low
    old_difference = small - low
    new_difference = small - high
    signs_unchanged = bool(
        np.all(np.signbit(old_difference) == np.signbit(new_difference))
    )
    bracket_unchanged = bool(new_difference[0] * new_difference[1] < 0.0)
    maximum = float(np.max(np.abs(shifts)))
    return {
        "r_xi_shifts": shifts.tolist(),
        "old_differences": old_difference.tolist(),
        "new_differences": new_difference.tolist(),
        "max_abs_r_xi_shift": maximum,
        "threshold": float(threshold),
        "signs_unchanged": signs_unchanged,
        "bracket_unchanged": bracket_unchanged,
        "accepted": bool(
            maximum < threshold and signs_unchanged and bracket_unchanged
        ),
    }
