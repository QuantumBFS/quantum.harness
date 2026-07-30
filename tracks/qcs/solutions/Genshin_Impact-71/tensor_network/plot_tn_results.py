#!/usr/bin/env python3
"""Plot exact TT rank structure and train-selected MPS audit accuracy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


INSTANCES = ("mystery-A", "mystery-B", "mystery-C", "mystery-D")
ORDERS = (
    "blocked_lsb",
    "blocked_msb",
    "interleaved_lsb",
    "interleaved_msb",
)
ORDER_LABELS = ("blocked LSB", "blocked MSB", "interleaved LSB", "interleaved MSB")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.summary.read_text(encoding="utf-8"))
    rank_lookup = {
        (item["instance"], item["order"]): max(
            item["oracle_audit_only"]["boolean_max_rank_by_cut"]
        )
        for item in data["rank_diagnostics"]
    }
    accuracy_lookup = {
        (item["instance"], item["order"]): item["full_domain_audit"][
            "exact_accuracy"
        ]
        for item in data["train_validation_selected"]
    }
    x_locations = np.arange(len(INSTANCES), dtype=np.float64)
    bar_width = 0.19
    colors = ("#4C78A8", "#72B7B2", "#F58518", "#E45756")
    figure, axes = plt.subplots(2, 1, figsize=(10.5, 8.2), constrained_layout=True)
    for order_index, (order, label, color) in enumerate(
        zip(ORDERS, ORDER_LABELS, colors)
    ):
        offsets = x_locations + (order_index - 1.5) * bar_width
        ranks = [rank_lookup[(instance, order)] for instance in INSTANCES]
        accuracies = [
            accuracy_lookup[(instance, order)] for instance in INSTANCES
        ]
        axes[0].bar(offsets, ranks, width=bar_width, label=label, color=color)
        axes[1].bar(offsets, accuracies, width=bar_width, label=label, color=color)
        for x_value, rank in zip(offsets, ranks):
            axes[0].annotate(
                str(rank),
                (x_value, rank),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )
        for x_value, accuracy in zip(offsets, accuracies):
            axes[1].annotate(
                f"{accuracy:.3f}",
                (x_value, accuracy),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
                rotation=90,
            )
    axes[0].set_yscale("log", base=2)
    axes[0].set_ylabel("max exact Boolean TT rank (log₂)")
    axes[0].set_title("Variable order changes TT complexity sharply")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    axes[1].set_ylim(0.0, 1.05)
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1)
    axes[1].set_ylabel("full-domain exact-match accuracy")
    axes[1].set_title("Train-validation-selected continuous MPS remains inexact")
    axes[1].grid(axis="y", alpha=0.25)
    for axis in axes:
        axis.set_xticks(x_locations)
        axis.set_xticklabels(INSTANCES)
    figure.suptitle(
        "Issue 71 tensor-network arm — seed 42; 0 exact models, 0 legal circuits",
        fontsize=13,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp.png")
    figure.savefig(temporary, dpi=180)
    plt.close(figure)
    temporary.replace(args.output)
    print(args.output, flush=True)


if __name__ == "__main__":
    main()
