#!/usr/bin/env python3
"""Finite-chi and finite-size analysis for dual-unitary MPS trajectories."""

from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Unable to import Axes3D.*")
    import matplotlib.pyplot as plt
import numpy as np


DEFAULT_THRESHOLDS = (1e-4, 3e-5, 1e-5, 3e-6, 1e-6)


def trajectory_entropy_density(record: Mapping, start_fraction: float = 0.0) -> float:
    """Fit the measurement-record cost per site linearly in recorded time."""
    L = int(record["L"])
    cumulative = np.asarray(record["cumulative_record_cost"], dtype=float)
    fraction = float(start_fraction)
    if L <= 0 or cumulative.ndim != 1 or cumulative.size < 2:
        raise ValueError("trajectory has an invalid size or cumulative record")
    if not 0.0 <= fraction < 1.0 or np.any(~np.isfinite(cumulative)):
        raise ValueError("invalid fit fraction or non-finite cumulative record")
    start = int(np.floor(fraction * cumulative.size))
    if cumulative.size - start < 2:
        raise ValueError("too few retained time points")
    times = np.arange(1, cumulative.size + 1, dtype=float)[start:]
    design = np.column_stack((np.ones_like(times), times))
    coefficients, _, _, _ = np.linalg.lstsq(
        design, cumulative[start:] / L, rcond=None
    )
    return float(coefficients[1])


