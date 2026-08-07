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
    covariance_matrices_from_sums,
    estimate_rg_jacobian,
    scaling_dimensions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the biased RG Jacobian using paper Eqs. 15-17"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--thermalization", type=int, default=5000)
    parser.add_argument("--measurements", type=int, default=1_000_000)
    parser.add_argument("--spacing", type=int, default=1)
    parser.add_argument("--runs", type=int, default=16)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260740)
    parser.add_argument(
        "--seed-manifest",
        type=Path,
        help="JSON with explicit NumPy SeedSequence entropy/spawn_key records",
    )
    return parser.parse_args()


def _run_sequences(
    args: argparse.Namespace,
) -> tuple[list[np.random.SeedSequence], dict[str, object], int]:
    if args.seed_manifest is None:
        sequences = list(np.random.SeedSequence(args.seed).spawn(args.runs))
        records = [
            {"entropy": int(sequence.entropy), "spawn_key": list(sequence.spawn_key)}
            for sequence in sequences
        ]
        return sequences, {
            "master_seed": args.seed,
            "seed_manifest": None,
            "run_seed_sequences": records,
        }, args.seed + 1
    manifest_path = args.seed_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("run_seed_sequences")
    if not isinstance(records, list) or len(records) != args.runs:
        raise ValueError("seed manifest must contain exactly --runs run_seed_sequences")
    sequences = [
        np.random.SeedSequence(
            int(record["entropy"]),
            spawn_key=tuple(int(value) for value in record["spawn_key"]),
        )
        for record in records
    ]
    return sequences, {
        "master_seed": None,
        "seed_manifest": str(manifest_path),
        "run_seed_sequences": records,
    }, int(manifest["bootstrap_seed"])


def _summary_input(summary: dict[str, object]) -> tuple[int, np.ndarray, np.ndarray]:
    names = summary.get("operator_names")
    expected_names = [shape.name for shape in EVEN_SHAPES]
    if names != expected_names:
        raise ValueError("input does not use the published 13-even-operator basis")
    length = int(summary["length"])
    couplings = np.asarray(summary["input_couplings"], dtype=np.float64)
    renormalized = np.asarray(
        summary["final_renormalized_couplings"], dtype=np.float64
    )
    expected_shape = (len(EVEN_SHAPES),)
    if couplings.shape != expected_shape or renormalized.shape != expected_shape:
        raise ValueError("input coupling vectors have the wrong shape")
    return length, couplings, -renormalized


