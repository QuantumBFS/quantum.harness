#!/usr/bin/env python3
"""Analyze the issue-119 BP-TN G5 active feasibility pilot."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Iterable


SAFETY_FACTOR = 1.2


def _mean_se(values: list[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("cannot summarize an empty sample")
    mean = statistics.fmean(values)
    se = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return mean, se


def _paired_drift(records: list[dict], low: int, high: int) -> dict:
    by_chi = {
        chi: {
            int(record["params"]["seed"]): float(record["result"]["sample_value"])
            for record in records
            if record.get("status") == "success"
            and int(record["params"]["chi"]) == chi
            and str(record["params"]["delta"]) == "0.15"
        }
        for chi in (low, high)
    }
    common = sorted(set(by_chi[low]) & set(by_chi[high]))
    differences = [by_chi[high][seed] - by_chi[low][seed] for seed in common]
    if not differences:
        return {"n": 0, "mean": math.nan, "se": math.nan, "max_abs": math.nan}
    mean, se = _mean_se(differences)
    return {
        "n": len(differences),
        "mean": mean,
        "se": se,
        "max_abs": max(abs(value) for value in differences),
    }


def _fit_monotone_power_law(points: dict[int, float]) -> dict:
    if len(points) < 2 or any(value <= 0 for value in points.values()):
        raise ValueError("power-law resource fit needs at least two positive points")
    xs = [math.log(float(chi)) for chi in sorted(points)]
    ys = [math.log(float(points[chi])) for chi in sorted(points)]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    exponent = (
        sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
        / denominator
    )
    exponent = max(0.0, exponent)
    log_prefactor = y_mean - exponent * x_mean
    return {
        "prefactor": math.exp(log_prefactor),
        "exponent": exponent,
        "safety_factor": SAFETY_FACTOR,
    }


def _predict_resource(fit: dict, chi: int, observed_max: float) -> float:
    fitted = float(fit["prefactor"]) * float(chi) ** float(fit["exponent"])
    return SAFETY_FACTOR * max(fitted, observed_max)


def assess_g5(
    records: list[dict],
    *,
    expected_seeds: Iterable[int],
    observed_chis: Iterable[int],
    target_chis: Iterable[int],
    node_memory_bytes: int,
    wall_cap_seconds: float,
) -> dict:
    expected_seeds = tuple(int(seed) for seed in expected_seeds)
    observed_chis = tuple(int(chi) for chi in observed_chis)
    target_chis = tuple(int(chi) for chi in target_chis)
    expected_cells = {
        (chi, seed, "0.15")
        for chi in observed_chis
        for seed in expected_seeds
    }
    successful_records = [
        record
        for record in records
        if record.get("status") == "success"
        and str(record["params"].get("delta")) == "0.15"
    ]
    successful_cells = [
        (
            int(record["params"]["chi"]),
            int(record["params"]["seed"]),
            str(record["params"]["delta"]),
        )
        for record in successful_records
    ]
    complete_grid = (
        set(successful_cells) == expected_cells
        and len(successful_cells) == len(expected_cells)
    )

    per_chi: dict[str, dict] = {}
    max_wall_by_chi: dict[int, float] = {}
    max_rss_by_chi: dict[int, float] = {}
    for chi in observed_chis:
        group = [
            record
            for record in successful_records
            if int(record["params"]["chi"]) == chi
        ]
        if not group:
            continue
        values = [float(record["result"]["sample_value"]) for record in group]
        walls = [float(record["result"]["wall_seconds"]) for record in group]
        rss = [float(record["result"]["peak_rss_bytes"]) for record in group]
        mean_value, sample_se = _mean_se(values)
        max_wall_by_chi[chi] = max(walls)
        max_rss_by_chi[chi] = max(rss)
        per_chi[str(chi)] = {
            "n": len(group),
            "mean_sample_value": mean_value,
            "sample_se": sample_se,
            "mean_wall_seconds": statistics.fmean(walls),
            "max_wall_seconds": max(walls),
            "mean_peak_rss_bytes": statistics.fmean(rss),
            "max_peak_rss_bytes": max(rss),
            "max_layer_wall_seconds": max(
                float(record["result"]["max_layer_wall_seconds"])
                for record in group
                if record["result"].get("max_layer_wall_seconds") is not None
            ),
            "max_virtual_bond_dimension": max(
                int(record["result"]["max_virtual_bond_dimension"])
                for record in group
                if record["result"].get("max_virtual_bond_dimension") is not None
            ),
            "max_truncation_error": max(
                float(record["result"]["max_truncation_error"])
                for record in group
            ),
            "max_bp_residual": max(
                float(record["result"]["max_bp_residual"])
                for record in group
            ),
            "bp_nonconverged_layers": sum(
                int(record["result"]["bp_nonconverged_layers"])
                for record in group
            ),
        }

    fits = {}
    predictions = {}
    resource_fit_status = "withheld_incomplete_grid"
    if (
        complete_grid
        and len(max_wall_by_chi) >= 2
        and len(max_rss_by_chi) >= 2
    ):
        resource_fit_status = "complete_grid_empirical_fit"
        fits = {
            "wall_seconds": _fit_monotone_power_law(max_wall_by_chi),
            "peak_rss_bytes": _fit_monotone_power_law(max_rss_by_chi),
        }
        observed_max_wall = max(max_wall_by_chi.values())
        observed_max_rss = max(max_rss_by_chi.values())
        for chi in target_chis:
            predictions[str(chi)] = {
                "wall_seconds": _predict_resource(
                    fits["wall_seconds"],
                    chi,
                    observed_max_wall,
                ),
                "peak_rss_bytes": _predict_resource(
                    fits["peak_rss_bytes"],
                    chi,
                    observed_max_rss,
                ),
            }

    drift_64_128 = _paired_drift(successful_records, 64, 128)
    drift_128_192 = _paired_drift(successful_records, 128, 192)
    drift_threshold = max(
        2 * abs(drift_64_128["mean"])
        if math.isfinite(drift_64_128["mean"])
        else 0.0,
        3 * drift_128_192["se"]
        if math.isfinite(drift_128_192["se"])
        else 0.0,
        1e-3,
    )
    paired_drift_stable = (
        drift_128_192["n"] == len(expected_seeds)
        and math.isfinite(drift_128_192["mean"])
        and abs(drift_128_192["mean"]) <= drift_threshold
    )

    finite_and_bounded = bool(successful_records) and all(
        math.isfinite(float(record["result"]["sample_value"]))
        and abs(float(record["result"]["sample_value"])) <= 1.0 + 1e-6
        and math.isfinite(float(record["result"]["wall_seconds"]))
        and float(record["result"]["wall_seconds"]) > 0
        and math.isfinite(float(record["result"]["peak_rss_bytes"]))
        and float(record["result"]["peak_rss_bytes"]) > 0
        for record in successful_records
    )
    bp_stable = bool(successful_records) and all(
        int(record["result"]["bp_nonconverged_layers"]) == 0
        and float(record["result"]["max_bp_residual"])
        <= float(record["settings"]["bp_tolerance"])
        for record in successful_records
    )
    cell_ids = [record.get("cell_id") for record in records]
    array_recoverable = (
        all(cell_ids)
        and len(cell_ids) == len(set(cell_ids))
        and all(
            {"chi", "seed", "delta"} <= set(record.get("params", {}))
            for record in records
        )
    )

    available_norm_defects = [
        float(record["result"]["max_norm_defect"])
        for record in successful_records
        if record["result"].get("max_norm_defect") is not None
    ]
    if available_norm_defects:
        norm_status = "available"
    elif successful_records and all(
        bool(record.get("settings", {}).get("normalize_tensors"))
        for record in successful_records
    ):
        norm_status = "unavailable_by_normalization"
    else:
        norm_status = "unavailable_unexpectedly"

    highest_target = str(max(target_chis))
    memory_limit = 0.8 * float(node_memory_bytes)
    wall_limit = 0.7 * float(wall_cap_seconds)
    memory_feasible = (
        highest_target in predictions
        and predictions[highest_target]["peak_rss_bytes"] <= memory_limit
    )
    wall_feasible = (
        highest_target in predictions
        and predictions[highest_target]["wall_seconds"] <= wall_limit
    )
    checks = {
        "complete_grid": complete_grid,
        "finite_and_bounded": finite_and_bounded,
        "bp_stable": bp_stable,
        "paired_drift_stable": paired_drift_stable,
        "memory_feasible": memory_feasible,
        "wall_feasible": wall_feasible,
        "array_recoverable": array_recoverable,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "protocol": {
            "expected_seeds": list(expected_seeds),
            "observed_chis": list(observed_chis),
            "target_chis": list(target_chis),
            "expected_cells": len(expected_cells),
            "successful_cells": len(successful_records),
        },
        "per_chi": per_chi,
        "paired_drift": {
            "64_to_128": drift_64_128,
            "128_to_192": drift_128_192,
            "stability_threshold": drift_threshold,
        },
        "resource_fit_status": resource_fit_status,
        "resource_fits": fits,
        "predictions": predictions,
        "resource_limits": {
            "node_memory_bytes": int(node_memory_bytes),
            "memory_gate_bytes": memory_limit,
            "wall_cap_seconds": float(wall_cap_seconds),
            "wall_gate_seconds": wall_limit,
        },
        "diagnostics": {
            "norm": norm_status,
            "max_norm_defect": (
                max(available_norm_defects) if available_norm_defects else None
            ),
        },
        "gate": {
            "go": not failed_checks,
            "checks": checks,
            "failed_checks": failed_checks,
        },
    }


def write_g5_outputs(assessment: dict, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "g5-assessment.json"
    csv_path = output_dir / "g5-summary.csv"
    plot_path = output_dir / "g5-resource-fit.png"
    json_path.write_text(
        json.dumps(assessment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "kind",
                "chi",
                "n",
                "mean_sample_value",
                "sample_se",
                "max_wall_seconds",
                "max_peak_rss_bytes",
            ],
        )
        writer.writeheader()
        for chi, summary in sorted(
            assessment["per_chi"].items(),
            key=lambda item: int(item[0]),
        ):
            writer.writerow(
                {
                    "kind": "observed",
                    "chi": chi,
                    "n": summary["n"],
                    "mean_sample_value": summary["mean_sample_value"],
                    "sample_se": summary["sample_se"],
                    "max_wall_seconds": summary["max_wall_seconds"],
                    "max_peak_rss_bytes": summary["max_peak_rss_bytes"],
                }
            )
        for chi, prediction in sorted(
            assessment["predictions"].items(),
            key=lambda item: int(item[0]),
        ):
            writer.writerow(
                {
                    "kind": "predicted",
                    "chi": chi,
                    "n": "",
                    "mean_sample_value": "",
                    "sample_se": "",
                    "max_wall_seconds": prediction["wall_seconds"],
                    "max_peak_rss_bytes": prediction["peak_rss_bytes"],
                }
            )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    observed_chis = sorted(int(chi) for chi in assessment["per_chi"])
    predicted_chis = sorted(int(chi) for chi in assessment["predictions"])
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    axes[0].plot(
        observed_chis,
        [
            assessment["per_chi"][str(chi)]["max_wall_seconds"] / 60
            for chi in observed_chis
        ],
        "o-",
        label="observed maximum (successful cells)",
    )
    if predicted_chis:
        axes[0].plot(
            predicted_chis,
            [
                assessment["predictions"][str(chi)]["wall_seconds"] / 60
                for chi in predicted_chis
            ],
            "s--",
            label="1.2× empirical fit",
        )
    axes[0].axhline(
        assessment["resource_limits"]["wall_gate_seconds"] / 60,
        color="tab:red",
        linestyle=":",
        label="70% wall cap",
    )
    axes[0].set(xlabel="BP-TN bond dimension χ", ylabel="wall time (min)")
    axes[0].set_yscale("log")
    for chi in observed_chis:
        summary = assessment["per_chi"][str(chi)]
        axes[0].annotate(
            f"n={summary['n']}",
            (chi, summary["max_wall_seconds"] / 60),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    axes[0].legend(fontsize=8)

    axes[1].plot(
        observed_chis,
        [
            assessment["per_chi"][str(chi)]["max_peak_rss_bytes"] / 1024**3
            for chi in observed_chis
        ],
        "o-",
        label="observed maximum (successful cells)",
    )
    if predicted_chis:
        axes[1].plot(
            predicted_chis,
            [
                assessment["predictions"][str(chi)]["peak_rss_bytes"] / 1024**3
                for chi in predicted_chis
            ],
            "s--",
            label="1.2× empirical fit",
        )
    axes[1].axhline(
        assessment["resource_limits"]["memory_gate_bytes"] / 1024**3,
        color="tab:red",
        linestyle=":",
        label="80% node memory",
    )
    axes[1].set(xlabel="BP-TN bond dimension χ", ylabel="peak RSS (GiB)")
    axes[1].set_yscale("log")
    for chi in observed_chis:
        summary = assessment["per_chi"][str(chi)]
        axes[1].annotate(
            f"n={summary['n']}",
            (chi, summary["max_peak_rss_bytes"] / 1024**3),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    axes[1].legend(fontsize=8)
    figure.suptitle(
        "49×1296 BP-TN G5 resource gate: "
        + ("GO" if assessment["gate"]["go"] else "NO-GO")
        + (
            ""
            if assessment["resource_fit_status"] == "complete_grid_empirical_fit"
            else " (incomplete grid; fit withheld)"
        )
    )
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)
    return {"json": json_path, "csv": csv_path, "plot": plot_path}


def load_run_records(run_dir: Path) -> list[dict]:
    records = []
    for manifest_path in sorted((run_dir / "cells").glob("*/manifest.json")):
        records.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--node-memory-mib", type=int, default=1_500_000)
    parser.add_argument("--wall-cap-hours", type=float, default=24.0)
    args = parser.parse_args()
    records = load_run_records(args.run_dir)
    assessment = assess_g5(
        records,
        expected_seeds=range(1, 21),
        observed_chis=(64, 128, 192),
        target_chis=(256, 384, 512),
        node_memory_bytes=args.node_memory_mib * 1024**2,
        wall_cap_seconds=args.wall_cap_hours * 3600,
    )
    outputs = write_g5_outputs(assessment, args.output_dir or args.run_dir)
    print(f"gate_go={str(assessment['gate']['go']).lower()}", flush=True)
    print(
        "failed_checks=" + ",".join(assessment["gate"]["failed_checks"]),
        flush=True,
    )
    for name, path in outputs.items():
        print(f"{name}={path}", flush=True)


if __name__ == "__main__":
    main()
