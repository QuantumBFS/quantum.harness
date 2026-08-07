"""Plot several online fresh-noise recovery methods on shared axes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--series",
        action="append",
        required=True,
        help="Legend label followed by '=' and a metrics.json path",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_series(specification: str) -> tuple[str, list[dict[str, object]]]:
    label, separator, filename = specification.partition("=")
    if not separator or not label or not filename:
        raise ValueError("--series must use LABEL=PATH syntax")
    metrics = json.loads(Path(filename).read_text(encoding="utf-8"))
    return label, metrics


def values(
    records: list[dict[str, object]],
    key: str,
    floor: float | None = None,
) -> np.ndarray:
    array = np.asarray([record[key] for record in records], dtype=float)
    return np.maximum(array, floor) if floor is not None else array


def main() -> None:
    args = parse_args()
    series = [load_series(specification) for specification in args.series]
    plt.rcParams.update(
        {
            "text.color": "#0f172a",
            "axes.labelcolor": "#334155",
            "axes.edgecolor": "#94a3b8",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
        }
    )
    figure, axes = plt.subplots(2, 2, figsize=(13.5, 8.2), constrained_layout=True)
    figure.patch.set_facecolor("#ffffff")
    colors = ("#0284c7", "#ea580c", "#059669", "#7c3aed", "#ca8a04")

    for index, (label, records) in enumerate(series):
        color = colors[index % len(colors)]
        steps = values(records, "step")
        axes[0, 0].plot(
            steps,
            values(records, "word_accuracy"),
            label=label,
            color=color,
            linewidth=2.4,
        )
        axes[0, 1].plot(
            steps,
            values(records, "clean_bce", floor=1e-6),
            label=label,
            color=color,
            linewidth=2.2,
        )
        axes[1, 0].plot(
            steps,
            values(records, "bit_uncertainty", floor=1e-4),
            label=label,
            color=color,
            linewidth=2.2,
        )
        axes[1, 1].plot(
            steps,
            values(records, "normalized_mae", floor=1e-7),
            label=label,
            color=color,
            linewidth=2.2,
        )

    for axis in axes.flat:
        axis.set_xscale("symlog", linthresh=100)
        axis.set_xlabel("Training steps (100 fresh examples per step)")
        axis.grid(color="#cbd5e1", alpha=0.7)
        axis.set_facecolor("#f8fafc")
    axes[0, 0].set_title("Exact 12-bit word recovery")
    axes[0, 0].set_ylabel("Clean exact-word accuracy")
    axes[0, 0].set_ylim(-0.02, 1.02)
    axes[0, 0].axhline(0.98, color="#64748b", alpha=0.55, linestyle="--")
    axes[0, 0].legend(loc="lower right", framealpha=0.85)
    axes[0, 1].set_title("Clean full-domain loss")
    axes[0, 1].set_ylabel("Binary cross-entropy")
    axes[0, 1].set_yscale("log")
    axes[1, 0].set_title("Disagreement across four random initializations")
    axes[1, 0].set_ylabel("Summed bit uncertainty (0 to 12)")
    axes[1, 0].set_yscale("log")
    axes[1, 1].set_title("Numerical significance of remaining errors")
    axes[1, 1].set_ylabel("Normalized numerical MAE")
    axes[1, 1].set_yscale("log")
    figure.suptitle(
        "Fresh-noise recovery at 25% independent bit flips",
        fontsize=18,
        fontweight="bold",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180, facecolor=figure.get_facecolor())
    print(args.output)


if __name__ == "__main__":
    main()
