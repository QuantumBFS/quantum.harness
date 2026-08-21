#!/usr/bin/env python3
"""Plot the line-update efficiency, scaling, and epsilon benchmark CSVs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


COLORS = {"loop": "#2563eb", "line": "#dc2626", "triangular": "#7c3aed", "honeycomb": "#059669"}
MARKERS = {"triangular": "o", "honeycomb": "s"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def plot_efficiency(data_dir: Path) -> None:
    rows = read_rows(data_dir / "efficiency.csv")
    observables = ["E", "mx", "m2", "m4"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    width = 0.18
    for lattice_index, lattice in enumerate(("triangular", "honeycomb")):
        subset = [row for row in rows if row["lattice"] == lattice]
        for algorithm_index, algorithm in enumerate(("loop", "line")):
            selected = {row["observable"]: row for row in subset if row["algorithm"] == algorithm}
            offset = (2 * lattice_index + algorithm_index - 1.5) * width
            label = f"{lattice}, {algorithm}"
            axes[0].bar(
                [i + offset for i in range(len(observables))],
                [float(selected[obs]["ess_per_second"]) for obs in observables],
                width=width,
                label=label,
                color=COLORS[algorithm],
                alpha=1.0 if lattice == "triangular" else 0.55,
                hatch="" if lattice == "triangular" else "//",
            )
            axes[1].bar(
                [i + offset for i in range(len(observables))],
                [float(selected[obs]["tau_int"]) for obs in observables],
                width=width,
                color=COLORS[algorithm],
                alpha=1.0 if lattice == "triangular" else 0.55,
                hatch="" if lattice == "triangular" else "//",
            )
    for axis, ylabel in zip(axes, ("Effective samples / second", r"Integrated autocorrelation $\tau_{int}$")):
        axis.set_xticks(range(len(observables)), observables)
        axis.set_yscale("log")
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8)
    fig.savefig(data_dir / "efficiency.png", dpi=180)
    plt.close(fig)


def plot_scaling(data_dir: Path) -> None:
    rows = read_rows(data_dir / "scaling.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), constrained_layout=True)
    for lattice in ("triangular", "honeycomb"):
        subset = sorted((row for row in rows if row["lattice"] == lattice), key=lambda row: int(row["threads"]))
        threads = [int(row["threads"]) for row in subset]
        style = dict(color=COLORS[lattice], marker=MARKERS[lattice], linewidth=2, label=lattice)
        axes[0].plot(threads, [float(row["color_speedup"]) for row in subset], **style)
        axes[1].plot(threads, [float(row["full_speedup"]) for row in subset], **style)
    ideal_threads = sorted({int(row["threads"]) for row in rows})
    for axis, title in zip(axes, ("Color sweep only", "Full sweep (Amdahl honest)")):
        axis.plot(ideal_threads, ideal_threads, color="#6b7280", linestyle="--", label="ideal")
        axis.set(xlabel="Julia threads", ylabel="Speedup", title=title, xticks=ideal_threads)
        axis.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.savefig(data_dir / "scaling.png", dpi=180)
    plt.close(fig)


def plot_epsilon(data_dir: Path) -> None:
    candidates = [row for path in sorted(data_dir.glob("epsilon*.csv")) for row in read_rows(path)]
    longest: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in candidates:
        key = (row["lattice"], row["epsilon"], row["observable"])
        if key not in longest or int(row["measurement_sweeps"]) > int(longest[key]["measurement_sweeps"]):
            longest[key] = row
    rows = [row for row in longest.values() if row["observable"] == "m2"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), constrained_layout=True)
    for lattice in ("triangular", "honeycomb"):
        subset = sorted((row for row in rows if row["lattice"] == lattice), key=lambda row: float(row["epsilon"]))
        epsilon = [float(row["epsilon"]) for row in subset]
        style = dict(color=COLORS[lattice], marker=MARKERS[lattice], linewidth=2, label=lattice)
        axes[0].plot(epsilon, [float(row["acceptance"]) for row in subset], **style)
        axes[1].plot(epsilon, [float(row["mean_operator_count"]) for row in subset], **style)
        axes[2].plot(epsilon, [float(row["ess_per_second"]) for row in subset], **style)
    for axis, ylabel in zip(axes, ("Segment acceptance", "Mean operator count", r"$m^2$ ESS / second")):
        axis.set(xlabel=r"Bond shift $\epsilon$", ylabel=ylabel, xticks=[0.25, 0.5, 1.0])
        axis.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.savefig(data_dir / "epsilon.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path)
    args = parser.parse_args()
    plot_efficiency(args.data_dir)
    plot_scaling(args.data_dir)
    plot_epsilon(args.data_dir)


if __name__ == "__main__":
    main()
