#!/usr/bin/env python3
"""Plot the trajectory-free finite-field and projected-kernel hierarchy.

No Heisenberg trajectory is read.  The curves use the exact infinite-
temperature TBA spectral sum, the stationary KPZ cumulants, and the declared
time window only.  The right panel emphasizes that a two-mode model is one
optional finite-pole approximation to the exact memory kernel.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (
    EXACT_D0_INFINITY_T,
    SPECTRAL_REGULATOR_D1_INFINITY_T,
    finite_field_scale_correction,
    finite_field_spectral_regulator_diffusion,
    kpz_tcl_gradient_coefficients,
    theory_only_scale_corrected_projection,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/figures/running_kernel_hierarchy.png"),
        help="PNG output path; a PDF with the same stem is also written",
    )
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    return parser.parse_args()


def _box(
    axis: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    *,
    color: str,
    fontsize: float = 8.0,
) -> None:
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.02",
        facecolor=color,
        edgecolor="0.25",
        linewidth=0.9,
    )
    axis.add_patch(patch)
    axis.text(
        xy[0] + width / 2.0,
        xy[1] + height / 2.0,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        linespacing=1.25,
    )


def _arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    style: str = "-",
) -> None:
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=10,
        linewidth=1.0,
        linestyle=style,
        color="0.3",
        connectionstyle="arc3",
    )
    axis.add_patch(arrow)


def main() -> int:
    args = _arguments()
    if not (0.0 < args.t_start < args.t_stop):
        raise ValueError("Require 0 < t-start < t-stop")

    fields = np.geomspace(1.0e-3, 8.0e-2, 65)
    spectral = np.array(
        [finite_field_spectral_regulator_diffusion(field) for field in fields]
    )
    remainder = spectral - EXACT_D0_INFINITY_T / fields
    correction = finite_field_scale_correction()
    corrected_pair = theory_only_scale_corrected_projection(
        correction, args.t_start, args.t_stop
    )

    times = np.linspace(args.t_start, args.t_stop, 300)
    tcl = kpz_tcl_gradient_coefficients(times)
    fourth_equivalent = -tcl["hyperdiffusion"] / tcl["length"] ** 2

    plt.rcParams.update(
        {
            "font.size": 8.5,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "legend.fontsize": 7.7,
            "figure.dpi": 160,
        }
    )
    fig = plt.figure(figsize=(13.0, 4.25), constrained_layout=True)
    grid = fig.add_gridspec(1, 3, width_ratios=(1.0, 1.0, 1.35))
    axes = [fig.add_subplot(grid[0, index]) for index in range(3)]

    axes[0].semilogx(
        fields,
        remainder,
        color="#0072B2",
        linewidth=2.0,
        label=r"$D_{\rm sp}(h)-D_0/h$",
    )
    axes[0].axhline(
        SPECTRAL_REGULATOR_D1_INFINITY_T,
        color="#D55E00",
        linestyle="--",
        linewidth=1.5,
        label=r"$-2/(3\pi)$",
    )
    axes[0].set_title("(a) Analytic finite-field regulator")
    axes[0].set_xlabel(r"field $h$")
    axes[0].set_ylabel(r"subleading remainder")
    axes[0].legend(frameon=False, loc="lower right")
    axes[0].text(
        0.04,
        0.96,
        r"$D_{\rm sp}=5\pi/(27h)-2/(3\pi)+O(h)$"
        "\n"
        + fr"scale-only projection: $(a,D)=({corrected_pair[0]:.3f},"
        + fr"{corrected_pair[1]:.3f})$"
        "\n" + r"full physical $D_{\mathrm{spin}}$ still contains $w_s$",
        transform=axes[0].transAxes,
        ha="left",
        va="top",
        bbox={"facecolor": "white", "edgecolor": "0.8", "alpha": 0.9},
    )

    axes[1].plot(
        times,
        tcl["diffusion"],
        color="#009E73",
        linewidth=2.2,
        label=r"$D_2(t)\propto t^{1/3}$",
    )
    axes[1].plot(
        times,
        fourth_equivalent,
        color="#CC79A7",
        linewidth=1.7,
        linestyle="--",
        label=r"$-H_4(t)/L(t)^2$ at $k=L^{-1}$",
    )
    axes[1].axvspan(
        args.t_start,
        args.t_stop,
        color="#F0E442",
        alpha=0.12,
        linewidth=0.0,
    )
    axes[1].set_title("(b) Exact leading mean generator")
    axes[1].set_xlabel(r"time $t$")
    axes[1].set_ylabel("running Fourier-generator coefficient")
    axes[1].legend(frameon=False, loc="upper left")
    axes[1].text(
        0.04,
        0.06,
        r"$\partial_t\hat p=-k^2D_{\rm TCL}(k,t)\hat p$"
        "\nfull multiplier required when $kL=O(1)$",
        transform=axes[1].transAxes,
        ha="left",
        va="bottom",
    )

    hierarchy = axes[2]
    hierarchy.set_title("(c) Controlled hierarchy (two modes are optional)")
    hierarchy.set_xlim(0.0, 1.0)
    hierarchy.set_ylim(0.0, 1.0)
    hierarchy.axis("off")
    _box(
        hierarchy,
        (0.27, 0.84),
        0.46,
        0.10,
        "Microscopic continuity\n+ infinite fluctuating GHD",
        color="#D9EAF7",
    )
    _box(
        hierarchy,
        (0.27, 0.64),
        0.46,
        0.10,
        "Exact projection\nMori memory matrix $K(k,t)$",
        color="#D8F0E5",
    )
    _arrow(hierarchy, (0.50, 0.84), (0.50, 0.74))
    _box(
        hierarchy,
        (0.04, 0.38),
        0.27,
        0.13,
        "Keep full kernel\nnonlocal / running\nmean equation",
        color="#E5F4EA",
        fontsize=7.7,
    )
    _box(
        hierarchy,
        (0.365, 0.38),
        0.27,
        0.13,
        "Finite-pole Markov\nembedding\n(two-mode is one choice)",
        color="#FFF1CC",
        fontsize=7.7,
    )
    _box(
        hierarchy,
        (0.69, 0.38),
        0.27,
        0.13,
        "Short-memory / local\ngradient expansion\nwith running terms",
        color="#F5E4EF",
        fontsize=7.7,
    )
    for x_end in (0.175, 0.50, 0.825):
        _arrow(hierarchy, (0.50, 0.64), (x_end, 0.51))
    _box(
        hierarchy,
        (0.27, 0.10),
        0.46,
        0.12,
        "Specified window + field + norm\nconstant deterministic Burgers surrogate",
        color="#F4D9D5",
    )
    for x_start in (0.175, 0.50, 0.825):
        _arrow(hierarchy, (x_start, 0.38), (0.50, 0.22), style="--")
    hierarchy.text(
        0.5,
        0.02,
        "A successful surrogate does not identify the unique microscopic closure.",
        ha="center",
        va="bottom",
        fontsize=7.8,
        color="0.25",
    )

    fig.suptitle(
        "XXX spin chain: finite-field correction, running mean dynamics, and closure hierarchy",
        fontsize=12.0,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300)
    fig.savefig(args.output.with_suffix(".pdf"))
    print(
        f"wrote {args.output} and {args.output.with_suffix('.pdf')}; "
        f"scale_correction={correction:.9f}; "
        f"corrected_pair=({corrected_pair[0]:.8f},{corrected_pair[1]:.8f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
