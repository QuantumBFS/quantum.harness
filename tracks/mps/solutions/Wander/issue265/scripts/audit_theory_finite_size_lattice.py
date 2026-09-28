#!/usr/bin/env python3
"""Audit finite-size and lattice effects in the theory-only KPZ projection.

The script samples the universal stationary-KPZ wall on the declared XXX-chain
lattice and repeats the strong-form two-operator projection with exact centered
lattice differences.  It never opens a Heisenberg trajectory and never accepts
target Burgers coefficients.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

import numpy as np
from scipy.interpolate import CubicSpline


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    kpz_lambda_from_tba,
    theory_only_strong_projection,
)


KPZ_TABLE_URL = (
    "https://collab.dvb.bayern/download/attachments/56921793/gy.txt"
    "?version=1&modificationDate=1678352316510&api=v2"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.05)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _load_spline(table: Path | None) -> CubicSpline:
    if table is not None:
        values = np.loadtxt(table)
    else:
        with tempfile.TemporaryDirectory(prefix="kpz_ps_") as directory:
            destination = Path(directory) / "gy.txt"
            urllib.request.urlretrieve(KPZ_TABLE_URL, destination)
            values = np.loadtxt(destination)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("KPZ table must contain y and g(y) columns")
    return CubicSpline(values[:, 0], values[:, 1])


def _wall_and_time_derivative(
    x: np.ndarray,
    time: float,
    spline: CubicSpline,
    lambda_kpz: float,
) -> tuple[np.ndarray, np.ndarray]:
    length = (lambda_kpz * time) ** (2.0 / 3.0)
    y = x / length
    table_edge = float(spline.x[-1])
    absolute = np.minimum(np.abs(y), table_edge)
    wall = np.sign(y) * spline(absolute, 1) / 4.0
    wall = np.where(y < -table_edge, -0.5, wall)
    wall = np.where(y > table_edge, 0.5, wall)
    density = np.where(np.abs(y) <= table_edge, spline(absolute, 2) / 4.0, 0.0)
    time_derivative = -(2.0 / 3.0) * y * density / time
    return wall, time_derivative


def derive(
    *,
    length: int,
    dx: float,
    dt: float,
    t_start: float,
    t_stop: float,
    spline: CubicSpline,
) -> dict[str, object]:
    if length < 8 or length % 2 != 0:
        raise ValueError("length must be an even integer >= 8")
    if dx <= 0.0 or dt <= 0.0 or not 0.0 < t_start < t_stop:
        raise ValueError("Require dx,dt>0 and 0<t-start<t-stop")

    lambda_kpz = kpz_lambda_from_tba()
    x = (np.arange(length, dtype=float) - 0.5 * (length - 1)) * dx
    times = np.arange(t_start, t_stop + 0.5 * dt, dt)
    weights = np.full(times.size, dt)
    weights[[0, -1]] *= 0.5
    gram = np.zeros((2, 2))
    rhs = np.zeros(2)
    exact_norm = 0.0
    for time, weight in zip(times, weights, strict=True):
        wall, time_derivative = _wall_and_time_derivative(
            x, float(time), spline, lambda_kpz
        )
        first_difference = (wall[2:] - wall[:-2]) / (2.0 * dx)
        second_difference = (wall[2:] - 2.0 * wall[1:-1] + wall[:-2]) / dx**2
        design = np.column_stack(
            (-wall[1:-1] * first_difference, second_difference)
        )
        target = time_derivative[1:-1]
        gram += weight * dx * design.T @ design
        rhs += weight * dx * design.T @ target
        exact_norm += weight * dx * float(target @ target)

    coefficient, diffusion = np.linalg.solve(gram, rhs)
    residual_squared = (
        exact_norm
        - 2.0 * float(np.array([coefficient, diffusion]) @ rhs)
        + float(np.array([coefficient, diffusion]) @ gram @ np.array([coefficient, diffusion]))
    )
    continuum = theory_only_strong_projection(
        t_start, t_stop, lambda_kpz=lambda_kpz
    )
    front_length = (lambda_kpz * t_stop) ** (2.0 / 3.0)
    boundary_y = 0.5 * length * dx / front_length
    boundary_wall = float(spline(boundary_y, 1) / 4.0)
    discarded_mass = max(0.0, 1.0 - 2.0 * boundary_wall)
    return {
        "schema_version": 1,
        "inputs": {
            "length": int(length),
            "dx": float(dx),
            "dt": float(dt),
            "t_start": float(t_start),
            "t_stop": float(t_stop),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "kpz_scale": float(lambda_kpz),
        "front_length_at_t_stop": float(front_length),
        "boundary_scaled_coordinate": float(boundary_y),
        "two_sided_probability_mass_beyond_boundaries": float(discarded_mass),
        "continuum_strong_projection": {
            "a": float(continuum[0]),
            "D": float(continuum[1]),
        },
        "centered_lattice_strong_projection": {
            "a": float(coefficient),
            "D": float(diffusion),
            "relative_residual": float(
                np.sqrt(max(residual_squared, 0.0) / exact_norm)
            ),
        },
        "lattice_minus_continuum": {
            "a": float(coefficient - continuum[0]),
            "D": float(diffusion - continuum[1]),
        },
    }


def main() -> int:
    args = _arguments()
    result = derive(
        length=args.length,
        dx=args.dx,
        dt=args.dt,
        t_start=args.t_start,
        t_stop=args.t_stop,
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
