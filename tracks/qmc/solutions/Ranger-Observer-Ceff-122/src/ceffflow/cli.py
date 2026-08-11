"""Command-line interface for observer-dependent central-charge studies."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .clean_ising import fit_clean_ising
from .runner import cell_from_run_spec, run_cell


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def benchmark(output: Path) -> dict[str, object]:
    lengths = np.arange(8, 42, 2)
    fit = fit_clean_ising(lengths)
    payload: dict[str, object] = {
        "clean_ising": {
            "lengths": lengths.tolist(),
            "central_charge": fit.central_charge,
            "absolute_error": abs(fit.central_charge - 0.5),
            "passed": abs(fit.central_charge - 0.5) < 5e-4,
        }
    }
    _write_json(output / "benchmark.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ceffflow")
    commands = parser.add_subparsers(dest="command", required=True)
    benchmark_parser = commands.add_parser("benchmark")
    benchmark_parser.add_argument("--output", type=Path, required=True)
    cell_parser = commands.add_parser("cell")
    cell_parser.add_argument("--run-spec", type=Path, required=True)
    cell_parser.add_argument("--cell-id", required=True)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("--run-spec", type=Path, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    convergence_parser = commands.add_parser("particle-convergence")
    convergence_parser.add_argument(
        "--reference-run-spec", type=Path, required=True
    )
    convergence_parser.add_argument(
        "--candidate-run-spec", type=Path, required=True
    )
    convergence_parser.add_argument("--output", type=Path, required=True)
    convergence_parser.add_argument(
        "--absolute-tolerance", type=float, default=0.05
    )
    convergence_parser.add_argument("--confidence-z", type=float, default=1.96)
    pair_parser = commands.add_parser("particle-pair-convergence")
    pair_parser.add_argument("--run-spec", type=Path, required=True)
    pair_parser.add_argument("--output", type=Path, required=True)
    pair_parser.add_argument("--lower-particles", type=int, required=True)
    pair_parser.add_argument("--higher-particles", type=int, required=True)
    pair_parser.add_argument("--absolute-tolerance", type=float, default=0.05)
    pair_parser.add_argument("--confidence-z", type=float, default=1.96)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "benchmark":
        benchmark(args.output)
        return 0
    if args.command == "cell":
        config, output = cell_from_run_spec(args.run_spec, args.cell_id)
        run_cell(config, output, cell_id=args.cell_id)
        return 0
    if args.command == "particle-convergence":
        from .convergence import analyze_particle_convergence

        analyze_particle_convergence(
            args.reference_run_spec,
            args.candidate_run_spec,
            args.output,
            absolute_tolerance=args.absolute_tolerance,
            confidence_z=args.confidence_z,
        )
        return 0
    if args.command == "particle-pair-convergence":
        from .convergence import analyze_particle_pair_run

        analyze_particle_pair_run(
            args.run_spec,
            args.output,
            lower_particles=args.lower_particles,
            higher_particles=args.higher_particles,
            absolute_tolerance=args.absolute_tolerance,
            confidence_z=args.confidence_z,
        )
        return 0
    from .analysis import analyze_run

    analyze_run(args.run_spec, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
