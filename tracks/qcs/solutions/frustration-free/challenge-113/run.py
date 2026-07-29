from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from qcontrol.artifacts import ArtifactConflict, ArtifactStore
from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig
from qcontrol.experiments import (
    default_sweep_configs,
    generate_paired_trials,
    read_plan,
    run_sweep,
    sweep_status,
    validate_sweep,
)
from qcontrol.landscape import analyze_landscape
from qcontrol.open_loop import optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


def _shots(value: str) -> int | None:
    if value == "exact":
        return None
    try:
        shots = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("shots must be 'exact' or a positive integer") from None
    if shots <= 0:
        raise argparse.ArgumentTypeError("shots must be 'exact' or a positive integer")
    return shots


def _system(name: str, segments: int | None = None) -> SystemConfig:
    return SystemConfig(
        name,
        segments if segments is not None else (6 if name == "one_qubit" else 20),
        4.0,
    )


def _trial_config(args: argparse.Namespace) -> ExperimentConfig:
    system = _system(args.system, args.segments)
    return ExperimentConfig(
        run_kind=args.kind,
        system=system,
        device=DeviceConfig(
            gap=args.gap,
            shots=args.shots,
            perturbation_seed=args.perturbation_seed,
        ),
        search=SearchConfig(
            args.method,
            args.dimension,
            200 if args.kind == "development" else 2_000,
        ),
        trial_seed=args.seed,
    )


def _print(payload: object) -> None:
    print(json.dumps(payload, allow_nan=False, sort_keys=True))


def _geometry(args: argparse.Namespace) -> int:
    system_config = _system(args.system, args.segments)
    system = make_system(system_config)
    pulse_space = PulseSpace.from_system(system, system_config.segments)
    result = optimize_open_loop(system, pulse_space, seed=args.seed)
    landscape = analyze_landscape(
        system,
        pulse_space,
        result,
        leading_count=min(pulse_space.parameter_count, system.dimension**2 - 1),
        dense_validation=pulse_space.parameter_count <= 80,
    )
    payload = {
        "eigenvalue_ordering": landscape.eigenvalue_ordering,
        "hessian_ranks": {
            str(key): value for key, value in landscape.hessian_ranks.items()
        },
        "jacobian_ranks": {
            str(key): value for key, value in landscape.jacobian_ranks.items()
        },
        "leading_eigenvalues": [
            float(value) for value in landscape.leading_eigenvalues
        ],
        "open_loop": {
            "evaluations": result.evaluations,
            "gradient_norm": result.gradient_norm,
            "loss": result.loss,
            "starts": result.starts,
        },
        "schema_version": 1,
        "system": system_config.name,
    }
    store = ArtifactStore(args.output)
    store.bind_provenance(
        {
            "command": "geometry",
            "seed": args.seed,
            "system": {
                "amplitude_bound": system_config.amplitude_bound,
                "duration": system_config.effective_duration,
                "name": system_config.name,
                "segments": system_config.segments,
            },
        }
    )
    digest = store.publish_json("geometry.json", payload, immutable=True)
    _print({"artifact": "geometry.json", "sha256": digest})
    return 0


def _trial(args: argparse.Namespace) -> int:
    config = _trial_config(args)
    store = ArtifactStore(args.output)
    status = run_sweep(generate_paired_trials([config]), store)
    _print(status.canonical_dict())
    return 0


def _sweep(args: argparse.Namespace) -> int:
    specs = generate_paired_trials(default_sweep_configs(args.kind))
    store = ArtifactStore(args.output)
    status = run_sweep(
        specs,
        store,
        stop_after=args.stop_after,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    _print(status.canonical_dict())
    return 0


def _load_specs(store: ArtifactStore):
    return read_plan(store)


def _validate(args: argparse.Namespace) -> int:
    store = ArtifactStore(args.output)
    if not (store.root / "plan.json").exists():
        _print({"errors": ["missing trial plan"], "valid": False})
        return 1
    try:
        report = validate_sweep(_load_specs(store), store)
    except ArtifactConflict as error:
        _print({"errors": [str(error)], "valid": False})
        return 1
    _print(report.canonical_dict())
    return 0 if report.valid else 1


def _status(args: argparse.Namespace) -> int:
    store = ArtifactStore(args.output)
    try:
        status = sweep_status(_load_specs(store), store)
    except ArtifactConflict as error:
        _print({"error": str(error)})
        return 1
    _print(status.canonical_dict())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restartable Challenge 113 experiment orchestration"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    geometry = subparsers.add_parser("geometry")
    geometry.add_argument("--system", choices=("one_qubit", "two_qubit"), required=True)
    geometry.add_argument("--segments", type=int)
    geometry.add_argument("--seed", type=int, default=0)
    geometry.add_argument("--output", type=Path, required=True)
    geometry.set_defaults(handler=_geometry)

    trial = subparsers.add_parser("trial")
    trial.add_argument("--kind", choices=("development", "production"), required=True)
    trial.add_argument("--system", choices=("one_qubit", "two_qubit"), required=True)
    trial.add_argument("--segments", type=int)
    trial.add_argument("--gap", type=float, required=True)
    trial.add_argument("--shots", type=_shots, default=None)
    trial.add_argument("--perturbation-seed", type=int, required=True)
    trial.add_argument(
        "--method",
        choices=("full", "model_hessian", "random", "oracle"),
        required=True,
    )
    trial.add_argument("--dimension", type=int, required=True)
    trial.add_argument("--seed", type=int, required=True)
    trial.add_argument("--output", type=Path, required=True)
    trial.set_defaults(handler=_trial)

    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--kind", choices=("development", "production"), required=True)
    sweep.add_argument("--stop-after", type=int)
    sweep.add_argument("--shard-index", type=int, default=0)
    sweep.add_argument("--shard-count", type=int, default=1)
    sweep.add_argument("--output", type=Path, required=True)
    sweep.set_defaults(handler=_sweep)

    for command, handler in (("validate", _validate), ("status", _status)):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--output", type=Path, required=True)
        subparser.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ArtifactConflict, ValueError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    sys.exit(main())
