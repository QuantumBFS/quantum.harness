#!/usr/bin/env python3
"""Propagate a target-free regular Mori-kernel correction through a KPZ wall.

The leading stationary-KPZ structure factor is constructed from the
Praehofer--Spohn scaling table.  If the small-k memory kernel is changed by a
constant regular term ``d``, first-order resolvent perturbation gives

    delta S(k,t) = -d khat(k)^2 integral_0^t S0(k,s) S0(k,t-s) ds.

This script performs that causal convolution, inverse transforms the complete
structure factor to the wall profile, and applies the frozen public weak
projection.  It does not read a spin-chain trajectory or accept target Burgers
coefficients.  The default ``d=-2/(3 pi)`` is a spectral-regulator diagnostic,
not a certified physical finite part of the XXX Mori kernel.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import fftconvolve, savgol_filter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_theory_finite_size_lattice import _load_spline  # noqa: E402
from src.heisenberg_burgers_bridge import (  # noqa: E402
    SPECTRAL_REGULATOR_D1_INFINITY_T,
    kpz_lambda_from_tba,
)
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=(-120.0, 120.0))
    parser.add_argument("--regular-kernel", type=float, default=SPECTRAL_REGULATOR_D1_INFINITY_T)
    parser.add_argument("--characteristic-grid", type=int, default=12001)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _universal_characteristic(
    spline: CubicSpline,
    maximum_argument: float,
    grid_size: int,
) -> CubicSpline:
    """Return the even KPZ density characteristic function by quadrature."""
    if grid_size < 1001:
        raise ValueError("characteristic grid must contain at least 1001 points")
    y = np.linspace(0.0, float(spline.x[-1]), 4097)
    density = np.maximum(np.asarray(spline(y, 2), dtype=float) / 4.0, 0.0)
    normalization = 2.0 * np.trapezoid(density, y)
    if not normalization > 0.0:
        raise ValueError("KPZ density table has non-positive normalization")
    density /= normalization
    arguments = np.linspace(0.0, maximum_argument, grid_size)
    characteristic = np.empty_like(arguments)
    # Chunking avoids a several-hundred-MiB cosine matrix.
    for start in range(0, grid_size, 256):
        stop = min(start + 256, grid_size)
        cosine = np.cos(np.multiply.outer(arguments[start:stop], y))
        characteristic[start:stop] = 2.0 * np.trapezoid(cosine * density, y, axis=1)
    characteristic[0] = 1.0
    return CubicSpline(arguments, characteristic)


def _weak_fit(
    x: np.ndarray,
    times: np.ndarray,
    wall: np.ndarray,
    fit_window: tuple[float, float],
    x_crop: tuple[float, float],
) -> dict[str, float | int]:
    smoothed = savgol_filter(wall, 31, 7, axis=1, mode="interp")
    fit = fit_profiled_weak(
        x,
        times,
        smoothed,
        t_window=fit_window,
        x_crop=x_crop,
        gamma=0.0,
    )
    return {
        "a": float(fit.a),
        "D": float(fit.D0),
        "mse": float(fit.mse),
        "n_obs": int(fit.n_obs),
    }


def derive(
    *,
    length: int,
    dx: float,
    dt: float,
    profile_start: float,
    profile_stop: float,
    fit_start: float,
    fit_stop: float,
    x_crop: tuple[float, float],
    regular_kernel: float,
    characteristic_grid: int,
    spline: CubicSpline,
) -> dict[str, object]:
    if length < 32 or length % 2:
        raise ValueError("length must be an even integer >=32")
    if dx <= 0.0 or dt <= 0.0:
        raise ValueError("dx and dt must be positive")
    if not 0.0 < profile_start <= fit_start < fit_stop <= profile_stop:
        raise ValueError("fit window must lie inside the profile window")

    lambda_kpz = float(kpz_lambda_from_tba())
    all_times = np.arange(0.0, profile_stop + 0.5 * dt, dt)
    k = 2.0 * np.pi * np.fft.fftfreq(length, d=dx)
    khat_squared = (2.0 * np.sin(0.5 * k * dx) / dx) ** 2
    front_lengths = (lambda_kpz * all_times) ** (2.0 / 3.0)
    maximum_argument = float(np.max(np.abs(k)) * front_lengths[-1])
    characteristic = _universal_characteristic(
        spline, maximum_argument, characteristic_grid
    )
    leading_structure = characteristic(
        np.multiply.outer(front_lengths, np.abs(k))
    )
    leading_structure[0, :] = 1.0

    convolution = np.empty_like(leading_structure)
    for mode in range(length):
        raw = dt * fftconvolve(
            leading_structure[:, mode], leading_structure[:, mode], mode="full"
        )[: all_times.size]
        # Trapezoidal endpoint correction.  S0(k,0)=1, so the rectangular
        # convolution overcounts its two half-weight endpoints by dt*S0(k,t).
        convolution[:, mode] = raw - dt * leading_structure[:, mode]
    convolution[0, :] = 0.0
    delta_structure = (
        -float(regular_kernel)
        * convolution
        * khat_squared[np.newaxis, :]
    )
    corrected_structure = leading_structure + delta_structure

    profile_mask = all_times >= profile_start - 0.25 * dt
    times = all_times[profile_mask]
    x = (np.arange(length, dtype=float) - 0.5 * (length - 1)) * dx
    inverse_phase = np.exp(1.0j * np.multiply.outer(x, k)) / (length * dx)

    def structure_to_density_and_wall(structure: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        density = np.real(structure[profile_mask] @ inverse_phase.T)
        wall = dx * np.cumsum(density, axis=1) - 0.5
        # Center the discrete cumulative wall at the bond between the two
        # central half-integer sites.
        wall -= 0.5 * dx * density
        return density, wall

    leading_density, leading_wall = structure_to_density_and_wall(leading_structure)
    corrected_density, corrected_wall = structure_to_density_and_wall(corrected_structure)
    delta_wall = corrected_wall - leading_wall

    leading_fit = _weak_fit(
        x, times, leading_wall, (fit_start, fit_stop), x_crop
    )
    corrected_fit = _weak_fit(
        x, times, corrected_wall, (fit_start, fit_stop), x_crop
    )
    return {
        "schema_version": 1,
        "inputs": {
            "length": int(length),
            "dx": float(dx),
            "dt": float(dt),
            "profile_window": [float(profile_start), float(profile_stop)],
            "fit_window": [float(fit_start), float(fit_stop)],
            "x_crop": [float(x_crop[0]), float(x_crop[1])],
            "regular_kernel_d": float(regular_kernel),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "theory": {
            "kpz_scale": lambda_kpz,
            "leading_profile": "stationary_Praehofer_Spohn_KPZ",
            "resolvent_correction": "delta_S=-d*khat^2*(S0 convolution S0)",
            "physical_regular_kernel_certified": False,
            "reason_not_certified": "UV/contact matching to the exact QLQ continuum is incomplete",
        },
        "frozen_weak_estimator": {
            "leading_kpz": leading_fit,
            "regular_mori_first_order": corrected_fit,
            "shift": {
                "a": float(corrected_fit["a"] - leading_fit["a"]),
                "D": float(corrected_fit["D"] - leading_fit["D"]),
            },
        },
        "correction_audit": {
            "maximum_absolute_delta_structure_factor": float(np.max(np.abs(delta_structure[profile_mask]))),
            "maximum_absolute_delta_wall": float(np.max(np.abs(delta_wall))),
            "minimum_leading_density": float(np.min(leading_density)),
            "minimum_corrected_density": float(np.min(corrected_density)),
            "maximum_mass_error_leading": float(np.max(np.abs(dx * np.sum(leading_density, axis=1) - 1.0))),
            "maximum_mass_error_corrected": float(np.max(np.abs(dx * np.sum(corrected_density, axis=1) - 1.0))),
        },
        "decision": {
            "constant_regular_kernel_sufficient": False,
            "criterion": "requires a certified d and stable simultaneous a,D prediction",
        },
    }


def main() -> int:
    args = _arguments()
    result = derive(
        length=args.length,
        dx=args.dx,
        dt=args.dt,
        profile_start=args.profile_start,
        profile_stop=args.profile_stop,
        fit_start=args.fit_start,
        fit_stop=args.fit_stop,
        x_crop=(float(args.x_crop[0]), float(args.x_crop[1])),
        regular_kernel=args.regular_kernel,
        characteristic_grid=args.characteristic_grid,
        spline=_load_spline(args.kpz_table),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
