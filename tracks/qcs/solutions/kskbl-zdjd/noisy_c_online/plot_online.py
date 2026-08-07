"""Plot convergence and uncertainty from an online noisy-C run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = json.loads((args.run_dir / "metrics.json").read_text(encoding="utf-8"))
    output = args.output or args.run_dir / "convergence.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    x = np.asarray([row["examples_seen"] for row in records], dtype=float)
    clean_bce = np.asarray([row["clean_bce"] for row in records], dtype=float)
    bit_accuracy = np.asarray([row["bit_accuracy"] for row in records], dtype=float)
    word_accuracy = np.asarray([row["word_accuracy"] for row in records], dtype=float)
    nmae = np.asarray([row["normalized_mae"] for row in records], dtype=float)
    ubit = np.asarray([row["bit_uncertainty"] for row in records], dtype=float)
    uvalue = np.asarray([row["value_uncertainty"] for row in records], dtype=float)
    train = np.asarray(
        [
            np.nan if row["train_loss_ema"] is None else row["train_loss_ema"]
            for row in records
        ],
        dtype=float,
    )

    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    fig.patch.set_facecolor("#0d1322")
    for axis in axes.flat:
        axis.set_facecolor("#111b2d")
        axis.grid(alpha=0.16)
        axis.set_xlabel("Fresh training examples seen")

    axes[0, 0].plot(x, clean_bce, label="clean full-domain BCE", color="#6ee7ff")
    axes[0, 0].plot(x, train, label="noisy train loss EMA", color="#ff9f72")
    axes[0, 0].set_ylabel("Loss")
    axes[0, 0].set_title("Blind training versus clean evaluation")
    axes[0, 0].legend(frameon=False)

    axes[0, 1].plot(x, bit_accuracy, label="bit accuracy", color="#6ff0b0")
    axes[0, 1].plot(x, word_accuracy, label="exact word accuracy", color="#a69aff")
    axes[0, 1].set_ylim(-0.02, 1.02)
    axes[0, 1].set_ylabel("Accuracy")
    axes[0, 1].set_title("Recovery of the hidden clean map")
    axes[0, 1].legend(frameon=False)

    axes[1, 0].plot(x, ubit, label="summed bit uncertainty", color="#e7c76e")
    axes[1, 0].set_ylabel("Ubit, range 0 to 12")
    twin = axes[1, 0].twinx()
    twin.plot(x, uvalue, label="value uncertainty", color="#ff8291")
    twin.set_ylabel("Normalized value uncertainty")
    handles_a, labels_a = axes[1, 0].get_legend_handles_labels()
    handles_b, labels_b = twin.get_legend_handles_labels()
    axes[1, 0].legend(handles_a + handles_b, labels_a + labels_b, frameon=False)
    axes[1, 0].set_title("Ensemble disagreement")

    axes[1, 1].plot(x, nmae, color="#74a8ff")
    axes[1, 1].set_ylabel("Normalized numerical MAE")
    axes[1, 1].set_title("Numerical significance of remaining errors")

    final = records[-1]
    fig.suptitle(
        "Task C+ online fresh-noise recovery\n"
        f"final bit={final['bit_accuracy']:.4f}, "
        f"word={final['word_accuracy']:.4f}, "
        f"Ubit={final['bit_uncertainty']:.3f}",
        fontsize=15,
    )
    fig.savefig(output, dpi=170, facecolor=fig.get_facecolor())
    print(output)


if __name__ == "__main__":
    main()
