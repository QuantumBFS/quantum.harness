"""Certify that Robbins-Monro VMCRG does not diffuse away from a known solution.

This is the first optimizer gate.  It starts from the independently supervised
identity-RG model, performs stochastic VMCRG updates, freezes the result, and
then applies the existing distribution and complete 13-coupling gates.  It
tests stability only; convergence from random initialization is a separate
later experiment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.neural_challenge import project, read_json, train, validate, write_json


PROTOCOLS = {
    "smoke": {
        "training": dict(walkers=4, steps=5, sweeps=1, targets=8),
        "gradient_accumulation_steps": 2,
        "learning_rate": 0.02,
        "decay_scale": 2.0,
        "decay_power": 0.75,
    },
    "pilot": {
        "training": dict(walkers=8, steps=200, sweeps=2, targets=16),
        "gradient_accumulation_steps": 2,
        "learning_rate": 0.02,
        "decay_scale": 50.0,
        "decay_power": 0.75,
    },
}


def run(
    *,
    preset: str,
    output: Path,
    fixed_point_map: Path,
    initial_model: Path,
    model_seed: int,
    optimizer_seed: int,
    validation_seed: int,
    projection_seed: int,
) -> dict:
    protocol = PROTOCOLS[preset]
    train(
        output,
        "smoke" if preset == "smoke" else "pilot",
        fixed_point_map,
        model_seed=model_seed,
        optimizer_seed=optimizer_seed,
        representation="pure",
        block_size=1,
        length_override=15,
        training_overrides=protocol["training"],
        optimizer_name="robbins_monro_sgd",
        learning_rate_override=protocol["learning_rate"],
        gradient_accumulation_steps=protocol["gradient_accumulation_steps"],
        decay_scale=protocol["decay_scale"],
        decay_power=protocol["decay_power"],
        initial_model_path=initial_model,
    )
    validation = validate(
        output,
        "smoke" if preset == "smoke" else "pilot",
        seed=validation_seed,
        enforce_formal_gate=False,
    )
    projection = project(
        output,
        "smoke" if preset == "smoke" else "pilot",
        seed=projection_seed,
        enforce_formal_gate=False,
    )
    config = read_json(output / "config.json")
    passed = validation["status"] == "PASS" and projection["status"] == "PASS"
    report = {
        "status": "PASS" if passed else "FAIL",
        "experiment": "identity_rg_robbins_monro_stability_certification",
        "scope": "stability_from_certified_checkpoint_not_random_initialization",
        "preset": preset,
        "length": config["length"],
        "block_size": config["block_size"],
        "optimizer_name": config["optimizer_name"],
        "training_steps": config["steps"],
        "gradient_accumulation_steps": config["gradient_accumulation_steps"],
        "total_walker_sweeps": config["total_walker_sweeps"],
        "initial_learning_rate": config["learning_rate"],
        "final_learning_rate": read_json(output / "summary.json")[
            "final_learning_rate"
        ],
        "validation": validation["status"],
        "projection": projection["status"],
        "projection_linf_residual": projection["fixed_point_linf_residual"],
        "projection_relative_l2_residual": projection[
            "fixed_point_relative_l2_residual"
        ],
        "seeds": {
            "model": model_seed,
            "optimizer": optimizer_seed,
            "validation": validation_seed,
            "projection": projection_seed,
        },
    }
    write_json(output / "optimizer_stability_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=tuple(PROTOCOLS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fixed-point-map",
        type=Path,
        default=ROOT
        / "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json",
    )
    parser.add_argument(
        "--initial-model",
        type=Path,
        default=ROOT
        / "output/neural_supervised_identity_formal_v1/supervised_model.npz",
    )
    parser.add_argument("--model-seed", type=int, default=202607291)
    parser.add_argument("--optimizer-seed", type=int, default=202607292)
    parser.add_argument("--validation-seed", type=int, default=202607293)
    parser.add_argument("--projection-seed", type=int, default=202607294)
    args = parser.parse_args()
    run(
        preset=args.preset,
        output=args.output.resolve(),
        fixed_point_map=args.fixed_point_map.resolve(),
        initial_model=args.initial_model.resolve(),
        model_seed=args.model_seed,
        optimizer_seed=args.optimizer_seed,
        validation_seed=args.validation_seed,
        projection_seed=args.projection_seed,
    )


if __name__ == "__main__":
    main()
