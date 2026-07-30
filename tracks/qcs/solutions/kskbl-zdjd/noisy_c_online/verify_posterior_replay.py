"""Independently reload and verify a posterior-replay neural ensemble."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from hidden_oracle import CleanDomainEvaluator
from train_online import evaluate, make_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(
        (args.run_dir / "config.json").read_text(encoding="utf-8")
    )
    metrics = json.loads(
        (args.run_dir / "metrics.json").read_text(encoding="utf-8")
    )
    device = torch.device("cpu")
    models = []
    for member in range(config["ensemble_size"]):
        model = make_model(
            config["architecture"],
            config["hidden"],
            config["depth"],
        ).to(device)
        state = torch.load(
            args.run_dir / f"model-{member:02d}.pt",
            map_location=device,
            weights_only=True,
        )
        model.load_state_dict(state)
        model.eval()
        models.append(model)

    observed = evaluate(models, CleanDomainEvaluator(device))
    recorded = metrics[-1]
    scalar_keys = (
        "clean_bce",
        "bit_accuracy",
        "word_accuracy",
        "normalized_mae",
        "bit_uncertainty",
        "value_uncertainty",
    )
    mismatches = {
        key: {
            "recorded": recorded[key],
            "observed": observed[key],
        }
        for key in scalar_keys
        if abs(float(recorded[key]) - float(observed[key])) > 1e-8
    }
    if mismatches:
        raise RuntimeError(
            "checkpoint verification mismatch: "
            + json.dumps(mismatches, indent=2)
        )
    print(
        json.dumps(
            {
                "run_dir": args.run_dir.as_posix(),
                "domain_size": 4096,
                "word_accuracy": observed["word_accuracy"],
                "bit_accuracy": observed["bit_accuracy"],
                "normalized_mae": observed["normalized_mae"],
                "bit_uncertainty": observed["bit_uncertainty"],
                "status": "verified",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
