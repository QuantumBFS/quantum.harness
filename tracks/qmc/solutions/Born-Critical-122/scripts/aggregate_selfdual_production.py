#!/usr/bin/env python3
"""Validate and fit the Stage-4 weak-self-dual production ensemble."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from borncritical.casimir_fit import fit_bootstrap_samples, fit_casimir


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty table {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def standard_error(values: np.ndarray) -> float:
    return float(np.std(values, ddof=1) / math.sqrt(values.size))


def lag_one(values: np.ndarray) -> float:
    if values.size < 3:
        return math.nan
    centered = values - np.mean(values)
    denominator = float(centered @ centered)
    if denominator == 0.0:
        return 0.0
    return float(centered[:-1] @ centered[1:] / denominator)


def longest_sign_run(values: np.ndarray) -> int:
    longest = current = 0
    previous = 0.0
    for sign in np.sign(values):
        if sign == 0.0:
            current = 0
        elif sign == previous:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous = sign
    return longest


def svg_series(
    path: Path, summary: list[dict[str, Any]], primary: dict[str, Any]
) -> None:
    width, height = 940, 500
    left, top, plot_width, plot_height = 95, 55, 760, 350
    sizes = np.array([row["L"] for row in summary], dtype=float)
    x_values = sizes**-2
    y_values = np.array([row["mean_h"] for row in summary])
    errors = np.array([row["replica_standard_error_h"] for row in summary])
    x_min, x_max = 0.0, float(x_values.max() * 1.06)
    pad = max(float(np.ptp(y_values)) * 0.08, float(errors.max() * 6.0))
    y_min, y_max = float(y_values.min() - pad), float(y_values.max() + pad)

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    coefficients = np.asarray(primary["coefficients"])
    fit_x = np.linspace(0.0, primary["lmin"] ** -2, 300)
    fit_y = coefficients[0] + coefficients[1] * fit_x
    if primary["model"] == "M1":
        fit_y += coefficients[2] * fit_x**2
    points = " ".join(
        f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(fit_x, fit_y)
    )
    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">Weak self-dual Born Shannon Casimir scaling</text>',
        f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#111827"/>',
        f'<polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="2"/>',
    ]
    for size, x_value, y_value, error in zip(
        sizes, x_values, y_values, errors
    ):
        elements.extend(
            [
                f'<line x1="{sx(x_value):.2f}" y1="{sy(y_value-error):.2f}" x2="{sx(x_value):.2f}" y2="{sy(y_value+error):.2f}" stroke="#dc2626"/>',
                f'<circle cx="{sx(x_value):.2f}" cy="{sy(y_value):.2f}" r="4" fill="#dc2626"/>',
                f'<text x="{sx(x_value):.2f}" y="{sy(y_value)-9:.2f}" text-anchor="middle" font-family="sans-serif" font-size="11">{int(size)}</text>',
            ]
        )
    elements.extend(
        [
            f'<text x="{left+plot_width/2}" y="460" text-anchor="middle" font-family="sans-serif" font-size="15">1 / L²</text>',
            f'<text x="24" y="{top+plot_height/2}" transform="rotate(-90 24 {top+plot_height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">h_L</text>',
            f'<text x="{left+15}" y="{top+25}" font-family="monospace" font-size="13" fill="#2563eb">{primary["model"]}, Lmin={primary["lmin"]}, c={primary["central_charge_bootstrap_median"]:.7f}</text>',
        ]
    )
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        + "\n".join(elements)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def svg_stability(path: Path, fits: list[dict[str, Any]]) -> None:
    width, height = 940, 500
    left, top, plot_width, plot_height = 95, 55, 760, 350
    y_low = min(f["central_charge_bootstrap_95_interval"][0] for f in fits)
    y_high = max(f["central_charge_bootstrap_95_interval"][1] for f in fits)
    y_low, y_high = min(y_low, 0.444), max(y_high, 0.450)

    def sx(index: int) -> float:
        return left + (index + 0.4) / max(len(fits) - 0.2, 1.0) * plot_width

    def sy(value: float) -> float:
        return top + (y_high - value) / (y_high - y_low) * plot_height

    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">Weak self-dual fit-window stability</text>',
        f'<rect x="{left}" y="{sy(0.448):.2f}" width="{plot_width}" height="{sy(0.446)-sy(0.448):.2f}" fill="#dcfce7"/>',
        f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#111827"/>',
    ]
    for index, fit in enumerate(fits):
        low, high = fit["central_charge_bootstrap_95_interval"]
        median = fit["central_charge_bootstrap_median"]
        x_value = sx(index)
        elements.extend(
            [
                f'<line x1="{x_value:.2f}" y1="{sy(low):.2f}" x2="{x_value:.2f}" y2="{sy(high):.2f}" stroke="#2563eb" stroke-width="2"/>',
                f'<circle cx="{x_value:.2f}" cy="{sy(median):.2f}" r="4" fill="#1d4ed8"/>',
                f'<text x="{x_value:.2f}" y="{top+plot_height+22}" text-anchor="middle" font-family="sans-serif" font-size="10">{fit["model"]}/{fit["lmin"]}</text>',
            ]
        )
    elements.extend(
        [
            f'<text x="{left+plot_width/2}" y="465" text-anchor="middle" font-family="sans-serif" font-size="15">model / Lmin</text>',
            f'<text x="24" y="{top+plot_height/2}" transform="rotate(-90 24 {top+plot_height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">c Casimir</text>',
        ]
    )
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        + "\n".join(elements)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def fit_record(
    *,
    model: str,
    lmin: int,
    sizes: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    bootstrap_values: np.ndarray,
    declaration: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    selected = sizes >= lmin
    fit_sizes = sizes[selected]
    result = fit_casimir(
        fit_sizes,
        values[selected],
        errors=errors[selected],
        model=model,
        quantity="shannon",
        alpha=float(declaration["alpha"]),
    )
    charges, failures = fit_bootstrap_samples(
        fit_sizes,
        bootstrap_values[:, selected],
        errors=errors[selected],
        model=model,
        quantity="shannon",
        alpha=float(declaration["alpha"]),
    )
    valid = charges[np.isfinite(charges)]
    quantiles = np.quantile(valid, [0.025, 0.16, 0.5, 0.84, 0.975])
    standardized = result.residuals / errors[selected]
    rule = declaration["primary_selection_rule"]
    checks = {
        "reduced_chi_squared": (
            result.reduced_chi_squared
            <= float(rule["maximum_reduced_chi_squared"])
        ),
        "standardized_residual": (
            float(np.max(np.abs(standardized)))
            <= float(rule["maximum_absolute_standardized_residual"])
        ),
        "residual_sign_run": (
            longest_sign_run(standardized)
            <= int(rule["maximum_same_sign_residual_run"])
        ),
        "condition_number": (
            result.design_condition_number
            <= float(rule["maximum_design_condition_number"])
        ),
    }
    record = {
        "model": model,
        "lmin": lmin,
        "lmax": int(fit_sizes.max()),
        "sizes": fit_sizes.astype(int).tolist(),
        "coefficients": result.coefficients.tolist(),
        "coefficient_covariance": result.coefficient_covariance.tolist(),
        "central_charge": result.central_charge,
        "central_charge_analytic_error": result.central_charge_error,
        "central_charge_bootstrap_mean": float(np.mean(valid)),
        "central_charge_bootstrap_standard_deviation": float(
            np.std(valid, ddof=1)
        ),
        "central_charge_bootstrap_median": float(quantiles[2]),
        "central_charge_bootstrap_68_interval": [
            float(quantiles[1]),
            float(quantiles[3]),
        ],
        "central_charge_bootstrap_95_interval": [
            float(quantiles[0]),
            float(quantiles[4]),
        ],
        "bootstrap_valid": int(valid.size),
        "bootstrap_failures": int(failures),
        "chi_squared": result.chi_squared,
        "degrees_of_freedom": result.degrees_of_freedom,
        "reduced_chi_squared": result.reduced_chi_squared,
        "design_condition_number": result.design_condition_number,
        "well_conditioned": result.well_conditioned,
        "residuals": result.residuals.tolist(),
        "standardized_residuals": standardized.tolist(),
        "maximum_absolute_standardized_residual": float(
            np.max(np.abs(standardized))
        ),
        "longest_same_sign_residual_run": longest_sign_run(standardized),
        "quality_checks": checks,
        "passes_primary_quality_rule": all(checks.values()),
    }
    return record, charges


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    declaration = json.loads(args.declaration.read_text(encoding="utf-8"))
    spec = json.loads((run / "run_spec.json").read_text(encoding="utf-8"))

    failures: list[dict[str, Any]] = []
    by_size: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    settings_payloads: set[str] = set()
    seeds: set[int] = set()
    maximum_probability_error = 0.0
    maximum_qr_error = 0.0
    maximum_purity_error = 0.0
    for cell in spec["cells"]:
        cell_id = cell["cell_id"]
        root = run / "cells" / cell_id
        manifest_path = root / "manifest.json"
        observable_path = root / "observables.json"
        if not manifest_path.is_file() or not observable_path.is_file():
            failures.append({"cell_id": cell_id, "reason": "missing artifact"})
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            failures.append(
                {"cell_id": cell_id, "reason": f"status={manifest.get('status')}"}
            )
            continue
        if manifest.get("params") != cell["params"]:
            failures.append({"cell_id": cell_id, "reason": "parameter mismatch"})
            continue
        if sha256(observable_path) != manifest.get("observables_sha256"):
            failures.append({"cell_id": cell_id, "reason": "checksum mismatch"})
            continue
        seed = int(manifest["params"]["seed"])
        if seed in seeds:
            failures.append({"cell_id": cell_id, "reason": "duplicate seed"})
            continue
        seeds.add(seed)
        observable = json.loads(observable_path.read_text(encoding="utf-8"))
        blocks = observable.get("blocks", [])
        expected_blocks = (
            int(manifest["result"]["measurement_rows"])
            // int(manifest["result"]["block_rows"])
        )
        if len(blocks) != expected_blocks:
            failures.append({"cell_id": cell_id, "reason": "block count mismatch"})
            continue
        required = (
            "rao_blackwell_shannon_rate",
            "e_density",
            "m_density",
            "probability_normalization_error",
            "qr_orthogonality_error",
            "covariance_purity_residual",
        )
        if not all(
            key in row and math.isfinite(float(row[key]))
            for row in blocks
            for key in required
        ):
            failures.append({"cell_id": cell_id, "reason": "invalid block value"})
            continue
        settings_payloads.add(json.dumps(manifest["settings"], sort_keys=True))
        maximum_probability_error = max(
            maximum_probability_error,
            float(manifest["result"]["maximum_probability_normalization_error"]),
        )
        maximum_qr_error = max(
            maximum_qr_error,
            float(manifest["result"]["maximum_qr_orthogonality_error"]),
        )
        maximum_purity_error = max(
            maximum_purity_error,
            float(manifest["result"]["maximum_covariance_purity_residual"]),
        )
        by_size.setdefault(int(manifest["params"]["size"]), []).append(
            (manifest, observable)
        )

    if failures:
        atomic_json(output / "failures.json", failures)
        raise RuntimeError(f"production has {len(failures)} invalid cells")
    if len(settings_payloads) != 1:
        raise RuntimeError("production settings lack consensus")

    summary: list[dict[str, Any]] = []
    replica_h: dict[int, np.ndarray] = {}
    replica_e: dict[int, np.ndarray] = {}
    replica_m: dict[int, np.ndarray] = {}
    for size in sorted(by_size):
        entries = sorted(by_size[size], key=lambda item: item[0]["params"]["replica"])
        if len(entries) != 64:
            raise RuntimeError(f"L={size}: expected 64 replicas, found {len(entries)}")
        h_blocks = [
            np.array(
                [row["rao_blackwell_shannon_rate"] for row in observable["blocks"]],
                dtype=float,
            )
            for _, observable in entries
        ]
        e_blocks = [
            np.array([row["e_density"] for row in observable["blocks"]], dtype=float)
            for _, observable in entries
        ]
        m_blocks = [
            np.array([row["m_density"] for row in observable["blocks"]], dtype=float)
            for _, observable in entries
        ]
        h_means = np.array([np.mean(values) for values in h_blocks])
        e_means = np.array([np.mean(values) for values in e_blocks])
        m_means = np.array([np.mean(values) for values in m_blocks])
        replica_h[size], replica_e[size], replica_m[size] = h_means, e_means, m_means
        doubled = [
            0.5 * (values[0::2] + values[1::2])
            for values in h_blocks
            if values.size % 2 == 0
        ]
        h_se = standard_error(h_means)
        e_se = standard_error(e_means)
        m_se = standard_error(m_means)
        signal = math.pi * 0.447 / (6.0 * size**2)
        summary.append(
            {
                "L": size,
                "replicas": len(entries),
                "blocks_per_replica": int(h_blocks[0].size),
                "measurement_rows_per_replica": int(
                    entries[0][0]["result"]["measurement_rows"]
                ),
                "mean_h": float(np.mean(h_means)),
                "replica_standard_error_h": h_se,
                "mean_e_density": float(np.mean(e_means)),
                "replica_standard_error_e_density": e_se,
                "e_density_distance_standard_errors": (
                    abs(float(np.mean(e_means)) - 0.375) / e_se
                ),
                "mean_m_density": float(np.mean(m_means)),
                "replica_standard_error_m_density": m_se,
                "m_density_distance_standard_errors": (
                    abs(float(np.mean(m_means)) - 0.375) / m_se
                ),
                "casimir_signal_anchor_c_0p447": signal,
                "casimir_signal_to_replica_error": signal / h_se,
                "maximum_absolute_adjacent_block_correlation": float(
                    max(abs(lag_one(values)) for values in h_blocks)
                ),
                "median_absolute_adjacent_block_correlation": float(
                    np.median([abs(lag_one(values)) for values in h_blocks])
                ),
                "block_doubling_mean_shift": float(
                    abs(
                        np.mean([np.mean(values) for values in doubled])
                        - np.mean(h_means)
                    )
                ),
                "median_rows_per_second": float(
                    np.median(
                        [item[0]["result"]["rows_per_second"] for item in entries]
                    )
                ),
            }
        )

    sizes = np.array([row["L"] for row in summary], dtype=float)
    values = np.array([row["mean_h"] for row in summary])
    errors = np.array([row["replica_standard_error_h"] for row in summary])
    count = int(declaration["bootstrap_samples"])
    rng = np.random.default_rng(int(declaration["bootstrap_seed"]))
    bootstrap_values = np.empty((count, sizes.size), dtype=float)
    for column, size in enumerate(sizes.astype(int)):
        means = replica_h[size]
        indices = rng.integers(0, means.size, size=(count, means.size))
        bootstrap_values[:, column] = np.mean(means[indices], axis=1)

    fits: list[dict[str, Any]] = []
    bootstrap_charges: dict[str, np.ndarray] = {}
    for model, key in (("M1", "stability_m1_lmin"), ("M0", "stability_m0_lmin")):
        for lmin_value in declaration[key]:
            lmin = int(lmin_value)
            record, charges = fit_record(
                model=model,
                lmin=lmin,
                sizes=sizes,
                values=values,
                errors=errors,
                bootstrap_values=bootstrap_values,
                declaration=declaration,
            )
            fits.append(record)
            bootstrap_charges[f"{model}_Lmin{lmin}"] = charges

    candidates = [
        next(
            fit
            for fit in fits
            if fit["model"] == declaration["main_model"]
            and fit["lmin"] == int(lmin)
        )
        for lmin in declaration["main_candidates_lmin"]
    ]
    passing = [fit for fit in candidates if fit["passes_primary_quality_rule"]]
    primary = passing[0] if passing else candidates[-1]
    primary_selection_passed = bool(passing)
    primary_index = candidates.index(primary)
    adjacent = (
        candidates[primary_index + 1]
        if primary_index + 1 < len(candidates)
        else candidates[primary_index - 1]
    )
    m0_reference = next(
        fit
        for fit in fits
        if fit["model"] == "M0"
        and fit["lmin"] == int(declaration["acceptance_m0_reference_lmin"])
    )

    def stability(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        difference = abs(
            left["central_charge_bootstrap_median"]
            - right["central_charge_bootstrap_median"]
        )
        combined = math.hypot(
            left["central_charge_bootstrap_standard_deviation"],
            right["central_charge_bootstrap_standard_deviation"],
        )
        distance = difference / combined
        return {
            "left": f"{left['model']}/Lmin={left['lmin']}",
            "right": f"{right['model']}/Lmin={right['lmin']}",
            "absolute_difference": difference,
            "combined_standard_deviation": combined,
            "distance_combined_sigma": distance,
            "passes": (
                distance
                <= float(
                    declaration["acceptance"][
                        "maximum_stability_distance_combined_sigma"
                    ]
                )
            ),
        }

    stability_checks = [
        stability(primary, adjacent),
        stability(primary, m0_reference),
    ]
    target_low, target_high = declaration["acceptance"]["target_interval"]
    ci_low, ci_high = primary["central_charge_bootstrap_95_interval"]
    density_limit = float(
        declaration["acceptance"]["density_maximum_distance_standard_errors"]
    )
    acceptance = {
        "all_512_cells_valid": len(seeds) == len(spec["cells"]) == 512,
        "probability_normalization": (
            maximum_probability_error
            <= float(
                declaration["acceptance"][
                    "maximum_probability_normalization_error"
                ]
            )
        ),
        "qr_orthogonality": (
            maximum_qr_error
            <= float(
                declaration["acceptance"]["maximum_qr_orthogonality_error"]
            )
        ),
        "all_size_standard_errors_at_target": all(
            row["replica_standard_error_h"]
            <= float(declaration["acceptance"]["maximum_standard_error"])
            for row in summary
        ),
        "e_density_consistent": all(
            row["e_density_distance_standard_errors"] <= density_limit
            for row in summary
        ),
        "m_density_consistent": all(
            row["m_density_distance_standard_errors"] <= density_limit
            for row in summary
        ),
        "primary_selection_quality_rule": primary_selection_passed,
        "primary_95_interval_intersects_target": (
            ci_high >= target_low and ci_low <= target_high
        ),
        "m0_m1_and_adjacent_windows_stable": all(
            item["passes"] for item in stability_checks
        ),
        "largest_size_signal_to_noise": (
            summary[-1]["casimir_signal_to_replica_error"]
            >= float(
                declaration["acceptance"][
                    "minimum_largest_size_signal_to_noise"
                ]
            )
        ),
        "all_bootstrap_fits_valid": all(
            fit["bootstrap_failures"]
            <= int(declaration["acceptance"]["maximum_bootstrap_failures"])
            for fit in fits
        ),
    }
    metrics = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "cells": len(seeds),
        "sizes": sizes.astype(int).tolist(),
        "replicas_per_size": 64,
        "bootstrap_samples": count,
        "maximum_probability_normalization_error": maximum_probability_error,
        "maximum_qr_orthogonality_error": maximum_qr_error,
        "maximum_covariance_purity_residual": maximum_purity_error,
        "primary_fit": primary,
        "stability_checks": stability_checks,
        "acceptance": acceptance,
        "passes": all(acceptance.values()),
    }
    write_csv(output / "size-summary.csv", summary)
    write_csv(
        output / "fit-summary.csv",
        [
            {
                "model": fit["model"],
                "lmin": fit["lmin"],
                "lmax": fit["lmax"],
                "central_charge": fit["central_charge"],
                "analytic_error": fit["central_charge_analytic_error"],
                "bootstrap_median": fit["central_charge_bootstrap_median"],
                "bootstrap_standard_deviation": fit[
                    "central_charge_bootstrap_standard_deviation"
                ],
                "bootstrap_95_low": fit["central_charge_bootstrap_95_interval"][0],
                "bootstrap_95_high": fit["central_charge_bootstrap_95_interval"][1],
                "reduced_chi_squared": fit["reduced_chi_squared"],
                "condition_number": fit["design_condition_number"],
                "quality_rule": fit["passes_primary_quality_rule"],
                "bootstrap_failures": fit["bootstrap_failures"],
            }
            for fit in fits
        ],
    )
    np.savez_compressed(
        output / "bootstrap-samples.npz",
        h_by_size=bootstrap_values,
        sizes=sizes,
        **bootstrap_charges,
    )
    atomic_json(output / "fits.json", fits)
    atomic_json(output / "metrics.json", metrics)
    atomic_json(output / "declaration.json", declaration)
    atomic_json(output / "failures.json", failures)
    svg_series(output / "finite-size-fit.svg", summary, primary)
    svg_stability(output / "fit-stability.svg", fits)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0 if metrics["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
