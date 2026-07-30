#!/usr/bin/env python3
"""Create audited diagnostic figures for the challenge analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


COLORS = [
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#000000",
    "#6A3D9A",
]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]
YT = 1.587
YI = -0.815
NORMAL_95 = 1.959963984540054


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "legend.fontsize": 7,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )


def _save_pair(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    png_path = path.with_suffix(".png")
    pdf_path = path.with_suffix(".pdf")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def plot_binder_curves(
    cells: list[dict[str, Any]],
    lattice: str,
    path: Path,
) -> None:
    _style()
    selected = [
        row
        for row in cells
        if row["lattice"] == lattice
        and math.isclose(float(row["FixedDltau"]), 0.013, rel_tol=0.0, abs_tol=1e-12)
    ]
    sizes = sorted({int(row["L"]) for row in selected})
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    for index, size in enumerate(sizes):
        rows = sorted(
            (row for row in selected if int(row["L"]) == size),
            key=lambda row: float(row["hTrfd"]),
        )
        ax.errorbar(
            [float(row["hTrfd"]) for row in rows],
            [float(row["binder_Q"]) for row in rows],
            yerr=[float(row["binder_Q_error"]) for row in rows],
            color=COLORS[index % len(COLORS)],
            marker=MARKERS[index % len(MARKERS)],
            markersize=3.2,
            linewidth=0.9,
            capsize=1.5,
            label=f"L={size}",
        )
    ax.set_xlabel("Transverse field h")
    ax.set_ylabel("Binder moment ratio Q")
    ax.set_title(f"{lattice.capitalize()} lattice, requested Δτ=0.013")
    ax.legend(frameon=False, ncol=2)
    _save_pair(fig, path)


def plot_fit_stability(
    fits: list[dict[str, Any]],
    lattice: str,
    path: Path,
) -> None:
    _style()
    lattices = ("triangular", "honeycomb") if lattice == "both" else (lattice,)
    fig, axes = plt.subplots(1, len(lattices), figsize=(7.2, 3.2), squeeze=False)
    for panel, current in enumerate(lattices):
        ax = axes[0, panel]
        selected = [row for row in fits if row["lattice"] == current]
        terms = sorted({str(row["terms"]) for row in selected})
        for index, term in enumerate(terms):
            rows = sorted(
                (row for row in selected if str(row["terms"]) == term),
                key=lambda row: int(row["Lmin"]),
            )
            ax.errorbar(
                [int(row["Lmin"]) + 0.08 * (index - len(terms) / 2) for row in rows],
                [float(row["h_c"]) for row in rows],
                yerr=[float(row["h_c_bootstrap_std"]) for row in rows],
                fmt=MARKERS[index % len(MARKERS)],
                color=COLORS[index % len(COLORS)],
                markersize=3.2,
                capsize=1.5,
                label=term,
            )
            unstable = [
                row
                for row in rows
                if float(row.get("bootstrap_success_fraction", 1.0)) < 0.95
            ]
            if unstable:
                ax.scatter(
                    [int(row["Lmin"]) for row in unstable],
                    [float(row["h_c"]) for row in unstable],
                    marker="x",
                    color="#D55E00",
                    s=35,
                    zorder=6,
                )
        ax.set_xlabel("Minimum size Lmin")
        ax.set_ylabel("Fitted h at requested Δτ=0.013")
        ax.set_title(current.capitalize())
        ax.legend(frameon=False, fontsize=6, ncol=2)
    fig.tight_layout()
    _save_pair(fig, path)


def _primary_collapse_fit(
    fits: list[dict[str, Any]],
    lattice: str,
) -> dict[str, Any]:
    variant_id = f"{lattice}-Lmin16-a2"
    matches = [row for row in fits if row.get("variant_id") == variant_id]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one primary finite-size fit {variant_id}, "
            f"found {len(matches)}"
        )
    return matches[0]


def plot_data_collapse(
    cells: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    path: Path,
) -> None:
    """Plot the declared correction-adjusted Binder-ratio data collapse."""
    _style()
    lattices = ("triangular", "honeycomb")
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(7.2, 5.2),
        sharex="col",
        gridspec_kw={"height_ratios": [2.4, 1.0]},
    )
    for panel, lattice in enumerate(lattices):
        fit = _primary_collapse_fit(fits, lattice)
        h_c = float(fit["h_c"])
        q_star = float(fit["Q_star"])
        a1 = float(fit["a1"])
        b1 = float(fit["b1"])
        a2 = float(fit["a2"])
        selected = [
            row
            for row in cells
            if row["lattice"] == lattice
            and int(row["L"]) >= 16
            and math.isclose(
                float(row["FixedDltau"]),
                0.013,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ]
        sizes = sorted({int(row["L"]) for row in selected})
        all_x: list[float] = []
        for index, size in enumerate(sizes):
            rows = sorted(
                (row for row in selected if int(row["L"]) == size),
                key=lambda row: float(row["hTrfd"]),
            )
            x = np.array(
                [
                    (float(row["hTrfd"]) - h_c) * size**YT
                    for row in rows
                ]
            )
            q_error = np.array(
                [float(row["binder_Q_error"]) for row in rows]
            )
            q_corrected = np.array(
                [
                    float(row["binder_Q"]) - b1 * size**YI
                    for row in rows
                ]
            )
            q_model = q_star + a1 * x + a2 * x**2
            residual = (q_corrected - q_model) / q_error
            color = COLORS[index % len(COLORS)]
            marker = MARKERS[index % len(MARKERS)]
            axes[0, panel].errorbar(
                x,
                q_corrected,
                yerr=q_error,
                color=color,
                marker=marker,
                linestyle="none",
                markersize=3.0,
                capsize=1.3,
                label=f"L={size}",
            )
            axes[1, panel].scatter(
                x,
                residual,
                color=color,
                marker=marker,
                s=12,
            )
            all_x.extend(x.tolist())
        if not all_x:
            raise ValueError(f"no Δτ=0.013, L>=16 cells for {lattice}")
        grid = np.linspace(min(all_x), max(all_x), 300)
        axes[0, panel].plot(
            grid,
            q_star + a1 * grid + a2 * grid**2,
            color="#000000",
            linewidth=1.0,
            label="primary scaling function",
        )
        axes[0, panel].set_title(lattice.capitalize())
        axes[0, panel].set_ylabel("Corrected Binder ratio Q − b₁Lʸⁱ")
        axes[0, panel].legend(frameon=False, fontsize=6, ncol=2)
        axes[1, panel].axhline(0.0, color="#000000", linewidth=0.8)
        axes[1, panel].axhline(
            2.0,
            color="#777777",
            linewidth=0.7,
            linestyle=":",
        )
        axes[1, panel].axhline(
            -2.0,
            color="#777777",
            linewidth=0.7,
            linestyle=":",
        )
        axes[1, panel].set_xlabel("Scaled field (h − h_c)Lʸᵗ")
        axes[1, panel].set_ylabel("Residual / SEM")
    fig.suptitle(
        "Finite-size data collapse at requested Δτ=0.013 "
        "(yₜ=1.587, yᵢ=−0.815)",
        y=0.995,
    )
    fig.tight_layout()
    _save_pair(fig, path)


def plot_dtau_extrapolation(
    points: list[dict[str, Any]],
    lattice: str,
    path: Path,
) -> None:
    _style()
    lattices = ("triangular", "honeycomb") if lattice == "both" else (lattice,)
    fig, axes = plt.subplots(1, len(lattices), figsize=(7.2, 3.2), squeeze=False)
    for panel, current in enumerate(lattices):
        ax = axes[0, panel]
        rows = [
            row
            for row in points
            if row["lattice"] == current and row["record_type"] == "step"
        ]
        x = np.array([float(row["actual_dtau2_mean"]) for row in rows])
        y = np.array([float(row["h_c"]) for row in rows])
        error = np.array([float(row["h_c_error"]) for row in rows])
        ax.errorbar(x, y, yerr=error, fmt="o", color=COLORS[0], capsize=2, label="two-stage points")
        weights = 1.0 / error
        coefficients = np.polyfit(x, y, 1, w=weights)
        grid = np.linspace(0.0, max(x) * 1.06, 100)
        ax.plot(grid, np.polyval(coefficients, grid), color=COLORS[0], linewidth=1.0)
        outside = [row for row in rows if not _as_bool(row["inside_field_scan"])]
        if outside:
            ax.scatter(
                [float(row["actual_dtau2_mean"]) for row in outside],
                [float(row["h_c"]) for row in outside],
                facecolors="none",
                edgecolors="#D55E00",
                s=52,
                linewidths=1.1,
                label="h outside scanned field",
                zorder=5,
            )
        joint = [
            row
            for row in points
            if row["lattice"] == current and row["record_type"] == "joint_sensitivity"
        ]
        if joint:
            ax.errorbar(
                [0.0],
                [float(joint[0]["h_c"])],
                yerr=[float(joint[0]["h_c_error"])],
                fmt="s",
                color=COLORS[2],
                capsize=2,
                label="joint actual-Δτ fit",
            )
        ax.set_xlabel("Actual Δτ²")
        ax.set_ylabel("Fitted critical field")
        ax.set_title(current.capitalize())
        ax.legend(frameon=False)
    fig.tight_layout()
    _save_pair(fig, path)


def ratio_comparison_series(
    primary: dict[str, Any],
    sensitivity: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the three independently labelled critical-field-ratio estimates."""
    primary_ratio = primary["ratio"]
    sensitivity_ratio = sensitivity["ratio"]
    pre_ratio = primary["pre_comparison"]["ratio"]
    pre_value = float(pre_ratio["value"])
    pre_sem = float(pre_ratio["standard_error"])
    return [
        {
            "label": "Blöte–Deng PRE 66, 066110 (2002)",
            "value": pre_value,
            "standard_error": pre_sem,
            "low": pre_value - NORMAL_95 * pre_sem,
            "high": pre_value + NORMAL_95 * pre_sem,
            "interval": "95% propagated normal interval",
        },
        {
            "label": "Primary analysis (243 cells)",
            "value": float(primary_ratio["median"]),
            "standard_error": float(primary_ratio["standard_error"]),
            "low": float(primary_ratio["ci95"][0]),
            "high": float(primary_ratio["ci95"][1]),
            "interval": "95% bootstrap interval",
        },
        {
            "label": "Δτ=0.004 sensitivity (273 cells)",
            "value": float(sensitivity_ratio["median"]),
            "standard_error": float(sensitivity_ratio["standard_error"]),
            "low": float(sensitivity_ratio["ci95"][0]),
            "high": float(sensitivity_ratio["ci95"][1]),
            "interval": "95% bootstrap interval",
        },
    ]


