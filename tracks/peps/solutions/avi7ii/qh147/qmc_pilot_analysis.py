"""Acceptance diagnostics and Trotter extrapolation for the equilibrated QMC pilot."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np

from .qmc_analysis import trotter_extrapolate


M_VALUES = (32, 64, 128)
CHAINS = (0, 1, 2, 3)
BLOCK_BINS = 8
SPLIT_Z_MAX = 3.0
RHAT_MAX = 1.05
REDUCED_CHI2_MAX = 4.0


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _block_means(values: np.ndarray, width: int = BLOCK_BINS) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2 * width or len(values) % width:
        raise ValueError("chain bins must form at least two complete blocks")
    if not np.isfinite(values).all():
        raise ValueError("chain bins must be finite")
    return values.reshape(-1, width).mean(axis=1)


def _lag_one(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    left = values[:-1] - np.mean(values[:-1])
    right = values[1:] - np.mean(values[1:])
    denominator = float(np.sqrt(np.sum(left**2) * np.sum(right**2)))
    return float(np.sum(left * right) / denominator) if denominator else 0.0


def _split_half_z(blocks: np.ndarray) -> tuple[float, float]:
    midpoint = len(blocks) // 2
    first = blocks[:midpoint]
    second = blocks[midpoint:]
    difference = float(np.mean(second) - np.mean(first))
    variance = float(
        np.var(first, ddof=1) / len(first)
        + np.var(second, ddof=1) / len(second)
    )
    if variance == 0.0:
        return difference, 0.0 if difference == 0.0 else float("inf")
    return difference, abs(difference) / np.sqrt(variance)


def _rhat(chain_blocks: np.ndarray) -> float:
    chain_blocks = np.asarray(chain_blocks, dtype=float)
    if chain_blocks.ndim != 2 or chain_blocks.shape[0] != len(CHAINS):
        raise ValueError("R-hat requires four chains of block means")
    samples = chain_blocks.shape[1]
    within = float(np.mean(np.var(chain_blocks, axis=1, ddof=1)))
    between = float(samples * np.var(np.mean(chain_blocks, axis=1), ddof=1))
    if within == 0.0:
        return 1.0 if between == 0.0 else float("inf")
    variance = ((samples - 1) * within + between) / samples
    return float(max(1.0, np.sqrt(variance / within)))


def _load_run(run_dir: Path) -> tuple[float, np.ndarray, np.ndarray, dict[int, int]]:
    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    cells = spec.get("cells", [])
    expected_pairs = {(m, chain) for m in M_VALUES for chain in CHAINS}
    actual_pairs = {
        (int(cell["params"]["M"]), int(cell["params"]["chain"]))
        for cell in cells
    }
    if len(cells) != 12 or actual_pairs != expected_pairs:
        raise ValueError("run spec must contain the complete M-by-chain pilot")
    betas = {float(cell["params"]["beta"]) for cell in cells}
    fields = {float(cell["params"]["h"]) for cell in cells}
    if betas != {0.5} or fields != {3.0}:
        raise ValueError("equilibrated pilot must use beta=0.5 and h=3")

    planned_ids = {cell["cell_id"] for cell in cells}
    observed_ids = {
        path.parent.name for path in (run_dir / "cells").glob("*/manifest.json")
    }
    if observed_ids != planned_ids:
        raise ValueError("observed QMC cells do not exactly match the run spec")

    arrays: dict[tuple[int, int], np.ndarray] = {}
    thermal: dict[int, int] = {}
    for cell in cells:
        params = cell["params"]
        m_value = int(params["M"])
        chain = int(params["chain"])
        expected_settings = {**spec.get("settings", {}), **cell.get("settings", {})}
        root = run_dir / "cells" / cell["cell_id"]
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            raise ValueError(f"{cell['cell_id']} is not successful")
        if manifest.get("params") != params:
            raise ValueError(f"{cell['cell_id']} parameter echo mismatch")
        if manifest.get("settings") != expected_settings:
            raise ValueError(f"{cell['cell_id']} settings echo mismatch")
        if manifest.get("provenance") != spec.get("provenance", {}):
            raise ValueError(f"{cell['cell_id']} provenance mismatch")
        runtime = manifest.get("runtime_settings", {})
        expected_thermal = int(expected_settings["thermal_sweeps"])
        if int(runtime.get("thermal_sweeps", -1)) != expected_thermal:
            raise ValueError(f"{cell['cell_id']} runtime thermalization mismatch")
        expected_measurement = int(expected_settings["measure_sweeps"])
        if int(runtime.get("measure_sweeps", -1)) != expected_measurement:
            raise ValueError(f"{cell['cell_id']} runtime measurement mismatch")
        if int(runtime.get("seed", 0)) <= 0:
            raise ValueError(f"{cell['cell_id']} runtime seed is missing")
        with np.load(root / "bins.npz", allow_pickle=False) as payload:
            values = np.asarray(payload["energy"], dtype=float)
        if values.shape != (80,) or not np.isfinite(values).all():
            raise ValueError(f"{cell['cell_id']} must contain 80 finite bins")
        arrays[(m_value, chain)] = values
        thermal[m_value] = expected_thermal

    bins = np.stack(
        [np.stack([arrays[(m, chain)] for chain in CHAINS]) for m in M_VALUES]
    )
    return 0.5, np.asarray(M_VALUES, dtype=float), bins, thermal


def analyze_bins(
    beta: float,
    m_values: np.ndarray,
    bins: np.ndarray,
    *,
    bootstrap_samples: int = 5000,
    seed: int = 147,
) -> dict:
    m_values = np.asarray(m_values, dtype=float)
    bins = np.asarray(bins, dtype=float)
    if bins.shape != (len(m_values), len(CHAINS), 80):
        raise ValueError("bins must have shape (M, 4, 80)")
    if bootstrap_samples < 2:
        raise ValueError("at least two bootstrap samples are required")

    blocks = np.stack(
        [
            np.stack([_block_means(bins[m_index, chain]) for chain in CHAINS])
            for m_index in range(len(m_values))
        ]
    )
    diagnostics = []
    for m_index, m_value in enumerate(m_values):
        split = [_split_half_z(blocks[m_index, chain]) for chain in CHAINS]
        diagnostics.append(
            {
                "M": int(m_value),
                "rhat": _rhat(bins[m_index]),
                "rhat_input": "80 saved bin means per chain",
                "max_abs_split_half_difference": max(abs(item[0]) for item in split),
                "max_split_half_z": max(item[1] for item in split),
                "lag_one": [
                    _lag_one(bins[m_index, chain]) for chain in CHAINS
                ],
            }
        )

    rng = np.random.default_rng(seed)
    boot_means = np.empty((bootstrap_samples, len(m_values)), dtype=float)
    block_count = blocks.shape[2]
    for sample in range(bootstrap_samples):
        for m_index in range(len(m_values)):
            chain_means = []
            for chain in CHAINS:
                indices = rng.integers(0, block_count, size=block_count)
                chain_means.append(float(np.mean(blocks[m_index, chain, indices])))
            boot_means[sample, m_index] = float(np.mean(chain_means))

    observed = np.mean(bins, axis=(1, 2))
    errors = np.std(boot_means, axis=0, ddof=1)
    fit = trotter_extrapolate(beta, m_values, observed, errors)
    x_values = (float(beta) / m_values) ** 2
    design = np.column_stack((np.ones_like(x_values), x_values))
    weights = 1.0 / errors**2
    covariance = np.linalg.inv(design.T @ (weights[:, None] * design))
    projector = covariance @ design.T @ np.diag(weights)
    fit_samples = boot_means @ projector.T
    intercept_samples = fit_samples[:, 0]
    lower, upper = np.quantile(intercept_samples, [0.025, 0.975])
    predicted = fit.value + fit.slope * x_values
    residual_sigma = (observed - predicted) / errors

    split_ok = all(item["max_split_half_z"] <= SPLIT_Z_MAX for item in diagnostics)
    rhat_ok = all(item["rhat"] <= RHAT_MAX for item in diagnostics)
    fit_ok = fit.reduced_chi2 < REDUCED_CHI2_MAX
    return {
        "protocol": "chain-stratified-8-bin-block-bootstrap",
        "bootstrap_samples": bootstrap_samples,
        "thresholds": {
            "split_half_z_max": SPLIT_Z_MAX,
            "rhat_max": RHAT_MAX,
            "reduced_chi2_max": REDUCED_CHI2_MAX,
        },
        "accepted": bool(split_ok and rhat_ok and fit_ok),
        "gates": {
            "split_half": split_ok,
            "chain_rhat": rhat_ok,
            "trotter_fit": fit_ok,
        },
        "fit": {
            "u_infinity": fit.value,
            "bootstrap_se": float(np.std(intercept_samples, ddof=1)),
            "ci95": [float(lower), float(upper)],
            "slope": fit.slope,
            "reduced_chi2": fit.reduced_chi2,
        },
        "finite_m": [
            {
                "M": int(m_value),
                "x": float(x_value),
                "u": float(value),
                "bootstrap_se": float(error),
                "residual_sigma": float(residual),
            }
            for m_value, x_value, value, error, residual in zip(
                m_values, x_values, observed, errors, residual_sigma, strict=True
            )
        ],
        "diagnostics": diagnostics,
    }


def _write_table(result: dict, thermal: dict[int, int], path: Path) -> None:
    fields = (
        "M",
        "thermal_sweeps",
        "x",
        "u",
        "bootstrap_se",
        "residual_sigma",
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result["finite_m"]:
            writer.writerow({**row, "thermal_sweeps": thermal[row["M"]]})
    os.replace(temporary, path)


def _plot(result: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = result["finite_m"]
    x_values = np.asarray([row["x"] for row in rows])
    values = np.asarray([row["u"] for row in rows])
    errors = np.asarray([row["bootstrap_se"] for row in rows])
    residuals = np.asarray([row["residual_sigma"] for row in rows])
    fit = result["fit"]
    x_line = np.linspace(0.0, 1.05 * np.max(x_values), 100)
    y_line = fit["u_infinity"] + fit["slope"] * x_line

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.labelsize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
        }
    )
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(4.6, 4.6),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
        constrained_layout=True,
    )
    axes[0].plot(x_line, y_line, color="#0072B2", lw=1.4, label="linear fit")
    axes[0].errorbar(
        x_values,
        values,
        yerr=errors,
        fmt="o",
        color="#D55E00",
        ecolor="#D55E00",
        capsize=3,
        label="8-bin block bootstrap SE",
    )
    axes[0].errorbar(
        [0.0],
        [fit["u_infinity"]],
        yerr=[fit["bootstrap_se"]],
        fmt="*",
        ms=8,
        color="#009E73",
        capsize=3,
        label="zero-step limit",
    )
    axes[0].set_ylabel("Internal energy per site")
    axes[0].legend(frameon=False, fontsize=7)
    axes[0].set_title(
        f"QMC Trotter extrapolation, beta J = 0.5; chi2/nu = {fit['reduced_chi2']:.2f}"
    )
    axes[1].axhline(0.0, color="#000000", lw=0.8)
    axes[1].axhspan(-2.0, 2.0, color="#999999", alpha=0.15)
    axes[1].scatter(x_values, residuals, color="#CC79A7", marker="s", s=22)
    axes[1].set_xlabel("(beta / M)^2")
    axes[1].set_ylabel("Residual / SE")
    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    fig.savefig(output / "trotter-fit.png", dpi=300)
    fig.savefig(output / "trotter-fit.pdf")
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=147)
    args = parser.parse_args(argv)

    beta, m_values, bins, thermal = _load_run(args.run_dir)
    result = analyze_bins(
        beta,
        m_values,
        bins,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    _atomic_text(
        args.run_dir / "analysis.json",
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )
    _write_table(result, thermal, args.run_dir / "trotter-fit.csv")
    _plot(result, args.run_dir)
    print(json.dumps(result["fit"], sort_keys=True), flush=True)
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
