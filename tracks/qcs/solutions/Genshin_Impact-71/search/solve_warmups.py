#!/usr/bin/env python3
"""Build and independently verify both disclosed issue #71 warm-ups."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from circuit import (
    build_adder,
    build_multiplier,
    read_commitment,
    verify_dataset,
    verify_formula,
    write_predictions,
)


def solve_one(
    *,
    instance: str,
    family: str,
    circuit,
    data_root: Path,
    output_root: Path,
) -> dict:
    instance_data = data_root / "datasets" / instance
    circuit_path = output_root / "circuits" / f"{instance}.txt"
    prediction_path = (
        output_root / "predictions" / instance / "test_outputs.csv"
    )
    circuit.write(circuit_path)
    training = verify_dataset(circuit, instance_data / "train.csv")
    exhaustive = verify_formula(circuit, family)
    actual_hash = write_predictions(
        circuit, instance_data / "test_inputs.csv", prediction_path
    )
    expected_hash = read_commitment(instance_data / "commitment.sha256")
    result = {
        "instance": instance,
        "family": family,
        "gates": len(circuit.gates),
        "training": training,
        "exhaustive": exhaustive,
        "prediction_sha256": actual_hash,
        "commitment_sha256": expected_hash,
        "commitment_match": actual_hash == expected_hash,
        "circuit": str(circuit_path),
        "predictions": str(prediction_path),
    }
    if training["exact"] != training["rows"]:
        raise RuntimeError(f"{instance}: training verification failed")
    if exhaustive["failures"]:
        raise RuntimeError(f"{instance}: exhaustive formula verification failed")
    if actual_hash != expected_hash:
        raise RuntimeError(f"{instance}: prediction commitment mismatch")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    results = [
        solve_one(
            instance="practice-add-n4",
            family="add",
            circuit=build_adder(4),
            data_root=args.data_root,
            output_root=args.output_root,
        ),
        solve_one(
            instance="practice-mul-n4",
            family="mul",
            circuit=build_multiplier(4),
            data_root=args.data_root,
            output_root=args.output_root,
        ),
    ]
    manifest = {
        "schema": "occam71-warmup-v1",
        "root_seed": 42,
        "note": "Deterministic construction; no random stream was required.",
        "results": results,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "warmup_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
