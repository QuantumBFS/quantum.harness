#!/usr/bin/env python3
"""Peel the exact microscopic Mori moments from the leading KPZ kernel.

The calculation combines only the public stationary-KPZ scaling table, the
microscopic XXX commutator moments, a declared chain length, and declared
times.  It does not read a Heisenberg transport trajectory or target Burgers
coefficients.  The output is the positive low-frequency Lanczos terminator
required by the leading KPZ structure factor after eight exact recurrents have
been removed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.interpolate import CubicSpline


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    finite_field_scale_correction,
    kpz_lambda_from_tba,
    kpz_mori_laplace_first_correction,
    kpz_mori_laplace_scaling,
    mori_lanczos_terminator_from_kernel,
    mori_lanczos_stieltjes_bounds,
    xxx_mori_lanczos_recurrents,
    xxx_mori_long_wave_lanczos,
)


KPZ_TABLE_URL = (
    "https://collab.dvb.bayern/download/attachments/56921793/gy.txt"
    "?version=1&modificationDate=1678352316510&api=v2"
)


def _load_table(path: Path | None) -> np.ndarray:
    if path is not None:
        return np.loadtxt(path)
    with tempfile.TemporaryDirectory(prefix="kpz_lanczos_") as directory:
        destination = Path(directory) / "gy.txt"
        urllib.request.urlretrieve(KPZ_TABLE_URL, destination)
        return np.loadtxt(destination)


def scaled_structure_laplace(
    table: np.ndarray,
    scaled_frequency: np.ndarray,
    *,
    quadrature_order: int = 600,
    fourier_cutoff: float = 20.0,
) -> np.ndarray:
    r"""Return ``Phi(s)=int exp(-s*u) fhat(u**(2/3)) du``."""

    if table.ndim != 2 or table.shape[1] < 2:
        raise ValueError("KPZ table must contain y and g(y) columns")
    s = np.asarray(scaled_frequency, dtype=float)
    if np.any(~np.isfinite(s)) or np.any(s <= 0.0):
        raise ValueError("scaled frequencies must be positive")
    if quadrature_order < 100 or fourier_cutoff <= 0.0:
        raise ValueError("quadrature order/cutoff is too small")

    spline = CubicSpline(table[:, 0], table[:, 1])
    nodes, weights = leggauss(quadrature_order)
    y_max = float(table[-1, 0])
    y = 0.5 * y_max * (nodes + 1.0)
    y_weight = 0.5 * y_max * weights
    density_weight = y_weight * spline(y, 2) / 4.0

    q = 0.5 * fourier_cutoff * (nodes + 1.0)
    q_weight = 0.5 * fourier_cutoff * weights
    fhat = 2.0 * (np.cos(np.outer(q, y)) @ density_weight)
    integrand_weight = 1.5 * q_weight * np.sqrt(q) * fhat
    return np.asarray(
        [
            np.sum(integrand_weight * np.exp(-value * q ** 1.5))
            for value in np.ravel(s)
        ]
    ).reshape(s.shape)


def scale_correction_structure_laplace(
    table: np.ndarray,
    scaled_frequency: np.ndarray,
    scale_correction: float,
    *,
    quadrature_order: int = 600,
    fourier_cutoff: float = 20.0,
) -> np.ndarray:
    r"""Return ``Phi1`` for ``L=L0*(1+b*t**(-1/3))``.

    For ``q=u**(2/3)``, the correction is
    ``F1(u)=b*q*d_q fhat(q)`` and therefore
    ``Phi1=3*b/2 int q exp(-s*q**(3/2))*d_q fhat(q) dq``.
    """

    s = np.asarray(scaled_frequency, dtype=float)
    b = float(scale_correction)
    if np.any(~np.isfinite(s)) or np.any(s <= 0.0) or not np.isfinite(b):
        raise ValueError("scaled frequencies must be positive and b finite")
    spline = CubicSpline(table[:, 0], table[:, 1])
    nodes, weights = leggauss(quadrature_order)
    y_max = float(table[-1, 0])
    y = 0.5 * y_max * (nodes + 1.0)
    y_weight = 0.5 * y_max * weights
    density_weight = y_weight * spline(y, 2) / 4.0
    q = 0.5 * fourier_cutoff * (nodes + 1.0)
    q_weight = 0.5 * fourier_cutoff * weights
    fhat_derivative = -2.0 * (np.sin(np.outer(q, y)) @ (y * density_weight))
    integrand_weight = 1.5 * b * q_weight * q * fhat_derivative
    return np.asarray(
        [
            np.sum(integrand_weight * np.exp(-value * q ** 1.5))
            for value in np.ravel(s)
        ]
    ).reshape(s.shape)


def derive(
    table: np.ndarray,
    *,
    length: int,
    modes: list[int],
    times: list[float],
    quadrature_order: int = 600,
) -> dict[str, object]:
    if length <= 0 or not modes or not times:
        raise ValueError("length, modes and times must be non-empty and positive")
    if min(modes) <= 0 or max(modes) >= length or min(times) <= 0.0:
        raise ValueError("invalid periodic mode or time")
    lam = kpz_lambda_from_tba()
    lanczos = xxx_mori_long_wave_lanczos()
    rows: list[dict[str, float | int]] = []
    requests: list[tuple[int, float, float, float, float]] = []
    scaled: list[float] = []
    for mode in modes:
        k = 2.0 * np.pi * mode / length
        rate = lam * abs(k) ** 1.5
        for time in times:
            z = 1.0 / time
            value = z / rate
            scaled.append(value)
            requests.append((mode, time, k, z, value))
    phi = scaled_structure_laplace(
        table, np.asarray(scaled), quadrature_order=quadrature_order
    )
    spectral_b = finite_field_scale_correction()
    phi1 = scale_correction_structure_laplace(
        table,
        np.asarray(scaled),
        spectral_b,
        quadrature_order=quadrature_order,
    )
    for request, phi_value, phi1_value in zip(requests, phi, phi1, strict=True):
        mode, time, k, z, scaled_frequency = request
        kernel = float(
            kpz_mori_laplace_scaling(k, z, phi_value, lambda_kpz=lam)
        )
        squared_recurrents = xxx_mori_lanczos_recurrents(np.asarray(k))
        delta_kernel = float(
            kpz_mori_laplace_first_correction(
                k, phi_value, phi1_value, lambda_kpz=lam
            )
        )
        corrected_kernel = kernel + delta_kernel
        terminator = float(
            mori_lanczos_terminator_from_kernel(
                z,
                kernel,
                float(lanczos["mu0"]),
                squared_recurrents,
            )
        )
        corrected_terminator = float(
            mori_lanczos_terminator_from_kernel(
                z,
                corrected_kernel,
                float(lanczos["mu0"]),
                squared_recurrents,
            )
        )
        moment_bounds = mori_lanczos_stieltjes_bounds(
            np.asarray(z), float(lanczos["mu0"]), squared_recurrents
        )
        rows.append(
            {
                "mode": mode,
                "time": time,
                "k": k,
                "z": z,
                "scaled_frequency": scaled_frequency,
                "Phi0": float(phi_value),
                "spectral_scale_Phi1_diagnostic": float(phi1_value),
                "leading_kpz_kernel_laplace": kernel,
                "spectral_scale_delta_kernel_diagnostic": delta_kernel,
                "spectral_scale_corrected_kernel_diagnostic": corrected_kernel,
                "spectral_scale_relative_kernel_correction": delta_kernel / kernel,
                "exact_k_squared_recurrents": squared_recurrents.tolist(),
                "eighth_lanczos_terminator": terminator,
                "spectral_scale_corrected_eighth_terminator_diagnostic": (
                    corrected_terminator
                ),
                "moment_only_kernel_lower": float(moment_bounds["lower"]),
                "moment_only_kernel_upper": float(moment_bounds["upper"]),
            }
        )
    return {
        "schema": 1,
        "inputs": {
            "length": length,
            "modes": modes,
            "times": times,
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "kpz_lambda": lam,
        "spectral_scale_diagnostic": {
            "scale_correction": spectral_b,
            "physical_subleading_coefficient_claimed": False,
        },
        "exact_long_wave_lanczos": {
            key: np.asarray(value).tolist() for key, value in lanczos.items()
        },
        "all_terminators_positive": all(
            float(row["eighth_lanczos_terminator"]) > 0.0 for row in rows
        ),
        "all_scale_corrected_terminators_positive": all(
            float(
                row[
                    "spectral_scale_corrected_eighth_terminator_diagnostic"
                ]
            )
            > 0.0
            for row in rows
        ),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--modes", type=int, nargs="+", default=[1, 2, 3, 4])
    parser.add_argument("--times", type=float, nargs="+", default=[50.0, 100.0, 200.0])
    parser.add_argument("--quadrature-order", type=int, default=600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        _load_table(args.kpz_table),
        length=args.length,
        modes=args.modes,
        times=args.times,
        quadrature_order=args.quadrature_order,
    )
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
