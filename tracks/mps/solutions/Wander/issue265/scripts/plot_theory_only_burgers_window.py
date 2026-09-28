#!/usr/bin/env python3
"""Plot the trajectory-free KPZ-to-Burgers finite-window calculation.

The only numerical table used is the universal stationary KPZ scaling
function published by Praehofer and Spohn.  No Heisenberg-chain trajectory is
read.  The Burgers solution is evolved from the theoretical KPZ wall at
``t_start`` by the Cole--Hopf heat-kernel formula.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile
import urllib.request

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import trapezoid
from scipy.interpolate import CubicSpline
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (
    KPZ_CURRENT_M2_INTEGRAL,
    finite_field_scale_correction,
    kpz_lambda_from_tba,
    theory_only_current_projection,
    theory_only_current_projection_diagnostics,
    theory_only_running_current_projection,
    theory_only_scale_corrected_projection,
    theory_only_strong_projection,
    theory_only_strong_scale_corrected_projection,
    theory_only_width_rate_projection,
)


KPZ_TABLE_URL = (
    "https://collab.dvb.bayern/download/attachments/56921793/gy.txt"
    "?version=1&modificationDate=1678352316510&api=v2"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/figures/theory_only_kpz_burgers_window.png"),
        help="PNG output path; a PDF with the same stem is also written",
    )
    parser.add_argument(
        "--kpz-table",
        type=Path,
        help="Optional local Praehofer--Spohn gy.txt table",
    )
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--crop", type=float, default=120.0)
    parser.add_argument("--dx", type=float, default=0.125)
    return parser.parse_args()


def _load_kpz_spline(table: Path | None) -> CubicSpline:
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


def _kpz_wall(
    x: np.ndarray,
    t: float,
    spline: CubicSpline,
    lambda_kpz: float,
) -> np.ndarray:
    """Return U=F_KPZ-1/2 using U(y)=sign(y) g'(|y|)/4."""

    y_max = float(spline.x[-1])
    scaled = x / (lambda_kpz * float(t)) ** (2.0 / 3.0)
    absolute = np.minimum(np.abs(scaled), y_max)
    wall = np.sign(scaled) * spline(absolute, 1) / 4.0
    return np.where(
        scaled < -y_max,
        -0.5,
        np.where(scaled > y_max, 0.5, wall),
    )


def _cole_hopf_trajectory(
    x: np.ndarray,
    times: np.ndarray,
    initial: np.ndarray,
    coefficient: float,
    diffusion: float,
) -> np.ndarray:
    dx = float(x[1] - x[0])
    nonnegative = x >= 0.0
    positive_x = x[nonnegative]
    positive_u = initial[nonnegative]
    primitive_positive = np.r_[
        0.0,
        np.cumsum(0.5 * (positive_u[:-1] + positive_u[1:]) * dx),
    ]
    primitive = np.empty_like(x)
    primitive[nonnegative] = primitive_positive
    primitive[~nonnegative] = np.interp(
        -x[~nonnegative], positive_x, primitive_positive
    )
    phi_initial = np.exp(-coefficient * primitive / (2.0 * diffusion))
    phi_x_initial = (
        -coefficient * initial * phi_initial / (2.0 * diffusion)
    )

    trajectory = []
    t_start = float(times[0])
    for time in times:
        lag = float(time - t_start)
        if lag == 0.0:
            trajectory.append(initial.copy())
            continue
        radius = 8.0 * np.sqrt(2.0 * diffusion * lag) + 5.0
        count = int(np.ceil(radius / dx))
        kernel_x = np.arange(-count, count + 1, dtype=float) * dx
        kernel = np.exp(-kernel_x**2 / (4.0 * diffusion * lag)) / np.sqrt(
            4.0 * np.pi * diffusion * lag
        )
        phi = fftconvolve(phi_initial, kernel, mode="same") * dx
        phi_x = fftconvolve(phi_x_initial, kernel, mode="same") * dx
        trajectory.append(-2.0 * diffusion * phi_x / (coefficient * phi))
    return np.asarray(trajectory)


def _current_residual_grid(
    coefficient: np.ndarray,
    diffusion: np.ndarray,
    diagnostics: dict[str, float | np.ndarray],
    lambda_kpz: float,
    t_start: float,
    t_stop: float,
) -> np.ndarray:
    gram = np.asarray(diagnostics["gram"], dtype=float)
    rhs = np.asarray(diagnostics["rhs"], dtype=float)
    exact_norm = (
        (4.0 / 9.0)
        * KPZ_CURRENT_M2_INTEGRAL
        * lambda_kpz**2
        * (t_stop - t_start)
    )
    result = np.empty_like(coefficient)
    for index in np.ndindex(coefficient.shape):
        beta = np.array([coefficient[index], diffusion[index]])
        residual = exact_norm - 2.0 * beta @ rhs + beta @ gram @ beta
        result[index] = 100.0 * np.sqrt(max(float(residual), 0.0) / exact_norm)
    return result


