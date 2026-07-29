#!/usr/bin/env python3
"""Aggregate Stage-4C pilot diagnostics and project production cost."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics

import numpy as np

from borncritical.casimir_fit import fit_casimir


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def standard_error(values: list[float]) -> float:
    return statistics.stdev(values) / math.sqrt(len(values))


def lag_one(values: list[float]) -> float:
    if len(values) < 3:
        return math.nan
    mean = statistics.fmean(values)
    denominator = sum((value - mean) ** 2 for value in values)
    if denominator == 0.0:
        return 0.0
    return sum(
        (left - mean) * (right - mean)
        for left, right in zip(values[:-1], values[1:], strict=True)
    ) / denominator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    spec = json.loads((run / "run_spec.json").read_text())
    # Pilot v1/v2 predate the explicit field but their stored cycle rates are
    # otherwise valid.  A cycle contains MZ and MX, i.e. two paper Ly steps.
    sublayers_per_cycle = int(
        spec["settings"].get("spacetime_sublayers_per_cycle", 2)
    )
    stored_rates_are_per_cycle = all(
        "spacetime_sublayers" not in block
        for cell in spec["cells"][:1]
        for block in (
            json.loads(
                (
                    run
                    / "cells"
                    / cell["cell_id"]
                    / "observables.json"
                ).read_text()
            ).get("blocks", [])[:1]
        )
    )
    rate_normalization = (
        1.0 / sublayers_per_cycle if stored_rates_are_per_cycle else 1.0
    )
    manifests = {}
    observables = {}
    failures = []
    for cell in spec["cells"]:
        cell_id = cell["cell_id"]
        root = run / "cells" / cell_id
        if not (root / "manifest.json").exists():
            failures.append({"cell_id": cell_id, "reason": "missing"})
            continue
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest.get("status") != "success":
            failures.append({"cell_id": cell_id, "reason": manifest.get("status")})
            continue
        manifests[cell_id] = manifest
        observables[cell_id] = json.loads((root / "observables.json").read_text())

    sizes: dict[str, object] = {}
    for size in (4, 6, 8, 10, 12):
        selected = [
            manifest
            for manifest in manifests.values()
            if manifest["params"]["size"] == size
            and manifest["params"]["role"] == "main"
        ]
        h = [
            rate_normalization * item["result"]["mean_shannon_rate"]
            for item in selected
        ]
        rb_h = [
            (
                None
                if item["result"].get("mean_rao_blackwell_shannon_rate") is None
                else rate_normalization
                * item["result"]["mean_rao_blackwell_shannon_rate"]
            )
            for item in selected
        ]
        has_rao_blackwell = all(value is not None for value in rb_h)
        e = [item["result"]["mean_e_density"] for item in selected]
        m = [item["result"]["mean_m_density"] for item in selected]
        rates = [item["result"]["rows_per_second"] for item in selected]
        correlations = []
        for item in selected:
            blocks = observables[item["cell_id"]]["blocks"]
            correlations.append(lag_one([row["shannon_rate"] for row in blocks]))
        h_se = standard_error(h)
        rb_h_values = [float(value) for value in rb_h if value is not None]
        rb_h_se = standard_error(rb_h_values) if has_rao_blackwell else math.nan
        target_se = min(
            2e-6, 0.05 * math.pi * 0.447 / (6.0 * size * size)
        )
        rows_now = int(spec["settings"]["measurement_rows"])
        rows_required = math.ceil(rows_now * (h_se / target_se) ** 2)
        rb_rows_required = (
            math.ceil(rows_now * (rb_h_se / target_se) ** 2)
            if has_rao_blackwell
            else None
        )
        trajectory_seconds = rows_required / statistics.median(rates)
        sizes[str(size)] = {
            "replicas": len(selected),
            "mean_shannon_rate": statistics.fmean(h),
            "standard_error_shannon_rate": h_se,
            "mean_rao_blackwell_shannon_rate": (
                statistics.fmean(rb_h_values) if has_rao_blackwell else None
            ),
            "standard_error_rao_blackwell_shannon_rate": (
                rb_h_se if has_rao_blackwell else None
            ),
            "mean_e_density": statistics.fmean(e),
            "standard_error_e_density": standard_error(e),
            "mean_m_density": statistics.fmean(m),
            "standard_error_m_density": standard_error(m),
            "maximum_abs_adjacent_block_correlation": max(
                abs(value) for value in correlations
            ),
            "median_rows_per_second": statistics.median(rates),
            "target_standard_error": target_se,
            "projected_rows_per_trajectory_at_16_replicas": rows_required,
            "projected_hours_per_trajectory": trajectory_seconds / 3600.0,
            "projected_node_hours_at_16_replicas": (
                16.0 * trajectory_seconds / 3600.0
            ),
            "rao_blackwell_projected_rows_per_trajectory_at_16_replicas": (
                rb_rows_required
            ),
            "rao_blackwell_projected_node_hours_at_16_replicas": (
                None
                if rb_rows_required is None
                else 16.0
                * rb_rows_required
                / statistics.median(rates)
                / 3600.0
            ),
        }

    qr_stability = {}
    for size in (4, 6, 8, 10, 12):
        values = {}
        for interval in (1, 2, 4, 8):
            cell_id = f"L{size:02d}-r000-q{interval:02d}"
            if cell_id not in observables:
                continue
            blocks = observables[cell_id]["blocks"]
            values[str(interval)] = {
                "mean_shannon_rate": statistics.fmean(
                    row["shannon_rate"] for row in blocks
                ),
                "maximum_exponent": blocks[-1]["maximum_exponent"],
                "maximum_orthogonality_error": max(
                    row["qr_orthogonality_error"] for row in blocks
                ),
            }
        if len(values) < 2:
            continue
        reference = values[min(values, key=int)]
        qr_stability[str(size)] = {
            "by_interval": values,
            "maximum_shannon_difference": max(
                abs(value["mean_shannon_rate"] - reference["mean_shannon_rate"])
                for value in values.values()
            ),
            "maximum_exponent_difference": max(
                abs(value["maximum_exponent"] - reference["maximum_exponent"])
                for value in values.values()
            ),
        }

    all_manifests = list(manifests.values())
    fit_rows = []
    ordered_sizes = np.array(sorted(int(value) for value in sizes), dtype=float)
    ordered_values = np.array(
        [
            sizes[str(int(size))]["mean_rao_blackwell_shannon_rate"]
            for size in ordered_sizes
        ],
        dtype=float,
    )
    ordered_errors = np.array(
        [
            sizes[str(int(size))][
                "standard_error_rao_blackwell_shannon_rate"
            ]
            for size in ordered_sizes
        ],
        dtype=float,
    )
    for model, minimum_size in (("M1", 4), ("M1", 6), ("M0", 6), ("M0", 8)):
        mask = ordered_sizes >= minimum_size
        if np.count_nonzero(mask) <= (3 if model == "M1" else 2):
            continue
        fit = fit_casimir(
            ordered_sizes[mask],
            ordered_values[mask],
            errors=ordered_errors[mask],
            model=model,
            quantity="shannon",
        )
        fit_rows.append(
            {
                "model": model,
                "minimum_size": minimum_size,
                "sizes": [int(value) for value in ordered_sizes[mask]],
                "central_charge": fit.central_charge,
                "analytic_standard_error": fit.central_charge_error,
                "chi_squared": fit.chi_squared,
                "degrees_of_freedom": fit.degrees_of_freedom,
                "reduced_chi_squared": fit.reduced_chi_squared,
                "design_condition_number": fit.design_condition_number,
                "well_conditioned": fit.well_conditioned,
                "coefficients": fit.coefficients.tolist(),
                "residuals": fit.residuals.tolist(),
            }
        )
    gates = {
        "all_cells_success": not failures and len(manifests) == len(spec["cells"]),
        "probability_normalization": max(
            item["result"]["maximum_probability_normalization_error"]
            for item in all_manifests
        )
        <= 1e-12,
        "qr_orthogonality": max(
            item["result"]["maximum_qr_orthogonality_error"]
            for item in all_manifests
        )
        <= 1e-9,
        "density_e_within_4se": all(
            abs(value["mean_e_density"] - 0.375)
            <= 4.0 * value["standard_error_e_density"]
            for value in sizes.values()
        ),
        "density_m_within_4se": all(
            abs(value["mean_m_density"] - 0.375)
            <= 4.0 * value["standard_error_m_density"]
            for value in sizes.values()
        ),
        "qr_interval_stable": (
            True
            if not qr_stability
            else max(
                value["maximum_exponent_difference"]
                for value in qr_stability.values()
            )
            <= 5e-10
        ),
    }
    payload = {
        "schema_version": 1,
        "run_id": spec["run_id"],
        "spacetime_sublayers_per_cycle": sublayers_per_cycle,
        "stored_rate_normalization_applied": rate_normalization,
        "cells_expected": len(spec["cells"]),
        "cells_success": len(manifests),
        "failures": failures,
        "sizes": sizes,
        "qr_stability": qr_stability,
        "pilot_fits": fit_rows,
        "gates": gates,
        "passes": all(gates.values()),
    }
    aggregate = run / "aggregate"
    aggregate.mkdir(exist_ok=True)
    atomic_json(aggregate / "pilot_summary.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
