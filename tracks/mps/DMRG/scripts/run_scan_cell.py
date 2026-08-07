#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.config import load_experiment_config
from vmcrg_ref.scan import resolve_run_spec_cell
from vmcrg_ref.workflow import run_full_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute one opaque chi x seed run-spec cell")
    parser.add_argument("--run-spec", type=Path, default=os.environ.get("HARNESS_RUN_SPEC"))
    parser.add_argument("--array-index", type=int, default=os.environ.get("SLURM_ARRAY_TASK_ID"))
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if args.run_spec is None or args.array_index is None:
        raise ValueError("run spec and one-based array index are required")
    cell = resolve_run_spec_cell(args.run_spec, int(args.array_index))
    chi = int(cell.params["chi"])
    seed = int(cell.params["seed"])
    if chi not in (2, 4, 8):
        raise ValueError(f"unsupported formal chi={chi}")
    config = load_experiment_config(ROOT / f"config/mps_chi{chi}.toml")
    expected = {
        "length": config.model.length,
        "coupling": config.model.coupling,
        "rg_levels": config.model.rg_levels,
        "operator_count": config.model.operator_count,
        "walkers": config.training.walkers,
        "baseline_steps": config.training.baseline_steps,
        "residual_steps": config.training.residual_steps,
        "sweeps_per_step": config.training.sweeps_per_step,
        "measurement_sweeps": config.measurement.measurement_sweeps,
    }
    for key, value in expected.items():
        if cell.settings.get(key) != value:
            raise ValueError(f"run-spec setting mismatch for {key}: {cell.settings.get(key)} != {value}")
    output_root = args.output_root or Path(cell.run_dir)
    output = output_root / "cells" / cell.cell_id
    try:
        summary = run_full_experiment(config, seed=seed, output=output)
        manifest = {
            "success": True,
            "cell_id": cell.cell_id,
            "params": cell.params,
            "settings": cell.settings,
            "provenance": cell.provenance,
            "metrics": {
                "objective": summary["training"]["final_record"]["objective"],
                "patch_tv": summary["evaluation"]["traditional_mps"]["patch_distances"]["total_variation"],
                "tau_int": summary["evaluation"]["traditional_mps"]["autocorrelation"]["tau_int"],
                "ess_per_second": summary["evaluation"]["traditional_mps"]["autocorrelation"]["ess_per_second"],
            },
        }
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        manifest = {
            "success": False,
            "cell_id": cell.cell_id,
            "params": cell.params,
            "settings": cell.settings,
            "provenance": cell.provenance,
            "error_type": type(error).__name__,
            "error": str(error),
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        raise
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"cell={cell.cell_id} chi={chi} seed={seed} success", flush=True)


if __name__ == "__main__":
    main()
