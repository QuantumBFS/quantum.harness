#!/usr/bin/env python3
"""Render compact ED heatmaps from an aggregate table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("m3", "m4"), required=True)
    args = parser.parse_args()
    with args.table.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows = [
        row
        for row in rows
        if row["variant"]
        == ("noncommuting_n4" if args.mode == "m3" else "noncommuting")
        and (args.mode == "m4" or float(row["mu"]) == 0.0)
    ]
    t_grid = sorted({float(row["t"]) for row in rows})
    g_grid = sorted({float(row["g_b_over_g_a"]) for row in rows})
    metrics = (
        ("channel_balance", "channel balance"),
        ("sector_gap", "fixed-N gap"),
        ("commutator_sq", "noncommuting response"),
        ("nematic_sq", "fiber nematic²"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    for axis, (metric, title) in zip(axes.flat, metrics, strict=True):
        values = np.full((len(t_grid), len(g_grid)), np.nan)
        for row in rows:
            i = t_grid.index(float(row["t"]))
            j = g_grid.index(float(row["g_b_over_g_a"]))
            values[i, j] = float(row[metric])
        image = axis.imshow(values, origin="lower", aspect="auto")
        axis.set_xticks(range(len(g_grid)), [f"{value:g}" for value in g_grid])
        axis.set_yticks(range(len(t_grid)), [f"{value:g}" for value in t_grid])
        axis.set_xlabel("g_B / g_A")
        axis.set_ylabel("t / g_A")
        axis.set_title(title)
        fig.colorbar(image, ax=axis, shrink=0.85)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.suptitle(f"Tensor-square {args.mode} ED pilot")
    fig.savefig(args.output, dpi=180)
    print(args.output, flush=True)


if __name__ == "__main__":
    main()
