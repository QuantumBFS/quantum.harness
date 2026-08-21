# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fine-grid two-size crossing diagnostic for Challenge 148 direct SSE."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import analyze_stage4 as stage4


def load_size(path: Path, n_boot: int, seed: int):
    chains, metadata = stage4.load_bins(path)
    cells = stage4.grouped_cells(chains)
    sizes = sorted({L for L, _ in cells})
    if len(sizes) != 1:
        raise ValueError(f"{path} must contain one size, found {sizes}")
    points, autocorrelation = stage4.point_estimates(
        cells, metadata, n_boot, np.random.default_rng(seed)
    )
    sampling, failures = stage4.sampling_diagnostics(cells)
    return {
        "L": sizes[0],
        "cells": cells,
        "metadata": metadata,
        "points": points,
        "autocorrelation": autocorrelation,
        "sampling": sampling,
        "sampling_failures": failures,
    }


def estimate(observable, sampled, key, metadata):
    if observable == "Q":
        return stage4.q_value(sampled)
    return stage4.xi_value(sampled, key[0], metadata[key]["q_norm"])


def crossing_bootstrap(observable, fields, datasets, n_boot: int, seed: int):
    curves = {
        data["L"]: np.asarray([
            data["points"][(data["L"], float(h))][observable]
            for h in fields
        ])
        for data in datasets
    }
    sizes = sorted(curves)
    crossing = stage4.crossing(fields, curves[sizes[0]], curves[sizes[1]])
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(n_boot):
        sampled_curves = {}
        for data in datasets:
            size = data["L"]
            values = []
            for h in fields:
                key = (size, float(h))
                sampled = stage4.resample_cell(
                    data["cells"][key], data["points"][key]["block"], rng
                )
                values.append(estimate(
                    observable, sampled, key, data["metadata"]
                ))
            sampled_curves[size] = np.asarray(values)
        root = stage4.crossing(
            fields, sampled_curves[sizes[0]], sampled_curves[sizes[1]]
        )
        if np.isfinite(root):
            samples.append(root)
    samples = np.asarray(samples)
    if len(samples) < 2:
        raise ValueError(f"{observable} bootstrap produced fewer than two roots")
    return {
        "crossing": float(crossing),
        "conditional_bootstrap_error": float(samples.std(ddof=1)),
        "conditional_ci95_low": float(np.quantile(samples, 0.025)),
        "conditional_ci95_high": float(np.quantile(samples, 0.975)),
        "bootstrap_success": int(len(samples)),
        "bootstrap_failed_no_unique_root": int(n_boot - len(samples)),
        "bootstrap_failure_rate": float(1.0 - len(samples) / n_boot),
    }


def write_outputs(prefix: Path, datasets, fields, crossings):
    prefix.parent.mkdir(parents=True, exist_ok=True)
    points_path = prefix.with_name(prefix.name + "_points.csv")
    with points_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "L", "h", "Q", "Q_err", "xi_over_L", "xi_err",
            "block_bins", "block_sweeps", "chains",
        ])
        for data in datasets:
            for (L, h), point in sorted(data["points"].items()):
                writer.writerow([
                    L, h, point["Q"], point["Q_err"], point["xi"],
                    point["xi_err"], point["block"], point["block_sweeps"],
                    point["chains"],
                ])

    sampling_path = prefix.with_name(prefix.name + "_sampling_gates.csv")
    with sampling_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "L", "h", "hot_chains", "cold_chains",
            "minimum_independent_blocks", "hot_cold_z_max",
            "stationarity_z_max", "bin_growth_z_max",
            "bin_error_ratio_max", "chain_spread_z_max", "passed",
        ])
        for data in datasets:
            writer.writerows(data["sampling"])

    autocorrelation_path = prefix.with_name(prefix.name + "_autocorrelation.csv")
    with autocorrelation_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "L", "h", "initial_state", "seed", "tau_m2", "tau_m4",
            "tau_S0", "tau_Sq", "tau_E", "tau_max_bins",
            "tau_max_sweeps", "effective_samples", "independent_blocks",
        ])
        for data in datasets:
            writer.writerows(data["autocorrelation"])

    crossings_path = prefix.with_name(prefix.name + "_crossings.csv")
    with crossings_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "observable", "L_first", "L_second", "crossing",
                "conditional_bootstrap_error", "conditional_ci95_low",
                "conditional_ci95_high", "bootstrap_success",
                "bootstrap_failed_no_unique_root", "bootstrap_failure_rate",
            ],
        )
        writer.writeheader()
        sizes = sorted(data["L"] for data in datasets)
        for observable in ("Q", "xi"):
            writer.writerow({
                "observable": observable,
                "L_first": sizes[0],
                "L_second": sizes[1],
                **crossings[observable],
            })

    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for observable, error_key, ylabel, axis in (
        ("Q", "Q_err", "Q", axes[0]),
        ("xi", "xi_err", r"$\xi/L$", axes[1]),
    ):
        for data in datasets:
            size = data["L"]
            values = np.asarray([
                data["points"][(size, float(h))][observable] for h in fields
            ])
            errors = np.asarray([
                data["points"][(size, float(h))][error_key] for h in fields
            ])
            axis.errorbar(fields, values, yerr=errors, marker="o", capsize=2, label=f"L={size}")
        axis.axvline(
            crossings[observable]["crossing"], color="black",
            linestyle="--", linewidth=1,
        )
        axis.set_xlabel("h/J")
        axis.set_ylabel(ylabel)
        axis.legend()
    plot_path = prefix.with_name(prefix.name + "_curves.png")
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)

    return [points_path, sampling_path, autocorrelation_path, crossings_path, plot_path]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("first_bins", type=Path)
    parser.add_argument("second_bins", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260729)
    args = parser.parse_args()
    if args.bootstrap < 2:
        parser.error("--bootstrap must be at least 2")

    datasets = [
        load_size(args.first_bins, 1000, args.seed),
        load_size(args.second_bins, 1000, args.seed + 1),
    ]
    datasets.sort(key=lambda data: data["L"])
    if datasets[0]["L"] == datasets[1]["L"]:
        raise ValueError("inputs must contain different sizes")
    identities = {
        (
            next(iter(data["metadata"].values()))["lattice"],
            next(iter(data["metadata"].values()))["geometry_version"],
            next(iter(data["metadata"].values()))["c_tau"],
        )
        for data in datasets
    }
    if len(identities) != 1:
        raise ValueError("inputs do not share lattice, geometry, and c_tau")
    field_sets = [
        {h for L, h in data["points"] if L == data["L"]} for data in datasets
    ]
    if field_sets[0] != field_sets[1]:
        raise ValueError("inputs do not share the same field grid")
    fields = np.asarray(sorted(field_sets[0]))
    crossings = {
        observable: crossing_bootstrap(
            observable, fields, datasets, args.bootstrap,
            args.seed + 100 + index,
        )
        for index, observable in enumerate(("Q", "xi"))
    }
    artifacts = write_outputs(args.output_prefix, datasets, fields, crossings)
    failures = sum(
        (data["sampling_failures"] for data in datasets), start=[]
    )
    print(json.dumps({
        "lattice_identity": list(next(iter(identities))),
        "sizes": [data["L"] for data in datasets],
        "fields": fields.tolist(),
        "sampling_passed": not failures,
        "crossings": crossings,
        "artifacts": [str(path) for path in artifacts],
    }, indent=2, sort_keys=True))
    if failures:
        raise ValueError("sampling gates failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
