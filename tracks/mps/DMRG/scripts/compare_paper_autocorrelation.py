from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

import numpy as np

from vmcrg_ref import (
    EVEN_SHAPES,
    FastMultiOperatorBiasedMetropolis,
    IsingLattice,
    OperatorBasis,
    integrated_autocorrelation_time,
    normalized_connected_autocorrelation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare biased and unbiased correlation of S0(sigma)S0(sigma')"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--thermalization", type=int, default=5000)
    parser.add_argument("--measurements", type=int, default=100_000)
    parser.add_argument("--spacing", type=int, default=1)
    parser.add_argument("--max-lag", type=int, default=2000)
    parser.add_argument("--chains", type=int, default=8)
    parser.add_argument("--ratio-threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260750)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.thermalization < 0:
        raise ValueError("thermalization cannot be negative")
    if args.measurements <= args.max_lag or args.spacing <= 0:
        raise ValueError("measurements must exceed max_lag and spacing must be positive")
    if args.chains < 3 or args.ratio_threshold <= 0.0:
        raise ValueError("at least three chains and a positive ratio threshold are required")

    input_dir = args.input.resolve()
    output = (args.output or input_dir / "paper_autocorrelation.json").resolve()
    arrays_output = output.with_suffix(".npz")
    if output.exists() or arrays_output.exists():
        raise FileExistsError(f"refusing to overwrite autocorrelation output: {output}")
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    if summary.get("operator_names") != [shape.name for shape in EVEN_SHAPES]:
        raise ValueError("input does not use the published 13-even-operator basis")
    length = int(summary["length"])
    couplings = np.asarray(summary["input_couplings"], dtype=np.float64)
    biased = -np.asarray(summary["final_renormalized_couplings"], dtype=np.float64)
    zero_bias = np.zeros_like(biased)
    basis_micro = OperatorBasis(length, EVEN_SHAPES)
    basis_block = OperatorBasis(length // 3, EVEN_SHAPES)
    basis_micro.packed_incidence()
    basis_block.packed_incidence()
    sequences = np.random.SeedSequence(args.seed).spawn(args.chains * 3)

    def one_chain(index: int) -> tuple[np.ndarray, np.ndarray, float, float]:
        initial_rng = np.random.default_rng(sequences[3 * index])
        initial = IsingLattice.random(length, initial_rng).spins.copy()
        series: list[np.ndarray] = []
        acceptance_rates: list[float] = []
        for bias, sequence in (
            (biased, sequences[3 * index + 1]),
            (zero_bias, sequences[3 * index + 2]),
        ):
            rng = np.random.default_rng(sequence)
            sampler = FastMultiOperatorBiasedMetropolis(
                IsingLattice(initial.copy()),
                couplings,
                bias,
                rng,
                EVEN_SHAPES,
                micro_basis=basis_micro,
                block_basis=basis_block,
            )
            if args.thermalization:
                sampler.run_sweeps(args.thermalization)
            attempted_before = sampler.attempted
            accepted_before = sampler.accepted
            series.append(
                sampler.nearest_neighbor_product_series(args.measurements, args.spacing)
            )
            attempted = sampler.attempted - attempted_before
            accepted = sampler.accepted - accepted_before
            acceptance_rates.append(accepted / attempted)
            sampler.assert_cache_consistent()
        return series[0], series[1], acceptance_rates[0], acceptance_rates[1]

    with ThreadPoolExecutor(max_workers=min(args.chains, os.cpu_count() or 1)) as pool:
        results = list(pool.map(one_chain, range(args.chains)))
    biased_series = np.stack([result[0] for result in results])
    unbiased_series = np.stack([result[1] for result in results])
    biased_acf = np.stack(
        [normalized_connected_autocorrelation(values, args.max_lag) for values in biased_series]
    )
    unbiased_acf = np.stack(
        [normalized_connected_autocorrelation(values, args.max_lag) for values in unbiased_series]
    )
    biased_tau = np.asarray([integrated_autocorrelation_time(acf) for acf in biased_acf])
    unbiased_tau = np.asarray(
        [integrated_autocorrelation_time(acf) for acf in unbiased_acf]
    )
    ratios = biased_tau / unbiased_tau
    ratio_mean = float(ratios.mean())
    ratio_se = float(ratios.std(ddof=1) / np.sqrt(args.chains))
    ratio_upper_bound = ratio_mean + 2.0 * ratio_se
    passed = bool(ratio_upper_bound < args.ratio_threshold)
    result = {
        "status": "PASS" if passed else "FAIL",
        "observable": "normalized_S0_micro_times_S0_block",
        "correlation_definition": "connected_normalized_autocovariance",
        "window": "initial_positive_sequence",
        "input": str(input_dir),
        "length": length,
        "thermalization_sweeps": args.thermalization,
        "thermalization_schedule_source": "implementation_choice_not_published",
        "measurements_per_chain": args.measurements,
        "measurement_schedule_source": "implementation_choice_not_published",
        "sweeps_between_measurements": args.spacing,
        "max_lag": args.max_lag,
        "independent_paired_chains": args.chains,
        "seed": args.seed,
        "ratio_threshold": args.ratio_threshold,
        "paired_ratio_mean": ratio_mean,
        "paired_ratio_standard_error": ratio_se,
        "paired_ratio_mean_plus_2se": ratio_upper_bound,
        "biased_tau_mean": float(biased_tau.mean()),
        "unbiased_tau_mean": float(unbiased_tau.mean()),
        "biased_tau_by_chain": biased_tau.tolist(),
        "unbiased_tau_by_chain": unbiased_tau.tolist(),
        "biased_acceptance_rates": [float(result[2]) for result in results],
        "unbiased_acceptance_rates": [float(result[3]) for result in results],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    np.savez_compressed(
        arrays_output,
        biased_series=biased_series,
        unbiased_series=unbiased_series,
        biased_acf=biased_acf,
        unbiased_acf=unbiased_acf,
        biased_tau=biased_tau,
        unbiased_tau=unbiased_tau,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
