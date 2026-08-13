#!/usr/bin/env python3
"""Plot Stage 2 DQMC/ED agreement and low-temperature convergence."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def values(rows, key):
    return np.asarray([float(row[key]) for row in rows])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--m4-ed-table", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.table.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with args.m4_ed_table.open(encoding="utf-8") as handle:
        ed_rows = list(csv.DictReader(handle))
    m3 = sorted(
        (row for row in rows if int(row["m"]) == 3),
        key=lambda row: float(row["dt"]),
    )
    m4 = sorted(
        (
            row
            for row in rows
            if int(row["m"]) == 4 and float(row["dt"]) == 0.1
        ),
        key=lambda row: float(row["beta"]),
    )
    m4_ed = next(
        row
        for row in ed_rows
        if float(row["t"]) == 1.0
        and float(row["g_b_over_g_a"]) == 1.0
    )
    m4_ed_energy = float(m4_ed["energy"])
    m4_ed_q = 0.5 * (
        float(m4_ed["q_a_sq"]) + float(m4_ed["q_b_sq"])
    )
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    dt = values(m3, "dt")
    axes[0, 0].errorbar(
        dt,
        values(m3, "energy_mean"),
        yerr=values(m3, "energy_stderr"),
        marker="o",
        label="DQMC",
    )
    axes[0, 0].axhline(float(m3[0]["energy_ed"]), color="black", label="ED")
    axes[0, 0].set(xlabel="Δτ", ylabel="energy", title="m=3, β=2")
    axes[0, 0].legend()
    axes[0, 1].errorbar(
        dt,
        values(m3, "q_combined_mean"),
        yerr=values(m3, "q_combined_stderr"),
        marker="o",
    )
    axes[0, 1].axhline(float(m3[0]["q_combined_ed"]), color="black")
    axes[0, 1].set(
        xlabel="Δτ", ylabel="(Q_A²+Q_B²)/2", title="m=3 channel correlation"
    )
    beta = values(m4, "beta")
    axes[1, 0].errorbar(
        beta,
        values(m4, "energy_mean"),
        yerr=values(m4, "energy_stderr"),
        marker="o",
    )
    axes[1, 0].axhline(m4_ed_energy, color="black", label="N=8 ED ground")
    axes[1, 0].set(xlabel="β", ylabel="energy", title="m=4, Δτ=0.1")
    axes[1, 0].legend()
    axes[1, 1].errorbar(
        beta,
        values(m4, "q_combined_mean"),
        yerr=values(m4, "q_combined_stderr"),
        marker="o",
    )
    axes[1, 1].axhline(m4_ed_q, color="black")
    axes[1, 1].set(
        xlabel="β",
        ylabel="(Q_A²+Q_B²)/2",
        title="m=4 channel correlation",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    print(args.output, flush=True)


if __name__ == "__main__":
    main()
