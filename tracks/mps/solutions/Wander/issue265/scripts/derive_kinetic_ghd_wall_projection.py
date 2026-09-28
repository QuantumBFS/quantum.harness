#!/usr/bin/env python3
"""Blind finite-window wall from node-resolved finite-field GHD kinetics.

The calculation keeps the velocity and diagonal scattering width of every
XXX string/rapidity node.  The effective field is fixed by the giant-string
thermal-fluctuation relation at the leading KPZ length.  It reads neither a
Heisenberg trajectory nor target Burgers coefficients.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.signal import savgol_filter
from scipy.special import erf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    diagonal_diffusion_width_field,
)
from src.heisenberg_burgers_bridge import kpz_lambda_from_tba  # noqa: E402
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def kinetic_wall_at_time(
    x: np.ndarray,
    time: float,
    *,
    string_xi_cutoff: float,
    string_xi_buffer: float,
    rapidity_u_extent: float,
    rapidity_step: float,
    velocity_series_terms: int,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Return the normalized sharp-wall response at one declared time."""

    lam = kpz_lambda_from_tba()
    front_length = (lam * time) ** (2.0 / 3.0)
    # At infinite temperature chi=1/4, hence 4*chi=1.
    field = 1.0 / np.sqrt(front_length)
    node = diagonal_diffusion_width_field(
        field,
        string_xi_cutoff=string_xi_cutoff,
        string_xi_buffer=string_xi_buffer,
        rapidity_u_extent=rapidity_u_extent,
        rapidity_step=rapidity_step,
        velocity_series_terms=velocity_series_terms,
        velocity_group_ratio=1.3,
        string_boundary="robin",
    )
    weight = (
        node["filling"][:, None]
        * node["holes"][:, None]
        * node["rho_total"]
        * node["dressed_magnetization"][:, None] ** 2
        * float(node["rapidity_step"])
    )
    captured = float(np.sum(weight))
    weight = weight / captured
    width = np.maximum(np.asarray(node["width"], dtype=float), 1.0e-14)
    center = np.asarray(node["velocity"], dtype=float) * time
    argument = (
        x[:, None, None] - center[None, :, :]
    ) / np.sqrt(4.0 * time * width[None, :, :])
    wall = 0.5 * np.sum(weight[None, :, :] * erf(argument), axis=(1, 2))
    exact_chi = 1.0 / (4.0 * np.cosh(field) ** 2)
    return wall, {
        "time": float(time),
        "field": float(field),
        "front_length": float(front_length),
        "active_strings": int(node["active_strings"]),
        "susceptibility_captured_fraction": float(captured / exact_chi),
        "minimum_width": float(np.min(width)),
        "maximum_width": float(np.max(width)),
    }


def derive(
    *,
    length: int = 400,
    knot_times: np.ndarray,
    dt: float = 0.2,
    string_xi_cutoff: float = 6.0,
    string_xi_buffer: float = 4.0,
    rapidity_u_extent: float = 30.0,
    rapidity_step: float = 0.4,
    velocity_series_terms: int = 80,
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    if length < 32 or length % 2 or knot_times.size < 5:
        raise ValueError("require an even length and at least five time knots")
    if np.any(np.diff(knot_times) <= 0.0) or knot_times[0] < 50.0:
        raise ValueError("time knots must increase inside the finite window")
    x = np.arange(length, dtype=float) - 0.5 * (length - 1)
    knot_walls = []
    diagnostics = []
    for time in knot_times:
        wall, diagnostic = kinetic_wall_at_time(
            x,
            float(time),
            string_xi_cutoff=string_xi_cutoff,
            string_xi_buffer=string_xi_buffer,
            rapidity_u_extent=rapidity_u_extent,
            rapidity_step=rapidity_step,
            velocity_series_terms=velocity_series_terms,
        )
        knot_walls.append(wall)
        diagnostics.append(diagnostic)
    knot_wall = np.stack(knot_walls)
    times = np.arange(knot_times[0], knot_times[-1] + 0.5 * dt, dt)
    wall = PchipInterpolator(knot_times, knot_wall, axis=0)(times)
    wall = savgol_filter(wall, 31, 7, axis=1, mode="interp")
    fit = fit_profiled_weak(
        x,
        times,
        wall,
        t_window=(52.0, 198.0),
        x_crop=(-120.0, 120.0),
        gamma=0.0,
    )
    report = {
        "schema_version": 1,
        "inputs": {
            "microscopic_model": "spin-1/2 isotropic Heisenberg chain, J=1",
            "state": "infinite temperature, zero mean magnetization",
            "initial_condition": "infinitesimal sharp domain wall",
            "length": int(length),
            "knot_times": knot_times.tolist(),
            "dt": float(dt),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "closure": "node-resolved diagonal finite-field GHD Gaussian kinetics",
            "string_xi_cutoff": float(string_xi_cutoff),
            "string_xi_buffer": float(string_xi_buffer),
            "rapidity_u_extent": float(rapidity_u_extent),
            "rapidity_step": float(rapidity_step),
            "velocity_series_terms": int(velocity_series_terms),
        },
        "time_nodes": diagnostics,
        "frozen_weak_projection": {
            "a": float(fit.a),
            "D": float(fit.D0),
            "mse": float(fit.mse),
            "n_obs": int(fit.n_obs),
        },
        "limitations": [
            "off-diagonal diffusion-kernel propagation is not included",
            "the fluctuating field is closed at the leading KPZ length",
            "time dependence between microscopic knots is shape-preserving interpolation",
        ],
    }
    arrays = {
        "x": x,
        "times": times,
        "wall": wall,
        "knot_times": knot_times,
        "knot_wall": knot_wall,
    }
    return report, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument(
        "--times", type=float, nargs="+", default=[50, 75, 100, 125, 150, 175, 200]
    )
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--string-xi-cutoff", type=float, default=6.0)
    parser.add_argument("--string-xi-buffer", type=float, default=4.0)
    parser.add_argument("--rapidity-u-extent", type=float, default=30.0)
    parser.add_argument("--rapidity-step", type=float, default=0.4)
    parser.add_argument("--velocity-series-terms", type=int, default=80)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profiles", type=Path)
    args = parser.parse_args()
    report, arrays = derive(
        length=args.length,
        knot_times=np.asarray(args.times, dtype=float),
        dt=args.dt,
        string_xi_cutoff=args.string_xi_cutoff,
        string_xi_buffer=args.string_xi_buffer,
        rapidity_u_extent=args.rapidity_u_extent,
        rapidity_step=args.rapidity_step,
        velocity_series_terms=args.velocity_series_terms,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    if args.profiles is not None:
        args.profiles.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.profiles, **arrays)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
