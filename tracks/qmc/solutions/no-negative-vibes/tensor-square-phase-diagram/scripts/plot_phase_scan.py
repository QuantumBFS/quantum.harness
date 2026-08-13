#!/usr/bin/env python3
"""Render the first Stage 3 rough phase map."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cells = _read_csv(args.aggregate_dir / "table.csv")
    regions = _read_csv(args.aggregate_dir / "regions.csv")
    g_values = [0.0, 0.25, 0.5, 1.0, 2.0]
    t_values = [0.0, 0.25, 0.5, 1.0, 2.0]
    mu_values = [-1.5, 0.0, 1.5]
    low = {
        (
            float(row["g_b_over_g_a"]),
            float(row["t"]),
            float(row["mu"]),
        ): row
        for row in cells
        if int(row["m"]) == 8 and float(row["beta"]) == 8.0
    }
    region_lookup = {
        (
            float(row["g_b_over_g_a"]),
            float(row["t"]),
            float(row["mu"]),
        ): row
        for row in regions
    }
    q_values = [
        float(row["q_combined_mean"])
        for row in low.values()
        if np.isfinite(float(row["q_combined_mean"]))
    ]
    q_min, q_max = np.percentile(q_values, [2.0, 98.0])
    if q_min == q_max:
        q_min, q_max = q_min - 0.5, q_max + 0.5
    class_value = {"BROKEN": -1.0, "STOP": 0.0, "EXTEND": 1.0, "SURVIVE": 2.0}
    class_letter = {"BROKEN": "B", "STOP": "×", "EXTEND": "E", "SURVIVE": "S"}

    figure, axes = plt.subplots(3, 3, figsize=(12.2, 11.0), constrained_layout=True)
    image_q = image_balance = image_class = None
    for column, mu in enumerate(mu_values):
        q_matrix = np.full((5, 5), np.nan)
        balance_matrix = np.full((5, 5), np.nan)
        classification_matrix = np.full((5, 5), np.nan)
        annotations: dict[tuple[int, int], str] = {}
        for row_index, g_ratio in enumerate(g_values):
            for column_index, t in enumerate(t_values):
                key = (g_ratio, t, mu)
                if key in low:
                    q_matrix[row_index, column_index] = float(
                        low[key]["q_combined_mean"]
                    )
                    balance_matrix[row_index, column_index] = float(
                        low[key]["channel_balance_mean"]
                    )
                if key in region_lookup:
                    label = region_lookup[key]["classification"]
                    classification_matrix[row_index, column_index] = class_value[label]
                    annotations[(row_index, column_index)] = class_letter[label]
        image_q = axes[0, column].imshow(
            q_matrix,
            origin="lower",
            aspect="auto",
            vmin=q_min,
            vmax=q_max,
            cmap="viridis",
        )
        image_balance = axes[1, column].imshow(
            balance_matrix,
            origin="lower",
            aspect="auto",
            vmin=-1.0,
            vmax=1.0,
            cmap="coolwarm",
        )
        image_class = axes[2, column].imshow(
            classification_matrix,
            origin="lower",
            aspect="auto",
            norm=colors.BoundaryNorm([-1.5, -0.5, 0.5, 1.5, 2.5], 4),
            cmap=colors.ListedColormap(["#232323", "#d9d9d9", "#fdae61", "#1a9850"]),
        )
        for (row_index, column_index), letter in annotations.items():
            axes[2, column].text(
                column_index,
                row_index,
                letter,
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
        axes[0, column].set_title(rf"$\mu/g_A={mu:g}$")
        for row in range(3):
            axes[row, column].set_xticks(range(5), [f"{value:g}" for value in t_values])
            axes[row, column].set_yticks(range(5), [f"{value:g}" for value in g_values])
            axes[row, column].set_xlabel(r"$t/g_A$")
            if column == 0:
                axes[row, column].set_ylabel(r"$g_B/g_A$")
    axes[0, 0].text(
        -0.35,
        0.5,
        r"$Q_{\rm combined}^2$ ($m=8,\beta=8$)",
        rotation=90,
        transform=axes[0, 0].transAxes,
        ha="center",
        va="center",
    )
    axes[1, 0].text(
        -0.35,
        0.5,
        "channel balance",
        rotation=90,
        transform=axes[1, 0].transAxes,
        ha="center",
        va="center",
    )
    axes[2, 0].text(
        -0.35,
        0.5,
        "early classification",
        rotation=90,
        transform=axes[2, 0].transAxes,
        ha="center",
        va="center",
    )
    assert image_q is not None and image_balance is not None and image_class is not None
    figure.colorbar(image_q, ax=axes[0, :], shrink=0.82, label=r"$Q^2$")
    figure.colorbar(image_balance, ax=axes[1, :], shrink=0.82, label="B−A / B+A")
    colorbar = figure.colorbar(image_class, ax=axes[2, :], shrink=0.82)
    colorbar.set_ticks([-1.0, 0.0, 1.0, 2.0])
    colorbar.set_ticklabels(["BROKEN", "STOP", "EXTEND", "SURVIVE"])
    figure.suptitle(
        "Tensor-square Stage 3 rough phase map (short-chain screening)",
        fontsize=15,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=220)
    plt.close(figure)


if __name__ == "__main__":
    main()
