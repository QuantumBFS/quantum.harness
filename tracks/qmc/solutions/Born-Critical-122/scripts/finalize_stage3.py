#!/usr/bin/env python3
"""Merge Stage-3 evidence into one machine-readable acceptance verdict."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--crosschecks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = load(args.baseline)
    pilot = load(args.pilot)
    production = load(args.production)
    crosschecks = load(args.crosschecks)
    primary = production["primary_fit"]
    pc_span = crosschecks["pc_sensitivity"][
        "central_charge_absolute_half_span"
    ]
    pc_passes = pc_span < primary["bootstrap_standard_deviation"]
    production_acceptance = production["acceptance"]
    gates = {
        "stage3a_internal_upstream_baseline": bool(
            baseline["all_gates_passed"]
        ),
        "stage3b_pilot_all_cells": bool(pilot["all_cells_success"]),
        "stage3b_qr_interval_frozen": int(pilot["selected_qr_interval"]) == 5,
        "stage3c_production_all_cells": bool(
            production["all_cells_success"]
        ),
        "stage3d_primary_fit_quality": bool(
            production_acceptance["primary_selection_quality_rule"]
        ),
        "stage3d_target_interval": bool(
            production_acceptance["primary_95_interval_intersects_target"]
        ),
        "stage3d_window_stability": bool(
            production_acceptance["m0_m1_and_adjacent_windows_stable"]
        ),
        "stage3d_largest_size_signal": bool(
            production_acceptance["largest_size_signal_to_noise"]
        ),
        "stage3d_bootstrap_valid": bool(
            production_acceptance["all_bootstrap_fits_valid"]
        ),
        "stage3d_pc_uncertainty_subdominant": pc_passes,
        "crosscheck_clean_limit": bool(
            crosschecks["gates"]["clean_limit"]
        ),
        "crosscheck_upstream_complete_distribution": bool(
            crosschecks["gates"]["upstream_complete_distribution"]
        ),
        "crosscheck_parity_defect": bool(
            crosschecks["gates"]["parity_defect_finite"]
        ),
    }
    verdict = {
        "schema_version": 1,
        "stage": "stage3-nishimori-rbim",
        "status": "passed" if all(gates.values()) else "failed",
        "primary_fit": primary,
        "critical_probability_propagation": {
            "absolute_c_half_span": pc_span,
            "production_bootstrap_standard_deviation": primary[
                "bootstrap_standard_deviation"
            ],
            "ratio": pc_span / primary["bootstrap_standard_deviation"],
            "passes": pc_passes,
        },
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output, verdict)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["all_gates_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
