#!/usr/bin/env python3
"""Compare fixed-rank device subspace tracking with widening baselines."""

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
from dataclasses import asdict
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

from landscapes import (
    endpoint_jacobian,
    jacobian_subspace,
    subspace_metrics,
)
from optimizers import optimize_black_box_scipy
from sim_to_real import (
    BlackBoxDevice,
    make_demo_problem,
    make_drift_perturbation,
    make_fidelity,
    with_drift_mismatch,
)
from subspace_tracking import optimize_rank_preserving


warnings.filterwarnings(
    "ignore",
    message=".*encountered in matmul",
    category=RuntimeWarning,
)

METHODS = ("tracked_rank15", "fixed_top15", "fixed_top30", "raw_full40")


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
        default=Path("tracks/qcs/results/sim-to-real-rank15-tracking-v1"),
    )
    parser.add_argument(
        "--epsilons", type=float, nargs="+", default=[0.3, 0.5]
    )
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--shots", type=int, default=65536)
    parser.add_argument("--max-queries", type=int, default=1000)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--perturbation-seed", type=int, default=113)
    parser.add_argument("--seed", type=int, default=4517)
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=METHODS,
        default=list(METHODS),
    )
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    args = parse_args()
    if not args.calibration.exists():
        raise FileNotFoundError(f"missing calibration: {args.calibration}")
    if args.trials <= 0 or args.shots <= 0 or args.max_queries <= 0:
        raise ValueError("trials, shots, and max_queries must be positive")

    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    eigenvalues = np.asarray(
        calibration["hessian_eigenvalues"], dtype=np.float64
    )
    eigenvectors = np.asarray(
        calibration["hessian_eigenvectors"], dtype=np.float64
    )
    model_top15 = eigenvectors[:, :15]
    model_top30 = eigenvectors[:, :30]
    prior_curvatures = np.maximum(eigenvalues[:15], 1e-12)

    problem = make_demo_problem()
    perturbation = make_drift_perturbation(
        problem, seed=args.perturbation_seed
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    stage_records: list[dict[str, object]] = []
    total_runs = len(args.epsilons) * args.trials * len(args.methods)
    completed = 0
    total_start = time.perf_counter()
    progress(
        f"[1/4] rank-15 tracking study: {total_runs} runs, "
        f"shots/query={args.shots}, budget={args.max_queries}"
    )

    for epsilon_index, epsilon in enumerate(args.epsilons):
        true_problem = with_drift_mismatch(problem, perturbation, epsilon)
        exact_fidelity = jax.jit(
            make_fidelity(
                true_problem, integrator="expm", n_steps=args.n_steps
            )
        )
        exact_fidelity(theta_star).block_until_ready()
        true_initial_jacobian = endpoint_jacobian(
            true_problem, theta_star, n_steps=args.n_steps
        )
        _, true_initial_basis = jacobian_subspace(
            true_initial_jacobian, 15
        )
        initial_overlap = subspace_metrics(
            model_top15, true_initial_basis
        )
        progress(
            f"[2/4] epsilon={epsilon:g}: initial top-15 overlap="
            f"{initial_overlap.mean_overlap:.3f}"
        )

        for trial in range(args.trials):
            for method_index, method in enumerate(args.methods):
                seed = (
                    args.seed
                    + 100000 * epsilon_index
                    + 10000 * method_index
                    + trial
                )
                device = BlackBoxDevice(
                    exact_fidelity,
                    shots=args.shots,
                    seed=seed,
                )
                start = time.perf_counter()
                tracking_stages = None
                final_basis = None
                final_origin = None
                if method == "tracked_rank15":
                    result = optimize_rank_preserving(
                        device,
                        theta_star,
                        model_top15,
                        prior_curvatures,
                        stage_query_budgets=(200, 200, 272),
                        max_total_queries=args.max_queries,
                        target_infidelity=args.target_infidelity,
                        scout_count=2,
                        finite_difference_step=0.4,
                        center_repeats=4,
                        confirmation_queries=4,
                        confirmation_z_score=1.64,
                        diagonal_blend=0.5,
                        cross_shrink=0.2,
                        seed=seed + 700000,
                    )
                    summary = result.summary
                    final_basis = result.final_basis
                    final_origin = result.final_origin
                    tracking_stages = result.stages
                else:
                    basis = {
                        "fixed_top15": model_top15,
                        "fixed_top30": model_top30,
                        "raw_full40": None,
                    }[method]
                    summary = optimize_black_box_scipy(
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

                final_overlap_mean = None
                final_overlap_minimum = None
                final_largest_angle = None
                if final_basis is not None and final_origin is not None:
                    true_final_jacobian = endpoint_jacobian(
                        true_problem,
                        final_origin,
                        n_steps=args.n_steps,
                    )
                    _, true_final_basis = jacobian_subspace(
                        true_final_jacobian, 15
                    )
                    final_overlap = subspace_metrics(
                        final_basis, true_final_basis
                    )
                    final_overlap_mean = final_overlap.mean_overlap
                    final_overlap_minimum = final_overlap.minimum_overlap
                    final_largest_angle = (
                        final_overlap.largest_angle_degrees
                    )

                best_infidelity = 1.0 - summary.best_exact_fidelity
                records.append(
                    {
                        "epsilon": epsilon,
                        "method": method,
                        "rank": {
                            "tracked_rank15": 15,
                            "fixed_top15": 15,
                            "fixed_top30": 30,
                            "raw_full40": 40,
                        }[method],
                        "trial": trial,
                        "seed": seed,
                        "success": summary.query_to_target is not None,
                        "query_to_target": summary.query_to_target,
                        "queries_used": summary.query_count,
                        "shots_to_target": (
                            None
                            if summary.query_to_target is None
                            else summary.query_to_target * args.shots
                        ),
                        "shots_used": summary.shot_count,
                        "best_exact_infidelity": best_infidelity,
                        "initial_overlap_mean": initial_overlap.mean_overlap,
                        "final_overlap_mean": final_overlap_mean,
                        "final_overlap_minimum": final_overlap_minimum,
                        "final_largest_angle_degrees": final_largest_angle,
                        "wall_seconds": wall_seconds,
                    }
                )
                if tracking_stages is not None:
                    for stage in tracking_stages:
                        stage_records.append(
                            {
                                "epsilon": epsilon,
                                "trial": trial,
                                "seed": seed,
                                **asdict(stage),
                            }
                        )
                completed += 1
                progress(
                    f"      {completed:>2}/{total_runs} {method:>14} "
                    f"#{trial}: best={best_infidelity:.2e}, "
                    f"q*={summary.query_to_target}, "
                    f"q={summary.query_count}"
                )

    progress("[3/4] aggregate and render")
    with (args.output_dir / "tracking_trials.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)
    with (args.output_dir / "tracking_stages.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(stage_records[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(stage_records)

    summaries: list[dict[str, object]] = []
    for epsilon in args.epsilons:
        for method in args.methods:
            selected = [
                record
                for record in records
                if record["epsilon"] == epsilon
                and record["method"] == method
            ]
            censored = np.asarray(
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
                    "epsilon": epsilon,
                    "method": method,
                    "rank": selected[0]["rank"],
                    "success_rate": float(
                        np.mean(
                            [bool(record["success"]) for record in selected]
                        )
                    ),
                    "censored_query_median": float(np.median(censored)),
                    "censored_query_q25": float(np.quantile(censored, 0.25)),
                    "censored_query_q75": float(np.quantile(censored, 0.75)),
                    "best_infidelity_median": float(
                        np.median(
                            [
                                record["best_exact_infidelity"]
                                for record in selected
                            ]
                        )
                    ),
                    "queries_used_median": float(
                        np.median(
                            [record["queries_used"] for record in selected]
                        )
                    ),
                    "final_overlap_mean_median": (
                        None
                        if method != "tracked_rank15"
                        else float(
                            np.median(
                                [
                                    record["final_overlap_mean"]
                                    for record in selected
                                ]
                            )
                        )
                    ),
                }
            )
    with (args.output_dir / "tracking_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(summaries[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(summaries)

    figure, (success_axis, query_axis) = plt.subplots(
        1, 2, figsize=(11, 4.5)
    )
    x = np.arange(len(args.epsilons), dtype=np.float64)
    width = 0.18
    colors = {
        "tracked_rank15": "tab:blue",
        "fixed_top15": "tab:cyan",
        "fixed_top30": "tab:orange",
        "raw_full40": "tab:red",
    }
    labels = {
        "tracked_rank15": "tracked rank 15",
        "fixed_top15": "fixed top 15",
        "fixed_top30": "fixed top 30",
        "raw_full40": "raw full 40",
    }
    for method_index, method in enumerate(args.methods):
        selected = [
            summary for summary in summaries if summary["method"] == method
        ]
        offset = (method_index - (len(args.methods) - 1) / 2.0) * width
        success_axis.bar(
            x + offset,
            [summary["success_rate"] for summary in selected],
            width,
            color=colors[method],
            label=labels[method],
        )
        medians = np.asarray(
            [summary["censored_query_median"] for summary in selected]
        )
        lowers = np.asarray(
            [summary["censored_query_q25"] for summary in selected]
        )
        uppers = np.asarray(
            [summary["censored_query_q75"] for summary in selected]
        )
        query_axis.errorbar(
            x + offset,
            medians,
            yerr=np.vstack([medians - lowers, uppers - medians]),
            fmt="o",
            capsize=3,
            color=colors[method],
            label=labels[method],
        )
    for axis in (success_axis, query_axis):
        axis.set_xticks(x, [f"ε={epsilon:g}" for epsilon in args.epsilons])
        axis.grid(axis="y", alpha=0.2)
    success_axis.set(
        ylabel="success rate",
        ylim=(0.0, 1.05),
        title="Probability of reaching 1−F ≤ 10⁻³",
    )
    query_axis.axhline(
        args.max_queries, color="gray", linestyle=":", label="query budget"
    )
    query_axis.set(
        ylabel="queries to target\n(failures censored at budget+1)",
        ylim=(0.0, args.max_queries * 1.08),
        title="Closed-loop query cost",
    )
    handles, legend_labels = success_axis.get_legend_handles_labels()
    figure.legend(
        handles,
        legend_labels,
        loc="upper center",
        ncol=len(args.methods),
        fontsize=8,
    )
    figure.suptitle(
        "Fixed-rank subspace tracking versus permanent widening",
        y=1.03,
    )
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "rank15_tracking_comparison.png", dpi=180
    )
    plt.close(figure)

    tracked_records = [
        record for record in records if record["method"] == "tracked_rank15"
    ]
    figure, axis = plt.subplots(figsize=(7, 4.5))
    positions = np.arange(len(args.epsilons))
    initial_values = []
    final_values = []
    for epsilon in args.epsilons:
        selected = [
            record
            for record in tracked_records
            if record["epsilon"] == epsilon
        ]
        initial_values.append(
            float(np.median([r["initial_overlap_mean"] for r in selected]))
        )
        final_values.append(
            float(np.median([r["final_overlap_mean"] for r in selected]))
        )
    axis.plot(positions, initial_values, "o--", label="initial model rank-15")
    axis.plot(positions, final_values, "s-", label="tracked rank-15")
    axis.set_xticks(
        positions, [f"ε={epsilon:g}" for epsilon in args.epsilons]
    )
    axis.set(
        ylabel="mean squared principal-angle cosine",
        ylim=(0.0, 1.02),
        title="Offline diagnostic: alignment with device active subspace",
    )
    axis.grid(alpha=0.2)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "rank15_subspace_alignment.png", dpi=180
    )
    plt.close(figure)

    report = {
        "schema_version": 1,
        "run": "sim-to-real-rank15-tracking-v1",
        "purpose": (
            "Keep the deployed search rank fixed at d^2-1 while rotating "
            "the basis from query-only device feedback."
        ),
        "setup": {
            "epsilons": args.epsilons,
            "trials": args.trials,
            "shots_per_query": args.shots,
            "max_queries": args.max_queries,
            "target_infidelity": args.target_infidelity,
            "n_steps": args.n_steps,
            "perturbation_seed": args.perturbation_seed,
            "methods": args.methods,
            "tracking_rank": 15,
            "tracking_stage_query_budgets": [200, 200, 272],
            "scout_count_per_update": 2,
            "update_method": "targeted cross-block curvature",
            "finite_difference_step": 0.4,
            "diagonal_blend": 0.5,
            "cross_shrink": 0.2,
        },
        "black_box_boundary": (
            "Tracking decisions use only reported query values. Exact "
            "fidelity and true Jacobian overlaps are offline diagnostics."
        ),
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
            "tracking_trials.csv",
            "tracking_stages.csv",
            "tracking_summary.csv",
            "rank15_tracking_comparison.png",
            "rank15_subspace_alignment.png",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/"
            "run_rank15_tracking.py"
        ),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    progress(
        f"[4/4] complete in {report['wall_seconds']:.1f}s: "
        f"{args.output_dir}/run.json"
    )


if __name__ == "__main__":
    main()