def load_trajectory_records(run_dir: Path, start_fraction: float = 0.0) -> list[dict]:
    """Load all successful trajectory JSON files from one fetched run."""
    run_dir = Path(run_dir)
    records = []
    seen = set()
    for path in sorted((run_dir / "cells").glob("*/result.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        key = (int(raw["L"]), int(raw["chi"]), int(raw["sample_index"]))
        if key in seen:
            raise ValueError(f"duplicate trajectory {key}")
        seen.add(key)
        split_count = int(raw["split_count"])
        if split_count <= 0:
            raise ValueError("trajectory split_count must be positive")
        records.append(
            {
                "L": key[0],
                "chi": key[1],
                "sample_index": key[2],
                "seed": int(raw["seed"]),
                "tilde_f": trajectory_entropy_density(raw, start_fraction),
                "discarded_weight_rate": float(raw["discarded_weight_sum"])
                / split_count,
                "runtime_seconds": float(raw["runtime_seconds"]),
            }
        )
    if not records:
        raise ValueError(f"no trajectory results found below {run_dir}")
    return records


def _group_records(records: Iterable[Mapping]) -> dict[tuple[int, int], list[dict]]:
    grouped: dict[tuple[int, int], list[dict]] = defaultdict(list)
    seen = set()
    for item in records:
        record = dict(item)
        key = (int(record["L"]), int(record["chi"]), int(record["sample_index"]))
        if key in seen:
            raise ValueError(f"duplicate trajectory {key}")
        seen.add(key)
        value = float(record["tilde_f"])
        discard = float(record["discarded_weight_rate"])
        if not math.isfinite(value) or not math.isfinite(discard) or discard < 0.0:
            raise ValueError("trajectory values must be finite and nonnegative")
        grouped[(key[0], key[1])].append(record)
    if not grouped:
        raise ValueError("at least one trajectory is required")
    return grouped


def chi_group_summary(records: Iterable[Mapping]) -> list[dict]:
    """Summarize independent trajectory estimates at every (L, chi)."""
    rows = []
    for (L, chi), group in sorted(_group_records(records).items()):
        values = np.asarray([float(item["tilde_f"]) for item in group])
        discards = np.asarray(
            [float(item["discarded_weight_rate"]) for item in group]
        )
        if values.size < 2:
            raise ValueError(f"L={L}, chi={chi} needs at least two trajectories")
        rows.append(
            {
                "L": L,
                "chi": chi,
                "trajectory_count": int(values.size),
                "tilde_f": float(values.mean()),
                "tilde_f_se": float(values.std(ddof=1) / np.sqrt(values.size)),
                "discarded_weight_rate": float(discards.mean()),
                "discarded_weight_rate_max": float(discards.max()),
            }
        )
    return rows


def _converged_suffix(chis: Sequence[int], rates: Sequence[float], threshold: float) -> list[int]:
    chis = list(map(int, chis))
    rates = list(map(float, rates))
    for start in range(len(chis)):
        if all(rate <= threshold for rate in rates[start:]):
            return chis[start:]
    return []


def estimate_infinite_chi(
    records: Iterable[Mapping], discard_rate_threshold: float = 1e-5
) -> list[dict]:
    """Pool the contiguous high-chi plateau whose discarded rate is negligible."""
    records = [dict(item) for item in records]
    grouped = _group_records(records)
    threshold = float(discard_rate_threshold)
    if not math.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("discard_rate_threshold must be finite and positive")
    rows = []
    for L in sorted({key[0] for key in grouped}):
        chis = sorted(chi for width, chi in grouped if width == L)
        rates = [
            float(
                np.mean(
                    [item["discarded_weight_rate"] for item in grouped[(L, chi)]]
                )
            )
            for chi in chis
        ]
        selected_chis = _converged_suffix(chis, rates, threshold)
        if not selected_chis:
            raise ValueError(f"L={L} has no chi plateau below {threshold:g}")
        selected = [
            item
            for chi in selected_chis
            for item in grouped[(L, chi)]
        ]
        values = np.asarray([float(item["tilde_f"]) for item in selected])
        if values.size < 2:
            raise ValueError(f"L={L} chi plateau needs at least two trajectories")
        rows.append(
            {
                "L": L,
                "f_infinite": float(values.mean()),
                "f_infinite_se": float(values.std(ddof=1) / np.sqrt(values.size)),
                "chi_systematic": 0.0,
                "trajectory_count": int(values.size),
                "selected_chis": selected_chis,
                "chi_min": int(selected_chis[0]),
                "discard_rate_threshold": threshold,
            }
        )
    return rows


def fit_central_charge(
    rows: Sequence[Mapping], include_l4: bool = False, alpha: float = 1.0
) -> dict:
    """Fit f(L)=f_bulk+a/L^2(+b/L^4), with c_eff=-6a/(pi alpha)."""
    rows = sorted(rows, key=lambda item: int(item["L"]))
    alpha = float(alpha)
    parameter_count = 3 if include_l4 else 2
    if len(rows) <= parameter_count or not math.isfinite(alpha) or alpha <= 0.0:
        raise ValueError("insufficient widths or invalid anisotropy alpha")
    widths = np.asarray([float(item["L"]) for item in rows])
    values = np.asarray([float(item["f_infinite"]) for item in rows])
    errors = np.asarray(
        [float(item.get("total_se", item["f_infinite_se"])) for item in rows]
    )
    if np.any(~np.isfinite(values)) or np.any(~np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("fit values and errors must be finite and errors positive")
    columns = [np.ones_like(widths), widths**-2]
    if include_l4:
        columns.append(widths**-4)
    design = np.column_stack(columns)
    weighted_design = design / errors[:, None]
    coefficients, _, _, _ = np.linalg.lstsq(
        weighted_design, values / errors, rcond=None
    )
    covariance = np.linalg.inv(weighted_design.T @ weighted_design)
    residual = (values - design @ coefficients) / errors
    dof = len(values) - parameter_count
    central_charge = -6.0 * coefficients[1] / (np.pi * alpha)
    central_charge_se = 6.0 * np.sqrt(covariance[1, 1]) / (np.pi * alpha)
    return {
        "include_l4": bool(include_l4),
        "alpha": alpha,
        "widths": widths.astype(int).tolist(),
        "coefficients": coefficients.tolist(),
        "coefficient_se": np.sqrt(np.diag(covariance)).tolist(),
        "central_charge": float(central_charge),
        "central_charge_linear_se": float(central_charge_se),
        "chi2": float(np.sum(residual**2)),
        "dof": int(dof),
        "chi2_per_dof": float(np.sum(residual**2) / dof),
    }


def threshold_fit_envelope(
    records: Iterable[Mapping],
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    alpha: float = 1.0,
) -> dict:
    """Repeat the leading finite-size fit over converged-chi thresholds."""
    records = [dict(item) for item in records]
    fits = []
    for threshold in thresholds:
        try:
            rows = estimate_infinite_chi(records, threshold)
            fit = fit_central_charge(rows, include_l4=False, alpha=alpha)
        except ValueError:
            continue
        fits.append(
            {
                "threshold": float(threshold),
                "central_charge": fit["central_charge"],
                "f_infinite": {str(row["L"]): row["f_infinite"] for row in rows},
                "selected_chis": {
                    str(row["L"]): row["selected_chis"] for row in rows
                },
            }
        )
    if not fits:
        raise ValueError("no threshold supports all finite-size fits")
    charges = [item["central_charge"] for item in fits]
    return {
        "fits": fits,
        "central_charge_min": float(min(charges)),
        "central_charge_max": float(max(charges)),
    }


def _add_chi_systematics(
    primary_rows: list[dict], threshold_summary: Mapping
) -> list[dict]:
    for row in primary_rows:
        alternatives = [
            float(item["f_infinite"][str(row["L"])])
            for item in threshold_summary["fits"]
        ]
        systematic = max(abs(value - row["f_infinite"]) for value in alternatives)
        row["chi_systematic"] = float(systematic)
        row["total_se"] = float(np.hypot(row["f_infinite_se"], systematic))
    return primary_rows


def bootstrap_central_charge(
    records: Iterable[Mapping],
    primary_rows: Sequence[Mapping],
    samples: int = 5000,
    seed: int = 0,
    alpha: float = 1.0,
) -> dict:
    """Bootstrap complete trajectories within each selected high-chi plateau."""
    records = [dict(item) for item in records]
    samples = int(samples)
    if samples < 2:
        raise ValueError("bootstrap needs at least two samples")
    selected = {}
    fixed_rows = {int(row["L"]): dict(row) for row in primary_rows}
    for L, row in fixed_rows.items():
        values = np.asarray(
            [
                float(item["tilde_f"])
                for item in records
                if int(item["L"]) == L
                and int(item["chi"]) in set(row["selected_chis"])
            ]
        )
        if values.size < 2:
            raise ValueError(f"L={L} bootstrap plateau is too small")
        selected[L] = values
    rng = np.random.default_rng(seed)
    leading, corrected = [], []
    for _ in range(samples):
        rows = []
        for L in sorted(selected):
            values = selected[L]
            item = dict(fixed_rows[L])
            item["f_infinite"] = float(
                rng.choice(values, size=values.size, replace=True).mean()
            )
            rows.append(item)
        leading.append(
            fit_central_charge(rows, include_l4=False, alpha=alpha)[
                "central_charge"
            ]
        )
        corrected.append(
            fit_central_charge(rows, include_l4=True, alpha=alpha)[
                "central_charge"
            ]
        )
    leading = np.asarray(leading)
    corrected = np.asarray(corrected)
    return {
        "samples": samples,
        "seed": int(seed),
        "l2_se": float(leading.std(ddof=1)),
        "l2_percentile_95": np.percentile(leading, [2.5, 97.5]).tolist(),
        "l4_se": float(corrected.std(ddof=1)),
        "l4_percentile_95": np.percentile(corrected, [2.5, 97.5]).tolist(),
    }


def _apply_italic_style(axis) -> None:
    artists = [
        axis.title,
        axis.xaxis.label,
        axis.yaxis.label,
        *axis.get_xticklabels(),
        *axis.get_yticklabels(),
        *axis.texts,
    ]
    legend = axis.get_legend()
    if legend is not None:
        artists.extend(legend.get_texts())
    for artist in artists:
        artist.set_fontstyle("italic")


def make_chi_figure(
    group_rows: Sequence[Mapping], infinite_rows: Sequence[Mapping]
):
    infinite = {int(row["L"]): row for row in infinite_rows}
    figure, axes = plt.subplots(2, 3, figsize=(12.0, 7.0), sharex=True)
    for axis, L in zip(axes.flat, sorted(infinite)):
        group = sorted(
            (row for row in group_rows if int(row["L"]) == L),
            key=lambda row: int(row["chi"]),
        )
        x = 1.0 / np.asarray([row["chi"] for row in group], dtype=float)
        y = np.asarray([row["tilde_f"] for row in group])
        error = np.asarray([row["tilde_f_se"] for row in group])
        selected = set(infinite[L]["selected_chis"])
        mask = np.asarray([int(row["chi"]) in selected for row in group])
        axis.errorbar(
            x[~mask], y[~mask], yerr=error[~mask], fmt="o", markersize=8,
            alpha=0.78, capsize=3, color="tab:blue", label="truncated",
        )
        axis.errorbar(
            x[mask], y[mask], yerr=error[mask], fmt="o", markersize=10,
            alpha=0.78, capsize=3, color="red", label="plateau",
        )
        row = infinite[L]
        axis.axhline(row["f_infinite"], color="red", linestyle="-", alpha=0.78)
        axis.fill_between(
            [0.0, max(x) * 1.05],
            row["f_infinite"] - row["total_se"],
            row["f_infinite"] + row["total_se"],
            color="red",
            alpha=0.10,
        )
        axis.set_title(f"L={L}, chi_min={row['chi_min']}")
        axis.grid(alpha=0.22)
        _apply_italic_style(axis)
    axes.flat[-1].axis("off")
    axes[1, 0].set_xlabel(r"$1/\chi$")
    axes[1, 1].set_xlabel(r"$1/\chi$")
    axes[0, 0].set_ylabel(r"$\widetilde f(L,\chi)$")
    axes[1, 0].set_ylabel(r"$\widetilde f(L,\chi)$")
    axes[0, 0].legend(frameon=False)
    figure.tight_layout()
    return figure


def make_central_charge_figure(
    rows: Sequence[Mapping], l2_fit: Mapping, l4_fit: Mapping
):
    rows = sorted(rows, key=lambda row: int(row["L"]))
    widths = np.asarray([row["L"] for row in rows], dtype=float)
    x = widths**-2
    values = np.asarray([row["f_infinite"] for row in rows])
    errors = np.asarray([row["total_se"] for row in rows])
    grid = np.linspace(0.0, x.max() * 1.05, 300)
    line_l2 = l2_fit["coefficients"][0] + l2_fit["coefficients"][1] * grid
    line_l4 = (
        l4_fit["coefficients"][0]
        + l4_fit["coefficients"][1] * grid
        + l4_fit["coefficients"][2] * grid**2
    )
    figure, axis = plt.subplots(figsize=(6.8, 4.8))
    axis.errorbar(
        x, values, yerr=errors, fmt="o", markersize=10, alpha=0.78,
        capsize=3, color="tab:blue", label=r"$\chi\to\infty$ plateau",
    )
    axis.plot(
        grid, line_l2, color="red", linestyle="-", alpha=0.78,
        label=rf"$L^{{-2}}$: $c_{{\rm eff}}={l2_fit['central_charge']:.3f}$",
    )
    axis.plot(
        grid, line_l4, color="tab:orange", linestyle="--", alpha=0.78,
        label=rf"$L^{{-2}}+L^{{-4}}$: $c_{{\rm eff}}={l4_fit['central_charge']:.3f}$",
    )
    axis.set_xlabel(r"$1/L^2$")
    axis.set_ylabel(r"$\widetilde f(L,\chi\to\infty)$")
    axis.grid(alpha=0.22)
    axis.legend(frameon=False)
    _apply_italic_style(axis)
    figure.tight_layout()
    return figure


def _write_csv(path: Path, rows: Sequence[Mapping], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            for field in fields:
                if isinstance(rendered.get(field), (list, tuple)):
                    rendered[field] = " ".join(map(str, rendered[field]))
            writer.writerow({field: rendered[field] for field in fields})


def run_analysis(
    run_dir: Path,
    output_dir: Path | None = None,
    primary_threshold: float = 1e-5,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    bootstrap_samples: int = 5000,
    seed: int = 12220260730,
    alpha: float = 1.0,
) -> tuple[list[dict], dict]:
    run_dir = Path(run_dir)
    output_dir = Path(output_dir) if output_dir else run_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    records = load_trajectory_records(run_dir)
    group_rows = chi_group_summary(records)
    threshold_summary = threshold_fit_envelope(records, thresholds, alpha)
    infinite_rows = estimate_infinite_chi(records, primary_threshold)
    _add_chi_systematics(infinite_rows, threshold_summary)
    l2_fit = fit_central_charge(infinite_rows, include_l4=False, alpha=alpha)
    l4_fit = fit_central_charge(infinite_rows, include_l4=True, alpha=alpha)
    bootstrap = bootstrap_central_charge(
        records,
        infinite_rows,
        samples=bootstrap_samples,
        seed=seed,
        alpha=alpha,
    )
    summary = {
        "run_dir": str(run_dir),
        "primary_discard_rate_threshold": float(primary_threshold),
        "alpha": float(alpha),
        "trajectory_count": len(records),
        "l2_fit": l2_fit,
        "l4_stability_fit": l4_fit,
        "bootstrap": bootstrap,
        "chi_threshold_envelope": threshold_summary,
        "reported": {
            "central_charge": l2_fit["central_charge"],
            "bootstrap_se": bootstrap["l2_se"],
            "bootstrap_percentile_95": bootstrap["l2_percentile_95"],
            "chi_threshold_lower": threshold_summary["central_charge_min"],
            "chi_threshold_upper": threshold_summary["central_charge_max"],
            "l4_stability_central_charge": l4_fit["central_charge"],
            "finite_size_form_shift": abs(
                l4_fit["central_charge"] - l2_fit["central_charge"]
            ),
        },
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(
        output_dir / "trajectory_summary.csv",
        records,
        (
            "L", "chi", "sample_index", "seed", "tilde_f",
            "discarded_weight_rate", "runtime_seconds",
        ),
    )
    _write_csv(
        output_dir / "chi_summary.csv",
        group_rows,
        (
            "L", "chi", "trajectory_count", "tilde_f", "tilde_f_se",
            "discarded_weight_rate", "discarded_weight_rate_max",
        ),
    )
    _write_csv(
        output_dir / "infinite_chi_summary.csv",
        infinite_rows,
        (
            "L", "f_infinite", "f_infinite_se", "chi_systematic", "total_se",
            "trajectory_count", "selected_chis", "chi_min",
            "discard_rate_threshold",
        ),
    )
    figure = make_chi_figure(group_rows, infinite_rows)
    figure.savefig(output_dir / "chi_extrapolation.png", dpi=180)
    plt.close(figure)
    figure = make_central_charge_figure(infinite_rows, l2_fit, l4_fit)
    figure.savefig(output_dir / "central_charge_fit.png", dpi=180)
    plt.close(figure)
    print(
        f"c_eff={l2_fit['central_charge']:.8f} "
        f"bootstrap_se={bootstrap['l2_se']:.3e} "
        f"l4={l4_fit['central_charge']:.8f}",
        flush=True,
    )
    return infinite_rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("results/dual-unitary-mps-20260730"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--discard-rate-threshold", type=float, default=1e-5)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=12220260730)
    parser.add_argument("--alpha", type=float, default=1.0)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    run_analysis(
        run_dir=args.run_dir,
        output_dir=args.output_dir,
        primary_threshold=args.discard_rate_threshold,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
        alpha=args.alpha,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