def main() -> int:
    args = _arguments()
    if not (0.0 < args.t_start < args.t_stop):
        raise ValueError("Require 0 < t-start < t-stop")
    if args.crop <= 0.0 or args.dx <= 0.0:
        raise ValueError("crop and dx must be positive")

    spline = _load_kpz_spline(args.kpz_table)
    lambda_kpz = kpz_lambda_from_tba()
    coefficient, diffusion = theory_only_current_projection(
        args.t_start, args.t_stop, lambda_kpz=lambda_kpz
    )
    diagnostics = theory_only_current_projection_diagnostics(
        args.t_start, args.t_stop, lambda_kpz=lambda_kpz
    )
    strong_coefficient, strong_diffusion = theory_only_strong_projection(
        args.t_start, args.t_stop, lambda_kpz=lambda_kpz
    )
    spectral_coefficient, spectral_diffusion = (
        theory_only_strong_scale_corrected_projection(
            finite_field_scale_correction(),
            args.t_start,
            args.t_stop,
            lambda_kpz=lambda_kpz,
        )
    )
    spectral_current_coefficient, spectral_current_diffusion = (
        theory_only_scale_corrected_projection(
            finite_field_scale_correction(),
            args.t_start,
            args.t_stop,
            lambda_kpz=lambda_kpz,
        )
    )
    moment_projection = theory_only_width_rate_projection(
        args.t_start, args.t_stop, lambda_kpz=lambda_kpz
    )
    running_times = np.geomspace(args.t_start, args.t_stop, 80)
    running_projection = theory_only_running_current_projection(
        running_times, lambda_kpz=lambda_kpz
    )
    scheme_pairs = np.asarray(
        [
            (strong_coefficient, strong_diffusion),
            (coefficient, diffusion),
            (spectral_coefficient, spectral_diffusion),
            (spectral_current_coefficient, spectral_current_diffusion),
        ]
    )
    scheme_lower = np.min(scheme_pairs, axis=0)
    scheme_upper = np.max(scheme_pairs, axis=0)
    scheme_center = 0.5 * (scheme_lower + scheme_upper)
    scheme_half_width = 0.5 * (scheme_upper - scheme_lower)

    x_extent = max(512.0, 4.0 * args.crop)
    x = np.arange(-x_extent, x_extent + 0.5 * args.dx, args.dx)
    times = np.arange(args.t_start, args.t_stop + 0.5, 1.0)
    exact = np.stack(
        [_kpz_wall(x, time, spline, lambda_kpz) for time in times]
    )
    burgers = _cole_hopf_trajectory(
        x, times, exact[0], coefficient, diffusion
    )
    crop = np.abs(x) <= args.crop
    numerator_t = np.array(
        [trapezoid((row_b[crop] - row_e[crop]) ** 2, x[crop])
         for row_b, row_e in zip(burgers, exact, strict=True)]
    )
    denominator_t = np.array(
        [trapezoid(row[crop] ** 2, x[crop]) for row in exact]
    )
    relative_t = np.sqrt(numerator_t / denominator_t)
    aggregate = np.sqrt(
        trapezoid(numerator_t, times) / trapezoid(denominator_t, times)
    )

    plt.rcParams.update(
        {
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "legend.fontsize": 8.0,
            "figure.dpi": 160,
        }
    )
    colors = ["#0072B2", "#D55E00", "#009E73"]
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 7.2), constrained_layout=True)

    selected_times = [75.0, 125.0, 200.0]
    for color, time in zip(colors, selected_times, strict=True):
        index = int(round(time - args.t_start))
        axes[0, 0].plot(
            x[crop], exact[index, crop], color=color, lw=2.0,
            label=fr"KPZ, $t={time:.0f}$",
        )
        axes[0, 0].plot(
            x[crop], burgers[index, crop], color=color, lw=1.25, ls="--",
        )
        axes[0, 1].plot(
            x[crop], 1e3 * (burgers[index, crop] - exact[index, crop]),
            color=color, lw=1.8, label=fr"$t={time:.0f}$",
        )
    axes[0, 0].set_title("(a) Theory-only wall profiles")
    axes[0, 0].set_xlabel(r"$x$")
    axes[0, 0].set_ylabel(r"$U(x,t)$")
    axes[0, 0].legend(frameon=False, loc="upper left")
    axes[0, 0].text(
        0.98, 0.05, "solid: KPZ\ndashed: Burgers",
        transform=axes[0, 0].transAxes, ha="right", va="bottom",
    )
    axes[0, 1].axhline(0.0, color="0.4", lw=0.7)
    axes[0, 1].set_title("(b) Profile difference")
    axes[0, 1].set_xlabel(r"$x$")
    axes[0, 1].set_ylabel(r"$10^3(U_{\rm B}-U_{\rm KPZ})$")
    axes[0, 1].legend(frameon=False)

    axes[1, 0].plot(times, 100.0 * relative_t, color="#0072B2", lw=2.0)
    axes[1, 0].axhline(
        100.0 * float(diagnostics["relative_current_residual"]),
        color="#D55E00", ls="--", lw=1.6,
        label="current-space residual (different norm)",
    )
    axes[1, 0].set_title("(c) Residual filtering by continuity + viscosity")
    axes[1, 0].set_xlabel(r"$t$")
    axes[1, 0].set_ylabel("relative error (%)")
    axes[1, 0].legend(frameon=False)
    axes[1, 0].text(
        0.03, 0.76,
        fr"window profile error $={100.0 * aggregate:.3f}\%$",
        transform=axes[1, 0].transAxes,
    )

    a_values = np.linspace(0.10, 0.32, 281)
    d_values = np.linspace(1.2, 3.7, 281)
    aa, dd = np.meshgrid(a_values, d_values)
    residual = _current_residual_grid(
        aa, dd, diagnostics, lambda_kpz, args.t_start, args.t_stop
    )
    levels = [2.2, 2.5, 3.0, 4.0, 6.0, 10.0, 20.0]
    contour = axes[1, 1].contour(aa, dd, residual, levels=levels, cmap="viridis")
    axes[1, 1].clabel(contour, inline=True, fontsize=7, fmt="%.1f%%")
    axes[1, 1].plot(
        coefficient, diffusion, marker="*", ms=11, color="#D55E00",
        label="theory current projection",
    )
    axes[1, 1].plot(
        strong_coefficient,
        strong_diffusion,
        marker="s",
        ms=6,
        mfc="white",
        mec="#009E73",
        label="original strong loss",
    )
    axes[1, 1].annotate(
        "spectral scale\ncorrection",
        xy=(spectral_coefficient, spectral_diffusion),
        xytext=(0.175, 1.72),
        arrowprops={"arrowstyle": "->", "color": "#009E73", "lw": 1.2},
        color="#006B4F",
        fontsize=7.5,
    )
    axes[1, 1].plot(
        spectral_coefficient,
        spectral_diffusion,
        marker="D",
        ms=5,
        color="#009E73",
        label="strong + spectral scale",
    )
    axes[1, 1].plot(
        moment_projection["coefficient"],
        moment_projection["diffusion"],
        marker="^",
        ms=6,
        mfc="white",
        mec="black",
        label="analytic width-rate projection",
    )
    axes[1, 1].plot(
        running_projection["coefficient"],
        running_projection["diffusion"],
        color="#CC79A7",
        lw=2.0,
        label=r"running one-field closure, $t=50\to200$",
    )
    axes[1, 1].scatter(
        np.asarray(running_projection["coefficient"])[[0, -1]],
        np.asarray(running_projection["diffusion"])[[0, -1]],
        s=20,
        color="#CC79A7",
        zorder=4,
    )
    axes[1, 1].errorbar(
        scheme_center[0],
        scheme_center[1],
        xerr=scheme_half_width[0],
        yerr=scheme_half_width[1],
        marker="X",
        ms=6,
        color="#E69F00",
        capsize=3,
        lw=1.2,
        label="restricted theory scheme band",
    )
    axes[1, 1].plot(
        0.2301488, 1.97, marker="o", ms=6, mfc="white", mec="#0072B2",
        label="trajectory result (comparison only)",
    )
    axes[1, 1].set_title("(d) Nearly degenerate coefficient valley")
    axes[1, 1].set_xlabel(r"$a$")
    axes[1, 1].set_ylabel(r"$D$")
    axes[1, 1].legend(
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=7.0,
    )
    axes[1, 1].text(
        0.98, 0.95,
        fr"normalized condition number $={float(diagnostics['normalized_condition_number']):.1f}$",
        transform=axes[1, 1].transAxes, ha="right", va="top",
    )
    axes[1, 1].text(
        0.98,
        0.04,
        "contours: current-space loss only",
        transform=axes[1, 1].transAxes,
        ha="right",
        va="bottom",
        fontsize=7.5,
        color="0.3",
    )

    fig.suptitle(
        r"XXX chain: trajectory-free KPZ $\rightarrow$ finite-window Burgers projections",
        fontsize=12.0,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300)
    fig.savefig(args.output.with_suffix(".pdf"))
    print(
        f"wrote {args.output} and {args.output.with_suffix('.pdf')}; "
        f"aggregate_profile_error={aggregate:.9f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
