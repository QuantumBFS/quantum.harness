#!/usr/bin/env python3
"""Headline sweep: black-box cost versus reduced search dimension."""

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

from landscapes import random_subspace
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
        default=Path("tracks/qcs/results/sim-to-real-dimension-sweep-v1"),
    )
    parser.add_argument(
        "--epsilons", type=float, nargs="+", default=[0.1, 0.3, 0.5]
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        nargs="+",
        default=[3, 5, 10, 15, 20, 30, 40],
    )
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--shots", type=int, default=65536)
    parser.add_argument("--max-queries", type=int, default=1000)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--perturbation-seed", type=int, default=113)
    parser.add_argument("--seed", type=int, default=1009)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def quantiles(values: list[float]) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    lower, median, upper = np.quantile(array, [0.25, 0.5, 0.75])
    return float(lower), float(median), float(upper)


def main() -> None:
    args = parse_args()
    if not args.calibration.exists():
        raise FileNotFoundError(f"missing calibration: {args.calibration}")
    if args.trials <= 0 or args.shots <= 0 or args.max_queries <= 0:
        raise ValueError("trials, shots, and max_queries must be positive")
    if any(epsilon < 0.0 for epsilon in args.epsilons):
        raise ValueError("epsilons must be non-negative")

    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    eigenvectors = np.asarray(
        calibration["hessian_eigenvectors"], dtype=np.float64
    )
    if any(
        dimension <= 0 or dimension > theta_star.size
        for dimension in args.dimensions
    ):
        raise ValueError(f"dimensions must lie in [1, {theta_star.size}]")
    if not np.isfinite(eigenvectors).all():
        raise FloatingPointError("non-finite model Hessian eigenvectors")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    problem = make_demo_problem()
    perturbation = make_drift_perturbation(
        problem, seed=args.perturbation_seed
    )
    records: list[dict[str, object]] = []
    total_start = time.perf_counter()
    total_runs = len(args.epsilons) * args.trials * (
        2 * len(args.dimensions) + 1
    )
    completed_runs = 0
    progress(
        f"[1/3] dimension sweep: {total_runs} runs, "
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
        warm_infidelity = 1.0 - float(exact_fidelity(theta_star))
        progress(
            f"[2/3] epsilon={epsilon:g}: "
            f"open-loop infidelity={warm_infidelity:.3e}"
        )

        for dimension in args.dimensions:
            informed_basis = eigenvectors[:, :dimension]
            for trial in range(args.trials):
                for subspace in ("hessian", "random"):
                    basis_seed = (
                        args.seed
                        + 100000 * epsilon_index
                        + 1000 * dimension
                        + trial
                    )
                    if subspace == "hessian":
                        basis = informed_basis
                    else:
                        basis = np.asarray(
                            random_subspace(
                                theta_star.size,
                                dimension,
                                seed=basis_seed,
                            )
                        )
                    device_seed = basis_seed + (
                        0 if subspace == "hessian" else 500000
                    )
                    device = BlackBoxDevice(
                        exact_fidelity,
                        shots=args.shots,
                        seed=device_seed,
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
                            "epsilon": epsilon,
                            "warm_infidelity": warm_infidelity,
                            "dimension": dimension,
                            "subspace": subspace,
                            "trial": trial,
                            "basis_seed": basis_seed,
                            "device_seed": device_seed,
                            "best_exact_infidelity": best_infidelity,
                            "success": result.query_to_target is not None,
                            "query_to_target": result.query_to_target,
                            "queries_used": result.query_count,
                            "shots_to_target": (
                                None
                                if result.query_to_target is None
                                else result.query_to_target * args.shots
                            ),
                            "shots_used": result.shot_count,
                            "wall_seconds": wall_seconds,
                        }
                    )
                    completed_runs += 1
                    progress(
                        f"      {completed_runs:>3}/{total_runs} "
                        f"k={dimension:>2} {subspace:>7} #{trial}: "
                        f"best={best_infidelity:.2e}, "
                        f"q*={result.query_to_target}"
                    )

        # The raw-coordinate full search is the operational baseline in the
        # challenge statement.  Keeping it separate from the k=40 Hessian
        # rotation also exposes coordinate-order sensitivity under shot noise.
        for trial in range(args.trials):
            device_seed = args.seed + 900000 + 100000 * epsilon_index + trial
            device = BlackBoxDevice(
                exact_fidelity,
                shots=args.shots,
                seed=device_seed,
            )
            start = time.perf_counter()
            result = optimize_black_box_scipy(
                device,
                theta_star,
                basis=None,
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
                    "epsilon": epsilon,
                    "warm_infidelity": warm_infidelity,
                    "dimension": theta_star.size,
                    "subspace": "raw_full",
                    "trial": trial,
                    "basis_seed": None,
                    "device_seed": device_seed,
                    "best_exact_infidelity": best_infidelity,
                    "success": result.query_to_target is not None,
                    "query_to_target": result.query_to_target,
                    "queries_used": result.query_count,
                    "shots_to_target": (
                        None
                        if result.query_to_target is None
                        else result.query_to_target * args.shots
                    ),
                    "shots_used": result.shot_count,
                    "wall_seconds": wall_seconds,
                }
            )
            completed_runs += 1
            progress(
                f"      {completed_runs:>3}/{total_runs} "
                f"k=40 raw_full #{trial}: best={best_infidelity:.2e}, "
                f"q*={result.query_to_target}"
            )

    csv_path = args.output_dir / "dimension_sweep.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)

    summaries: list[dict[str, object]] = []
    for epsilon in args.epsilons:
        for dimension in args.dimensions:
            subspaces = ("hessian", "random")
            if dimension == theta_star.size:
                subspaces = (*subspaces, "raw_full")
            for subspace in subspaces:
                selected = [
                    record
                    for record in records
                    if record["epsilon"] == epsilon
                    and record["dimension"] == dimension
                    and record["subspace"] == subspace
                ]
                success_rate = float(
                    np.mean([bool(record["success"]) for record in selected])
                )
                # Failed runs are right-censored at budget+1 for a compact,
                # conservative query-cost curve.
                censored_queries = [
                    float(
                        record["query_to_target"]
                        if record["query_to_target"] is not None
                        else args.max_queries + 1
                    )
                    for record in selected
                ]
                q25, median, q75 = quantiles(censored_queries)
                best_q25, best_median, best_q75 = quantiles(
                    [
                        float(record["best_exact_infidelity"])
                        for record in selected
                    ]
                )
                summaries.append(
                    {
                        "epsilon": epsilon,
                        "dimension": dimension,
                        "subspace": subspace,
                        "success_rate": success_rate,
                        "censored_query_q25": q25,
                        "censored_query_median": median,
                        "censored_query_q75": q75,
                        "best_infidelity_q25": best_q25,
                        "best_infidelity_median": best_median,
                        "best_infidelity_q75": best_q75,
                    }
                )

    with (args.output_dir / "dimension_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(summaries[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(summaries)

    fig, axes = plt.subplots(
        1,
        len(args.epsilons),
        figsize=(5.1 * len(args.epsilons), 4.6),
        sharey=True,
    )
    if len(args.epsilons) == 1:
        axes = [axes]
    styles = {
        "hessian": ("o-", "tab:blue", "model Hessian"),
        "random": ("s--", "tab:orange", "random"),
        "raw_full": ("X", "tab:red", "raw full 40"),
    }
    for axis, epsilon in zip(axes, args.epsilons, strict=True):
        for subspace, (style, color, label) in styles.items():
            selected = [
                summary
                for summary in summaries
                if summary["epsilon"] == epsilon
                and summary["subspace"] == subspace
            ]
            if not selected:
                continue
            plot_dimensions = [
                int(summary["dimension"]) for summary in selected
            ]
            medians = np.asarray(
                [summary["censored_query_median"] for summary in selected]
            )
            lowers = np.asarray(
                [summary["censored_query_q25"] for summary in selected]
            )
            uppers = np.asarray(
                [summary["censored_query_q75"] for summary in selected]
            )
            axis.errorbar(
                plot_dimensions,
                medians,
                yerr=np.vstack([medians - lowers, uppers - medians]),
                fmt=style,
                color=color,
                capsize=3,
                label=label,
            )
            for dimension, median, summary in zip(
                plot_dimensions, medians, selected, strict=True
            ):
                axis.annotate(
                    f"{summary['success_rate']:.0%}",
                    (dimension, median),
                    textcoords="offset points",
                    xytext=(0, 7 if subspace == "hessian" else -13),
                    ha="center",
                    fontsize=7,
                    color=color,
                )
        axis.axvline(15, color="black", linestyle=":", label="d²−1 = 15")
        axis.axhline(
            args.max_queries,
            color="gray",
            linestyle=":",
            label="query budget",
        )
        axis.set(
            xlabel="search dimension k",
            title=f"drift mismatch ε={epsilon:g}",
            ylim=(0, args.max_queries * 1.08),
        )
        axis.grid(alpha=0.2)
    axes[0].set_ylabel(
        "queries to true target\n(failures censored at budget+1)"
    )
    handles, labels = axes[-1].get_legend_handles_labels()
    unique = dict(zip(labels, handles, strict=True))
    fig.legend(
        unique.values(),
        unique.keys(),
        loc="upper center",
        ncol=len(unique),
        fontsize=8,
    )
    fig.suptitle(
        f"Finite-shot black-box calibration ({args.shots} shots/query)",
        y=1.03,
    )
    fig.tight_layout()
    fig.savefig(args.output_dir / "queries_vs_dimension.png", dpi=180)
    plt.close(fig)

    report = {
        "schema_version": 1,
        "run": "sim-to-real-dimension-sweep-v1",
        "setup": {
            "epsilons": args.epsilons,
            "dimensions": args.dimensions,
            "trials": args.trials,
            "shots_per_query": args.shots,
            "max_queries": args.max_queries,
            "target_infidelity": args.target_infidelity,
            "n_steps": args.n_steps,
            "perturbation_seed": args.perturbation_seed,
            "optimizer": "COBYQA",
            "initial_trust_region_radius": 0.25,
        },
        "interpretation": (
            "Query medians and IQR include failed runs right-censored at "
            "max_queries+1; percentages on the plot are success rates. "
            "Success is evaluated with latent exact fidelity and is never "
            "exposed to the optimizer."
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
            "dimension_sweep.csv",
            "dimension_summary.csv",
            "queries_vs_dimension.png",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/run_dimension_sweep.py"
        ),
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
