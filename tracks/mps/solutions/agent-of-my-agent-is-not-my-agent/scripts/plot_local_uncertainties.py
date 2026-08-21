#!/usr/bin/env python3
"""Plot separated MPS and MPO uncertainty for the local reproduction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.analysis.read_text())
    crossing = data["mpo"]["crossing"]
    mps = data["mps"]["comparisons"]
    mpo = data["mpo"]["comparisons"]

    colors = {"mps": "#0072B2", "mpo": "#D55E00"}
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.2), constrained_layout=True)

    ax = axes[0]
    if crossing["status"] == "complete":
        values = [crossing["K24"]["gamma"], crossing["K32"]["gamma"]]
        ax.plot([24, 32], values, "o-", color="#009E73", linewidth=1.5)
        ax.ticklabel_format(axis="y", useOffset=False)
    ax.set_xlabel("Exponential terms K")
    ax.set_ylabel("Two-size crossing Γ×")
    ax.set_title("Fixed-bracket crossing")
    ax.set_xticks([24, 32])

    ax = axes[1]
    mps_x = np.arange(len(mps))
    ax.scatter(
        mps_x,
        [abs(item["gap"]["relative"]) for item in mps],
        color=colors["mps"],
        marker="o",
        label="χ: 128→256, L=64",
    )
    mpo_labels = []
    mpo_values = []
    for item in mpo:
        mpo_labels.append(f"L={item['length']}\nΓ={item['gamma']:.3f}")
        mpo_values.append(abs(item["gap"]["relative"]))
    offset = len(mps_x) + 1
    ax.scatter(
        offset + np.arange(len(mpo_values)),
        mpo_values,
        color=colors["mpo"],
        marker="s",
        label="K: 24→32, χ=128",
    )
    labels = [f"Γ={item['gamma']:.3f}" for item in mps] + [""] + mpo_labels
    ax.set_xticks(np.arange(len(labels)), labels, rotation=35, ha="right")
    ax.set_yscale("log")
    ax.set_ylabel("Relative gap shift")
    ax.set_title("Gap uncertainty")
    ax.legend(frameon=False, fontsize=7)

    ax = axes[2]
    ax.scatter(
        mps_x,
        [abs(item["r_xi"]["absolute"]) for item in mps],
        color=colors["mps"],
        marker="o",
    )
    ax.scatter(
        offset + np.arange(len(mpo)),
        [abs(item["r_xi"]["absolute"]) for item in mpo],
        color=colors["mpo"],
        marker="s",
    )
    ax.set_xticks(np.arange(len(labels)), labels, rotation=35, ha="right")
    ax.set_yscale("log")
    ax.set_ylabel("Absolute Rξ shift")
    ax.set_title("Correlation-ratio uncertainty")

    for panel, ax in zip(("a", "b", "c"), axes, strict=True):
        ax.text(
            -0.16,
            1.05,
            panel,
            transform=ax.transAxes,
            fontweight="bold",
            va="top",
        )
        ax.spines[["top", "right"]].set_visible(False)

    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output_prefix.with_suffix(".png"), dpi=300)
    fig.savefig(args.output_prefix.with_suffix(".pdf"))
    print(f"wrote {args.output_prefix.with_suffix('.png')}", flush=True)


if __name__ == "__main__":
    main()
