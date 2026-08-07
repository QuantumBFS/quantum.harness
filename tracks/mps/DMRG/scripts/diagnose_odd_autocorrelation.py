from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

import numpy as np

from vmcrg_ref import (
    EVEN_SHAPES,
    ODD_SHAPES,
    FastMultiOperatorBiasedMetropolis,
    IsingLattice,
    OperatorBasis,
    integrated_autocorrelation_time,
    normalized_connected_autocorrelation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose autocorrelation of the leading odd-sector moments"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--runs-per-seed", type=int, default=8)
    parser.add_argument("--thermalization", type=int, default=5000)
    parser.add_argument("--measurements", type=int, default=100000)
    parser.add_argument("--spacing", type=int, default=1)
    parser.add_argument("--max-lag", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs_per_seed <= 0 or args.measurements <= args.max_lag:
        raise ValueError("invalid run count, measurement count, or maximum lag")
    input_dir = args.input.resolve()
    output = args.output.resolve()
    arrays_output = output.with_suffix(".npz")
    if output.exists() or arrays_output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    length = int(summary["length"])
    shapes = (*EVEN_SHAPES, *ODD_SHAPES)
    odd_index = len(EVEN_SHAPES)
    couplings = np.concatenate(
        (np.asarray(summary["input_couplings"], dtype=np.float64), np.zeros(len(ODD_SHAPES)))
    )
    bias = np.concatenate(
        (
            -np.asarray(summary["final_renormalized_couplings"], dtype=np.float64),
            np.zeros(len(ODD_SHAPES)),
        )
    )
    micro_basis = OperatorBasis(length, shapes)
    block_basis = OperatorBasis(length // 3, shapes)
    micro_basis.packed_incidence()
    block_basis.packed_incidence()

    jobs: list[tuple[int, np.random.SeedSequence]] = []
    for group, seed in enumerate(args.seeds):
        for sequence in np.random.SeedSequence(seed).spawn(args.runs_per_seed):
            jobs.append((group, sequence))

    def one_run(job: tuple[int, np.random.SeedSequence]) -> tuple[int, np.ndarray, np.ndarray]:
        group, sequence = job
        rng = np.random.default_rng(sequence)
        sampler = FastMultiOperatorBiasedMetropolis(
            IsingLattice.random(length, rng),
            couplings,
            bias,
            rng,
            shapes,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        sampler.run_sweeps(args.thermalization)
        cross, block_square = sampler.odd_magnetization_moment_series(
            odd_index, args.measurements, args.spacing
        )
        sampler.assert_cache_consistent()
        return group, cross, block_square

    with ThreadPoolExecutor(max_workers=min(len(jobs), os.cpu_count() or 1)) as pool:
        results = list(pool.map(one_run, jobs))
    cross = np.stack([item[1] for item in results])
    block_square = np.stack([item[2] for item in results])
    cross_acf = np.stack(
        [normalized_connected_autocorrelation(row, args.max_lag) for row in cross]
    )
    block_acf = np.stack(
        [
            normalized_connected_autocorrelation(row, args.max_lag)
            for row in block_square
        ]
    )
    cross_tau = np.asarray(
        [integrated_autocorrelation_time(row) for row in cross_acf]
    )
    block_tau = np.asarray(
        [integrated_autocorrelation_time(row) for row in block_acf]
    )
    groups: list[dict[str, object]] = []
    for group, seed in enumerate(args.seeds):
        selection = np.asarray([item[0] == group for item in results])
        groups.append(
            {
                "seed": seed,
                "runs": int(selection.sum()),
                "cross_mean": float(cross[selection].mean()),
                "block_square_mean": float(block_square[selection].mean()),
                "cross_tau_mean": float(cross_tau[selection].mean()),
                "cross_tau_max": float(cross_tau[selection].max()),
                "block_square_tau_mean": float(block_tau[selection].mean()),
                "block_square_tau_max": float(block_tau[selection].max()),
            }
        )
    report = {
        "status": "DIAGNOSTIC_ONLY",
        "method": "odd_magnetization_cross_and_block_square_time_series",
        "input": str(input_dir),
        "operator": ODD_SHAPES[0].name,
        "thermalization_sweeps": args.thermalization,
        "measurements": args.measurements,
        "spacing": args.spacing,
        "max_lag": args.max_lag,
        "groups": groups,
        "all_runs": {
            "cross_tau_mean": float(cross_tau.mean()),
            "cross_tau_max": float(cross_tau.max()),
            "block_square_tau_mean": float(block_tau.mean()),
            "block_square_tau_max": float(block_tau.max()),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(
        arrays_output,
        cross=cross,
        block_square=block_square,
        cross_acf=cross_acf,
        block_square_acf=block_acf,
        cross_tau=cross_tau,
        block_square_tau=block_tau,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
