"""Aggregate and plot the shared-reality Majorana two-cone scan."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import __version__


def summarize_angles(
    rows: pd.DataFrame,
    *,
    samples_per_cell: int,
) -> pd.DataFrame:
    grouped = rows.groupby(["block_size", "angle"], sort=True)
    summary = grouped.agg(
        cells=("cell_id", "count"),
        failed_cells=("status", lambda values: int((values != "success").sum())),
        negative=("negative", "sum"),
        complex=("complex", "sum"),
        uncertain=("uncertain", "sum"),
        negative_cells=("negative", lambda values: int((values > 0).sum())),
        max_structure_residual=("max_structure_residual", "max"),
        max_common_reality_residual=("max_common_reality_residual", "max"),
        max_square_identity_residual=("max_square_identity_residual", "max"),
        max_reliable_square_identity_residual=(
            "max_reliable_square_identity_residual",
            "max",
        ),
        unreliable_determinant_checks=("unreliable_determinant_checks", "sum"),
        min_cancellation_ratio=("min_cancellation_ratio", "min"),
    )
    summary["samples"] = summary["cells"] * samples_per_cell
    summary["negative_rate"] = summary["negative"] / summary["samples"]
    return summary.reset_index()


def first_negative_rows(rows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for (block_size, angle, scale), group in rows.groupby(
        ["block_size", "angle", "scale"],
        sort=True,
    ):
        failing = group[group["negative"] > 0]
        records.append(
            {
                "block_size": int(block_size),
                "angle": float(angle),
                "scale": float(scale),
                "first_negative_depth": (
                    int(failing["depth"].min()) if not failing.empty else np.nan
                ),
                "negative": int(group["negative"].sum()),
                "samples": int(group["samples_per_cell"].sum()),
            }
        )
    return pd.DataFrame.from_records(records)


def _plot_negative_rate(rows: pd.DataFrame, path: Path) -> None:
    block_sizes = sorted(rows["block_size"].unique())
    figure, axes = plt.subplots(
        len(block_sizes),
        1,
        figsize=(8.5, 3.6 * len(block_sizes)),
        sharex=True,
        squeeze=False,
    )
    for axis, block_size in zip(axes[:, 0], block_sizes):
        subset = rows[rows["block_size"] == block_size]
        for scale, group in subset.groupby("scale", sort=True):
            aggregate = group.groupby("angle", sort=True).agg(
                negative=("negative", "sum"),
                samples=("samples_per_cell", "sum"),
            )
            axis.plot(
                aggregate.index,
                aggregate["negative"] / aggregate["samples"],
                marker="o",
                label=f"scale={scale:g}",
            )
        axis.set_title(
            f"{2 * int(block_size)} Majoranas "
            f"(Fock dimension {2 ** int(block_size)})"
        )
        axis.set_ylabel("negative trace fraction")
        axis.grid(alpha=0.25)
        axis.legend()
    axes[-1, 0].set_xlabel("relative cone angle (radians)")
    figure.suptitle("Mixing two Majorana-positive cones with a shared reality structure")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_first_negative_depth(first: pd.DataFrame, path: Path) -> None:
    block_sizes = sorted(first["block_size"].unique())
    figure, axes = plt.subplots(
        len(block_sizes),
        1,
        figsize=(9.2, 3.7 * len(block_sizes)),
        squeeze=False,
    )
    for axis, block_size in zip(axes[:, 0], block_sizes):
        subset = first[first["block_size"] == block_size]
        pivot = subset.pivot(
            index="scale",
            columns="angle",
            values="first_negative_depth",
        )
        masked = np.ma.masked_invalid(pivot.to_numpy(dtype=float))
        image = axis.imshow(
            masked,
            aspect="auto",
            origin="lower",
            cmap="viridis_r",
            vmin=2,
            vmax=16,
        )
        axis.set_xticks(
            np.arange(len(pivot.columns)),
            [f"{angle:.2f}" for angle in pivot.columns],
        )
        axis.set_yticks(
            np.arange(len(pivot.index)),
            [f"{scale:g}" for scale in pivot.index],
        )
        axis.set_ylabel("generator scale")
        axis.set_title(f"{2 * int(block_size)} Majoranas")
        for row in range(masked.shape[0]):
            for column in range(masked.shape[1]):
                value = masked[row, column]
                label = "none" if np.ma.is_masked(value) else str(int(value))
                axis.text(
                    column,
                    row,
                    label,
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="black",
                )
        figure.colorbar(image, ax=axis, label="first depth with a negative sample")
    axes[-1, 0].set_xlabel("relative cone angle (radians)")
    figure.suptitle("First observed failure depth")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def write_report(
    run_dir: str | Path,
    *,
    samples_per_cell: int,
) -> dict[str, object]:
    run_path = Path(run_dir)
    rows = pd.read_csv(run_path / "parameter-scan.csv")
    rows["samples_per_cell"] = samples_per_cell
    angle_summary = summarize_angles(rows, samples_per_cell=samples_per_cell)
    first_negative = first_negative_rows(rows)
    angle_summary.to_csv(run_path / "angle-summary.csv", index=False)
    first_negative.to_csv(run_path / "first-negative-depth.csv", index=False)
    _plot_negative_rate(rows, run_path / "negative-rate-vs-angle.png")
    _plot_first_negative_depth(
        first_negative,
        run_path / "first-negative-depth.png",
    )

    status_counts = {
        str(key): int(value) for key, value in rows["status"].value_counts().items()
    }
    run = {
        "schema_version": 1,
        "run_id": run_path.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "oracle_version": __version__,
        "cells": int(len(rows)),
        "samples_per_cell": samples_per_cell,
        "samples": int(len(rows) * samples_per_cell),
        "status_counts": status_counts,
        "negative": int(rows["negative"].sum()),
        "complex": int(rows["complex"].sum()),
        "uncertain": int(rows["uncertain"].sum()),
        "max_structure_residual": float(rows["max_structure_residual"].max()),
        "max_common_reality_residual": float(
            rows["max_common_reality_residual"].max()
        ),
        "max_square_identity_residual": float(
            rows["max_square_identity_residual"].max()
        ),
        "max_reliable_square_identity_residual": float(
            rows["max_reliable_square_identity_residual"].max()
        ),
        "unreliable_determinant_checks": int(
            rows["unreliable_determinant_checks"].sum()
        ),
        "min_cancellation_ratio": float(rows["min_cancellation_ratio"].min()),
        "environment": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "pandas": importlib.metadata.version("pandas"),
            "matplotlib": importlib.metadata.version("matplotlib"),
        },
        "artifacts": [
            "parameter-scan.csv",
            "angle-summary.csv",
            "first-negative-depth.csv",
            "negative-rate-vs-angle.png",
            "first-negative-depth.png",
        ],
        "interpretation_limit": (
            "a negative Fock trace falsifies the two-cone union; "
            "zero hits do not prove positivity"
        ),
    }
    (run_path / "run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--samples-per-cell", type=int, required=True)
    args = parser.parse_args()
    run = write_report(args.run_dir, samples_per_cell=args.samples_per_cell)
    print(json.dumps(run, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
