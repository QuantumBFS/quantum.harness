#!/usr/bin/env python3
"""Theory-only strong projection including the known finite wall width.

The script uses only

* the infinite-temperature XXX TBA value of the KPZ scale,
* the universal stationary Praehofer--Spohn scaling table,
* the declared initial wall ``U(x,0)=tanh(x/w)/2``, and
* the requested time and spatial windows.

No Heisenberg trajectory or fitted width enters.  The optional scale
correction is the analytic giant-string *spectral-regulator* correction; it
is printed with that qualifier because it is not the constant term of the
full physical finite-field diffusion matrix.
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
from scipy.integrate import trapezoid
from scipy.interpolate import CubicSpline
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    finite_field_scale_correction,
    kpz_lambda_from_tba,
)


KPZ_TABLE_URL = (
    "https://collab.dvb.bayern/download/attachments/56921793/gy.txt"
    "?version=1&modificationDate=1678352316510&api=v2"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--wall-width", type=float, default=2.0)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--x-crop", type=float, default=120.0)
    parser.add_argument("--x-extent", type=float, default=512.0)
    parser.add_argument("--dx", type=float, default=0.0625)
    parser.add_argument("--time-order", type=int, default=100)
    parser.add_argument(
        "--scale-correction",
        type=float,
        help=(
            "Coefficient b in L=c(t^(2/3)+b*t^(1/3)); the default is the "
            "analytic spectral-regulator value"
        ),
    )
    return parser.parse_args()


def _load_table(path: Path | None) -> np.ndarray:
    if path is not None:
        return np.loadtxt(path)
    with tempfile.TemporaryDirectory(prefix="kpz_ps_") as directory:
        destination = Path(directory) / "gy.txt"
        urllib.request.urlretrieve(KPZ_TABLE_URL, destination)
        return np.loadtxt(destination)


def _sech_squared_density(x: np.ndarray, width: float) -> np.ndarray:
    """Return d[tanh(x/w)/2]/dx without hyperbolic overflow."""

    tail = np.exp(-2.0 * np.abs(x / width))
    return 2.0 * tail / (width * (1.0 + tail) ** 2)


def _project(
    values: np.ndarray,
    *,
    width: float,
    t_start: float,
    t_stop: float,
    x_crop: float,
    x_extent: float,
    dx: float,
    time_order: int,
    scale_correction: float,
) -> dict[str, float | list[list[float]] | list[float]]:
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("KPZ table must contain y and g(y) columns")
    if not (0.0 < t_start < t_stop):
        raise ValueError("Require 0 < t-start < t-stop")
    if min(width, x_crop, x_extent, dx) <= 0.0 or x_crop >= x_extent:
        raise ValueError("Widths must be positive and x-crop < x-extent")
    if time_order < 12:
        raise ValueError("time-order must be at least 12")

    spline = CubicSpline(values[:, 0], values[:, 1])
    y_max = float(spline.x[-1])
    lambda_kpz = kpz_lambda_from_tba()
    scale = lambda_kpz ** (2.0 / 3.0)
    b = float(scale_correction)

    x = np.arange(-x_extent, x_extent + 0.5 * dx, dx)
    initial_gradient = _sech_squared_density(x, width)
    nodes, weights = leggauss(time_order)
    times = 0.5 * (t_stop + t_start) + 0.5 * (t_stop - t_start) * nodes
    time_weights = 0.5 * (t_stop - t_start) * weights
    crop = np.abs(x) <= x_crop
    crop_x = x[crop]

    gram = np.zeros((2, 2), dtype=float)
    rhs = np.zeros(2, dtype=float)
    target_norm_squared = 0.0

    for time, time_weight in zip(times, time_weights, strict=True):
        u = time ** (1.0 / 3.0)
        length = scale * u * (u + b)
        length_derivative = scale / 3.0 * (2.0 / u + b / u**2)
        if length <= 0.0:
            raise ValueError("Corrected KPZ scale is non-positive in the window")

        y = x / length
        absolute_y = np.abs(y)
        inside = absolute_y <= y_max
        density = np.zeros_like(x)
        density_derivative = np.zeros_like(x)
        density[inside] = spline(absolute_y[inside], 2) / 4.0
        density_derivative[inside] = (
            np.sign(y[inside]) * spline(absolute_y[inside], 3) / 4.0
        )

        kernel = density / length
        kernel_time_derivative = -length_derivative / length**2 * (
            density + y * density_derivative
        )
        gradient = fftconvolve(kernel, initial_gradient, mode="same") * dx
        gradient_time_derivative = (
            fftconvolve(
                kernel_time_derivative, initial_gradient, mode="same"
            )
            * dx
        )
        # Its continuum integral is exactly zero.  Removing the tiny FFT/grid
        # mean prevents accumulation of a constant tail in U_t.
        gradient_time_derivative -= trapezoid(
            gradient_time_derivative, x
        ) / (2.0 * x_extent)

        wall = -0.5 + np.r_[
            0.0,
            np.cumsum(0.5 * (gradient[:-1] + gradient[1:]) * dx),
        ]
        wall_time_derivative = np.r_[
            0.0,
            np.cumsum(
                0.5
                * (
                    gradient_time_derivative[:-1]
                    + gradient_time_derivative[1:]
                )
                * dx
            ),
        ]
        gradient_x = np.gradient(gradient, dx, edge_order=2)

        x1 = (-wall * gradient)[crop]
        x2 = gradient_x[crop]
        target = wall_time_derivative[crop]
        gram[0, 0] += time_weight * trapezoid(x1 * x1, crop_x)
        gram[0, 1] += time_weight * trapezoid(x1 * x2, crop_x)
        gram[1, 1] += time_weight * trapezoid(x2 * x2, crop_x)
        rhs[0] += time_weight * trapezoid(x1 * target, crop_x)
        rhs[1] += time_weight * trapezoid(x2 * target, crop_x)
        target_norm_squared += time_weight * trapezoid(target**2, crop_x)

    gram[1, 0] = gram[0, 1]
    coefficient, diffusion = np.linalg.solve(gram, rhs)
    residual_squared = (
        target_norm_squared
        - 2.0 * np.array([coefficient, diffusion]) @ rhs
        + np.array([coefficient, diffusion])
        @ gram
        @ np.array([coefficient, diffusion])
    )
    return {
        "coefficient": float(coefficient),
        "diffusion": float(diffusion),
        "relative_strong_residual": float(
            np.sqrt(max(residual_squared, 0.0) / target_norm_squared)
        ),
        "gram_condition_number": float(np.linalg.cond(gram)),
        "gram": gram.tolist(),
        "rhs": rhs.tolist(),
    }


def main() -> int:
    args = _arguments()
    values = _load_table(args.kpz_table)
    correction = (
        finite_field_scale_correction()
        if args.scale_correction is None
        else float(args.scale_correction)
    )
    result = _project(
        values,
        width=args.wall_width,
        t_start=args.t_start,
        t_stop=args.t_stop,
        x_crop=args.x_crop,
        x_extent=args.x_extent,
        dx=args.dx,
        time_order=args.time_order,
        scale_correction=correction,
    )
    result.update(
        {
            "wall_width": float(args.wall_width),
            "time_window": [float(args.t_start), float(args.t_stop)],
            "space_crop": float(args.x_crop),
            "kpz_lambda": kpz_lambda_from_tba(),
            "scale_correction": correction,
            "scale_correction_kind": (
                "spectral_regulator"
                if args.scale_correction is None
                else "user_supplied"
            ),
            "uses_heisenberg_trajectory": False,
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
