#!/usr/bin/env python3
"""Closed-loop study with nominal and uncertainty-ensemble model directions."""

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

from landscapes import (
    endpoint_jacobian,
    random_subspace,
    stacked_jacobian_subspace,
)
from optimizers import (
    certify_reported_target,
    optimize_black_box_scipy,
    optimize_coordinate_scans,
)
from sim_to_real import (
    BlackBoxDevice,
    ControlProblem,
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
warnings.filterwarnings(
    "ignore",
    message=".*(divide by zero|overflow|invalid value).*matmul",
    category=RuntimeWarning,
)


TRAINING_SEEDS = [
    307,
    401,
    509,
    601,
    701,
    809,
    907,
    1009,
    1103,
    1201,
    1301,
    1409,
    1511,
    1601,
    1709,
]
HELD_OUT_SEEDS = [113, 211, 419, 523, 631]


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
        default=Path("tracks/qcs/results/sim-to-real-robust-closed-loop-v1"),
    )
    parser.add_argument(
        "--epsilons",
        type=float,
        nargs="+",
        default=[0.1, 0.3, 0.5],
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        nargs="+",
        default=[15, 20, 30],
    )
    parser.add_argument(
        "--training-seeds",
        type=int,
        nargs="+",
        default=TRAINING_SEEDS,
    )
    parser.add_argument(
        "--held-out-seeds",
        type=int,
        nargs="+",
        default=HELD_OUT_SEEDS,
    )
    parser.add_argument("--training-epsilon", type=float, default=0.35)
    parser.add_argument("--noise-seeds", type=int, default=3)
    parser.add_argument("--shots", type=int, default=65536)
    parser.add_argument("--max-queries", type=int, default=700)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--n-steps", type=int, default=128)
    parser.add_argument("--ensemble-n-steps", type=int, default=64)
    parser.add_argument("--max-cycles", type=int, default=4)
    parser.add_argument("--initial-step", type=float, default=0.3)
    parser.add_argument("--step-decay", type=float, default=0.5)
    parser.add_argument("--scan-points", type=int, default=5, choices=[3, 5])
    parser.add_argument("--certification-repeats", type=int, default=7)
    parser.add_argument(
        "--optimizer",
        choices=["coordinate", "cobyqa"],
        default="coordinate",
    )
    parser.add_argument("--seed", type=int, default=20260728)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def quantiles(values: list[float]) -> tuple[float, float, float]:
    lower, median, upper = np.quantile(
        np.asarray(values, dtype=np.float64),
        [0.25, 0.5, 0.75],
    )
    return float(lower), float(median), float(upper)


def build_training_models(
    nominal: ControlProblem,
    *,
    seeds: list[int],
    epsilon: float,
) -> list[ControlProblem]:
    """Create a model-only uncertainty ensemble, including the nominal model."""

    models = [nominal]
    for seed in seeds:
        perturbation = make_drift_perturbation(nominal, seed=seed)
        models.append(with_drift_mismatch(nominal, perturbation, epsilon))
    return models


