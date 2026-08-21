#!/usr/bin/env python3
"""Vectorized aggregation and central-charge fitting for Haar Slurm batches."""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    from haar_mipt_analysis import (
        double_fit_central_charge,
        l4_stability_fit,
        weighted_l2_fit,
    )
except ImportError:
    from scripts.haar_mipt_analysis import (
        double_fit_central_charge,
        l4_stability_fit,
        weighted_l2_fit,
    )


FAMILIES = ("global_haar", "product")


def _slopes(cumulative: np.ndarray, width: int) -> np.ndarray:
    steps = cumulative.shape[1]
    centered = np.arange(1, steps + 1, dtype=float)
    centered -= centered.mean()
    return cumulative @ centered / (float(width) * np.dot(centered, centered))


def load_batches(run_dir: Path) -> tuple[dict, dict, dict]:
    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    groups = defaultdict(lambda: defaultdict(list))
    curve_sums = {}
    curve_counts = defaultdict(int)
    observed_cells = set()
    for cell in spec["cells"]:
        cell_id = cell["cell_id"]
        cell_dir = run_dir / "cells" / cell_id
        manifest = json.loads((cell_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            raise RuntimeError(f"{cell_id} is not successful")
        width = int(cell["params"]["L"])
        family = str(cell["params"]["initial_family"])
        key = (width, family)
        with np.load(cell_dir / "batch.npz", allow_pickle=False) as data:
            cumulative = np.asarray(data["cumulative_record_cost"], dtype=float)
            slopes = _slopes(cumulative, width)
            endpoints = np.asarray(data["record_cost"], dtype=float) / (
                width * cumulative.shape[1]
            )
            sample_index = np.asarray(data["sample_index"], dtype=np.int32)
            seed = np.asarray(data["seed"], dtype=np.uint64)
            runtime = np.asarray(data["runtime_seconds"], dtype=np.float32)
            if slopes.size != int(manifest["samples_valid"]):
                raise RuntimeError(f"{cell_id} sample count mismatch")
            groups[key]["slope"].append(slopes)
            groups[key]["endpoint"].append(endpoints)
            groups[key]["sample_index"].append(sample_index)
            groups[key]["seed"].append(seed)
            groups[key]["runtime"].append(runtime)
            groups[key]["block_slope_mean"].append(float(slopes.mean()))
            if key not in curve_sums:
                curve_sums[key] = cumulative.sum(axis=0)
            else:
                curve_sums[key] += cumulative.sum(axis=0)
            curve_counts[key] += cumulative.shape[0]
        observed_cells.add(cell_id)
    if len(observed_cells) != len(spec["cells"]):
        raise RuntimeError("not every planned cell was observed")
    packed = {}
    for key, fields in groups.items():
        packed[key] = {
            name: np.concatenate(values) if name != "block_slope_mean" else np.asarray(values)
            for name, values in fields.items()
        }
        expected = int(spec["settings"]["samples_per_family_width"])
        if packed[key]["slope"].size != expected:
            raise RuntimeError(f"{key} has {packed[key]['slope'].size} samples, expected {expected}")
        if np.unique(packed[key]["sample_index"]).size != expected:
            raise RuntimeError(f"{key} has duplicate sample indices")
    curves = {key: curve_sums[key] / curve_counts[key] for key in curve_sums}
    return spec, packed, curves


def width_rows(groups: dict, estimator: str) -> list[dict]:
    rows = []
    for width in sorted({key[0] for key in groups}):
        families = {}
        for family in FAMILIES:
            values = groups[(width, family)][estimator]
            families[family] = {
                "count": int(values.size),
                "mean": float(values.mean()),
                "se": float(values.std(ddof=1) / np.sqrt(values.size)),
            }
        rows.append({
            "L": width,
            "tilde_f": 0.5 * sum(families[f]["mean"] for f in FAMILIES),
            "tilde_f_se": 0.5 * np.sqrt(sum(families[f]["se"] ** 2 for f in FAMILIES)),
            "estimator": estimator,
            "families": families,
        })
    return rows


def block_bootstrap(groups: dict, rows: list[dict], alpha: float, samples: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    errors = {row["L"]: row["tilde_f_se"] for row in rows}
    values = np.empty(samples, dtype=float)
    for draw in range(samples):
        sampled_rows = []
        for width in sorted(errors):
            means = []
            for family in FAMILIES:
                blocks = groups[(width, family)]["block_slope_mean"]
                means.append(float(rng.choice(blocks, size=blocks.size, replace=True).mean()))
            sampled_rows.append({
                "L": width,
                "tilde_f": 0.5 * sum(means),
                "tilde_f_se": errors[width],
            })
        values[draw] = double_fit_central_charge(sampled_rows, alpha=alpha)["central_charge"]
    return values


def write_tables(output: Path, slope_rows: list[dict], endpoint_rows: list[dict]) -> None:
    endpoint = {row["L"]: row for row in endpoint_rows}
    with (output / "width_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "L", "slope_mean", "slope_se", "endpoint_mean", "endpoint_se",
            "global_haar_slope_mean", "global_haar_slope_se",
            "product_slope_mean", "product_slope_se", "samples_per_family",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in slope_rows:
            other = endpoint[row["L"]]
            writer.writerow({
                "L": row["L"],
                "slope_mean": row["tilde_f"],
                "slope_se": row["tilde_f_se"],
                "endpoint_mean": other["tilde_f"],
                "endpoint_se": other["tilde_f_se"],
                "global_haar_slope_mean": row["families"]["global_haar"]["mean"],
                "global_haar_slope_se": row["families"]["global_haar"]["se"],
                "product_slope_mean": row["families"]["product"]["mean"],
                "product_slope_se": row["families"]["product"]["se"],
                "samples_per_family": row["families"]["global_haar"]["count"],
            })


def write_trajectory_npz(output: Path, groups: dict) -> None:
    arrays = {}
    for (width, family), data in sorted(groups.items()):
        prefix = f"L{width}_{family}"
        for name in ("sample_index", "seed", "slope", "endpoint", "runtime"):
            arrays[f"{prefix}_{name}"] = data[name]
    np.savez_compressed(output / "trajectory_estimators.npz", **arrays)


def _italic_axis(axis) -> None:
    axis.xaxis.label.set_fontstyle("italic")
    axis.yaxis.label.set_fontstyle("italic")
    axis.title.set_fontstyle("italic")
    for label in axis.get_xticklabels() + axis.get_yticklabels():
        label.set_fontstyle("italic")
    legend = axis.get_legend()
    if legend:
        for label in legend.get_texts():
            label.set_fontstyle("italic")


def plot_fit(output: Path, rows: list[dict], primary: dict) -> None:
    x = np.asarray([1.0 / row["L"] ** 2 for row in rows])
    y = np.asarray([row["tilde_f"] for row in rows])
    error = np.asarray([row["tilde_f_se"] for row in rows])
    fit = weighted_l2_fit(rows, lmin=8)
    line_x = np.linspace(0.0, 1.05 * x.max(), 300)
    fig, axis = plt.subplots(figsize=(6.5, 4.7))
    axis.errorbar(x, y, yerr=error, fmt="o", markersize=10, alpha=0.78, capsize=3,
                  label="equal-family trajectory slope")
    axis.plot(line_x, fit["intercept"] + fit["slope"] * line_x,
              color="red", linestyle="-", linewidth=1.8, label="weighted Lmin=8 fit")
    axis.set_xlabel("1/L²")
    axis.set_ylabel("f̃(L)")
    axis.set_title(f"Haar MIPT finite-size fit, c_eff={primary['central_charge']:.4f}")
    axis.legend(frameon=False)
    _italic_axis(axis)
    fig.tight_layout()
    fig.savefig(output / "central_charge_fit.png", dpi=200)
    plt.close(fig)


def plot_windows(output: Path, primary: dict, alpha: float) -> None:
    windows = primary["windows"]
    x = np.asarray([1.0 / fit["lmin"] ** 2 for fit in windows])
    y = np.asarray([fit["slope"] for fit in windows])
    line_x = np.linspace(0.0, 1.05 * x.max(), 300)
    line_y = primary["m0_inf"] + primary["slope_correction"] * line_x
    fig, axis = plt.subplots(figsize=(6.5, 4.7))
    axis.scatter(x, y, s=72, alpha=0.78, label="window slopes")
    axis.plot(line_x, line_y, color="red", linestyle="-", linewidth=1.8,
              label="linear extrapolation")
    axis.set_xlabel("1/Lmin²")
    axis.set_ylabel("m(Lmin)")
    axis.set_title(f"Slope extrapolation, α={alpha:g}")
    axis.legend(frameon=False)
    _italic_axis(axis)
    fig.tight_layout()
    fig.savefig(output / "window_slope_extrapolation.png", dpi=200)
    plt.close(fig)


def plot_growth(output: Path, curves: dict) -> None:
    fig, axis = plt.subplots(figsize=(6.5, 4.7))
    for width in sorted({key[0] for key in curves}):
        curve = 0.5 * (curves[(width, "global_haar")] + curves[(width, "product")])
        times = np.arange(1, curve.size + 1, dtype=float)
        axis.plot(times, curve / (width * times), label=f"L={width}")
    axis.set_xlabel("recorded half-layer t")
    axis.set_ylabel("⟨C(t)⟩/(Lt)")
    axis.set_title("Measurement-record entropy density")
    axis.legend(frameon=False, ncol=2)
    _italic_axis(axis)
    fig.tight_layout()
    fig.savefig(output / "record_entropy_growth.png", dpi=200)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--alpha", type=float, default=0.81)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=122170)
    args = parser.parse_args()
    output = args.output or args.run_dir / "analysis"
    output.mkdir(parents=True, exist_ok=True)

    spec, groups, curves = load_batches(args.run_dir)
    slope_rows = width_rows(groups, "slope")
    endpoint_rows = width_rows(groups, "endpoint")
    primary = double_fit_central_charge(slope_rows, alpha=args.alpha)
    stability = l4_stability_fit(slope_rows, alpha=args.alpha)
    endpoint_fit = double_fit_central_charge(endpoint_rows, alpha=args.alpha)
    bootstrap = block_bootstrap(groups, slope_rows, args.alpha, args.bootstrap, args.seed)
    summary = {
        "run_id": spec["run_id"],
        "p": spec["settings"]["p"],
        "alpha": args.alpha,
        "planned_cells": len(spec["cells"]),
        "samples_total": int(sum(data["slope"].size for data in groups.values())),
        "samples_per_family_width": spec["settings"]["samples_per_family_width"],
        "central_charge": primary["central_charge"],
        "m0_inf": primary["m0_inf"],
        "windows": primary["windows"],
        "block_bootstrap_samples": args.bootstrap,
        "block_bootstrap_se": float(bootstrap.std(ddof=1)),
        "block_bootstrap_percentile_95": np.percentile(bootstrap, [2.5, 97.5]).tolist(),
        "l4_stability_central_charge": stability["central_charge"],
        "endpoint_diagnostic_central_charge": endpoint_fit["central_charge"],
    }
    (output / "fit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_tables(output, slope_rows, endpoint_rows)
    write_trajectory_npz(output, groups)
    np.save(output / "central_charge_block_bootstrap.npy", bootstrap)
    plot_fit(output, slope_rows, primary)
    plot_windows(output, primary, args.alpha)
    plot_growth(output, curves)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
