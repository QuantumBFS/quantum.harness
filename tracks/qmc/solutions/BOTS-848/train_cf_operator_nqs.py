"""Protocol-bound production entry point for Route C training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from scalable_v1.protocol import load_protocol
from scalable_v1.routes.cf_operator_nqs.model import CFOperatorNQS
from scalable_v1.routes.cf_operator_nqs.sampler import SU2TangentMetropolis
from scalable_v1.routes.cf_operator_nqs.train import (
    EXPECTED_PROTOCOL_SHA256,
    FROZEN_BATCH_SIZE,
    FROZEN_BETA1,
    FROZEN_BETA2,
    FROZEN_BURN_IN_SWEEPS,
    FROZEN_CHAINS,
    FROZEN_CHECKPOINT_INTERVAL,
    FROZEN_EPSILON,
    FROZEN_GRADIENT_CLIP_NORM,
    FROZEN_LEARNING_RATE,
    FROZEN_TRAINING_SEEDS,
    FROZEN_UPDATES,
    _validate_training_seed,
    run_training,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen Challenge #15 Route C training schedule."
    )
    parser.add_argument(
        "--training-seed",
        type=int,
        required=True,
        choices=FROZEN_TRAINING_SEEDS,
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def _validated_protocol() -> object:
    protocol = load_protocol()
    if protocol.sha256 != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Route C protocol SHA-256 mismatch")
    physics = protocol.physics
    training = protocol.training
    sampling = protocol.sampling
    route = protocol.capacity["routes"]["cf_operator_nqs"]
    expected_training = {
        "seeds": list(FROZEN_TRAINING_SEEDS),
        "optimizer": "adam",
        "learning_rate": FROZEN_LEARNING_RATE,
        "beta1": FROZEN_BETA1,
        "beta2": FROZEN_BETA2,
        "epsilon": FROZEN_EPSILON,
        "gradient_clip_norm": FROZEN_GRADIENT_CLIP_NORM,
        "optimizer_updates": FROZEN_UPDATES,
        "batch_size_per_sector": FROZEN_BATCH_SIZE,
        "local_energy_evaluations_per_sector": (
            FROZEN_UPDATES * FROZEN_BATCH_SIZE
        ),
        "checkpoint_interval": FROZEN_CHECKPOINT_INTERVAL,
        "checkpoint_selection": "final_update",
        "dtype": "complex128",
    }
    if physics["n_electrons"] != 6 or physics["two_q"] != 15:
        raise ValueError("Route C production physics must be N=6, 2Q=15")
    if training != expected_training:
        raise ValueError("Route C frozen training protocol mismatch")
    if sampling["chains"] != FROZEN_CHAINS:
        raise ValueError("Route C frozen chain count mismatch")
    if sampling["burn_in_steps"] != FROZEN_BURN_IN_SWEEPS:
        raise ValueError("Route C frozen burn-in mismatch")
    if route != {
        "operator_layers": 1,
        "density_ranks": [2, 3, 4],
        "hidden_width": 64,
    }:
        raise ValueError("Route C frozen capacity mismatch")
    return protocol


def _build_production(training_seed: int) -> tuple[object, list[object]]:
    from scalable_v1.routes.cf_operator_nqs.jax_action import (
        build_family_action_kernel,
    )
    from scalable_v1.routes.cf_operator_nqs.seeds import JKCFSeedFamily

    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    action_kernel = build_family_action_kernel(
        family, platform="cpu", sector="family"
    )
    model = CFOperatorNQS.initialize(
        n_electrons=6,
        two_q=15,
        hidden_width=64,
        seed=training_seed,
        action_kernel=action_kernel,
    )
    samplers = [
        SU2TangentMetropolis(
            model=model,
            sector_index=sector_index,
            seed=training_seed + 100_000 * (sector_index + 1),
            chains=FROZEN_CHAINS,
            burn_in_sweeps=FROZEN_BURN_IN_SWEEPS,
        )
        for sector_index in range(6)
    ]
    return model, samplers


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _parser().parse_args(argv)
    training_seed = _validate_training_seed(arguments.training_seed)
    protocol = _validated_protocol()
    if arguments.run_dir.exists():
        raise FileExistsError(
            f"run directory already exists: {arguments.run_dir}"
        )
    print(
        json.dumps(
            {
                "event": "route-c-training-start",
                "protocol_sha256": protocol.sha256,
                "training_seed": training_seed,
                "optimizer_updates": FROZEN_UPDATES,
                "batch_size_per_sector": FROZEN_BATCH_SIZE,
                "chains": FROZEN_CHAINS,
                "burn_in_sweeps": FROZEN_BURN_IN_SWEEPS,
                "platform": "cpu",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    model, samplers = _build_production(training_seed)
    final_record = run_training(
        model=model,
        samplers=samplers,
        training_seed=training_seed,
        run_dir=arguments.run_dir,
    )
    print(json.dumps(final_record, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()


__all__ = ["_parser", "main"]
