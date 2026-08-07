from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from vmcrg_ref import EVEN_SHAPES, MultiOperatorOptimizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one 13-even-operator VMCRG step")
    parser.add_argument("--length", type=int, default=45)
    parser.add_argument("--coupling", type=float, default=0.436)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--sweeps", type=int, default=20)
    parser.add_argument("--walkers", type=int, default=16)
    parser.add_argument("--mu", type=float, default=5e-5)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument(
        "--previous",
        type=Path,
        help="previous RG output directory; warm-starts from its final bias",
    )
    parser.add_argument(
        "--couplings-file",
        type=Path,
        help="JSON fixed-point candidate containing candidate_couplings",
    )
    parser.add_argument(
        "--initial-bias-from",
        type=Path,
        help="RG output directory whose final bias initializes this run",
    )
    parser.add_argument("--output", type=Path, default=Path("output/L45_K0436_rg1"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.length % 3:
        raise ValueError("length must be divisible by 3")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.previous is not None and args.couplings_file is not None:
        raise ValueError("--previous and --couplings-file are mutually exclusive")
    input_source: str
    if args.couplings_file is not None:
        coupling_data = json.loads(args.couplings_file.read_text(encoding="utf-8"))
        couplings = np.asarray(coupling_data["candidate_couplings"], dtype=float)
        if couplings.shape != (len(EVEN_SHAPES),) or not np.all(np.isfinite(couplings)):
            raise ValueError("candidate_couplings must contain 13 finite values")
        initial_bias = -couplings
        input_source = str(args.couplings_file.resolve())
    elif args.previous is None:
        couplings = np.zeros(len(EVEN_SHAPES), dtype=float)
        couplings[0] = args.coupling
        initial_bias = np.zeros(len(EVEN_SHAPES), dtype=float)
        input_source = "nearest_neighbor_scalar"
    else:
        previous = json.loads(
            (args.previous / "summary.json").read_text(encoding="utf-8")
        )
        couplings = np.asarray(
            previous["final_renormalized_couplings"], dtype=float
        )
        initial_bias = -couplings
        input_source = str(args.previous.resolve())
    initial_bias_source = "default_for_input_source"
    if args.initial_bias_from is not None:
        bias_summary = json.loads(
            (args.initial_bias_from / "summary.json").read_text(encoding="utf-8")
        )
        initial_bias = -np.asarray(
            bias_summary["final_renormalized_couplings"], dtype=float
        )
        if initial_bias.shape != (len(EVEN_SHAPES),) or not np.all(
            np.isfinite(initial_bias)
        ):
            raise ValueError("initial bias source must contain 13 finite couplings")
        initial_bias_source = str(args.initial_bias_from.resolve())

    optimizer = MultiOperatorOptimizer(
        length=args.length,
        couplings=couplings,
        shapes=EVEN_SHAPES,
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
        args.output / "trajectory.npz",
        instantaneous_bias=instantaneous,
        running_bias=running,
        mean_operators=means,
        covariance=covariance,
        gradients=gradients,
        updates=updates,
    )

    final_couplings = -running[-1]
    block_sites = (args.length // 3) ** 2
    summary = {
        "length": args.length,
        "input_nearest_neighbor_coupling": float(couplings[0]),
        "input_couplings": couplings.tolist(),
        "input_source": input_source,
        "initial_bias_source": initial_bias_source,
        "initial_bias": initial_bias.tolist(),
        "steps": args.steps,
        "sweeps_per_step": args.sweeps,
        "walkers": args.walkers,
        "learning_rate": args.mu,
        "seed": args.seed,
        "elapsed_seconds": elapsed,
        "operator_names": [shape.name for shape in EVEN_SHAPES],
        "final_renormalized_couplings": final_couplings.tolist(),
        "final_mean_operators_per_block_site": (means[-1] / block_sites).tolist(),
        "final_acceptance_rates": [
            sampler.acceptance_rate for sampler in optimizer.samplers
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