def _combine_covariances(
    selection: np.ndarray,
    measurements: int,
    micro_sums: np.ndarray,
    block_sums: np.ndarray,
    cross_sums: np.ndarray,
    block_outer_sums: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    return covariance_matrices_from_sums(
        sample_count=measurements * selection.size,
        micro_sum=micro_sums[selection].sum(axis=0),
        block_sum=block_sums[selection].sum(axis=0),
        micro_block_sum=cross_sums[selection].sum(axis=0),
        block_outer_sum=block_outer_sums[selection].sum(axis=0),
    )


def _distribution(values: np.ndarray) -> dict[str, float]:
    if values.size < 2:
        raise ValueError("at least two valid bootstrap values are required")
    return {
        "mean": float(values.mean()),
        "standard_error": float(values.std(ddof=1)),
        "ci95_low": float(np.quantile(values, 0.025)),
        "ci95_high": float(np.quantile(values, 0.975)),
    }


def main() -> None:
    args = parse_args()
    if args.thermalization < 0:
        raise ValueError("thermalization cannot be negative")
    if args.measurements < 2 or args.spacing <= 0:
        raise ValueError("measurements must be at least two and spacing must be positive")
    if args.runs < 3 or args.bootstrap < 20:
        raise ValueError("at least three runs and twenty bootstrap replicates are required")

    input_dir = args.input.resolve()
    output = (args.output or input_dir / "paper_jacobian.json").resolve()
    arrays_output = output.with_suffix(".npz")
    if output.exists() or arrays_output.exists():
        raise FileExistsError(f"refusing to overwrite Jacobian output: {output}")
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    length, even_couplings, even_bias = _summary_input(summary)

    shapes = (*EVEN_SHAPES, *ODD_SHAPES)
    couplings = np.concatenate((even_couplings, np.zeros(len(ODD_SHAPES))))
    bias = np.concatenate((even_bias, np.zeros(len(ODD_SHAPES))))
    micro_basis = OperatorBasis(length, shapes)
    block_basis = OperatorBasis(length // 3, shapes)
    micro_basis.packed_incidence()
    block_basis.packed_incidence()
    sequences, seed_provenance, bootstrap_seed = _run_sequences(args)

    def one_run(sequence: np.random.SeedSequence) -> tuple[np.ndarray, ...]:
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
        if args.thermalization:
            sampler.run_sweeps(args.thermalization)
        attempted_before = sampler.attempted
        accepted_before = sampler.accepted
        moments = sampler.measure_moments(args.measurements, args.spacing)
        attempted = sampler.attempted - attempted_before
        accepted = sampler.accepted - accepted_before
        sampler.assert_cache_consistent()
        acceptance = np.asarray(accepted / attempted, dtype=np.float64)
        return (*moments, acceptance)

    with ThreadPoolExecutor(max_workers=min(args.runs, os.cpu_count() or 1)) as pool:
        results = list(pool.map(one_run, sequences))
    micro_sums = np.stack([result[0] for result in results])
    block_sums = np.stack([result[1] for result in results])
    cross_sums = np.stack([result[2] for result in results])
    block_outer_sums = np.stack([result[3] for result in results])
    acceptance_rates = np.asarray([result[4] for result in results])

    all_runs = np.arange(args.runs)
    a_all, b_all = _combine_covariances(
        all_runs,
        args.measurements,
        micro_sums,
        block_sums,
        cross_sums,
        block_outer_sums,
    )
    even_slice = slice(0, len(EVEN_SHAPES))
    odd_slice = slice(len(EVEN_SHAPES), len(shapes))
    even = estimate_rg_jacobian(a_all[even_slice, even_slice], b_all[even_slice, even_slice])
    odd = estimate_rg_jacobian(a_all[odd_slice, odd_slice], b_all[odd_slice, odd_slice])

    rng = np.random.default_rng(bootstrap_seed)
    bootstrap_even: list[float] = []
    bootstrap_odd: list[float] = []
    bootstrap_scaling: list[dict[str, float]] = []
    invalid_messages: list[str] = []
    for _ in range(args.bootstrap):
        selection = rng.integers(0, args.runs, size=args.runs)
        try:
            a_sample, b_sample = _combine_covariances(
                selection,
                args.measurements,
                micro_sums,
                block_sums,
                cross_sums,
                block_outer_sums,
            )
            lambda_even = estimate_rg_jacobian(
                a_sample[even_slice, even_slice], b_sample[even_slice, even_slice]
            ).leading_eigenvalue
            lambda_odd = estimate_rg_jacobian(
                a_sample[odd_slice, odd_slice], b_sample[odd_slice, odd_slice]
            ).leading_eigenvalue
        except (ValueError, np.linalg.LinAlgError) as error:
            if len(invalid_messages) < 5:
                invalid_messages.append(str(error))
            continue
        bootstrap_even.append(lambda_even)
        bootstrap_odd.append(lambda_odd)
        bootstrap_scaling.append(scaling_dimensions(lambda_even, lambda_odd))

    even_samples = np.asarray(bootstrap_even)
    odd_samples = np.asarray(bootstrap_odd)
    if even_samples.size < 2:
        raise RuntimeError("fewer than two valid bootstrap Jacobians were obtained")
    invalid_count = args.bootstrap - even_samples.size
    point_scaling = scaling_dimensions(even.leading_eigenvalue, odd.leading_eigenvalue)
    scaling_uncertainty = {
        name: _distribution(np.asarray([sample[name] for sample in bootstrap_scaling]))
        for name in point_scaling
    }
    exact_even = 3.0
    exact_odd = float(3.0 ** (15.0 / 8.0))
    result = {
        "status": "NUMERICALLY_STABLE" if invalid_count == 0 else "BOOTSTRAP_UNSTABLE",
        "method": "biased_ensemble_paper_equations_15_to_17",
        "input": str(input_dir),
        "length": length,
        "block_scale": 3,
        "thermalization_sweeps": args.thermalization,
        "thermalization_schedule_source": "implementation_choice_not_published",
        "measurements_per_run": args.measurements,
        "measurement_count_source": (
            "paper_Table_I_for_formal_preset; command_line_choice_otherwise"
        ),
        "sweeps_between_measurements": args.spacing,
        "independent_runs": args.runs,
        "independent_run_count_source": (
            "paper_Table_I_for_formal_preset; command_line_choice_otherwise"
        ),
        "bootstrap_replicates": args.bootstrap,
        "valid_bootstrap_replicates": int(even_samples.size),
        "invalid_bootstrap_replicates": int(invalid_count),
        "invalid_bootstrap_examples": invalid_messages,
        "seed": seed_provenance["master_seed"],
        "seed_manifest": seed_provenance["seed_manifest"],
        "run_seed_sequences": seed_provenance["run_seed_sequences"],
        "bootstrap_seed": bootstrap_seed,
        "mean_acceptance_rate": float(acceptance_rates.mean()),
        "even": {
            "operators": [shape.name for shape in EVEN_SHAPES],
            "leading_eigenvalue": even.leading_eigenvalue,
            "bootstrap": _distribution(even_samples),
            "b_condition_number": even.b_condition_number,
            "equation_relative_residual": even.equation_relative_residual,
            "paper_exact_value": exact_even,
            "difference_from_exact": even.leading_eigenvalue - exact_even,
        },
        "odd": {
            "operators": [shape.name for shape in ODD_SHAPES],
            "leading_eigenvalue": odd.leading_eigenvalue,
            "bootstrap": _distribution(odd_samples),
            "b_condition_number": odd.b_condition_number,
            "equation_relative_residual": odd.equation_relative_residual,
            "paper_exact_value": exact_odd,
            "difference_from_exact": odd.leading_eigenvalue - exact_odd,
        },
        "critical_exponents": {
            name: {"estimate": value, "bootstrap": scaling_uncertainty[name]}
            for name, value in point_scaling.items()
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    np.savez_compressed(
        arrays_output,
        a_even=even.a,
        b_even=even.b,
        t_even=even.transformation,
        a_odd=odd.a,
        b_odd=odd.b,
        t_odd=odd.transformation,
        bootstrap_lambda_even=even_samples,
        bootstrap_lambda_odd=odd_samples,
        run_micro_sums=micro_sums,
        run_block_sums=block_sums,
        run_cross_sums=cross_sums,
        run_block_outer_sums=block_outer_sums,
        acceptance_rates=acceptance_rates,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
