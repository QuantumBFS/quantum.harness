#!/usr/bin/env python3
"""Plot C++ versus Julia line-update throughput and speedup."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    with args.csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped[int(row["sites"])].append(row)

    sites = sorted(grouped)
    cpp_rate = [statistics.median(float(row["cpp_sweeps_per_second"]) for row in grouped[n]) for n in sites]
    julia_rate = [statistics.median(float(row["julia_sweeps_per_second"]) for row in grouped[n]) for n in sites]
    speedup = [statistics.median(float(row["speedup"]) for row in grouped[n]) for n in sites]

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), constrained_layout=True)
    axes[0].plot(sites, cpp_rate, "o-", label="C++17 line update", color="#0072B2")
    axes[0].plot(sites, julia_rate, "s--", label="Julia loop reference", color="#D55E00")
    axes[0].set(xlabel="Sites", ylabel="Sweeps / second", xscale="log", yscale="log")
    axes[0].legend(frameon=False)
    axes[1].plot(sites, speedup, "o-", color="#009E73")
    axes[1].axhline(1.0, color="#555555", linewidth=1.0, linestyle=":")
    axes[1].set(xlabel="Sites", ylabel="C++ speedup over warmed Julia", xscale="log")
    lattice = next(iter(grouped.values()))[0]["lattice"]
    figure.suptitle(f"Merge-unmerge TFIM line update ({lattice})")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
