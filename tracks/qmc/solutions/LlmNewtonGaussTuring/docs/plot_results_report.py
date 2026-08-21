#!/usr/bin/env python3
"""Generate the figures used by the current results report."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


WORKSPACE = Path(__file__).resolve().parents[2]
RESULTS = WORKSPACE / "src/TFIM-sqrt5-conjecture/data/processed"
FIGURES = Path(__file__).resolve().parent / "figures"

BENCHMARK = RESULTS / "tfim-cpp-cluster-loop-line-benchmark-full-20260730/efficiency.csv"
VALIDATION = RESULTS / "tfim-cpp-cluster-loop-line-ed-validation-20260730/validation.csv"

ALGORITHMS = ("cluster", "loop", "line")
OBSERVABLES = ("E", "mx", "m2", "m4")
LATTICES = ("triangular", "honeycomb")
COLORS = {"cluster": "#0072B2", "loop": "#009E73", "line": "#D55E00"}
MARKERS = {"cluster": "o", "loop": "s", "line": "^"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def mean_sd(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), statistics.stdev(values)


def plot_performance(rows: list[dict[str, str]]) -> None:
    ess: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    sweep_by_repeat: dict[tuple[str, str, str], float] = {}
    for row in rows:
        key = (row["lattice"], row["observable"], row["algorithm"])
        ess[key].append(float(row["ess_per_second"]))
        sweep_by_repeat[(row["lattice"], row["algorithm"], row["repeat"])] = 1000.0 * float(
            row["sweep_seconds"]
        )

    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.2), constrained_layout=True)
    width = 0.24
    offsets = (-width, 0.0, width)

    for axis, lattice in zip(axes[:2], LATTICES):
        for algorithm, offset in zip(ALGORITHMS, offsets):
            stats = [mean_sd(ess[(lattice, observable, algorithm)]) for observable in OBSERVABLES]
            axis.bar(
                [index + offset for index in range(len(OBSERVABLES))],
                [value[0] for value in stats],
                yerr=[value[1] for value in stats],
                width=width,
                color=COLORS[algorithm],
                label=algorithm,
                capsize=2.5,
                linewidth=0,
            )
        axis.set_yscale("log")
        axis.set_xticks(range(len(OBSERVABLES)), (r"$E$", r"$m_x$", r"$m^2$", r"$m^4$"))
        axis.set_title(lattice.capitalize())
        axis.set_ylabel("Effective samples per second")
        axis.grid(axis="y", alpha=0.25)

    wall_axis = axes[2]
    positions = range(len(LATTICES))
    for algorithm, offset in zip(ALGORITHMS, offsets):
        stats = []
        for lattice in LATTICES:
            values = [
                value
                for (row_lattice, row_algorithm, _), value in sweep_by_repeat.items()
                if row_lattice == lattice and row_algorithm == algorithm
            ]
            stats.append(mean_sd(values))
        wall_axis.bar(
            [index + offset for index in positions],
            [value[0] for value in stats],
            yerr=[value[1] for value in stats],
            width=width,
            color=COLORS[algorithm],
            label=algorithm,
            capsize=2.5,
            linewidth=0,
        )
    wall_axis.set_xticks(list(positions), ("Triangular", "Honeycomb"))
    wall_axis.set_ylabel("Wall time per sweep (ms)")
    wall_axis.set_title("Sweep cost")
    wall_axis.grid(axis="y", alpha=0.25)
    wall_axis.legend(frameon=False, ncols=1)

    fig.savefig(FIGURES / "challenge148_update_performance.png", dpi=180)
    plt.close(fig)


def plot_ed_validation(rows: list[dict[str, str]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.7), constrained_layout=True, sharey=True)
    for axis, lattice in zip(axes, LATTICES):
        subset = [row for row in rows if row["lattice"] == lattice]
        for algorithm in ALGORITHMS:
            selected = [row for row in subset if row["algorithm"] == algorithm]
            x = [OBSERVABLES.index(row["observable"]) for row in selected]
            y = [float(row["z_score"]) for row in selected]
            axis.scatter(
                x,
                y,
                color=COLORS[algorithm],
                marker=MARKERS[algorithm],
                s=48,
                label=algorithm,
            )
        axis.axhline(4.0, color="#555555", linewidth=1.2, linestyle=":")
        axis.set_xticks(range(3), (r"$E$", r"$m_x$", r"$m^2$"))
        axis.set_ylim(0.0, 4.4)
        axis.set_title(lattice.capitalize())
        axis.set_xlabel("Observable")
        axis.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Absolute QMC difference from ED (standard errors)")
    axes[1].legend(frameon=False)
    fig.savefig(FIGURES / "challenge148_ed_validation.png", dpi=180)
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plot_performance(read_csv(BENCHMARK))
    plot_ed_validation(read_csv(VALIDATION))


if __name__ == "__main__":
    main()
