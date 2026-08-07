"""Direct square-lattice kernels for the marginal long-range XY audit."""

from __future__ import annotations

import math

import numpy as np


CATALAN = 0.915965594177219015054603514932384110774
C_INFINITY_SIGMA2 = 6.0 / (math.pi**2 * CATALAN)
RHO_LOG_SIGMA2 = math.pi * C_INFINITY_SIGMA2 / 2.0


def _centered_axis(length: int) -> np.ndarray:
    if length < 4 or length % 2:
        raise ValueError("length must be an even integer >=4")
    return np.arange(-length // 2, length // 2, dtype=np.float64)


def minimum_image_kernel(
    length: int,
    *,
    sigma: float = 2.0,
    normalization: float = 4.0,
    momentum_index: int = 1,
    momentum_indices: tuple[int, int] | None = None,
    fixed_coupling: float | None = None,
) -> dict:
    """Evaluate the normalized minimum-image torus kernel.

    By default momentum is ``(2*pi*momentum_index/length, 0)``.  A general
    integer pair can be supplied through ``momentum_indices``.  The
    one-row-at-a-time summation keeps memory linear in ``length`` while
    retaining the exact finite torus convention.  The oscillator is
    evaluated as ``2*sin(phase/2)^2`` to avoid small-angle cancellation.
    """

    if sigma <= 0 or normalization <= 0:
        raise ValueError("sigma and normalization must be positive")
    if momentum_indices is None:
        if not isinstance(momentum_index, int) or momentum_index < 1:
            raise ValueError("momentum_index must be a positive integer")
        indices = (momentum_index, 0)
    else:
        if (
            len(momentum_indices) != 2
            or any(
                not isinstance(component, int)
                for component in momentum_indices
            )
            or momentum_indices == (0, 0)
        ):
            raise ValueError(
                "momentum_indices must be a nonzero integer pair"
            )
        indices = momentum_indices
    if fixed_coupling is not None and (
        not math.isfinite(fixed_coupling) or fixed_coupling <= 0
    ):
        raise ValueError("fixed_coupling must be finite and positive")

    axis = _centered_axis(length)
    qx = 2.0 * math.pi * indices[0] / length
    qy = 2.0 * math.pi * indices[1] / length
    q_norm = math.hypot(qx, qy)
    denominator = 0.0
    numerator = 0.0
    exponent = -(2.0 + sigma) / 2.0
    for m in axis:
        radius_squared = m * m + axis * axis
        nonzero = radius_squared > 0
        weights = np.power(radius_squared[nonzero], exponent)
        denominator += float(np.sum(weights, dtype=np.float64))
        phase = qx * float(m) + qy * axis[nonzero]
        oscillator = 2.0 * np.sin(0.5 * phase) ** 2
        numerator += float(
            np.sum(weights * oscillator, dtype=np.float64)
        )
    finite_coupling = normalization / denominator
    coupling_used = (
        finite_coupling
        if fixed_coupling is None
        else float(fixed_coupling)
    )
    energy = coupling_used * numerator
    return {
        "L": int(length),
        "sigma": float(sigma),
        "normalization": float(normalization),
        "momentum_index": int(indices[0]),
        "momentum_indices": [int(indices[0]), int(indices[1])],
        "qx": qx,
        "qy": qy,
        "q_norm": q_norm,
        "k": q_norm,
        "c_L": finite_coupling,
        "coupling_used": coupling_used,
        "fixed_coupling": (
            None if fixed_coupling is None else float(fixed_coupling)
        ),
        "phase_formula": "2*sin(phase/2)^2",
        "E": energy,
        "E_over_k2": energy / (q_norm * q_norm),
        "E_over_q2": energy / (q_norm * q_norm),
        "rho_ratio": energy / (
            q_norm * q_norm * math.log(length)
        ),
    }


def dyadic_effective_slopes(rows: list[dict]) -> list[dict]:
    """Return intercept-free slopes between matching sizes ``L`` and ``2L``.

    Every row must describe the same momentum-index pair.  If
    ``E_L(q_L)/|q_L|^2 = rho*log(L) + B + o(1)``, then the returned
    difference quotient converges to ``rho`` without fitting ``B``.
    """

    if len(rows) < 2:
        raise ValueError("at least two rows are required")
    ordered = sorted(rows, key=lambda row: int(row["L"]))
    family = tuple(ordered[0].get("momentum_indices", [1, 0]))
    if any(
        tuple(row.get("momentum_indices", [1, 0])) != family
        for row in ordered
    ):
        raise ValueError("all rows must share one momentum-index pair")
    by_length = {int(row["L"]): row for row in ordered}
    if len(by_length) != len(ordered):
        raise ValueError("lengths must be unique")

    result = []
    for length in sorted(by_length):
        if 2 * length not in by_length:
            continue
        first = float(by_length[length]["E_over_k2"])
        second = float(by_length[2 * length]["E_over_k2"])
        rho_eff = (second - first) / math.log(2.0)
        signed = rho_eff / RHO_LOG_SIGMA2 - 1.0
        result.append(
            {
                "L": length,
                "two_L": 2 * length,
                "momentum_indices": list(family),
                "rho_eff": rho_eff,
                "prediction": RHO_LOG_SIGMA2,
                "signed_relative_error": signed,
                "relative_error": abs(signed),
            }
        )
    if not result:
        raise ValueError("no dyadic size pairs were found")
    return result


def infinite_lattice_kernel_cutoff(
    k: float,
    radius: int,
    *,
    coupling: float = C_INFINITY_SIGMA2,
) -> dict:
    """Evaluate the sigma=2 infinite-lattice kernel in a square cutoff.

    The omitted positive tail is bounded using ``1-cos <= 2`` and a simple
    radial comparison.  This is intended as a transparent numerical check,
    not an Ewald implementation.
    """

    if not 0 < k < math.pi or radius < 4 or coupling <= 0:
        raise ValueError("invalid k, cutoff, or coupling")
    axis = np.arange(-radius, radius + 1, dtype=np.float64)
    numerator = 0.0
    for m in axis:
        radius_squared = m * m + axis * axis
        nonzero = radius_squared > 0
        weights = np.power(radius_squared[nonzero], -2.0)
        numerator += (
            1.0 - math.cos(k * float(m))
        ) * float(np.sum(weights, dtype=np.float64))
    energy = coupling * numerator
    # For radius >=4, a conservative shell comparison suffices:
    # sum_{|R|>radius} |R|^-4 <= 8*pi/(radius-1)^2.
    tail_bound = (
        16.0 * math.pi * coupling / float(radius - 1) ** 2
    )
    return {
        "k": float(k),
        "radius": int(radius),
        "coupling": float(coupling),
        "E_cutoff": energy,
        "E_over_k2": energy / (k * k),
        "positive_tail_upper_bound": tail_bound,
        "tail_bound_over_k2": tail_bound / (k * k),
    }


def logarithmic_slope(rows: list[dict]) -> dict:
    """Fit ``E/k^2 = slope*log(L) + intercept``."""

    if len(rows) < 3:
        raise ValueError("at least three rows are required")
    x = np.log(np.asarray([row["L"] for row in rows], dtype=float))
    y = np.asarray([row["E_over_k2"] for row in rows], dtype=float)
    design = np.column_stack([x, np.ones_like(x)])
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - design @ np.asarray([slope, intercept])
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "slope_over_prediction": float(slope / RHO_LOG_SIGMA2),
        "rms_residual": float(np.sqrt(np.mean(residual**2))),
        "prediction": RHO_LOG_SIGMA2,
    }
