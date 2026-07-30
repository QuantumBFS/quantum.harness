"""Strict Phase 8 crossing and finite-size sensitivity evaluations."""

from __future__ import annotations

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


def adjacent_effective_exponents(lengths, gaps) -> dict:
    """Return gap-based pairwise z_eff values and logarithmic midpoints."""
    sizes = np.asarray(lengths, dtype=float)
    values = np.asarray(gaps, dtype=float)
    if sizes.ndim != 1 or values.ndim != 1 or sizes.size != values.size:
        raise ValueError("sizes and gaps must be one-dimensional and equal-length")
    if sizes.size < 2:
        raise ValueError("at least two sizes and gaps are required")
    _require_finite(sizes, values)
    if np.any(sizes <= 0.0) or np.any(np.diff(sizes) <= 0.0):
        raise ValueError("sizes must be positive and strictly increasing")
    if np.any(values <= 0.0):
        raise ValueError("gaps must contain positive values")

    z_eff = -np.log(values[1:] / values[:-1]) / np.log(
        sizes[1:] / sizes[:-1]
    )
    effective_lengths = np.sqrt(sizes[:-1] * sizes[1:])
    pairs = [
        f"{int(left)}_{int(right)}"
        for left, right in zip(sizes[:-1], sizes[1:])
    ]
    return {
        "pairs": pairs,
        "effective_lengths": effective_lengths.tolist(),
        "values": z_eff.tolist(),
    }


def direct_gap_power_law(lengths, gaps) -> dict:
    """Regress positive gaps against Delta=A*L^(-z) in log coordinates."""
    sizes = np.asarray(lengths, dtype=float)
    values = np.asarray(gaps, dtype=float)
    if sizes.ndim != 1 or values.ndim != 1 or sizes.size != values.size:
        raise ValueError("sizes and gaps must be one-dimensional and equal-length")
    if sizes.size < 3:
        raise ValueError("at least three sizes and gaps are required")
    _require_finite(sizes, values)
    if np.any(sizes <= 0.0) or np.any(values <= 0.0):
        raise ValueError("sizes and gaps must be positive")
    if np.any(np.diff(sizes) <= 0.0):
        raise ValueError("sizes must be strictly increasing")

    log_sizes = np.log(sizes)
    log_gaps = np.log(values)
    design = np.column_stack([np.ones_like(log_sizes), log_sizes])
    coefficients, _, _, _ = np.linalg.lstsq(design, log_gaps, rcond=None)
    log_amplitude, slope = coefficients
    predicted = design @ coefficients
    residuals = log_gaps - predicted
    return {
        "amplitude": float(np.exp(log_amplitude)),
        "exponent": float(-slope),
        "predicted_gaps": np.exp(predicted).tolist(),
        "log_residuals": residuals.tolist(),
        "residual_sum_squares": float(residuals @ residuals),
        "residual_rms": float(np.sqrt(np.mean(residuals**2))),
        "residual_degrees_of_freedom": int(values.size - 2),
        "interpretation": "direct_log_linear_gap_regression",
    }


def sensitivity_regression(z_values, effective_lengths, form: str) -> dict:
    """Regress z_eff against a declared finite-size sensitivity coordinate."""
    values = np.asarray(z_values, dtype=float)
    lengths = np.asarray(effective_lengths, dtype=float)
    if values.ndim != 1 or lengths.ndim != 1 or values.size != lengths.size:
        raise ValueError(
            "z values and effective lengths must be one-dimensional and equal-length"
        )
    if values.size < 3:
        raise ValueError("at least three z values are required")
    _require_finite(values, lengths)
    if np.any(lengths <= 1.0) or np.any(np.diff(lengths) <= 0.0):
        raise ValueError(
            "effective lengths must be strictly increasing and exceed one"
        )

    if form == "power":
        coordinate = 1.0 / lengths
    elif form == "log":
        coordinate = 1.0 / np.log(lengths)
    else:
        raise ValueError("form must be power or log")

    design = np.column_stack([np.ones_like(coordinate), coordinate])
    coefficients, _, _, _ = np.linalg.lstsq(design, values, rcond=None)
    estimate, coefficient = coefficients
    predicted = design @ coefficients
    residuals = values - predicted
    return {
        "form": form,
        "estimate": float(estimate),
        "coefficient": float(coefficient),
        "coordinate_values": coordinate.tolist(),
        "predicted_values": predicted.tolist(),
        "residuals": residuals.tolist(),
        "residual_sum_squares": float(residuals @ residuals),
        "residual_rms": float(np.sqrt(np.mean(residuals**2))),
        "residual_degrees_of_freedom": int(values.size - 2),
        "coordinate_role": "sensitivity_only",
        "known_correction_exponent_assumed": False,
    }


def gap_scaling_summary(lengths, gaps) -> dict:
    """Separate adjacent z_eff diagnostics from sensitivity regressions."""
    sizes = np.asarray(lengths, dtype=float)
    values = np.asarray(gaps, dtype=float)
    if sizes.shape != (5,) or values.shape != (5,):
        raise ValueError("exactly five sizes and gaps are required")
    adjacent = adjacent_effective_exponents(sizes, values)
    power = sensitivity_regression(
        adjacent["values"], adjacent["effective_lengths"], "power"
    )
    log = sensitivity_regression(
        adjacent["values"], adjacent["effective_lengths"], "log"
    )
    leave_power = sensitivity_regression(
        adjacent["values"][1:], adjacent["effective_lengths"][1:], "power"
    )
    leave_log = sensitivity_regression(
        adjacent["values"][1:], adjacent["effective_lengths"][1:], "log"
    )
    return {
        "lengths": sizes.astype(int).tolist(),
        "gaps": values.tolist(),
        "z_eff": adjacent,
        "regression": {
            "power": power,
            "log": log,
            "spread": abs(power["estimate"] - log["estimate"]),
            "leave_L16_out": {
                "power": leave_power,
                "log": leave_log,
                "spread": abs(
                    leave_power["estimate"] - leave_log["estimate"]
                ),
            },
            "interpretation": (
                "deterministic_finite_size_sensitivity_regression"
            ),
            "shared_gap_correlations_ignored": True,
        },
    }
