"""Aggregate and plot a structured determinant-weight falsification scan."""

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


def summarize_rows(
    rows: pd.DataFrame,
    *,
    samples_per_cell: int,
) -> pd.DataFrame:
    grouped = rows.groupby("case", sort=True)
    summary = grouped.agg(
        cells=("cell_id", "count"),
        failed_cells=("status", lambda values: int((values != "success").sum())),
        negative=("negative", "sum"),
        complex=("complex", "sum"),
        uncertain=("uncertain", "sum"),
        negative_cells=("negative", lambda values: int((values > 0).sum())),
        complex_cells=("complex", lambda values: int((values > 0).sum())),
        max_structure_residual=("max_structure_residual", "max"),
    )
    summary["samples"] = summary["cells"] * samples_per_cell
    summary["negative_rate"] = summary["negative"] / summary["samples"]
    summary["complex_rate"] = summary["complex"] / summary["samples"]
    return summary


def _plot_summary(summary: pd.DataFrame, path: Path) -> None:
    ordered = summary.sort_values(
        ["complex_rate", "negative_rate"], ascending=[True, True]
    )
    positions = np.arange(len(ordered))
    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    ax.barh(
        positions,
        ordered["negative_rate"],
        color="#c84630",
        label="negative real weight",
    )
    ax.barh(
        positions,
        ordered["complex_rate"],
        left=ordered["negative_rate"],
        color="#6f52a2",
        label="complex weight",
    )
    ax.set_yticks(positions, ordered.index)
    ax.set_xlim(0.0, 1.02)
    ax.set_xlabel("fraction of sampled products")
    ax.set_title("Structured determinant-weight falsification scan")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right")
    for position, (_, row) in enumerate(ordered.iterrows()):
        fraction = row["negative_rate"] + row["complex_rate"]
        if fraction > 0:
            ax.text(
                min(fraction + 0.012, 0.96),
                position,
                f"{100.0 * fraction:.2f}%",
                va="center",
                fontsize=8,
            )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_report(run_dir: str | Path, *, samples_per_cell: int) -> dict[str, object]:
    run_path = Path(run_dir)
    rows = pd.read_csv(run_path / "parameter-scan.csv")
    summary = summarize_rows(rows, samples_per_cell=samples_per_cell)
    summary.to_csv(run_path / "family-summary.csv")
    _plot_summary(summary, run_path / "family-summary.png")

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
        "environment": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "pandas": importlib.metadata.version("pandas"),
            "matplotlib": importlib.metadata.version("matplotlib"),
        },
        "artifacts": [
            "parameter-scan.csv",
            "family-summary.csv",
            "family-summary.png",
        ],
        "interpretation_limit": (
            "negative or complex samples falsify universal nonnegativity; "
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
