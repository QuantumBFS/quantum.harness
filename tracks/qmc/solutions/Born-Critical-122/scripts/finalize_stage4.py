#!/usr/bin/env python3
"""Combine Stage-4 production, cross-check, and regression verdicts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--crosschecks", type=Path, required=True)
    parser.add_argument("--regression", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    production = json.loads(args.production.read_text(encoding="utf-8"))
    crosschecks = json.loads(args.crosschecks.read_text(encoding="utf-8"))
    regression = json.loads(args.regression.read_text(encoding="utf-8"))
    acceptance = production["acceptance"]
    gates = {
        "production_all_cells_and_numerics": all(
            acceptance[key]
            for key in (
                "all_512_cells_valid",
                "probability_normalization",
                "qr_orthogonality",
                "all_size_standard_errors_at_target",
            )
        ),
        "casimir_target_and_fit_stability": all(
            acceptance[key]
            for key in (
                "primary_selection_quality_rule",
                "primary_95_interval_intersects_target",
                "m0_m1_and_adjacent_windows_stable",
                "largest_size_signal_to_noise",
                "all_bootstrap_fits_valid",
            )
        ),
        "selfdual_vortex_densities": (
            acceptance["e_density_consistent"]
            and acceptance["m_density_consistent"]
        ),
        "exact_and_metropolis_crosschecks": (
            crosschecks["gates"][
                "dense_contraction_matches_gaussian_chain"
            ]
            and crosschecks["gates"][
                "metropolis_observables_match_sequential_born"
            ]
        ),
        "isotropy_alpha_one": crosschecks["gates"][
            "isotropic_construction_supports_alpha_one"
        ],
        "full_slurm_regression": regression.get("status") == "success",
    }
    payload = {
        "schema_version": 1,
        "stage": "stage4",
        "production_run_id": production["run_id"],
        "production_cells": production["cells"],
        "bootstrap_samples": production["bootstrap_samples"],
        "primary_fit": production["primary_fit"],
        "production_acceptance": acceptance,
        "crosscheck_job": crosschecks["slurm_job_id"],
        "regression_job": regression.get("slurm", {}).get("job_id"),
        "gates": gates,
        "passes": all(gates.values()),
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
