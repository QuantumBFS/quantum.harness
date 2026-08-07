"""Command-line entry point for measured VQE training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
)
from vqetape.training import train_vqe
from vqetape.training_spec import (
    VQETrainingRequest,
    VQETrainingResult,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure exact VQE time to a target energy error."
        )
    )
    parser.add_argument("--nqubits", required=True, type=int)
    parser.add_argument("--depth", required=True, type=int)
    parser.add_argument("--coupling", type=float, default=1.0)
    parser.add_argument("--field", type=float, default=1.0)
    parser.add_argument(
        "--dtype",
        choices=("complex64", "complex128"),
        default="complex64",
    )
    parser.add_argument(
        "--program",
        choices=(
            "statevector",
            "spatial",
            "z2-reference",
            "z2-native",
        ),
        default="spatial",
    )
    parser.add_argument(
        "--path-strategy",
        choices=("greedy", "random-greedy", "auto-hq"),
        default="greedy",
    )
    parser.add_argument("--block-width", type=int, default=1)
    parser.add_argument("--unroll", type=int, default=1)
    parser.add_argument(
        "--adjoint",
        choices=(
            "default",
            "remat",
            "segmented",
            "explicit",
        ),
        default="default",
    )
    parser.add_argument("--segment-length", type=int)
    parser.add_argument(
        "--optimizer",
        choices=("adam", "lbfgs", "natural-gradient"),
        required=True,
    )
    parser.add_argument(
        "--initialization",
        choices=("zeros", "random", "recycled"),
        required=True,
    )
    parser.add_argument("--target-error", required=True, type=float)
    parser.add_argument("--max-steps", required=True, type=int)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--damping", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ground-energy", type=float)
    parser.add_argument("--recycled-result", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _program(
    args: argparse.Namespace,
) -> ProgramConfig | SpatialProgramConfig:
    if args.program == "statevector":
        return ProgramConfig(
            "scan",
            args.adjoint,
            unroll=args.unroll,
            segment_length=args.segment_length,
        )
    symmetry = {
        "spatial": "none",
        "z2-reference": "z2-reference",
        "z2-native": "z2-native",
    }[args.program]
    return SpatialProgramConfig(
        args.path_strategy,
        args.adjoint,
        unroll=args.unroll,
        block_width=args.block_width,
        symmetry=symmetry,
        segment_length=args.segment_length,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    spec = TFIMVQESpec(
        nqubits=args.nqubits,
        depth=args.depth,
        coupling=args.coupling,
        field=args.field,
        dtype=args.dtype,
    )
    recycled_source_spec = None
    recycled_parameters = None
    if args.initialization == "recycled":
        if args.recycled_result is None:
            raise ValueError(
                "recycled initialization requires "
                "--recycled-result"
            )
        source = VQETrainingResult.from_dict(
            json.loads(
                args.recycled_result.read_text(
                    encoding="utf-8"
                )
            )
        )
        recycled_source_spec = source.request.spec
        recycled_parameters = source.final_parameters
    elif args.recycled_result is not None:
        raise ValueError(
            "--recycled-result is only valid with recycled "
            "initialization"
        )

    request = VQETrainingRequest(
        spec=spec,
        program=_program(args),
        optimizer=args.optimizer,
        initialization=args.initialization,
        target_energy_error=args.target_error,
        max_steps=args.max_steps,
        seed=args.seed,
        learning_rate=args.learning_rate,
        damping=args.damping,
        ground_energy=args.ground_energy,
        recycled_source_spec=recycled_source_spec,
        recycled_parameters=recycled_parameters,
    )
    result = train_vqe(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            result.to_dict(),
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(
        f"program={request.program.label} "
        f"optimizer={request.optimizer} "
        f"converged={result.converged} "
        f"evaluations={result.evaluations} "
        f"final_error={result.final_energy - result.ground_energy:.6g}"
    )
    return 0 if result.converged else 2


if __name__ == "__main__":
    raise SystemExit(main())
