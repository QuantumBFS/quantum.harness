#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_analysis(summary, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    diagnostic = summary["primary_diagnostic"]
    windows = summary["stability_diagnostic"]["accepted_matched_windows"]
    labels = [
        f'{row["model"]}, Lmin={row["L_min"]}, {row["yt_mode"]}' for row in windows
    ]
    values = [float(row["R"]) for row in windows]

    figure_height = max(4.2, 0.42 * (len(windows) + 2))
    fig, ax = plt.subplots(figsize=(9.0, figure_height), constrained_layout=True)
    positions = list(range(len(windows)))
    ax.scatter(values, positions, color="#2468b4", s=48, label="accepted matched windows")
    primary_y = len(windows) + 0.4
    ax.errorbar(
        [float(diagnostic["R"])],
        [primary_y],
        xerr=[float(diagnostic["R_covariance_stderr"])],
        fmt="o",
        color="#c63c32",
        capsize=4,
        label="frozen primary (rejected)",
    )
    ax.axvline(
        float(diagnostic["sqrt5"]), color="#222222", linestyle="--", linewidth=1.5,
        label="sqrt(5)",
    )
    ax.set_yticks(positions + [primary_y], labels + ["primary M1, Lmin=8"])
    ax.set_xlabel("critical-field ratio R")
    ax.set_title("Challenge #148: fit-window stability (gate-pending)")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="best", frameon=False)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    with arguments.summary.open(encoding="utf-8") as stream:
        summary = json.load(stream)
    plot_analysis(summary, arguments.output)


if __name__ == "__main__":
    main()
