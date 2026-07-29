"""Strict Phase 8 crossing and two-point sensitivity evaluations."""

from __future__ import annotations

import math

import numpy as np


def _require_finite(*arrays: np.ndarray) -> None:
    if any(not np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("inputs must be finite")


def strict_endpoint_crossing(gammas, r_small, r_large) -> dict:
    """Interpolate a crossing only across two endpoints with opposite signs."""
    x = np.asarray(gammas, dtype=float)
    small = np.asarray(r_small, dtype=float)
    large = np.asarray(r_large, dtype=float)
    if x.shape != (2,) or small.shape != (2,) or large.shape != (2,):
        raise ValueError("exactly two endpoint values are required")
    _require_finite(x, small, large)
    if not x[0] < x[1]:
        raise ValueError("Gamma endpoints must be strictly increasing")

    differences = small - large
    base = {
        "Gamma_endpoints": x.tolist(),
        "differences": differences.tolist(),
    }
    if not differences[0] * differences[1] < 0.0:
        return {
            **base,
            "status": "unresolved_no_L64_L128_bracket",
        }

    fraction = -differences[0] / (differences[1] - differences[0])
    return {
        **base,
        "status": "resolved",
        "fraction": float(fraction),
        "Gamma_x": float(x[0] + fraction * (x[1] - x[0])),
        "crossing_resolution": float((x[1] - x[0]) / 2.0),
    }


def two_point_sensitivity(values, base_lengths, form: str) -> dict:
    """Evaluate a two-point asymptotic sensitivity without regression."""
    y = np.asarray(values, dtype=float)
    lengths = np.asarray(base_lengths, dtype=float)
    if y.shape != (2,) or lengths.shape != (2,):
        raise ValueError("exactly two size-pair values are required")
    _require_finite(y, lengths)
    if np.any(lengths <= 1.0) or not lengths[0] < lengths[1]:
        raise ValueError("base lengths must be increasing and exceed one")

    if form == "power":
        coordinate = 1.0 / lengths
    elif form == "log":
        coordinate = 1.0 / np.log(lengths)
    else:
        raise ValueError("form must be power or log")

    coefficient = (y[1] - y[0]) / (coordinate[1] - coordinate[0])
    estimate = y[0] - coefficient * coordinate[0]
    return {
        "form": form,
        "estimate": float(estimate),
        "coefficient": float(coefficient),
        "residual_degrees_of_freedom": 0,
        "interpretation": "two_point_sensitivity_extrapolation",
        "coordinate_role": "sensitivity_only",
        "known_correction_exponent_assumed": False,
    }


def gap_scaling_summary(lengths, gaps) -> dict:
    """Keep two-size effective exponents separate from sensitivity values."""
    sizes = np.asarray(lengths, dtype=int)
    values = np.asarray(gaps, dtype=float)
    if sizes.shape != (3,) or np.any(sizes[1:] != 2 * sizes[:-1]):
        raise ValueError("sizes must be three consecutive doubling values")
    if values.shape != (3,):
        raise ValueError("gaps must contain three positive values")
    _require_finite(values)
    if np.any(values <= 0.0):
        raise ValueError("gaps must contain three positive values")

    z32 = float(math.log(values[0] / values[1]) / math.log(2.0))
    z64 = float(math.log(values[1] / values[2]) / math.log(2.0))
    power = two_point_sensitivity([z32, z64], sizes[:2], "power")
    log = two_point_sensitivity([z32, z64], sizes[:2], "log")
    return {
        "lengths": sizes.tolist(),
        "gaps": values.tolist(),
        "z_eff": {"32_64": z32, "64_128": z64},
        "sensitivity": {
            "power": power,
            "log": log,
            "spread": abs(power["estimate"] - log["estimate"]),
        },
    }
