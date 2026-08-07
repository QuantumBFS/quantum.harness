#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.config import load_experiment_config
from vmcrg_ref.workflow import run_full_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one traditional + local-MPS VMCRG cell")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cell-id", default="local")
    args = parser.parse_args()
    config = load_experiment_config(args.config)
    seed = config.run.seeds[0] if args.seed is None else args.seed
    output = args.output or config.run.output / f"seed-{seed}"
    try:
        summary = run_full_experiment(config, seed=seed, output=output)
        manifest = {
            "success": True,
            "cell_id": args.cell_id,
            "params": {"chi": config.mps.chi, "seed": seed},
            "settings": {
                "length": config.model.length,
                "coupling": config.model.coupling,
                "rg_levels": config.model.rg_levels,
                "walkers": config.training.walkers,
                "baseline_steps": config.training.baseline_steps,
                "residual_steps": config.training.residual_steps,
                "sweeps_per_step": config.training.sweeps_per_step,
            },
            "summary": summary,
        }
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        manifest = {
            "success": False,
            "cell_id": args.cell_id,
            "params": {"chi": config.mps.chi, "seed": seed},
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
    print(f"cell complete chi={config.mps.chi} seed={seed} output={output}", flush=True)


if __name__ == "__main__":
    main()
