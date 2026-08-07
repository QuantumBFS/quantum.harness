from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from statistics import NormalDist

import numpy as np

from vmcrg_ref import (
    EVEN_SHAPES,
    FastMultiOperatorBiasedMetropolis,
    IsingLattice,
    OperatorBasis,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a frozen 13-operator bias")
    parser.add_argument("--input", type=Path, default=Path("output/L45_K0436_rg1"))
    parser.add_argument("--thermalization", type=int, default=500)
    parser.add_argument("--measurements", type=int, default=1000)
    parser.add_argument("--runs", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260716)
    parser.add_argument("--family-alpha", type=float, default=0.05)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional report path; defaults to INPUT/frozen_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0.0 < args.family_alpha < 1.0:
        raise ValueError("family alpha must lie strictly between zero and one")
    summary = json.loads((args.input / "summary.json").read_text(encoding="utf-8"))
    length = int(summary["length"])
    if "input_couplings" in summary:
        couplings = np.asarray(summary["input_couplings"], dtype=float)
    else:
        couplings = np.zeros(len(EVEN_SHAPES), dtype=float)
        couplings[0] = float(summary["input_nearest_neighbor_coupling"])
    bias = -np.asarray(summary["final_renormalized_couplings"], dtype=float)
    micro_basis = OperatorBasis(length, EVEN_SHAPES)
    block_basis = OperatorBasis(length // 3, EVEN_SHAPES)
    sequences = np.random.SeedSequence(args.seed).spawn(args.runs)

    def one_run(sequence: np.random.SeedSequence) -> tuple[np.ndarray, float]:
        rng = np.random.default_rng(sequence)
        sampler = FastMultiOperatorBiasedMetropolis(
            IsingLattice.random(length, rng),
            couplings,
            bias,
            rng,
            EVEN_SHAPES,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        sampler.run_sweeps(args.thermalization)
        attempted_before = sampler.attempted
        accepted_before = sampler.accepted
        _, block_sum, _, _ = sampler.measure_moments(args.measurements, 1)
        attempted = sampler.attempted - attempted_before
        accepted = sampler.accepted - accepted_before
        sampler.assert_cache_consistent()
        return block_sum / args.measurements, accepted / attempted

    with ThreadPoolExecutor(max_workers=min(args.runs, os.cpu_count() or 1)) as pool:
        results = list(pool.map(one_run, sequences))
    run_means = np.stack([result[0] for result in results])
    block_sites = (length // 3) ** 2
    normalized = run_means / block_sites
    mean = normalized.mean(axis=0)
    se = normalized.std(axis=0, ddof=1) / np.sqrt(args.runs)
    z = mean / se
    critical_abs_z = NormalDist().inv_cdf(
        1.0 - args.family_alpha / (2.0 * len(EVEN_SHAPES))
    )
    max_abs_z = float(np.max(np.abs(z)))
    report = {
        "thermalization_sweeps": args.thermalization,
        "measurement_sweeps_per_run": args.measurements,
        "independent_runs": args.runs,
        "seed": args.seed,
        "mean_operators_per_block_site": mean.tolist(),
        "run_means_per_block_site": normalized.tolist(),
        "run_level_standard_errors": se.tolist(),
        "z_scores_against_uniform_target": z.tolist(),
        "max_abs_z": max_abs_z,
        "family_alpha": args.family_alpha,
        "multiple_testing_method": "two_sided_bonferroni",
        "bonferroni_critical_abs_z": critical_abs_z,
        "familywise_status": "PASS" if max_abs_z <= critical_abs_z else "FAIL",
        "acceptance_rates": [result[1] for result in results],
    }
    output = args.output or args.input / "frozen_validation.json"
    if args.output is not None and output.exists():
        raise FileExistsError(f"refusing to overwrite frozen validation: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
