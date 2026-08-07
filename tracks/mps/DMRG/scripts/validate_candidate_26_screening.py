from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

import numpy as np

from vmcrg_ref import (
    FastMultiOperatorBiasedMetropolis,
    IsingLattice,
    OperatorBasis,
    candidate_even_shapes,
    published_survivor_indices,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a frozen reconstructed 26-operator bias"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--thermalization", type=int, default=500)
    parser.add_argument("--measurements", type=int, default=1000)
    parser.add_argument("--runs", type=int, default=32)
    parser.add_argument("--bootstrap", type=int, default=20000)
    parser.add_argument("--family-alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=20260721)
    return parser.parse_args()


def simultaneous_bootstrap_critical(
    run_means: np.ndarray,
    standard_errors: np.ndarray,
    replicates: int,
    alpha: float,
    rng: np.random.Generator,
) -> float:
    centered = run_means - run_means.mean(axis=0)
    maxima: list[np.ndarray] = []
    batch_size = 500
    remaining = replicates
    while remaining:
        batch = min(batch_size, remaining)
        indices = rng.integers(0, run_means.shape[0], size=(batch, run_means.shape[0]))
        bootstrap_means = centered[indices].mean(axis=1)
        maxima.append(np.max(np.abs(bootstrap_means / standard_errors), axis=1))
        remaining -= batch
    return float(np.quantile(np.concatenate(maxima), 1.0 - alpha))


def main() -> None:
    args = parse_args()
    if args.runs < 3:
        raise ValueError("at least three independent runs are required")
    if args.bootstrap < 1000:
        raise ValueError("at least 1000 bootstrap replicates are required")
    if not 0.0 < args.family_alpha < 1.0:
        raise ValueError("family-alpha must lie between zero and one")

    summary = json.loads((args.input / "summary.json").read_text(encoding="utf-8"))
    if summary.get("coordinate_status") != "RECONSTRUCTED_NOT_SOURCE_VERIFIED":
        raise ValueError("input is not a reconstructed candidate-26 run")
    pair_tie = summary["pair_tie"]
    shapes = candidate_even_shapes(pair_tie)
    if summary["operator_names"] != [shape.name for shape in shapes]:
        raise ValueError("operator names do not match the declared candidate basis")

    length = int(summary["length"])
    couplings = np.asarray(summary["input_couplings"], dtype=float)
    final_couplings = np.asarray(
        summary["final_renormalized_couplings"], dtype=float
    )
    bias = -final_couplings
    micro_basis = OperatorBasis(length, shapes)
    block_basis = OperatorBasis(length // 3, shapes)
    # Materialize once; all compiled samplers then share these read-only arrays.
    micro_basis.packed_incidence()
    block_basis.packed_incidence()
    sequences = np.random.SeedSequence(args.seed).spawn(args.runs)

    def one_run(sequence: np.random.SeedSequence) -> tuple[np.ndarray, float]:
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
        total = np.zeros(len(shapes), dtype=float)
        for _ in range(args.measurements):
            sampler.sweep()
            total += sampler.block_values
        sampler.assert_cache_consistent()
        return total / args.measurements, sampler.acceptance_rate

    with ThreadPoolExecutor(max_workers=min(args.runs, os.cpu_count() or 1)) as pool:
        results = list(pool.map(one_run, sequences))

    block_sites = (length // 3) ** 2
    run_means = np.stack([result[0] for result in results]) / block_sites
    mean = run_means.mean(axis=0)
    standard_errors = run_means.std(axis=0, ddof=1) / np.sqrt(args.runs)
    if np.any(standard_errors == 0.0):
        raise RuntimeError("a target-moment standard error is zero")
    z_scores = mean / standard_errors
    critical = simultaneous_bootstrap_critical(
        run_means,
        standard_errors,
        args.bootstrap,
        args.family_alpha,
        np.random.default_rng(args.seed + 1),
    )
    target_moment_gate = bool(np.max(np.abs(z_scores)) <= critical)

    threshold = float(summary["screening_threshold"])
    observed = set(np.flatnonzero(np.abs(final_couplings) >= threshold).tolist())
    published = set(published_survivor_indices(shapes))
    geometry_match = observed == published
    if not target_moment_gate:
        status = "OPTIMIZATION_NOT_VALIDATED"
    elif not geometry_match:
        status = "CANDIDATE_SCREEN_MISMATCH"
    else:
        status = "CANDIDATE_SCREEN_MATCHES_PUBLISHED_SURVIVORS"

    report = {
        "verification_status": "VERIFIED_STOCHASTIC_FROZEN_BIAS_TEST",
        "coordinate_status": "RECONSTRUCTED_NOT_SOURCE_VERIFIED",
        "pair_tie": pair_tie,
        "thermalization_sweeps": args.thermalization,
        "measurement_sweeps_per_run": args.measurements,
        "independent_runs": args.runs,
        "bootstrap_replicates": args.bootstrap,
        "simultaneous_family_alpha": args.family_alpha,
        "bootstrap_max_statistic_critical": critical,
        "mean_operators_per_block_site": mean.tolist(),
        "run_level_standard_errors": standard_errors.tolist(),
        "z_scores_against_uniform_target": z_scores.tolist(),
        "max_abs_z": float(np.max(np.abs(z_scores))),
        "target_moment_gate": target_moment_gate,
        "screening_geometry_match": geometry_match,
        "validation_status": status,
        "acceptance_rates": [result[1] for result in results],
        "seed": args.seed,
    }
    output = args.input / "frozen_validation.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing validation: {output}")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
