#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.checkpoint import load_mps_checkpoint
from vmcrg_ref.config import load_experiment_config
from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.workflow import evaluate_three_arms, run_mps_training


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare random and level-1 MPS initialization at RG level 2")
    parser.add_argument("--config", type=Path, default=ROOT / "config/mps_warm_start.toml")
    parser.add_argument("--level1-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    config = load_experiment_config(args.config)
    if config.model.rg_levels != 2:
        raise ValueError("warm-start config must use rg_levels=2")
    checkpoint = load_mps_checkpoint(args.level1_checkpoint)
    if checkpoint.model.chi != config.mps.chi:
        raise ValueError("checkpoint chi does not match warm-start config")
    seed = config.run.seeds[0] if args.seed is None else args.seed
    root = args.output or config.run.output / f"seed-{seed}"
    root.mkdir(parents=True, exist_ok=False)
    arms = {}
    for label, initial_model in (
        ("random", PatchMPS.random(config.mps.chi, seed + 50_000)),
        ("warm", checkpoint.model),
    ):
        arm_root = root / label
        arm_root.mkdir(parents=True)
        model, alpha, training = run_mps_training(
            config,
            seed,
            checkpoint.linear_bias,
            arm_root,
            initial_model=initial_model,
        )
        evaluation = evaluate_three_arms(
            config, seed, checkpoint.linear_bias, model, alpha
        )
        (arm_root / "evaluation.json").write_text(
            json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        arms[label] = {
            "final_objective": training["trajectory"][-1]["objective"],
            "steps": len(training["trajectory"]),
            "alpha": alpha,
            "evaluation": evaluation,
        }
    payload = {
        "seed": seed,
        "rg_levels": 2,
        "linear_bias_source": str(args.level1_checkpoint),
        "control": "same J, walkers, sweeps, optimizer, thresholds, and seed",
        "arms": arms,
    }
    (root / "warm_start_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"warm-start comparison complete output={root}", flush=True)


if __name__ == "__main__":
    main()
