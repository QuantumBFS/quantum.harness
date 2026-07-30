from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from vmcrg_ref import (
    MultiOperatorOptimizer,
    candidate_basis_metadata,
    candidate_even_shapes,
    published_survivor_indices,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the reconstructed 26-operator preliminary VMCRG screen"
    )
    parser.add_argument(
        "--pair-tie",
        choices=("axis5", "generic43"),
        required=True,
        help="required reconstruction choice for the tied thirteenth pair orbit",
    )
    parser.add_argument(
        "--coupling",
        type=float,
        required=True,
        help="nearest-neighbor input coupling; the paper does not publish this preliminary value",
    )
    parser.add_argument("--length", type=int, default=45)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--sweeps", type=int, default=20)
    parser.add_argument("--walkers", type=int, default=16)
    parser.add_argument("--mu", type=float, default=5e-5)
    parser.add_argument("--threshold", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def default_output(args: argparse.Namespace) -> Path:
    coupling_tag = f"{args.coupling:.7f}".replace(".", "p")
    return Path(
        f"output/L{args.length}_K{coupling_tag}_candidate26_{args.pair_tie}"
    )


def main() -> None:
    args = parse_args()
    if args.length % 3:
        raise ValueError("length must be divisible by 3")
    if args.length < 45:
        raise ValueError(
            "the candidate basis requires L>=45 so its longest term does not alias "
            "on the L/3 block lattice"
        )
    if args.threshold <= 0.0:
        raise ValueError("threshold must be positive")

    output = args.output or default_output(args)
    if (output / "summary.json").exists() or (output / "trajectory.npz").exists():
        raise FileExistsError(f"refusing to overwrite an existing run: {output}")
    output.mkdir(parents=True, exist_ok=True)

    shapes = candidate_even_shapes(args.pair_tie)
    couplings = np.zeros(len(shapes), dtype=float)
    couplings[0] = args.coupling
    initial_bias = np.zeros(len(shapes), dtype=float)

    run_config = {
        "experiment": "reconstructed_candidate_26_to_13_screen",
        "coordinate_status": "RECONSTRUCTED_NOT_SOURCE_VERIFIED",
        "preliminary_input_coupling_status": "USER_SUPPLIED_PAPER_UNSPECIFIED",
        "pair_tie": args.pair_tie,
        "length": args.length,
        "input_nearest_neighbor_coupling": args.coupling,
        "steps": args.steps,
        "sweeps_per_step": args.sweeps,
        "walkers": args.walkers,
        "learning_rate": args.mu,
        "screening_threshold": args.threshold,
        "seed": args.seed,
        "operators": candidate_basis_metadata(args.pair_tie),
    }
    (output / "run_config.json").write_text(
        json.dumps(run_config, indent=2), encoding="utf-8"
    )

    optimizer = MultiOperatorOptimizer(
        length=args.length,
        couplings=couplings,
        shapes=shapes,
        walkers=args.walkers,
        seed=args.seed,
        initial_bias=initial_bias,
        compiled=True,
        parallel_walkers=True,
    )
    started = time.perf_counter()
    records = optimizer.run(
        steps=args.steps,
        sweeps_per_step=args.sweeps,
        learning_rate=args.mu,
    )
    elapsed = time.perf_counter() - started
    for sampler in optimizer.samplers:
        sampler.assert_cache_consistent()

    instantaneous = np.stack([record.instantaneous_bias for record in records])
    running = np.stack([record.running_bias for record in records])
    means = np.stack([record.mean_operators for record in records])
    covariance = np.stack([record.covariance for record in records])
    gradients = np.stack([record.gradient for record in records])
    updates = np.stack([record.update for record in records])
    np.savez_compressed(
        output / "trajectory.npz",
        instantaneous_bias=instantaneous,
        running_bias=running,
        mean_operators=means,
        covariance=covariance,
        gradients=gradients,
        updates=updates,
    )

    final_couplings = -running[-1]
    observed = set(np.flatnonzero(np.abs(final_couplings) >= args.threshold).tolist())
    published = set(published_survivor_indices(shapes))
    missing = sorted(published - observed)
    unexpected = sorted(observed - published)
    block_sites = (args.length // 3) ** 2
    summary = {
        **run_config,
        "elapsed_seconds": elapsed,
        "input_couplings": couplings.tolist(),
        "initial_bias": initial_bias.tolist(),
        "operator_names": [shape.name for shape in shapes],
        "final_renormalized_couplings": final_couplings.tolist(),
        "final_mean_operators_per_block_site": (means[-1] / block_sites).tolist(),
        "final_acceptance_rates": [
            sampler.acceptance_rate for sampler in optimizer.samplers
        ],
        "screened_survivor_indices_zero_based": sorted(observed),
        "screened_survivor_names": [shapes[index].name for index in sorted(observed)],
        "published_survivor_indices_zero_based": sorted(published),
        "missing_published_survivors": [shapes[index].name for index in missing],
        "unexpected_candidate_survivors": [
            shapes[index].name for index in unexpected
        ],
        "screening_geometry_match": observed == published,
        "screening_status": "UNVALIDATED_OPTIMIZATION_RESULT",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
