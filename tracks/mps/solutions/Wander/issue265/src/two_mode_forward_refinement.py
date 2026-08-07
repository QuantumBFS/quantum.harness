"""Deterministic space-time refinement gate for the registered NLFH forward map."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .two_mode_models import hidden_mode_initial_condition
from .two_mode_nlfh import TwoModeParams, simulate_two_mode

Array = np.ndarray


def _block_average(values: Array, stride: int) -> Array:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size % stride:
        raise ValueError("refinement grid is not divisible by stride")
    return values.reshape(values.size // stride, stride).mean(axis=1)


def _interpolate_rows(source_x: Array, values: Array, target_x: Array) -> Array:
    return np.stack(
        [np.interp(target_x, source_x, row) for row in np.asarray(values)]
    )


def _relative_l2(candidate: Array, reference: Array) -> float:
    return float(
        np.linalg.norm(candidate - reference)
        / max(float(np.linalg.norm(reference)), 1e-30)
    )


def audit_deterministic_forward_refinement(
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare registered screening/final grids against a finer reference."""

    length = int(config["L"])
    if length < 64 or length % 4:
        raise ValueError("refinement L must be at least 64 and divisible by four")
    full_x = np.arange(length, dtype=float) - 0.5 * (length - 1)
    mu = float(config["mu"])
    width = float(config["width"])
    alpha = float(config["alpha"])
    if mu <= 0 or width <= 0:
        raise ValueError("refinement mu and width must be positive")
    m_full = 0.5 * np.tanh(mu) * np.tanh(full_x / width)
    phi_full = hidden_mode_initial_condition(m_full, alpha)
    output_dt = float(config["output_dt"])
    t_max = float(config["t_max"])
    t = np.arange(0.0, t_max + 0.5 * output_dt, output_dt)
    params = TwoModeParams(**dict(config["params"]))
    levels = dict(config["levels"])
    required = {"screening", "final", "reference"}
    if set(levels) != required:
        raise ValueError("refinement levels must be screening/final/reference")

    simulations: dict[str, tuple[Array, Any]] = {}
    conservation: dict[str, float] = {}
    for name in ("screening", "final", "reference"):
        level = dict(levels[name])
        stride = int(level["spatial_stride"])
        dt_internal = float(level["dt_internal"])
        x = _block_average(full_x, stride)
        m0 = _block_average(m_full, stride)
        phi0 = _block_average(phi_full, stride)
        trajectory = simulate_two_mode(
            x=x,
            t=t,
            m0=m0,
            phi0=phi0,
            params=params,
            dt_internal=dt_internal,
            noise_faces=None,
        )
        simulations[name] = (x, trajectory)
        conservation[name] = max(
            float(np.max(np.abs(np.sum(trajectory.m, axis=1) - np.sum(m0)))),
            float(
                np.max(
                    np.abs(np.sum(trajectory.phi, axis=1) - np.sum(phi0))
                )
            ),
        )

    reference_x, reference = simulations["reference"]
    time_mask = t >= float(config["comparison_t_min"])
    space_mask = np.abs(reference_x) <= float(config["spatial_window"])
    reference_faces = 0.5 * (reference_x[:-1] + reference_x[1:])
    face_mask = np.abs(reference_faces) <= float(config["spatial_window"])
    comparisons: dict[str, dict[str, float]] = {}
    for name in ("screening", "final"):
        x, trajectory = simulations[name]
        interpolated_m = _interpolate_rows(x, trajectory.m, reference_x)
        faces = 0.5 * (x[:-1] + x[1:])
        interpolated_j = _interpolate_rows(
            faces,
            trajectory.jm_output[:, :-1],
            reference_faces,
        )
        comparisons[name] = {
            "profile_relative_l2": _relative_l2(
                interpolated_m[np.ix_(time_mask, space_mask)],
                reference.m[np.ix_(time_mask, space_mask)],
            ),
            "current_relative_l2": _relative_l2(
                interpolated_j[np.ix_(time_mask, face_mask)],
                reference.jm_output[:, :-1][np.ix_(time_mask, face_mask)],
            ),
        }

    thresholds = dict(config["thresholds"])
    final = comparisons["final"]
    screening = comparisons["screening"]
    checks = {
        "profile": final["profile_relative_l2"]
        <= float(thresholds["profile_relative_l2_max"]),
        "current": final["current_relative_l2"]
        <= float(thresholds["current_relative_l2_max"]),
        "profile_refines": final["profile_relative_l2"]
        < screening["profile_relative_l2"],
        "current_refines": final["current_relative_l2"]
        < screening["current_relative_l2"],
        "conservation": max(conservation.values())
        <= float(thresholds["conservation_error_max"]),
    }
    return {
        "status": "pass" if all(checks.values()) else "blocked",
        "quantum_fit_error_used": False,
        "levels": levels,
        "comparison_window": {
            "t_min": float(config["comparison_t_min"]),
            "t_max": float(t[-1]),
            "x_abs_max": float(config["spatial_window"]),
        },
        "comparisons": comparisons,
        "conservation_error": conservation,
        "checks": checks,
    }
