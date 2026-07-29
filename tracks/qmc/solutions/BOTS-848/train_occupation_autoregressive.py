"""Command-line entry point for Route A occupation-autoregressive training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)
from scalable_v1.protocol import load_protocol
from scalable_v1.routes.occupation_autoregressive.model import AutoregressiveNQS
from scalable_v1.routes.occupation_autoregressive.operators import (
    PreparedPairOperator,
)
from scalable_v1.routes.occupation_autoregressive.train import (
    FeatureStateError,
    ReducedTrainingConfig,
    run_reduced_training,
)


COMPARISON_SHA = "5aa9219f4cd24bc2274f0514b621c2f9b47cead7"
PROTOCOL_SHA256 = (
    "2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38"
)
A03_SMOKE_UPDATES = 16
A03_SMOKE_SEED = 848


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the Route A occupation-autoregressive candidate",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--smoke-updates", type=int)
    modes.add_argument("--n8-smoke", action="store_true")
    parser.add_argument("--training-seed", type=int, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.n8_smoke:
        raise FeatureStateError(
            "N=8 smoke is unavailable until the A05 tower and adapter capabilities are installed"
        )
    if arguments.smoke_updates is None:
        raise FeatureStateError(
            "full tower-aware training is unavailable until the A05 tower capability is installed"
        )
    if arguments.smoke_updates != A03_SMOKE_UPDATES:
        raise ValueError("A03 reduced smoke must use exactly 16 updates")
    if arguments.training_seed != A03_SMOKE_SEED:
        raise ValueError("A03 reduced smoke is frozen to training seed 848")

    protocol = load_protocol()
    if protocol.sha256 != PROTOCOL_SHA256:
        raise ValueError("scalable-v1 protocol SHA-256 mismatch")
    physics = protocol.physics
    training = protocol.training
    capacity = protocol.capacity["routes"]["occupation_autoregressive"]
    if training["batch_size_per_sector"] != 512:
        raise ValueError("A03 reduced smoke requires 512 samples per M=0 sector")

    model = AutoregressiveNQS.initialize(
        n_electrons=physics["n_electrons"],
        two_q=physics["two_q"],
        target_m2=0,
        width=capacity["hidden_width"],
        layers=capacity["hidden_layers"],
        seed=arguments.training_seed,
        max_trainable_parameters=protocol.capacity["max_trainable_parameters"],
    )
    integrals = coulomb_integrals(physics["two_q"])
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    operator = PreparedPairOperator.build(
        pairs,
        pair_matrix,
        physics["two_q"],
    )
    config = ReducedTrainingConfig(
        training_seed=arguments.training_seed,
        updates=arguments.smoke_updates,
        batch_size_per_sector=training["batch_size_per_sector"],
        learning_rate=training["learning_rate"],
        beta1=training["beta1"],
        beta2=training["beta2"],
        epsilon=training["epsilon"],
        gradient_clip_norm=training["gradient_clip_norm"],
        checkpoint_interval=training["checkpoint_interval"],
        protocol_sha256=protocol.sha256,
        comparison_sha=COMPARISON_SHA,
    )
    artifacts = run_reduced_training(
        model=model,
        operator=operator,
        config=config,
        run_dir=arguments.run_dir,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "a03-reduced-m0-smoke",
                "training_seed": arguments.training_seed,
                "updates": arguments.smoke_updates,
                "batch_size_per_sector": training["batch_size_per_sector"],
                "ground_sector": "M=0",
                "excited_sector": "M=0",
                "selection_rule": "final_update",
                "selected_update": artifacts.selected_update,
                "checkpoint_sha256": artifacts.checkpoint_sha256,
                "optimizer_state_sha256": artifacts.optimizer_state_sha256,
                "training_log_sha256": artifacts.training_log_sha256,
                "protocol_sha256": protocol.sha256,
                "comparison_sha": COMPARISON_SHA,
            },
            sort_keys=True,
            allow_nan=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FeatureStateError as error:
        raise SystemExit(f"feature state error: {error}") from error
