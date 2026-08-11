"""Exact PT-TEMPO versus Floquet-Markov comparison metrics and audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from .convergence import curve_residual


@dataclass(frozen=True)
class ErrorMetrics:
    trace_distance: float
    correlation: float
    heat: float


def trace_distance(
    first: NDArray[np.complex128], second: NDArray[np.complex128]
) -> float:
    if first.shape != second.shape or first.ndim != 2 or first.shape[0] != first.shape[1]:
        raise ValueError("density matrices must have the same square shape")
    difference = (first - second + (first - second).conj().T) / 2
    return float(0.5 * np.sum(abs(np.linalg.eigvalsh(difference))))


def correlation_error(
    exact_grid: NDArray[np.float64],
    exact: NDArray[np.complex128],
    markov_grid: NDArray[np.float64],
    markov: NDArray[np.complex128],
) -> float:
    return curve_residual(markov_grid, markov, exact_grid, exact)


def heat_error(
    exact_grid: NDArray[np.float64],
    exact: NDArray[np.float64],
    markov_grid: NDArray[np.float64],
    markov: NDArray[np.float64],
) -> float:
    return curve_residual(markov_grid, markov, exact_grid, exact)


def _complex_array(value: dict[str, Any]) -> NDArray[np.complex128]:
    return cast(
        NDArray[np.complex128],
        np.asarray(value["real"], dtype=float)
        + 1j * np.asarray(value["imag"], dtype=float),
    )


def build_error_record(
    exact: dict[str, Any], markov: dict[str, Any]
) -> dict[str, Any]:
    """Build a comparison only after checking scientific compatibility."""
    if not bool(exact.get("converged")):
        raise ValueError("exact PT-TEMPO input must be converged")
    exact_method = str(exact.get("method", ""))
    if exact_method not in {
        "pt_tempo_multitime",
        "uniform_tempo_floquet_multitime",
    }:
        raise ValueError("exact input must use an approved process-tensor method")
    if exact.get("model_hash") != markov.get("model_hash"):
        raise ValueError("model_hash mismatch")
    exact_normalization = exact.get("model", {}).get("normalization")
    markov_normalization = markov.get("model", {}).get("normalization")
    if exact_normalization != markov_normalization:
        raise ValueError("normalization mismatch")
    exact_frequency = np.asarray(exact["frequency"], dtype=float)
    markov_frequency = np.asarray(markov["frequency"], dtype=float)
    if (
        exact_frequency.shape != markov_frequency.shape
        or not np.allclose(exact_frequency, markov_frequency)
    ):
        raise ValueError("frequency grid mismatch")
    exact_delay = np.asarray(exact["correlation"]["delay"], dtype=float)
    markov_delay = np.asarray(markov["correlation"]["delay"], dtype=float)
    if exact_delay.shape != markov_delay.shape or not np.allclose(
        exact_delay, markov_delay
    ):
        raise ValueError("correlation grid mismatch")
    metrics = ErrorMetrics(
        trace_distance(
            _complex_array(exact["phase_state"]),
            _complex_array(markov["phase_state"]),
        ),
        correlation_error(
            exact_delay,
            _complex_array(exact["correlation"]["connected"]),
            markov_delay,
            _complex_array(markov["correlation"]["connected"]),
        ),
        heat_error(
            exact_frequency,
            np.asarray(exact["continuous"], dtype=float),
            markov_frequency,
            np.asarray(markov["continuous"], dtype=float),
        ),
    )
    return {
        "status": "converged",
        "model_hash": exact["model_hash"],
        "exact_method": exact["method"],
        "markov_method": markov["method"],
        "metrics": asdict(metrics),
        "convergence_evidence": exact.get("evidence", []),
    }


def audit_grid_manifest(
    manifest: dict[str, Any],
    alphas: tuple[float, ...] = (0.025, 0.05, 0.1),
    drive_ratios: tuple[float, ...] = (0.75, 1.0, 1.25),
) -> dict[str, Any]:
    """Require each requested cell to be converged or explicitly masked."""
    expected = {(float(alpha), float(ratio)) for alpha in alphas for ratio in drive_ratios}
    points = manifest.get("points")
    if not isinstance(points, list):
        raise ValueError("manifest points must be a list")
    observed: dict[tuple[float, float], dict[str, Any]] = {}
    for point in points:
        key = (float(point["alpha"]), float(point["drive_ratio"]))
        if key in observed:
            raise ValueError(f"duplicate grid point {key}")
        observed[key] = point
    if set(observed) != expected:
        missing = sorted(expected - set(observed))
        extra = sorted(set(observed) - expected)
        raise ValueError(f"grid mismatch; missing={missing}, extra={extra}")
    masked = 0
    for key, point in observed.items():
        status = point.get("status")
        if status == "converged":
            if not isinstance(point.get("metrics"), dict):
                raise ValueError(f"converged point {key} lacks metrics")
        elif status == "resource_ceiling":
            if point.get("metrics") is not None:
                raise ValueError(f"masked point {key} must not fabricate metrics")
            masked += 1
        else:
            raise ValueError(f"invalid status for point {key}: {status}")
    return {
        "complete": True,
        "requested_points": len(expected),
        "converged_points": len(expected) - masked,
        "masked_points": masked,
    }
