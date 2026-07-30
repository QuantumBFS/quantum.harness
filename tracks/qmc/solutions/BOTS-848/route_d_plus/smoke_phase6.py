"""Reduced GPU smoke for the real Phase 6 multiprocessing path."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import jax
import jsonschema

from .certify_phase6 import blind_training_audit
from .symmetry import verify_checkpoint_symmetry
from .train_dplus0 import (
    calibrate_architecture,
    train_seed,
    write_checkpoint,
)


def _validate(document: dict[str, object], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--calibration-seed", type=int, default=60_860)
    parser.add_argument("--training-seed", type=int, default=848)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    jax.config.update("jax_enable_x64", True)
    devices = jax.devices()
    if not devices or devices[0].platform != "gpu":
        raise RuntimeError("Phase 6 smoke requires a JAX GPU allocation")
    if not jax.config.read("jax_enable_x64"):
        raise RuntimeError("Phase 6 smoke requires JAX x64 mode")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = Path(__file__).resolve().parent
    with blind_training_audit() as events:
        print("calibration:start", flush=True)
        architecture = calibrate_architecture(
            args.calibration_seed,
            source_revision=args.source_revision,
        )
        architecture_path = output_dir / "architecture.json"
        write_checkpoint(architecture_path, architecture)
        architecture_sha256 = hashlib.sha256(
            architecture_path.read_bytes()
        ).hexdigest()
        _validate(
            architecture,
            package_dir / "architecture.schema.json",
        )
        print(f"calibration:done:{architecture_sha256}", flush=True)
        checkpoint, result = train_seed(
            args.training_seed,
            architecture=architecture,
            architecture_sha256=architecture_sha256,
            chains=2,
            updates=1,
            samples_per_update=2,
            final_samples_per_chain=8,
        )
        write_checkpoint(output_dir / "checkpoint.json", checkpoint)
        write_checkpoint(output_dir / "result.json", result)
        symmetry = verify_checkpoint_symmetry(architecture, checkpoint)
        _validate(symmetry, package_dir / "symmetry.schema.json")
        write_checkpoint(output_dir / "symmetry.json", symmetry)
    if events:
        raise RuntimeError(f"blind audit observed forbidden events: {events}")
    print(
        json.dumps(
            {
                "architecture_retained": architecture[
                    "retained_generators"
                ],
                "combined_metric": result["trace"][0][
                    "metric_structure"
                ],
                "ground_delta_maxima": checkpoint[
                    "ground_delta_maxima"
                ],
                "tower_delta_maxima": checkpoint[
                    "tower_delta_maxima"
                ],
                "ground_acceptance": result["final_ground"],
                "tower_acceptance": result["final_tower"],
                "symmetry_errors": symmetry["errors"],
                "symmetry_passed": symmetry["passed"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
