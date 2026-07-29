#!/usr/bin/env python3
"""Validate, aggregate, bootstrap, and fit the Stage-3 RBIM production run."""

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


def longest_sign_run(values: np.ndarray) -> int:
    signs = np.sign(values)
    longest = 0
    current = 0
    previous = 0.0
    for sign in signs:
        if sign == 0.0:
            current = 0
        elif sign == previous:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous = sign
    return longest


def fit_record(
    *,
    model: str,
    lmin: int,
    sizes: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    bootstrap_values: np.ndarray,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    selected = sizes >= lmin
    fit_sizes = sizes[selected]
    fit_values = values[selected]
    fit_errors = errors[selected]
    result = fit_casimir(
        fit_sizes,
        fit_values,
        errors=fit_errors,
        model=model,
        quantity="phi",
        alpha=float(declaration["alpha"]),
    )
    charges, failures = fit_bootstrap_samples(
        fit_sizes,
        bootstrap_values[:, selected],
        errors=fit_errors,
        model=model,
        quantity="phi",
        alpha=float(declaration["alpha"]),
    )
    valid = charges[np.isfinite(charges)]
    if valid.size < int(declaration["bootstrap_samples"]):
        raise RuntimeError(
            f"{model} Lmin={lmin}: only {valid.size} valid bootstrap fits"
        )
    quantiles = np.quantile(valid, [0.025, 0.16, 0.5, 0.84, 0.975])
    standardized = result.residuals / fit_errors
    rule = declaration["primary_selection_rule"]
    quality_checks = {
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
    return {
        "model": model,
        "lmin": lmin,
        "lmax": int(fit_sizes.max()),
        "sizes": fit_sizes.astype(int).tolist(),
        "n_sizes": int(fit_sizes.size),
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
        "quality_checks": quality_checks,
        "passes_primary_quality_rule": all(quality_checks.values()),
    }


def svg_series(
    path: Path,
    summary: list[dict[str, Any]],
    primary: dict[str, Any],
) -> None:
    width, height = 940, 500
    left, top, plot_width, plot_height = 95, 55, 760, 350
    sizes = np.array([row["L"] for row in summary], dtype=float)
    x_values = sizes**-2
    y_values = np.array([row["mean_phi"] for row in summary])
    errors = np.array([row["replica_standard_error"] for row in summary])
    x_min, x_max = 0.0, float(x_values.max() * 1.06)
    y_pad = max(float(np.ptp(y_values)) * 0.08, float(errors.max() * 6.0))
    y_min, y_max = float(y_values.min() - y_pad), float(y_values.max() + y_pad)

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    coefficients = np.asarray(primary["coefficients"], dtype=float)
    fit_x = np.linspace(0.0, float((primary["lmin"] ** -2)), 300)
    fit_y = coefficients[0] + coefficients[1] * fit_x
    if primary["model"] == "M1":
        fit_y += coefficients[2] * fit_x**2
    points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(fit_x, fit_y))
    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">Nishimori RBIM quenched free-energy scaling</text>',
        f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#111827"/>',
        f'<polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="2"/>',
    ]
    for size, x_value, y_value, error in zip(sizes, x_values, y_values, errors):
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
            f'<text x="24" y="{top+plot_height/2}" transform="rotate(-90 24 {top+plot_height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">phi_L</text>',
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
    y_low = min(y_low, 0.459)
    y_high = max(y_high, 0.469)
    x_values = np.arange(len(fits), dtype=float)

    def sx(value: float) -> float:
        return left + (value + 0.4) / max(len(fits) - 0.2, 1.0) * plot_width

    def sy(value: float) -> float:
        return top + (y_high - value) / (y_high - y_low) * plot_height

    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">Central-charge fit-window stability</text>',
        f'<rect x="{left}" y="{sy(0.468):.2f}" width="{plot_width}" height="{sy(0.460)-sy(0.468):.2f}" fill="#dcfce7"/>',
        f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#111827"/>',
    ]
    for x_value, fit in zip(x_values, fits):
        low, high = fit["central_charge_bootstrap_95_interval"]
        median = fit["central_charge_bootstrap_median"]
        x_pixel = sx(x_value)
        elements.extend(
            [
                f'<line x1="{x_pixel:.2f}" y1="{sy(low):.2f}" x2="{x_pixel:.2f}" y2="{sy(high):.2f}" stroke="#2563eb" stroke-width="2"/>',
                f'<circle cx="{x_pixel:.2f}" cy="{sy(median):.2f}" r="4" fill="#1d4ed8"/>',
                f'<text x="{x_pixel:.2f}" y="{top+plot_height+22}" text-anchor="middle" font-family="sans-serif" font-size="11">{fit["model"]}/{fit["lmin"]}</text>',
            ]
        )
    elements.extend(
        [
            f'<text x="{left+plot_width/2}" y="465" text-anchor="middle" font-family="sans-serif" font-size="15">model / Lmin</text>',
            f'<text x="24" y="{top+plot_height/2}" transform="rotate(-90 24 {top+plot_height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">effective central charge c</text>',
        ]
    )
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        + "\n".join(elements)
        + "\n</svg>\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run = args.run.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    declaration = json.loads(args.declaration.read_text(encoding="utf-8"))
    spec = json.loads((run / "run_spec.json").read_text(encoding="utf-8"))
    expected_bootstrap = int(declaration["bootstrap_samples"])

    failures: list[str] = []
    by_size: dict[int, list[tuple[dict[str, Any], np.ndarray]]] = {}
    settings_payloads: set[str] = set()
    provenance_payloads: set[str] = set()
    rng_fingerprints: set[str] = set()
    for cell in spec["cells"]:
        cell_id = cell["cell_id"]
        cell_dir = run / "cells" / cell_id
        manifest_path = cell_dir / "manifest.json"
        if not manifest_path.is_file():
            failures.append(f"{cell_id}: missing manifest")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            failures.append(f"{cell_id}: status={manifest.get('status')}")
            continue
        if manifest.get("params") != cell["params"]:
            failures.append(f"{cell_id}: parameter mismatch")
            continue
        settings_payloads.add(json.dumps(manifest["settings"], sort_keys=True))
        provenance_payloads.add(json.dumps(manifest["provenance"], sort_keys=True))
        fingerprint = str(manifest["result"]["rng_fingerprint"])
        if fingerprint in rng_fingerprints:
            failures.append(f"{cell_id}: duplicate RNG fingerprint")
            continue
        rng_fingerprints.add(fingerprint)
        block_path = cell_dir / manifest["artifacts"]["block_phi"]
        if not block_path.is_file():
            failures.append(f"{cell_id}: missing block data")
            continue
        if sha256(block_path) != manifest["artifacts"]["block_phi_sha256"]:
            failures.append(f"{cell_id}: block checksum mismatch")
            continue
        blocks = np.load(block_path, allow_pickle=False)
        expected_blocks = (
            int(manifest["result"]["measurement_rows"])
            // int(manifest["result"]["block_size"])
        )
        if (
            blocks.ndim != 1
            or blocks.size != expected_blocks
            or not np.all(np.isfinite(blocks))
        ):
            failures.append(f"{cell_id}: invalid block array")
            continue
        size = int(manifest["params"]["size"])
        by_size.setdefault(size, []).append((manifest, blocks))
    if failures:
        atomic_json(output / "failures.json", failures)
        raise RuntimeError(f"production has {len(failures)} invalid cells")
    if len(settings_payloads) != 1 or len(provenance_payloads) != 1:
        raise RuntimeError("production settings or provenance lack consensus")

    summary: list[dict[str, Any]] = []
    replica_means_by_size: dict[int, np.ndarray] = {}
    for size in sorted(by_size):
        entries = sorted(by_size[size], key=lambda item: item[0]["params"]["replica"])
        if len(entries) != 32:
            raise RuntimeError(f"L={size}: expected 32 replicas, found {len(entries)}")
        replica_means = np.array([np.mean(blocks) for _, blocks in entries])
        replica_means_by_size[size] = replica_means
        all_blocks = np.concatenate([blocks for _, blocks in entries])
        ensemble_mean = float(np.mean(replica_means))
        replica_se = float(np.std(replica_means, ddof=1) / math.sqrt(len(entries)))
        block_se = float(np.std(all_blocks, ddof=1) / math.sqrt(all_blocks.size))
        signal = math.pi * 0.464 / (6.0 * size**2)
        summary.append(
            {
                "L": size,
                "replicas": len(entries),
                "blocks": int(all_blocks.size),
                "rows": int(
                    sum(m["result"]["measurement_rows"] for m, _ in entries)
                ),
                "block_size": int(entries[0][0]["result"]["block_size"]),
                "mean_phi": ensemble_mean,
                "replica_standard_error": replica_se,
                "independent_block_standard_error": block_se,
                "standard_error_ratio_replica_to_block": replica_se / block_se,
                "casimir_signal_anchor_c_0p464": signal,
                "casimir_signal_to_replica_error": signal / replica_se,
                "median_rows_per_second": float(
                    np.median(
                        [m["result"]["rows_per_second"] for m, _ in entries]
                    )
                ),
                "maximum_absolute_cell_block_correlation": float(
                    max(
                        abs(m["result"]["adjacent_block_correlation"])
                        for m, _ in entries
                    )
                ),
                "maximum_orthogonality_error": float(
                    max(
                        m["result"]["maximum_orthogonality_error"]
                        for m, _ in entries
                    )
                ),
            }
        )

    sizes = np.array([row["L"] for row in summary], dtype=float)
    values = np.array([row["mean_phi"] for row in summary])
    errors = np.array([row["replica_standard_error"] for row in summary])
    rng = np.random.default_rng(int(declaration["bootstrap_seed"]))
    bootstrap_values = np.empty((expected_bootstrap, sizes.size), dtype=float)
    for column, size in enumerate(sizes.astype(int)):
        means = replica_means_by_size[size]
        indices = rng.integers(0, means.size, size=(expected_bootstrap, means.size))
        bootstrap_values[:, column] = np.mean(means[indices], axis=1)

    fits: list[dict[str, Any]] = []
    declared_pairs: set[tuple[str, int]] = set()
    for model, key in (
        ("M1", "stability_m1_lmin"),
        ("M0", "stability_m0_lmin"),
    ):
        for lmin in declaration[key]:
            pair = (model, int(lmin))
            if pair in declared_pairs:
                continue
            declared_pairs.add(pair)
            fits.append(
                fit_record(
                    model=model,
                    lmin=int(lmin),
                    sizes=sizes,
                    values=values,
                    errors=errors,
                    bootstrap_values=bootstrap_values,
                    declaration=declaration,
                )
            )

    primary_candidates = [
        fit
        for lmin in declaration["main_candidates_lmin"]
        for fit in fits
        if fit["model"] == declaration["main_model"]
        and fit["lmin"] == int(lmin)
    ]
    passing = [fit for fit in primary_candidates if fit["passes_primary_quality_rule"]]
    primary = passing[0] if passing else primary_candidates[-1]
    primary_selection_passed = bool(passing)
    primary_index = next(
        index for index, fit in enumerate(primary_candidates) if fit is primary
    )
    adjacent = (
        primary_candidates[primary_index + 1]
        if primary_index + 1 < len(primary_candidates)
        else primary_candidates[primary_index - 1]
    )
    m0_candidates = [fit for fit in fits if fit["model"] == "M0"]
    m0_reference = next(
        fit
        for fit in m0_candidates
        if fit["lmin"] == int(declaration["acceptance_m0_reference_lmin"])
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
    primary_low, primary_high = primary["central_charge_bootstrap_95_interval"]
    acceptance = {
        "primary_selection_quality_rule": primary_selection_passed,
        "primary_95_interval_intersects_target": (
            primary_high >= target_low and primary_low <= target_high
        ),
        "m0_m1_and_adjacent_windows_stable": all(
            check["passes"] for check in stability_checks
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
        "internal_upstream_baseline": "evaluated separately in Stage 3A",
        "critical_probability_propagation": "evaluated separately in cross-check job",
    }
    metrics = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "all_cells_success": True,
        "cells": len(spec["cells"]),
        "sizes": sizes.astype(int).tolist(),
        "replicas_per_size": 32,
        "settings_consensus": len(settings_payloads) == 1,
        "provenance_consensus": len(provenance_payloads) == 1,
        "unique_rng_fingerprints": len(rng_fingerprints),
        "bootstrap_samples": expected_bootstrap,
        "primary_fit": {
            "model": primary["model"],
            "lmin": primary["lmin"],
            "central_charge": primary["central_charge"],
            "bootstrap_median": primary["central_charge_bootstrap_median"],
            "bootstrap_standard_deviation": primary[
                "central_charge_bootstrap_standard_deviation"
            ],
            "bootstrap_68_interval": primary[
                "central_charge_bootstrap_68_interval"
            ],
            "bootstrap_95_interval": primary[
                "central_charge_bootstrap_95_interval"
            ],
            "reduced_chi_squared": primary["reduced_chi_squared"],
        },
        "primary_selection_passed_quality_rule": primary_selection_passed,
        "stability_checks": stability_checks,
        "acceptance": acceptance,
    }
    write_csv(output / "size-summary.csv", summary)
    fit_rows = [
        {
            "model": fit["model"],
            "lmin": fit["lmin"],
            "lmax": fit["lmax"],
            "n_sizes": fit["n_sizes"],
            "central_charge": fit["central_charge"],
            "analytic_error": fit["central_charge_analytic_error"],
            "bootstrap_median": fit["central_charge_bootstrap_median"],
            "bootstrap_standard_deviation": fit[
                "central_charge_bootstrap_standard_deviation"
            ],
            "bootstrap_68_low": fit["central_charge_bootstrap_68_interval"][0],
            "bootstrap_68_high": fit["central_charge_bootstrap_68_interval"][1],
            "bootstrap_95_low": fit["central_charge_bootstrap_95_interval"][0],
            "bootstrap_95_high": fit["central_charge_bootstrap_95_interval"][1],
            "chi_squared": fit["chi_squared"],
            "degrees_of_freedom": fit["degrees_of_freedom"],
            "reduced_chi_squared": fit["reduced_chi_squared"],
            "condition_number": fit["design_condition_number"],
            "max_abs_standardized_residual": fit[
                "maximum_absolute_standardized_residual"
            ],
            "quality_rule": fit["passes_primary_quality_rule"],
            "bootstrap_failures": fit["bootstrap_failures"],
        }
        for fit in fits
    ]
    write_csv(output / "fit-summary.csv", fit_rows)
    atomic_json(output / "fits.json", fits)
    atomic_json(output / "metrics.json", metrics)
    atomic_json(output / "declaration.json", declaration)
    svg_series(output / "finite-size-fit.svg", summary, primary)
    svg_stability(output / "fit-stability.svg", fits)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
