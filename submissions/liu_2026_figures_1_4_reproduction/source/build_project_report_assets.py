#!/usr/bin/env python3
"""Build reader-facing figures for the project-level report.

The script only reformats archived numerical evidence.  It does not run a
new optimizer, open a hidden benchmark instance, or modify scientific data.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "figures" / "project"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_abstract_calibration() -> None:
    data = read_json(
        ROOT
        / "data"
        / "core_benchmark"
        / "QL1F-attempt49-fresh-confirmation.json"
    )
    methods = data["summary"]["methods"]
    order = (
        "model-informed-k15",
        "model-informed-k40",
        "raw-coordinate-global-40",
    )
    labels = (
        "Hessian subspace\n(15D)",
        "Hessian + flat dirs\n(40D)",
        "Raw coordinates\n(40D)",
    )
    success = [methods[name]["success"]["estimate"] for name in order]
    lower = [methods[name]["success"]["lower_95"] for name in order]
    upper = [methods[name]["success"]["upper_95"] for name in order]
    queries = [methods[name]["full_cap"]["queries_per_run"] for name in order]
    shots = [methods[name]["full_cap"]["shots_per_run"] for name in order]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    colors = ("#198f7a", "#8199a3", "#b9bec2")
    x = np.arange(3)
    axes[0].bar(x, success, color=colors)
    axes[0].errorbar(
        x,
        success,
        yerr=[np.asarray(success) - lower, np.asarray(upper) - success],
        fmt="none",
        ecolor="black",
        capsize=4,
    )
    axes[0].set(
        xticks=x,
        xticklabels=labels,
        ylim=(0.0, 1.05),
        ylabel="Target-success fraction",
        title="Finite-shot calibration reliability",
    )
    for index, value in enumerate(success):
        axes[0].text(index, value + 0.035, f"{100 * value:.1f}%", ha="center")

    width = 0.36
    axes[1].bar(
        x - width / 2,
        queries,
        width,
        color="#3c6eaf",
        label="Queries",
    )
    shot_scale = max(shots) / max(queries)
    axes[1].bar(
        x + width / 2,
        np.asarray(shots) / shot_scale,
        width,
        color="#aa459d",
        label=f"Shots / {shot_scale:,.0f}",
    )
    axes[1].set(
        xticks=x,
        xticklabels=labels,
        ylabel="Count per run",
        title="Fixed online resource cap",
    )
    axes[1].legend(frameon=False)
    for index, value in enumerate(queries):
        axes[1].text(index - width / 2, value + 5, str(value), ha="center")
    fig.suptitle(
        "A 15-dimensional Hessian subspace calibrates a 40-parameter CNOT model"
    )
    fig.tight_layout()
    fig.savefig(OUTPUT / "abstract_finite_shot_calibration.png", dpi=180)
    plt.close(fig)


def build_ar_cz_design() -> None:
    data_dir = ROOT / "data" / "figures3_4" / "data"
    with np.load(data_dir / "robust_waveform.npz") as archive:
        times = np.asarray(archive["times_us"], dtype=float)
        amplitude = np.asarray(archive["amplitude"], dtype=float)
        phase = np.asarray(archive["phase_unwrapped"], dtype=float)

    spectrum_rows = list(
        csv.DictReader((data_dir / "fig3_hessian_spectrum.csv").open())
    )
    modes = np.asarray([int(row["mode"]) for row in spectrum_rows])
    eigenvalues = np.asarray(
        [abs(float(row["eigenvalue"])) for row in spectrum_rows]
    )

    intensity_rows = list(
        csv.DictReader((data_dir / "fig4_intensity_scaling.csv").open())
    )
    selected: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in intensity_rows:
        if (
            row["range"] == "paper_range"
            and row["fidelity_convention"] == "pointwise_cz_equivalent"
        ):
            selected[row["gate"]].append(
                (abs(float(row["delta_intensity"])), float(row["infidelity_raw"]))
            )

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.8))
    axes[0].plot(times, amplitude, color="#213a5c", label="Amplitude")
    phase_axis = axes[0].twinx()
    phase_axis.plot(times, phase, color="#c44e52", alpha=0.85, label="Phase")
    axes[0].set(
        xlabel="Time (μs)",
        ylabel="Normalized amplitude",
        title="Optimized 0.55 μs control",
    )
    phase_axis.set_ylabel("Unwrapped phase (rad)", color="#c44e52")

    axes[1].semilogy(modes, np.maximum(eigenvalues, 1e-18), "o-", ms=3)
    axes[1].axvline(10.5, color="#c44e52", ls="--", lw=1)
    axes[1].set(
        xlabel="Hessian mode",
        ylabel="|Eigenvalue|",
        title="Ten active calibration directions",
    )

    gate_styles = {
        "AR equivalent reoptimization": ("Amplitude-robust CZ", "o-", "#198f7a"),
        "same-duration non-robust surrogate": (
            "Non-robust CZ",
            "s-",
            "#c44e52",
        ),
    }
    for gate, (label, style, color) in gate_styles.items():
        points = sorted(
            (x, y) for x, y in selected.get(gate, []) if x > 0 and y > 0
        )
        if points:
            axes[2].loglog(
                [point[0] for point in points],
                [point[1] for point in points],
                style,
                color=color,
                ms=4,
                label=label,
            )
    axes[2].set(
        xlabel="|Relative intensity error|",
        ylabel="Gate error",
        title="Robustness to intensity error",
    )
    axes[2].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT / "ar_cz_design.png", dpi=180)
    plt.close(fig)


def build_hessian_search_comparison() -> None:
    path = (
        ROOT
        / "data"
        / "figure1"
        / "data"
        / "optimization-trajectories.csv"
    )
    rows_by_method: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["panel"] == "h":
                rows_by_method[row["method"]].append(row)

    styles = {
        "Hessian eigenvectors": ("Hessian eigenvectors", "#e1812c"),
        "Chebyshev, first 6 orders": ("Chebyshev basis", "#4c72b0"),
        "Analytical ansatz": ("Analytical ansatz", "#55a868"),
        "AA + orthogonal eigenbasis": (
            "Ansatz + orthogonal directions",
            "#c44e52",
        ),
    }
    fig, axis = plt.subplots(figsize=(7.2, 4.4))
    for method, (label, color) in styles.items():
        rows = rows_by_method[method]
        axis.semilogy(
            [int(row["step"]) for row in rows],
            [max(float(row["infidelity"]), 1e-15) for row in rows],
            marker="o",
            ms=3,
            lw=1.4,
            color=color,
            label=label,
        )
    axis.axhline(1e-5, color="black", ls="--", lw=1, label="Target 1−F=10⁻⁵")
    axis.set(
        xlabel="One-dimensional calibration scans",
        ylabel="Gate error 1−F",
        title="Matched initial pulse error: convergence by search basis",
        xlim=(0, 60),
    )
    axis.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT / "hessian_search_comparison.png", dpi=180)
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    build_abstract_calibration()
    build_ar_cz_design()
    build_hessian_search_comparison()
    print(f"wrote report assets to {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