def plot_ratio(
    primary: dict[str, Any],
    sensitivity: dict[str, Any],
    path: Path,
) -> None:
    _style()
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    series = ratio_comparison_series(primary, sensitivity)
    sqrt5 = float(primary["ratio"]["sqrt5"])
    y_positions = np.arange(len(series) - 1, -1, -1)
    for index, (item, y_position) in enumerate(zip(series, y_positions)):
        value = float(item["value"])
        low = float(item["low"])
        high = float(item["high"])
        ax.errorbar(
            [value],
            [y_position],
            xerr=[[value - low], [high - value]],
            fmt=MARKERS[index],
            color=COLORS[index],
            capsize=3,
            markersize=5,
        )
    ax.axvline(
        sqrt5,
        color="#000000",
        linestyle="--",
        linewidth=1.0,
        label="Conjecture √5",
    )
    ax.set_yticks(y_positions, [item["label"] for item in series])
    ax.set_xlabel("Critical-field ratio R")
    ax.set_title("Critical-field ratio: literature and present estimates")
    ax.legend(frameon=False, loc="upper right")
    distances = [abs(float(item["value"]) - sqrt5) for item in series]
    ax.text(
        0.02,
        -0.22,
        (
            f"Central-value distance |R−√5|: PRE {distances[0]:.2e}; "
            f"primary {distances[1]:.2e} (closer); "
            f"Δτ=0.004 sensitivity {distances[2]:.2e} (farther)."
        ),
        transform=ax.transAxes,
        fontsize=7,
    )
    _save_pair(fig, path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--finite-size-fits", type=Path, required=True)
    parser.add_argument("--dtau-fits", type=Path, required=True)
    parser.add_argument("--final-results", type=Path, required=True)
    parser.add_argument("--sensitivity-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cells = _read_csv(args.cells)
    fits = _read_csv(args.finite_size_fits)
    dtau = _read_csv(args.dtau_fits)
    final = json.loads(args.final_results.read_text(encoding="utf-8"))
    sensitivity = json.loads(args.sensitivity_results.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plot_binder_curves(cells, "triangular", args.output_dir / "binder_Q_triangular.png")
    plot_binder_curves(cells, "honeycomb", args.output_dir / "binder_Q_honeycomb.png")
    plot_data_collapse(cells, fits, args.output_dir / "data_collapse.png")
    plot_fit_stability(fits, "both", args.output_dir / "finite_size_fit_stability.png")
    plot_dtau_extrapolation(dtau, "both", args.output_dir / "dtau2_extrapolation.png")
    plot_ratio(final, sensitivity, args.output_dir / "ratio_vs_sqrt5.png")
    print(f"wrote 6 PNG/PDF figure pairs to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
