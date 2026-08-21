# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Build a measured Challenge 148 Stage 5 cost and error model."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

NU = 0.629971


def parse_values(text: str):
    values = [int(value.strip()) for value in text.split(",") if value.strip()]
    if not values or len(set(values)) != len(values) or min(values) < 2:
        raise ValueError("future sizes must be unique integers greater than one")
    return values


def fit_wall_model(rows):
    grouped = defaultdict(list)
    for size, wall in rows:
        if size < 2 or not np.isfinite(wall) or wall <= 0.0:
            raise ValueError("wall-time rows must contain L >= 2 and positive times")
        grouped[int(size)].append(float(wall))
    if len(grouped) < 2:
        raise ValueError("wall-time model needs at least two sizes")
    sizes = np.asarray(sorted(grouped), dtype=float)
    medians = np.asarray([np.median(grouped[int(size)]) for size in sizes])
    exponent, intercept = np.polyfit(np.log(sizes), np.log(medians), 1)
    return sizes, medians, float(np.exp(intercept)), float(exponent)


def read_manifests(run_dir: Path):
    rows = []
    for path in sorted((run_dir / "cells").glob("*/manifest.json")):
        manifest = json.loads(path.read_text())
        if manifest.get("status") != "success":
            raise ValueError(f"non-success manifest in cost model: {path}")
        rows.append((
            int(manifest["params"]["L"]), float(manifest["wall_seconds"])
        ))
    if not rows:
        raise ValueError(f"no successful manifests under {run_dir}")
    return rows


def read_fit_error(path: Path, observable: str):
    with path.open(newline="") as handle:
        matches = [row for row in csv.DictReader(handle)
                   if row["observable"] == observable]
    if len(matches) != 1:
        raise ValueError(f"expected one {observable} row in {path}")
    error = float(matches[0]["hc_boot_err"])
    if not np.isfinite(error) or error <= 0.0:
        raise ValueError("fit error must be positive")
    return error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--fit-csv", type=Path, required=True)
    parser.add_argument("--observable", choices=("Q", "xi"), default="xi")
    parser.add_argument("--target-error", type=float, required=True)
    parser.add_argument("--future-sizes", required=True)
    parser.add_argument("--field-count", type=int, required=True)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    if (not np.isfinite(args.target_error) or args.target_error <= 0.0
            or min(args.field_count, args.chains, args.workers) <= 0):
        parser.error("target error and count arguments must be positive")

    future_sizes = parse_values(args.future_sizes)
    wall_rows = read_manifests(args.run_dir)
    sizes, medians, coefficient, exponent = fit_wall_model(wall_rows)
    fit_error = read_fit_error(args.fit_csv, args.observable)
    current_aggregate = float(sum(wall for _, wall in wall_rows))
    naive_multiplier = (fit_error / args.target_error) ** 2
    current_max = float(max(size for size, _ in wall_rows))
    future_max = float(max(future_sizes))
    slope_gain = (future_max / current_max) ** (1.0 / NU)
    optimistic_multiplier = naive_multiplier / slope_gain**2
    future_cell_seconds = coefficient * np.asarray(future_sizes) ** exponent
    future_pilot_aggregate = float(
        args.field_count * args.chains * np.sum(future_cell_seconds)
    )
    production_aggregate = future_pilot_aggregate * optimistic_multiplier

    output = {
        "schema_version": "challenge148-cost-model-v1",
        "run_dir": str(args.run_dir),
        "fit_csv": str(args.fit_csv),
        "observable": args.observable,
        "measured_hc_error": fit_error,
        "target_hc_error": args.target_error,
        "measured_cells": len(wall_rows),
        "measured_aggregate_seconds": current_aggregate,
        "wall_model": {
            "form": "median cell wall_seconds = coefficient * L^exponent",
            "coefficient": coefficient,
            "exponent": exponent,
        },
        "future_grid": {
            "sizes": future_sizes,
            "field_count": args.field_count,
            "chains_per_point": args.chains,
            "workers": args.workers,
            "same_statistics_pilot_aggregate_seconds": future_pilot_aggregate,
            "ideal_pilot_wall_seconds": future_pilot_aggregate / args.workers,
        },
        "error_model": {
            "statistics_only_multiplier_at_current_sizes": naive_multiplier,
            "assumed_critical_slope": "dO/dh proportional to L^(1/nu)",
            "nu": NU,
            "future_to_current_slope_gain": slope_gain,
            "optimistic_statistics_multiplier_at_future_max_L": optimistic_multiplier,
            "optimistic_production_aggregate_seconds": production_aggregate,
            "optimistic_ideal_wall_seconds": production_aggregate / args.workers,
        },
        "limitations": [
            "The optimistic model assumes independent samples and no worsening autocorrelation.",
            "It excludes robustness failures, finite-size bias, c_tau resolution, queueing, and I/O.",
            "It is a lower-bound planning model, not evidence that the precision gate will pass.",
        ],
    }
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = args.output_prefix.with_name(args.output_prefix.name + "_cost_model.json")
    json_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    csv_path = args.output_prefix.with_name(args.output_prefix.name + "_wall_by_size.csv")
    with csv_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["L", "median_wall_seconds", "model_wall_seconds"])
        for size, median in zip(sizes, medians):
            writer.writerow([int(size), median, coefficient * size**exponent])

    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    dense = np.linspace(min(sizes), max(max(sizes), future_max), 200)
    axes[0].loglog(sizes, medians, "o", label="measured median")
    axes[0].loglog(
        dense, coefficient * dense**exponent, "-",
        label=f"fit L^{exponent:.2f}",
    )
    axes[0].set(xlabel="linear size L", ylabel="cell wall time (s)")
    axes[0].legend()
    axes[1].bar(
        ["same-statistics\npilot", "optimistic\nproduction"],
        [future_pilot_aggregate / args.workers / 3600.0,
         production_aggregate / args.workers / 3600.0],
    )
    axes[1].set(ylabel=f"ideal wall time on {args.workers} workers (h)")
    figure.savefig(
        args.output_prefix.with_name(args.output_prefix.name + "_cost_model.png"),
        dpi=180,
    )
    plt.close(figure)
    print(
        f"wall_model=L^{exponent:.3f} naive_multiplier={naive_multiplier:.3g} "
        f"optimistic_multiplier={optimistic_multiplier:.3g}"
    )
    print(f"outputs={json_path},{csv_path}")


if __name__ == "__main__":
    main()
