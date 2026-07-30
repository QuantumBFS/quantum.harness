#!/usr/bin/env python3
"""Build the reviewer-facing finite-size-scaling figures from accepted JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHASE8_ANALYSIS = (
    PROJECT_ROOT
    / "results"
    / "phase8-scaling"
    / "sigma-1.75"
    / "sensitivity-Gamma-ST"
    / "analysis"
    / "analysis.json"
)
DEFAULT_PHASE9_ANALYSIS = (
    PROJECT_ROOT
    / "results"
    / "phase9-validation"
    / "sigma1.8-z"
    / "report"
    / "analysis.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "report_Human" / "figures"

BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
GRAY = "#666666"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _apply_axis_style(axis) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(direction="out")


def _add_panel_label(axis, label: str) -> None:
    axis.text(
        -0.16,
        1.05,
        label,
        transform=axis.transAxes,
        fontsize=13,
        fontweight="bold",
        va="top",
    )


def build_figure_3(analysis_path: Path = DEFAULT_PHASE8_ANALYSIS):
    """Return the approved two-panel sigma=7/4 sensitivity figure."""

    analysis = _read_json(Path(analysis_path))
    self_consistent = analysis["branches"]["self_consistent_crossing_field"]
    published = analysis["branches"]["external_published_field"]

    figure, axes = plt.subplots(1, 2, figsize=(10.2, 4.15))
    axis_gap, axis_exponent = axes

    for branch, color, exponent_marker, label in (
        (self_consistent, BLUE, "o", "self-consistent field"),
        (published, ORANGE, "s", "published field"),
    ):
        lengths = np.asarray(sorted(int(value) for value in branch["gaps"]))
        gaps = np.asarray([branch["gaps"][str(length)] for length in lengths])
        axis_gap.loglog(
            lengths,
            gaps,
            marker="o",
            color=color,
            linewidth=2,
            markersize=7,
            label=label,
        )

        effective_lengths = np.asarray(
            branch["z_eff"]["effective_lengths"], dtype=float
        )
        effective_exponents = np.asarray(branch["z_eff"]["values"], dtype=float)
        axis_exponent.plot(
            effective_lengths,
            effective_exponents,
            marker=exponent_marker,
            color=color,
            linewidth=2,
            markersize=7,
            label=label,
        )

    axis_gap.set_xlabel("L")
    axis_gap.set_ylabel("gap")
    axis_gap.legend(frameon=False)

    axis_exponent.axhline(
        0.91,
        color=GREEN,
        linestyle=":",
        linewidth=2,
        label="Shiratani–Todo QMC z=0.91(2)",
    )
    axis_exponent.set_xlabel("effective L")
    axis_exponent.set_ylabel("z_eff")
    axis_exponent.legend(frameon=False, loc="best")

    for axis, label in zip(axes, ("A", "B"), strict=True):
        _apply_axis_style(axis)
        _add_panel_label(axis, label)

    figure.tight_layout(w_pad=2.5)
    return figure


def build_figure_4(analysis_path: Path = DEFAULT_PHASE9_ANALYSIS):
    """Return sigma=1.8 z_eff drift with the stored power correction."""

    analysis = _read_json(Path(analysis_path))
    scaling = analysis["gap_scaling"]
    effective_lengths = np.asarray(
        scaling["z_eff"]["effective_lengths"], dtype=float
    )
    effective_exponents = np.asarray(scaling["z_eff"]["values"], dtype=float)
    power = scaling["correction_sensitivity"]["power"]
    estimate = float(power["estimate"])
    coefficient = float(power["coefficient"])

    figure, axis = plt.subplots(figsize=(6.3, 4.5))
    axis.scatter(
        effective_lengths,
        effective_exponents,
        color=BLUE,
        marker="s",
        s=58,
        zorder=3,
        label=r"DMRG $z_{\mathrm{eff}}$",
    )

    fit_lengths = np.linspace(
        0.9 * effective_lengths.min(),
        1.12 * effective_lengths.max(),
        300,
    )
    axis.plot(
        fit_lengths,
        estimate + coefficient / fit_lengths,
        color=BLUE,
        linewidth=2.2,
        label="power correction",
    )
    axis.axhline(
        estimate,
        color=BLUE,
        linestyle="--",
        linewidth=1.8,
        label=rf"$z_{{\mathrm{{power}}}}={estimate:.3f}$",
    )
    axis.axhline(
        0.93,
        color=GRAY,
        linestyle=":",
        linewidth=1.6,
        label="Shiratani–Todo QMC z=0.93(2)",
    )

    axis.set_xlabel(r"Effective size $L_{\mathrm{eff}}$")
    axis.set_ylabel(r"Effective exponent $z_{\mathrm{eff}}$")
    axis.set_xlim(fit_lengths.min(), fit_lengths.max())
    axis.legend(frameon=False, loc="lower right")
    _apply_axis_style(axis)
    figure.tight_layout()
    return figure


def _save(figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase8-analysis", type=Path, default=DEFAULT_PHASE8_ANALYSIS
    )
    parser.add_argument(
        "--phase9-analysis", type=Path, default=DEFAULT_PHASE9_ANALYSIS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    _save(
        build_figure_3(args.phase8_analysis),
        args.output_dir / "figure-03-sigma-1p75-z-scaling.png",
    )
    _save(
        build_figure_4(args.phase9_analysis),
        args.output_dir / "figure-04-sigma-1p8-z-scaling.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
