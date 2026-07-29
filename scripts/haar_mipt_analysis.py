"""Pure analysis utilities for Haar measurement-induced transition records."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


_FAMILIES = ("global_haar", "product")


def aggregate_trajectory_records(records: Iterable[Mapping]) -> list[dict]:
    """Aggregate independent trajectories with exactly half weight per family."""
    records = list(records)
    seen = set()
    for record in records:
        key = (
            int(record["L"]),
            str(record["initial_family"]),
            int(record["sample_index"]),
        )
        if key in seen:
            raise ValueError(f"duplicate trajectory identity {key}")
        seen.add(key)
        if key[1] not in _FAMILIES:
            raise ValueError(f"unknown initial family {key[1]!r}")

    rows = []
    for width in sorted({int(record["L"]) for record in records}):
        families = {}
        for family in _FAMILIES:
            chosen = sorted(
                (
                    record
                    for record in records
                    if int(record["L"]) == width
                    and record["initial_family"] == family
                ),
                key=lambda record: int(record["sample_index"]),
            )
            if len(chosen) < 2:
                raise ValueError(f"L={width} family={family} needs two trajectories")
            values = np.asarray(
                [
                    float(record["record_cost"])
                    / (width * int(record["record_steps"]))
                    for record in chosen
                ],
                dtype=float,
            )
            families[family] = {
                "count": len(chosen),
                "values": values,
                "mean": float(values.mean()),
                "se": float(values.std(ddof=1) / np.sqrt(len(values))),
            }
        mean = 0.5 * sum(item["mean"] for item in families.values())
        standard_error = 0.5 * np.sqrt(
            sum(item["se"] ** 2 for item in families.values())
        )
        rows.append(
            {
                "L": width,
                "tilde_f": float(mean),
                "tilde_f_se": float(standard_error),
                "families": families,
            }
        )
    return rows


def weighted_l2_fit(width_rows: Sequence[Mapping], lmin: int) -> dict:
    """Fit ``tilde_f = intercept + slope/L**2`` using measured errors."""
    selected = sorted(
        (row for row in width_rows if int(row["L"]) >= int(lmin)),
        key=lambda row: int(row["L"]),
    )
    if len(selected) < 2:
        raise ValueError(f"lmin={lmin} leaves fewer than two widths")
    x = np.asarray([1.0 / int(row["L"]) ** 2 for row in selected])
    y = np.asarray([float(row["tilde_f"]) for row in selected])
    sigma = np.asarray([float(row["tilde_f_se"]) for row in selected])
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("width standard errors must be finite and positive")
    design = np.column_stack((np.ones_like(x), x))
    coefficients, _, _, _ = np.linalg.lstsq(
        design / sigma[:, None], y / sigma, rcond=None
    )
    return {
        "lmin": int(lmin),
        "intercept": float(coefficients[0]),
        "slope": float(coefficients[1]),
        "widths": [int(row["L"]) for row in selected],
    }


def extrapolate_slopes(window_fits: Sequence[Mapping], alpha: float) -> dict:
    """Extrapolate correlated window slopes linearly in ``1/lmin**2``."""
    if len(window_fits) < 2:
        raise ValueError("slope extrapolation needs at least two windows")
    alpha = float(alpha)
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("alpha must be finite and positive")
    x = np.asarray([1.0 / int(fit["lmin"]) ** 2 for fit in window_fits])
    y = np.asarray([float(fit["slope"]) for fit in window_fits])
    correction, asymptotic_slope = np.polyfit(x, y, 1)
    return {
        "m0_inf": float(asymptotic_slope),
        "slope_correction": float(correction),
        "central_charge": float(-6 * asymptotic_slope / (np.pi * alpha)),
    }


def double_fit_central_charge(
    width_rows: Sequence[Mapping],
    alpha: float = 0.81,
    lmins: Sequence[int] = (8, 10, 12, 14),
) -> dict:
    """Perform the primary finite-size window fit and slope extrapolation."""
    windows = [weighted_l2_fit(width_rows, lmin) for lmin in lmins]
    return {"windows": windows, **extrapolate_slopes(windows, alpha)}


def l4_stability_fit(width_rows: Sequence[Mapping], alpha: float = 0.81) -> dict:
    """Fit a single weighted model including both ``L**-2`` and ``L**-4``."""
    alpha = float(alpha)
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("alpha must be finite and positive")
    if len(width_rows) < 3:
        raise ValueError("L^-4 stability fit needs at least three widths")
    widths = np.asarray([float(row["L"]) for row in width_rows])
    y = np.asarray([float(row["tilde_f"]) for row in width_rows])
    sigma = np.asarray([float(row["tilde_f_se"]) for row in width_rows])
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("width standard errors must be finite and positive")
    design = np.column_stack((np.ones_like(widths), widths**-2, widths**-4))
    coefficients, _, _, _ = np.linalg.lstsq(
        design / sigma[:, None], y / sigma, rcond=None
    )
    return {
        "intercept": float(coefficients[0]),
        "l2_coefficient": float(coefficients[1]),
        "l4_coefficient": float(coefficients[2]),
        "central_charge": float(-6 * coefficients[1] / (np.pi * alpha)),
    }


def _bootstrap_central_charge(
    records: Sequence[Mapping], samples: int, seed: int, alpha: float
) -> np.ndarray:
    samples = int(samples)
    if samples < 1:
        raise ValueError("samples must be positive")
    observed = aggregate_trajectory_records(records)
    fixed_errors = {row["L"]: row["tilde_f_se"] for row in observed}
    groups = {
        (width, family): sorted(
            (
                record
                for record in records
                if int(record["L"]) == width
                and record["initial_family"] == family
            ),
            key=lambda record: int(record["sample_index"]),
        )
        for width in fixed_errors
        for family in _FAMILIES
    }
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(samples):
        resampled = []
        for group in groups.values():
            draws = rng.integers(0, len(group), size=len(group))
            for new_index, draw in enumerate(draws):
                item = dict(group[int(draw)])
                item["sample_index"] = new_index
                resampled.append(item)
        rows = aggregate_trajectory_records(resampled)
        for row in rows:
            row["tilde_f_se"] = fixed_errors[row["L"]]
        values.append(
            double_fit_central_charge(rows, alpha=alpha)["central_charge"]
        )
    return np.asarray(values, dtype=float)


def bootstrap_central_charge(
    records: Sequence[Mapping], samples: int = 1000, seed: int = 0
) -> np.ndarray:
    """Bootstrap complete trajectories using fixed observed fit weights."""
    return _bootstrap_central_charge(records, samples, seed, alpha=0.81)


def central_charge_summary(
    records: Sequence[Mapping],
    samples: int = 1000,
    seed: int = 0,
    alpha: float = 0.81,
) -> tuple[list[dict], dict]:
    """Return aggregated widths and the primary uncertainty summary."""
    if int(samples) < 2:
        raise ValueError("summary needs at least two bootstrap samples")
    alpha = float(alpha)
    width_rows = aggregate_trajectory_records(records)
    primary = double_fit_central_charge(width_rows, alpha=alpha)
    stability = l4_stability_fit(width_rows, alpha=alpha)
    bootstrap_values = _bootstrap_central_charge(records, samples, seed, alpha)
    summary = {
        "central_charge": primary["central_charge"],
        "bootstrap_se": float(np.std(bootstrap_values, ddof=1)),
        "bootstrap_percentile_95": np.percentile(
            bootstrap_values, [2.5, 97.5]
        ).tolist(),
        "alpha": alpha,
        "alpha_se": 0.09,
        "anisotropy_error": abs(primary["central_charge"]) * 0.09 / alpha,
        "stability_central_charge": stability["central_charge"],
        "fit_systematic": abs(
            primary["central_charge"] - stability["central_charge"]
        ),
        "pc": 0.168,
        "pc_literature_error": 0.005,
        "pc_error_propagated": False,
        "literature_central_charge": 0.25,
        "literature_central_charge_error": 0.03,
    }
    return width_rows, summary


def _write_trajectory_summary(records: Sequence[Mapping], path: Path) -> None:
    fields = (
        "L",
        "initial_family",
        "sample_index",
        "seed",
        "tilde_f",
        "runtime_seconds",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in sorted(
            records,
            key=lambda item: (
                int(item["L"]),
                str(item["initial_family"]),
                int(item["sample_index"]),
            ),
        ):
            width = int(record["L"])
            writer.writerow(
                {
                    "L": width,
                    "initial_family": record["initial_family"],
                    "sample_index": int(record["sample_index"]),
                    "seed": int(record["seed"]),
                    "tilde_f": float(record["record_cost"])
                    / (width * int(record["record_steps"])),
                    "runtime_seconds": float(record["runtime_seconds"]),
                }
            )


def _write_width_summary(width_rows: Sequence[Mapping], path: Path) -> None:
    fields = (
        "L",
        "tilde_f",
        "tilde_f_se",
        "global_haar_count",
        "global_haar_mean",
        "global_haar_se",
        "product_count",
        "product_mean",
        "product_se",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in width_rows:
            writer.writerow(
                {
                    "L": int(row["L"]),
                    "tilde_f": float(row["tilde_f"]),
                    "tilde_f_se": float(row["tilde_f_se"]),
                    **{
                        f"{family}_{field}": row["families"][family][field]
                        for family in _FAMILIES
                        for field in ("count", "mean", "se")
                    },
                }
            )


def _plot_central_charge(
    width_rows: Sequence[Mapping], summary: Mapping, path: Path
) -> None:
    x = np.asarray([1.0 / int(row["L"]) ** 2 for row in width_rows])
    y = np.asarray([float(row["tilde_f"]) for row in width_rows])
    sigma = np.asarray([float(row["tilde_f_se"]) for row in width_rows])
    line = _central_charge_plot_line(width_rows, lmin=8)

    figure, axis = plt.subplots(figsize=(6.4, 4.5))
    axis.errorbar(
        x,
        y,
        yerr=sigma,
        fmt="o",
        markersize=10,
        alpha=0.78,
        capsize=3,
        label="equal-family mean",
    )
    axis.plot(
        line["x"],
        line["y"],
        color="red",
        linestyle="-",
        label=r"weighted $L_{\min}=8$ fit",
    )
    axis.set_xlabel("$1/L^2$")
    axis.set_ylabel(r"$\widetilde{f}_L$")
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _central_charge_plot_line(
    width_rows: Sequence[Mapping], lmin: int = 8
) -> dict:
    """Return a display line whose intercept and slope come from one fit."""
    x = np.asarray([1.0 / int(row["L"]) ** 2 for row in width_rows])
    fit = weighted_l2_fit(width_rows, lmin=lmin)
    line_x = np.linspace(0.0, 1.05 * x.max(), 200)
    return {
        "x": line_x,
        "y": fit["intercept"] + fit["slope"] * line_x,
        "intercept": fit["intercept"],
        "slope": fit["slope"],
    }


def _plot_record_growth(records: Sequence[Mapping], path: Path) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 4.5))
    widths = sorted({int(record["L"]) for record in records})
    for width in widths:
        family_curves = []
        for family in _FAMILIES:
            group = [
                record
                for record in records
                if int(record["L"]) == width
                and record["initial_family"] == family
            ]
            retained_steps = min(
                len(record["cumulative_record_cost"]) for record in group
            )
            times = np.arange(1, retained_steps + 1, dtype=float)
            normalized = np.asarray(
                [
                    np.asarray(
                        record["cumulative_record_cost"][:retained_steps],
                        dtype=float,
                    )
                    / (width * times)
                    for record in group
                ]
            )
            family_curves.append(normalized.mean(axis=0))
        equal_family_curve = 0.5 * (family_curves[0] + family_curves[1])
        axis.plot(times, equal_family_curve, label=f"L={width}")
    axis.set_xlabel("retained half-layer $t$")
    axis.set_ylabel(r"$\langle C(t)\rangle/(Lt)$")
    axis.legend(frameon=False, ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def write_analysis_artifacts(
    records: Sequence[Mapping],
    width_rows: Sequence[Mapping],
    summary: Mapping,
    output_dir: str | Path,
) -> None:
    """Write tabular summaries, a JSON fit summary, and headless plots."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_trajectory_summary(records, output_dir / "trajectory_summary.csv")
    _write_width_summary(width_rows, output_dir / "width_summary.csv")
    with (output_dir / "fit_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(dict(summary), handle, indent=2, sort_keys=True)
        handle.write("\n")
    _plot_central_charge(width_rows, summary, output_dir / "central_charge_fit.png")
    _plot_record_growth(records, output_dir / "record_entropy_growth.png")
