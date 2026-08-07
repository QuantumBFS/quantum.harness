#!/usr/bin/env python3
"""Run and freeze the numerical ensemble-budget pilot."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.production_v2_manifest import sha256_file
from src.two_mode_forward_refinement import (
    audit_deterministic_forward_refinement,
)
from src.two_mode_nlfh import TwoModeParams, equilibrium_variance_sanity
from src.two_mode_solver_budget import audit_ensemble_budget


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "two_mode_solver_budget_20260730.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results_research_program" / "two_mode" / "solver_budget.json",
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if int(config.get("schema_version", -1)) != 1:
        raise SystemExit("unsupported solver-budget schema")
    pilot = config["pilot"]
    params = TwoModeParams(**pilot["params"])
    summaries: list[dict[str, object]] = []
    for ensemble in config["candidate_ensembles"]:
        summary = equilibrium_variance_sanity(
            params=params,
            n_cells=int(pilot["n_cells"]),
            n_ensemble=int(ensemble),
            n_steps=int(pilot["n_steps"]),
            dt=float(pilot["dt"]),
            dx=float(pilot["dx"]),
            seed=int(config["seed"]),
        )
        summary["n_ensemble"] = int(ensemble)
        summaries.append(summary)
    audit = audit_ensemble_budget(
        summaries,
        relative_tolerance=float(config["observable_relative_change_max"]),
        conservation_tolerance=float(config["conservation_error_max"]),
        variance_tolerance=float(config["variance_relative_error_max"]),
        skewness_tolerance=float(config["current_skewness_abs_max"]),
        screening_minimum=int(config["screening_ensemble"]),
        final_minimum=int(config["minimum_final_ensemble"]),
    )
    refinement = audit_deterministic_forward_refinement(
        config["forward_refinement"]
    )
    if refinement["status"] != "pass":
        audit["status"] = "blocked"
    source_paths = (
        "src/two_mode_nlfh.py",
        "src/two_mode_solver_budget.py",
        "src/two_mode_forward_refinement.py",
        "scripts/run_two_mode_solver_budget.py",
    )
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": audit["status"],
        "config_path": str(args.config.resolve()),
        "config_sha256": sha256_file(args.config),
        "source_sha256": {
            relative: sha256_file(ROOT / relative) for relative in source_paths
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "quantum_fit_error_used": False,
        "candidate_summaries": summaries,
        "forward_refinement": refinement,
        **audit,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "screening_ensemble": payload["screening_ensemble"],
                "final_ensemble": payload["final_ensemble"],
                "requires_extended_budget": payload["requires_extended_budget"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
