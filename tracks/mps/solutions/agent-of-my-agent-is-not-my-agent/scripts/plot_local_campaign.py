#!/usr/bin/env python3
"""Plot the Phase 6 local-campaign R_xi crossing from its CSV output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()

    with (args.results_dir / "analysis.json").open() as handle:
        analysis = json.load(handle)

    by_size: dict[int, tuple[list[float], list[float]]] = {}
    with (args.results_dir / "rxi.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            size = int(row["length"])
            gammas, values = by_size.setdefault(size, ([], []))
            gammas.append(float(row["gamma"]))
            values.append(float(row["r_xi"]))

    colors = {32: "#0072B2", 64: "#D55E00"}
    markers = {32: "o", 64: "s"}
    fig, ax = plt.subplots(figsize=(5.2, 3.4), constrained_layout=True)
    for size in sorted(by_size):
        gammas, values = by_size[size]
        ax.plot(
            gammas,
            values,
            marker=markers.get(size, "o"),
            color=colors.get(size),
            linewidth=1.7,
            markersize=5,
            label=f"L={size}",
        )

    crossing = analysis["crossing"]["gamma"]
    ax.axvline(
        crossing,
        color="#009E73",
        linestyle="--",
        linewidth=1.3,
        label=f"linear crossing {crossing:.5f}",
    )
    ax.set_xlabel("Transverse field Γ")
    ax.set_ylabel("Correlation ratio Rξ = ξ/L")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        0.02,
        0.03,
        "χ=128 pilot; crossing is provisional",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.savefig(args.results_dir / "rxi-crossing.png", dpi=300)
    fig.savefig(args.results_dir / "rxi-crossing.pdf")


if __name__ == "__main__":
    main()