def robust_basis_from_models(
    models: list[ControlProblem],
    params: np.ndarray,
    *,
    n_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return all robust directions from a normalized stacked Jacobian."""

    jacobians = np.stack(
        [
            np.asarray(endpoint_jacobian(model, params, n_steps=n_steps))
            for model in models
        ]
    )
    return stacked_jacobian_subspace(
        jacobians,
        params.size,
        normalize_blocks=True,
    )


def method_bases(
    *,
    nominal_basis: np.ndarray,
    robust_basis: np.ndarray,
    dimensions: list[int],
    parameter_dimension: int,
    random_seed: int,
) -> list[tuple[str, int, np.ndarray]]:
    methods: list[tuple[str, int, np.ndarray]] = []
    for dimension in dimensions:
        methods.append(
            ("nominal_hessian", dimension, nominal_basis[:, :dimension])
        )
        methods.append(
            ("robust_ensemble", dimension, robust_basis[:, :dimension])
        )
    reference_dimension = min(
        dimensions,
        key=lambda dimension: abs(dimension - 20),
    )
    methods.append(
        (
            "random",
            reference_dimension,
            np.asarray(
                random_subspace(
                    parameter_dimension,
                    reference_dimension,
                    seed=random_seed,
                )
            ),
        )
    )
    methods.append(
        ("raw_full", parameter_dimension, np.eye(parameter_dimension))
    )
    return methods


def summarize_records(
    records: list[dict[str, object]],
    *,
    max_queries: int,
    shots: int,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    keys = sorted(
        {
            (
                float(record["epsilon"]),
                str(record["method"]),
                int(record["dimension"]),
            )
            for record in records
        }
    )
    for epsilon, method, dimension in keys:
        selected = [
            record
            for record in records
            if float(record["epsilon"]) == epsilon
            and str(record["method"]) == method
            and int(record["dimension"]) == dimension
        ]
        certified = [
            bool(record["certified_success"]) for record in selected
        ]
        latent = [bool(record["latent_success"]) for record in selected]
        censored_queries = [
            float(
                record["certified_query_to_target"]
                if record["certified_query_to_target"] is not None
                else max_queries + 1
            )
            for record in selected
        ]
        query_q25, query_median, query_q75 = quantiles(censored_queries)
        best_q25, best_median, best_q75 = quantiles(
            [
                float(record["best_exact_infidelity"])
                for record in selected
            ]
        )
        summaries.append(
            {
                "epsilon": epsilon,
                "method": method,
                "dimension": dimension,
                "runs": len(selected),
                "certified_success_rate": float(np.mean(certified)),
                "latent_success_rate": float(np.mean(latent)),
                "censored_certified_query_q25": query_q25,
                "censored_certified_query_median": query_median,
                "censored_certified_query_q75": query_q75,
                "censored_certified_shots_median": query_median * shots,
                "best_exact_infidelity_q25": best_q25,
                "best_exact_infidelity_median": best_median,
                "best_exact_infidelity_q75": best_q75,
            }
        )
    return summaries


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def plot_queries_vs_dimension(
    summaries: list[dict[str, object]],
    *,
    epsilons: list[float],
    max_queries: int,
    output: Path,
) -> None:
    figure, axes = plt.subplots(
        1,
        len(epsilons),
        figsize=(5.1 * len(epsilons), 4.5),
        sharey=True,
    )
    if len(epsilons) == 1:
        axes = [axes]
    styles = {
        "nominal_hessian": ("o-", "tab:blue", "single-model Hessian"),
        "robust_ensemble": ("s-", "tab:green", "ensemble Hessian"),
        "random": ("D", "tab:orange", "random"),
        "raw_full": ("X", "tab:red", "raw full"),
    }
    for axis, epsilon in zip(axes, epsilons, strict=True):
        for method, (style, color, label) in styles.items():
            selected = sorted(
                [
                    row
                    for row in summaries
                    if float(row["epsilon"]) == epsilon
                    and row["method"] == method
                ],
                key=lambda row: int(row["dimension"]),
            )
            if not selected:
                continue
            dimensions = np.asarray(
                [int(row["dimension"]) for row in selected]
            )
            medians = np.asarray(
                [
                    float(row["censored_certified_query_median"])
                    for row in selected
                ]
            )
            lowers = np.asarray(
                [
                    float(row["censored_certified_query_q25"])
                    for row in selected
                ]
            )
            uppers = np.asarray(
                [
                    float(row["censored_certified_query_q75"])
                    for row in selected
                ]
            )
            axis.errorbar(
                dimensions,
                medians,
                yerr=np.vstack([medians - lowers, uppers - medians]),
                fmt=style,
                color=color,
                capsize=3,
                label=label,
            )
            for dimension, median, row in zip(
                dimensions,
                medians,
                selected,
                strict=True,
            ):
                axis.annotate(
                    f"{float(row['certified_success_rate']):.0%}",
                    (dimension, median),
                    xytext=(
                        0,
                        -15 if method == "robust_ensemble" else 7,
                    ),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7,
                    color=color,
                )
        axis.axvline(15, color="black", linestyle=":", label="d²−1=15")
        axis.axhline(max_queries, color="gray", linestyle=":")
        axis.set(
            xlabel="closed-loop search dimension",
            title=f"held-out mismatch ε={epsilon:g}",
            ylim=(0, max_queries * 1.08),
        )
        axis.grid(alpha=0.2)
    axes[0].set_ylabel(
        "queries to finite-shot certificate\n"
        "(failures censored at budget+1)"
    )
    handles, labels = axes[-1].get_legend_handles_labels()
    unique = dict(zip(labels, handles, strict=True))
    figure.legend(
        unique.values(),
        unique.keys(),
        loc="upper center",
        ncol=len(unique),
        fontsize=8,
    )
    figure.suptitle(
        "Query-only calibration with one-sided finite-shot certification",
        y=1.03,
    )
    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def plot_success_vs_epsilon(
    summaries: list[dict[str, object]],
    *,
    output: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(7.4, 4.5))
    selections = [
        ("nominal_hessian", 15, "o-", "tab:blue", "nominal k=15"),
        ("nominal_hessian", 20, "s-", "tab:cyan", "nominal k=20"),
        ("robust_ensemble", 20, "^-", "tab:green", "ensemble k=20"),
        ("nominal_hessian", 30, "v--", "tab:purple", "nominal k=30"),
        ("robust_ensemble", 30, "P--", "tab:brown", "ensemble k=30"),
        ("random", 20, "D--", "tab:orange", "random k=20"),
        ("raw_full", 40, "X--", "tab:red", "raw k=40"),
    ]
    for method, dimension, style, color, label in selections:
        selected = sorted(
            [
                row
                for row in summaries
                if row["method"] == method
                and int(row["dimension"]) == dimension
            ],
            key=lambda row: float(row["epsilon"]),
        )
        if not selected:
            continue
        axis.plot(
            [float(row["epsilon"]) for row in selected],
            [float(row["certified_success_rate"]) for row in selected],
            style,
            color=color,
            label=label,
        )
    axis.set(
        xlabel="held-out structural mismatch ε",
        ylabel="finite-shot certified success rate",
        ylim=(-0.03, 1.03),
    )
    axis.grid(alpha=0.2)
    axis.legend(ncol=2, fontsize=8)
    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> None:
    args = parse_args()
    if not args.calibration.exists():
        raise FileNotFoundError(f"missing calibration: {args.calibration}")
    if args.noise_seeds <= 0 or args.shots <= 0:
        raise ValueError("noise seeds and shots must be positive")
    if set(args.training_seeds) & set(args.held_out_seeds):
        raise ValueError("training and held-out perturbation seeds must be disjoint")

    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    nominal_basis = np.asarray(
        calibration["hessian_eigenvectors"],
        dtype=np.float64,
    )
    if any(
        dimension <= 0 or dimension > theta_star.size
        for dimension in args.dimensions
    ):
        raise ValueError("invalid search dimension")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    total_start = time.perf_counter()
    problem = make_demo_problem()
    training_models = build_training_models(
        problem,
        seeds=args.training_seeds,
        epsilon=args.training_epsilon,
    )
    progress(
        f"[1/4] building ensemble basis from {len(training_models)} "
        f"model-side Jacobians at ε_train={args.training_epsilon:g}"
    )
    robust_singular_values, robust_basis = robust_basis_from_models(
        training_models,
        theta_star,
        n_steps=args.ensemble_n_steps,
    )
    np.savez(
        args.output_dir / "robust_basis.npz",
        singular_values=robust_singular_values,
        basis=robust_basis,
        training_seeds=np.asarray(args.training_seeds),
        training_epsilon=args.training_epsilon,
    )

    methods_per_device = 2 * len(args.dimensions) + 2
    total_runs = (
        len(args.epsilons)
        * len(args.held_out_seeds)
        * args.noise_seeds
        * methods_per_device
    )
    progress(
        f"[2/4] {total_runs} paired query-only runs; "
        f"{args.shots} shots/query, budget={args.max_queries}"
    )
    records: list[dict[str, object]] = []
    completed = 0
    for epsilon_index, epsilon in enumerate(args.epsilons):
        for drift_index, perturbation_seed in enumerate(args.held_out_seeds):
            perturbation = make_drift_perturbation(
                problem,
                seed=perturbation_seed,
            )
            true_problem = with_drift_mismatch(
                problem,
                perturbation,
                epsilon,
            )
            exact_fidelity = jax.jit(
                make_fidelity(
                    true_problem,
                    integrator="expm",
                    n_steps=args.n_steps,
                )
            )
            exact_fidelity(theta_star).block_until_ready()
            warm_infidelity = 1.0 - float(exact_fidelity(theta_star))
            bases = method_bases(
                nominal_basis=nominal_basis,
                robust_basis=robust_basis,
                dimensions=args.dimensions,
                parameter_dimension=theta_star.size,
                random_seed=args.seed + perturbation_seed,
            )
            for noise_seed in range(args.noise_seeds):
                paired_device_seed = (
                    args.seed
                    + 100000 * epsilon_index
                    + 1000 * drift_index
                    + noise_seed
                )
                for method, dimension, basis in bases:
                    device = BlackBoxDevice(
                        exact_fidelity,
                        shots=args.shots,
                        seed=paired_device_seed,
                    )
                    start = time.perf_counter()
                    if args.optimizer == "coordinate":
                        result = optimize_coordinate_scans(
                            device,
                            theta_star,
                            basis=basis,
                            max_queries=args.max_queries,
                            target_infidelity=args.target_infidelity,
                            max_cycles=args.max_cycles,
                            initial_step=args.initial_step,
                            step_decay=args.step_decay,
                            scan_points=args.scan_points,
                            certification_repeats=args.certification_repeats,
                        )
                        certified_query = (
                            result.certified_query_to_target
                        )
                    else:
                        optimization_budget = (
                            args.max_queries - args.certification_repeats
                        )
                        result = optimize_black_box_scipy(
                            device,
                            theta_star,
                            basis=basis,
                            method="COBYQA",
                            max_queries=optimization_budget,
                            target_infidelity=args.target_infidelity,
                            optimizer_options={
                                "initial_tr_radius": 0.25,
                                "final_tr_radius": 1e-6,
                            },
                        )
                        certified = certify_reported_target(
                            device,
                            result.params,
                            target_infidelity=args.target_infidelity,
                            repeats=args.certification_repeats,
                            z_score=1.96,
                            max_queries=args.max_queries,
                        )
                        certified_query = (
                            device.query_count if certified else None
                        )
                    best_exact_fidelity = max(
                        record.exact_fidelity for record in device.history
                    )
                    latent_query = next(
                        (
                            record.query
                            for record in device.history
                            if 1.0 - record.exact_fidelity
                            <= args.target_infidelity
                        ),
                        None,
                    )
                    records.append(
                        {
                            "epsilon": epsilon,
                            "perturbation_seed": perturbation_seed,
                            "noise_seed": noise_seed,
                            "device_seed": paired_device_seed,
                            "method": method,
                            "dimension": dimension,
                            "warm_infidelity": warm_infidelity,
                            "best_exact_infidelity": (
                                1.0 - best_exact_fidelity
                            ),
                            "latent_success": latent_query is not None,
                            "query_to_latent_target": latent_query,
                            "certified_success": certified_query is not None,
                            "certified_query_to_target": certified_query,
                            "queries_used": device.query_count,
                            "shots_used": device.shot_count,
                            "shots_to_certificate": (
                                None
                                if certified_query is None
                                else certified_query * args.shots
                            ),
                            "cycles_completed": result.cycles_completed,
                            "message": result.message,
                            "wall_seconds": time.perf_counter() - start,
                        }
                    )
                    completed += 1
                    progress(
                        f"      {completed:>3}/{total_runs} "
                        f"ε={epsilon:g} drift={perturbation_seed} "
                        f"noise={noise_seed} {method}:{dimension} "
                        f"best={1.0-best_exact_fidelity:.2e} "
                        f"cert={certified_query}"
                    )

    summaries = summarize_records(
        records,
        max_queries=args.max_queries,
        shots=args.shots,
    )
    write_csv(args.output_dir / "closed_loop_runs.csv", records)
    write_csv(args.output_dir / "closed_loop_summary.csv", summaries)
    plot_queries_vs_dimension(
        summaries,
        epsilons=args.epsilons,
        max_queries=args.max_queries,
        output=args.output_dir / "closed_loop_queries_vs_dimension.png",
    )
    plot_success_vs_epsilon(
        summaries,
        output=args.output_dir / "closed_loop_success_vs_epsilon.png",
    )

    report = {
        "schema_version": 1,
        "run": "sim-to-real-robust-closed-loop-v1",
        "setup": {
            "target": "two-qubit CNOT",
            "parameter_dimension": int(theta_star.size),
            "generator_dimension": 15,
            "epsilons": args.epsilons,
            "dimensions": args.dimensions,
            "training_epsilon": args.training_epsilon,
            "training_seeds": args.training_seeds,
            "held_out_seeds": args.held_out_seeds,
            "noise_seeds": args.noise_seeds,
            "shots_per_query": args.shots,
            "max_queries": args.max_queries,
            "target_infidelity": args.target_infidelity,
            "n_steps": args.n_steps,
            "ensemble_n_steps": args.ensemble_n_steps,
            "optimizer": args.optimizer,
            "max_cycles": args.max_cycles,
            "initial_step": args.initial_step,
            "step_decay": args.step_decay,
            "certification": (
                f"{args.certification_repeats} repeated queries, "
                "one-sided 95% Wilson upper bound"
            ),
        },
        "information_boundary": (
            "Training-model Jacobians are used only before device evaluation. "
            "Held-out device Jacobians, exact fidelities, and epsilon are not "
            "available to the optimizer. Exact fidelity is retained only for "
            "offline false-positive/false-negative scoring."
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
        "artifacts": [
            "robust_basis.npz",
            "closed_loop_runs.csv",
            "closed_loop_summary.csv",
            "closed_loop_queries_vs_dimension.png",
            "closed_loop_success_vs_epsilon.png",
        ],
        "rerun": (
            "python3 "
            "tracks/qcs/solutions/Fermichen99/run_robust_closed_loop.py"
        ),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    progress(
        f"[3/4] wrote summaries and figures to {args.output_dir}"
    )
    progress(
        f"[4/4] complete in {report['wall_seconds']:.1f}s"
    )


if __name__ == "__main__":
    main()
