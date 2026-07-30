#!/usr/bin/env python3
"""Measure how finite-shot noise changes subspace calibration success."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
import tempfile
import time
import warnings
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "fermichen99-sim-to-real-matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy

from optimizers import optimize_black_box_scipy
from sim_to_real import (
    BlackBoxDevice,
    make_demo_problem,
    make_drift_perturbation,
    make_fidelity,
    with_drift_mismatch,
)


warnings.filterwarnings(
    "ignore",
    message=".*encountered in matmul",
    category=RuntimeWarning,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path(
            "tracks/qcs/results/sim-to-real-calibration-v1/calibration_data.npz"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tracks/qcs/results/sim-to-real-noise-sweep-v1"),
    )
    parser.add_argument(
        "--shot-budgets",
        type=int,
        nargs="+",
        default=[4096, 16384, 65536, 262144],
    )
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--epsilon", type=float, default=0.3)
    parser.add_argument("--max-queries", type=int, default=1000)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--perturbation-seed", type=int, default=113)
    parser.add_argument("--seed", type=int, default=2027)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    args = parse_args()
    if not args.calibration.exists():
        raise FileNotFoundError(f"missing calibration: {args.calibration}")
    if (
        args.trials <= 0
        or args.max_queries <= 0
        or any(shots <= 0 for shots in args.shot_budgets)
    ):
        raise ValueError("trials, max_queries, and shot budgets must be positive")

    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    top_15 = np.asarray(
        calibration["hessian_eigenvectors"], dtype=np.float64
    )[:, :15]
    problem = make_demo_problem()
    true_problem = with_drift_mismatch(
        problem,
        make_drift_perturbation(
            problem, seed=args.perturbation_seed
        ),
        args.epsilon,
    )
    exact_fidelity = jax.jit(
        make_fidelity(
            true_problem, integrator="expm", n_steps=args.n_steps
        )
    )
    exact_fidelity(theta_star).block_until_ready()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    total_runs = len(args.shot_budgets) * args.trials * 2
    completed = 0
    total_start = time.perf_counter()
    progress(
        f"[1/3] noise sweep: epsilon={args.epsilon:g}, "
        f"{total_runs} runs, query budget={args.max_queries}"
    )

    for shot_index, shots in enumerate(args.shot_budgets):
        progress(f"[2/3] shots/query={shots}")
        for method, basis in (("model_top_15", top_15), ("raw_full_40", None)):
            for trial in range(args.trials):
                seed = (
                    args.seed
                    + 100000 * shot_index
                    + (50000 if method == "raw_full_40" else 0)
                    + trial
                )
                device = BlackBoxDevice(
                    exact_fidelity,
                    shots=shots,
                    seed=seed,
                )
                start = time.perf_counter()
                result = optimize_black_box_scipy(
                    device,
                    theta_star,
                    basis=basis,
                    method="COBYQA",
                    max_queries=args.max_queries,
                    target_infidelity=args.target_infidelity,
                    optimizer_options={
                        "initial_tr_radius": 0.25,
                        "final_tr_radius": 1e-6,
                    },
                )
                wall_seconds = time.perf_counter() - start
                best_infidelity = 1.0 - result.best_exact_fidelity
                records.append(
                    {
                        "shots_per_query": shots,
                        "method": method,
                        "trial": trial,
                        "seed": seed,
                        "success": result.query_to_target is not None,
                        "query_to_target": result.query_to_target,
                        "shots_to_target": (
                            None
                            if result.query_to_target is None
                            else result.query_to_target * shots
                        ),
                        "best_exact_infidelity": best_infidelity,
                        "queries_used": result.query_count,
                        "shots_used": result.shot_count,
                        "wall_seconds": wall_seconds,
                    }
                )
                completed += 1
                progress(
                    f"      {completed:>2}/{total_runs} {method:>12} "
                    f"#{trial}: best={best_infidelity:.2e}, "
                    f"q*={result.query_to_target}"
                )

    with (args.output_dir / "noise_sweep.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)

    summaries: list[dict[str, object]] = []
    for shots in args.shot_budgets:
        for method in ("model_top_15", "raw_full_40"):
            selected = [
                record
                for record in records
                if record["shots_per_query"] == shots
                and record["method"] == method
            ]
            successes = [
                record
                for record in selected
                if bool(record["success"])
            ]
            censored_queries = np.asarray(
                [
                    (
                        record["query_to_target"]
                        if record["query_to_target"] is not None
                        else args.max_queries + 1
                    )
                    for record in selected
                ],
                dtype=np.float64,
            )
            summaries.append(
                {
                    "shots_per_query": shots,
                    "method": method,
                    "success_rate": float(len(successes) / len(selected)),
                    "censored_query_median": float(
                        np.median(censored_queries)
                    ),
                    "query_median_successes": (
                        None
                        if not successes
                        else float(
                            np.median(
                                [
                                    record["query_to_target"]
                                    for record in successes
                                ]
                            )
                        )
                    ),
                    "shots_median_successes": (
                        None
                        if not successes
                        else float(
                            np.median(
                                [
                                    record["shots_to_target"]
                                    for record in successes
                                ]
                            )
                        )
                    ),
                    "best_infidelity_median": float(
                        np.median(
                            [
                                record["best_exact_infidelity"]
                                for record in selected
                            ]
                        )
                    ),
                }
            )

    with (args.output_dir / "noise_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(summaries[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(summaries)

    fig, (success_axis, cost_axis) = plt.subplots(1, 2, figsize=(10.5, 4.3))
    styles = {
        "model_top_15": ("o-", "model top 15"),
        "raw_full_40": ("s--", "raw full 40"),
    }
    for method, (style, label) in styles.items():
        selected = [
            summary for summary in summaries if summary["method"] == method
        ]
        success_axis.semilogx(
            args.shot_budgets,
            [summary["success_rate"] for summary in selected],
            style,
            label=label,
        )
        cost_axis.loglog(
            args.shot_budgets,
            [
                summary["censored_query_median"] * shots
                for summary, shots in zip(
                    selected, args.shot_budgets, strict=True
                )
            ],
            style,
            label=label,
        )
    success_axis.set(
        xlabel="shots per query",
        ylabel="success rate",
        ylim=(-0.04, 1.04),
        title="Probability of reaching 1−F ≤ 10⁻³",
    )
    cost_axis.set(
        xlabel="shots per query",
        ylabel="median total shots\n(failures censored)",
        title="Measurement cost to target",
    )
    for axis in (success_axis, cost_axis):
        axis.grid(alpha=0.2)
        axis.legend()
    fig.suptitle(f"Shot-noise boundary at drift mismatch ε={args.epsilon:g}")
    fig.tight_layout()
    fig.savefig(args.output_dir / "success_vs_shots.png", dpi=180)
    plt.close(fig)

    report = {
        "schema_version": 1,
        "run": "sim-to-real-noise-sweep-v1",
        "setup": {
            "epsilon": args.epsilon,
            "shot_budgets": args.shot_budgets,
            "trials": args.trials,
            "max_queries": args.max_queries,
            "target_infidelity": args.target_infidelity,
            "n_steps": args.n_steps,
            "perturbation_seed": args.perturbation_seed,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "jax": jax.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "devices": [str(device) for device in jax.devices()],
        },
        "wall_seconds": time.perf_counter() - total_start,
        "summaries": summaries,
        "artifacts": [
            "noise_sweep.csv",
            "noise_summary.csv",
            "success_vs_shots.png",
        ],
        "rerun": "python3 tracks/qcs/solutions/Fermichen99/run_noise_sweep.py",
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    progress(
        f"[3/3] complete in {report['wall_seconds']:.1f}s: "
        f"{args.output_dir}/run.json"
    )


if __name__ == "__main__":
    main()
