#!/usr/bin/env python3
"""Closed-loop dimension sweep for the d=2, d²−1=3 invariant."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "fermichen99-sim-to-real-matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy

from landscapes import explicit_hessian, random_subspace, sorted_eigensystem
from optimizers import (
    certify_reported_target,
    optimize_black_box_scipy,
    optimize_cma_es,
    optimize_coordinate_scans,
    optimize_differentiable,
)
from sim_to_real import (
    BlackBoxDevice,
    make_drift_perturbation,
    make_fidelity,
    make_loss,
    make_single_qubit_problem,
    with_drift_mismatch,
)


HELD_OUT_SEEDS = [113, 211, 419, 523, 631]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "tracks/qcs/results/sim-to-real-single-qubit-closed-loop-v1"
        ),
    )
    parser.add_argument(
        "--epsilons",
        type=float,
        nargs="+",
        default=[0.05, 0.1, 0.3],
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4],
    )
    parser.add_argument(
        "--held-out-seeds",
        type=int,
        nargs="+",
        default=HELD_OUT_SEEDS,
    )
    parser.add_argument("--noise-seeds", type=int, default=3)
    parser.add_argument("--shots", type=int, default=65536)
    parser.add_argument("--max-queries", type=int, default=500)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--n-steps", type=int, default=128)
    parser.add_argument(
        "--optimizer",
        choices=["coordinate", "cobyqa", "cmaes"],
        default="coordinate",
    )
    parser.add_argument("--certification-repeats", type=int, default=7)
    parser.add_argument("--seed", type=int, default=20260728)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def quantiles(values: list[float]) -> tuple[float, float, float]:
    result = np.quantile(
        np.asarray(values, dtype=np.float64),
        [0.25, 0.5, 0.75],
    )
    return tuple(float(value) for value in result)


def spaces(
    hessian_basis: np.ndarray,
    *,
    dimensions: list[int],
    random_seed: int,
) -> list[tuple[str, int, np.ndarray]]:
    result = [
        ("nominal_hessian", dimension, hessian_basis[:, :dimension])
        for dimension in dimensions
    ]
    result.append(
        (
            "random",
            3,
            np.asarray(
                random_subspace(
                    hessian_basis.shape[0],
                    3,
                    seed=random_seed,
                )
            ),
        )
    )
    result.append(
        (
            "raw_full",
            hessian_basis.shape[0],
            np.eye(hessian_basis.shape[0]),
        )
    )
    return result


def optimize(
    optimizer: str,
    device: BlackBoxDevice,
    theta_star: np.ndarray,
    basis: np.ndarray,
    *,
    args: argparse.Namespace,
    seed: int,
) -> tuple[object, int | None]:
    if optimizer == "coordinate":
        result = optimize_coordinate_scans(
            device,
            theta_star,
            basis=basis,
            max_queries=args.max_queries,
            target_infidelity=args.target_infidelity,
            max_cycles=5,
            initial_step=0.3,
            step_decay=0.5,
            scan_points=5,
            certification_repeats=args.certification_repeats,
        )
        return result, result.certified_query_to_target
    if optimizer == "cmaes":
        result = optimize_cma_es(
            device,
            theta_star,
            basis=basis,
            max_queries=args.max_queries,
            target_infidelity=args.target_infidelity,
            initial_sigma=0.25 / np.sqrt(basis.shape[1]),
            seed=seed,
            certification_repeats=args.certification_repeats,
        )
        return result, result.certified_query_to_target

    result = optimize_black_box_scipy(
        device,
        theta_star,
        basis=basis,
        method="COBYQA",
        max_queries=args.max_queries - args.certification_repeats,
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
    return result, device.query_count if certified else None


def summarize(
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
        censored = [
            float(
                record["certified_query_to_target"]
                if record["certified_query_to_target"] is not None
                else max_queries + 1
            )
            for record in selected
        ]
        query_q25, query_median, query_q75 = quantiles(censored)
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
                "certified_success_rate": float(
                    np.mean(
                        [
                            bool(record["certified_success"])
                            for record in selected
                        ]
                    )
                ),
                "latent_success_rate": float(
                    np.mean(
                        [
                            bool(record["latent_success"])
                            for record in selected
                        ]
                    )
                ),
                "censored_query_q25": query_q25,
                "censored_query_median": query_median,
                "censored_query_q75": query_q75,
                "censored_shots_median": query_median * shots,
                "best_exact_infidelity_q25": best_q25,
                "best_exact_infidelity_median": best_median,
                "best_exact_infidelity_q75": best_q75,
            }
        )
    return summaries


def plot_results(
    summaries: list[dict[str, object]],
    *,
    epsilons: list[float],
    max_queries: int,
    output: Path,
) -> None:
    figure, axes = plt.subplots(
        1,
        len(epsilons),
        figsize=(5.2 * len(epsilons), 4.6),
        sharey=True,
    )
    if len(epsilons) == 1:
        axes = [axes]
    styles = {
        "nominal_hessian": ("o-", "tab:blue", "model Hessian"),
        "random": ("D", "tab:orange", "random k=3"),
        "raw_full": ("X", "tab:red", "raw k=20"),
    }
    for axis, epsilon in zip(axes, epsilons, strict=True):
        for method, (style, color, label) in styles.items():
            selected = sorted(
                [
                    row
                    for row in summaries
                    if float(row["epsilon"]) == epsilon
                    and str(row["method"]) == method
                ],
                key=lambda row: int(row["dimension"]),
            )
            if not selected:
                continue
            x = np.asarray(
                [int(row["dimension"]) for row in selected],
                dtype=np.float64,
            )
            y = np.asarray(
                [
                    float(row["censored_query_median"])
                    for row in selected
                ]
            )
            low = np.asarray(
                [float(row["censored_query_q25"]) for row in selected]
            )
            high = np.asarray(
                [float(row["censored_query_q75"]) for row in selected]
            )
            axis.errorbar(
                x,
                y,
                yerr=np.vstack([y - low, high - y]),
                fmt=style,
                color=color,
                capsize=3,
                label=label,
            )
            for xx, yy, row in zip(x, y, selected, strict=True):
                axis.annotate(
                    f"{float(row['certified_success_rate']):.0%}",
                    (xx, yy),
                    xytext=(0, 7),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7,
                    color=color,
                )
        axis.axvline(3, color="black", linestyle=":", label="d²−1=3")
        axis.axhline(max_queries + 1, color="gray", linestyle=":")
        axis.set(
            xlabel="closed-loop search dimension",
            title=f"single-qubit X, ε={epsilon:g}",
            ylim=(0, 1.08 * (max_queries + 1)),
        )
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("queries to finite-shot certificate")
    handles, labels = axes[-1].get_legend_handles_labels()
    unique = dict(zip(labels, handles, strict=True))
    figure.legend(
        unique.values(),
        unique.keys(),
        loc="upper center",
        bbox_to_anchor=(0.5, 0.99),
        ncol=len(unique),
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.89))
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_args()
    if any(dimension <= 0 or dimension > 20 for dimension in args.dimensions):
        raise ValueError("single-qubit dimensions must lie in [1, 20]")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    problem = make_single_qubit_problem()
    model_loss = make_loss(
        problem,
        integrator="expm",
        n_steps=args.n_steps,
    )
    progress("[1/5] optimizing the d=2 Pauli-X nominal model")
    open_loop = optimize_differentiable(
        model_loss,
        problem.initial_params,
        method="BFGS",
        gtol=1e-7,
        maxiter=1000,
    )
    theta_star = np.asarray(open_loop.params, dtype=np.float64)
    hessian = explicit_hessian(model_loss, jnp.asarray(theta_star))
    eigenvalues, eigenvectors = sorted_eigensystem(hessian)
    hessian_basis = np.asarray(eigenvectors, dtype=np.float64)
    relative = np.abs(np.asarray(eigenvalues))
    relative /= max(float(np.max(relative)), 1e-300)
    observed_rank = int(np.count_nonzero(relative > 1e-6))
    progress(
        f"[2/5] model loss={open_loop.loss:.3e}; "
        f"Hessian rank={observed_rank}, prediction=3"
    )

    total_runs = (
        len(args.epsilons)
        * len(args.held_out_seeds)
        * args.noise_seeds
        * (len(args.dimensions) + 2)
    )
    progress(
        f"[3/5] {total_runs} paired query-only runs with "
        f"optimizer={args.optimizer}"
    )
    total_start = time.perf_counter()
    records: list[dict[str, object]] = []
    completed = 0
    for epsilon_index, epsilon in enumerate(args.epsilons):
        for drift_index, drift_seed in enumerate(args.held_out_seeds):
            perturbation = make_drift_perturbation(
                problem,
                seed=drift_seed,
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
            search_spaces = spaces(
                hessian_basis,
                dimensions=args.dimensions,
                random_seed=args.seed + drift_seed,
            )
            for noise_seed in range(args.noise_seeds):
                device_seed = (
                    args.seed
                    + 100000 * epsilon_index
                    + 1000 * drift_index
                    + noise_seed
                )
                for space_index, (method, dimension, basis) in enumerate(
                    search_spaces
                ):
                    device = BlackBoxDevice(
                        exact_fidelity,
                        shots=args.shots,
                        seed=device_seed,
                    )
                    result, certified_query = optimize(
                        args.optimizer,
                        device,
                        theta_star,
                        basis,
                        args=args,
                        seed=device_seed + 100000 * space_index,
                    )
                    best_exact_fidelity = max(
                        record.exact_fidelity
                        for record in device.history
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
                            "perturbation_seed": drift_seed,
                            "noise_seed": noise_seed,
                            "device_seed": device_seed,
                            "method": method,
                            "dimension": dimension,
                            "optimizer": args.optimizer,
                            "warm_infidelity": warm_infidelity,
                            "best_exact_infidelity": (
                                1.0 - best_exact_fidelity
                            ),
                            "latent_success": latent_query is not None,
                            "query_to_latent_target": latent_query,
                            "certified_success": (
                                certified_query is not None
                            ),
                            "certified_query_to_target": certified_query,
                            "queries_used": device.query_count,
                            "shots_used": device.shot_count,
                            "message": result.message,
                        }
                    )
                    completed += 1
                    progress(
                        f"      {completed:>3}/{total_runs} "
                        f"ε={epsilon:g} drift={drift_seed} "
                        f"{method}:{dimension} "
                        f"best={1.0-best_exact_fidelity:.2e} "
                        f"cert={certified_query}"
                    )

    summaries = summarize(
        records,
        max_queries=args.max_queries,
        shots=args.shots,
    )
    write_csv(args.output_dir / "single_qubit_runs.csv", records)
    write_csv(args.output_dir / "single_qubit_summary.csv", summaries)
    plot_results(
        summaries,
        epsilons=args.epsilons,
        max_queries=args.max_queries,
        output=args.output_dir / "single_qubit_queries_vs_dimension.png",
    )
    np.savez(
        args.output_dir / "single_qubit_calibration.npz",
        theta_star=theta_star,
        hessian=np.asarray(hessian),
        hessian_eigenvalues=np.asarray(eigenvalues),
        hessian_eigenvectors=hessian_basis,
    )
    report = {
        "schema_version": 1,
        "run": "sim-to-real-single-qubit-closed-loop-v1",
        "setup": {
            "target": "single-qubit Pauli-X",
            "hilbert_dimension": 2,
            "parameter_dimension": 20,
            "predicted_dimension": 3,
            "observed_hessian_rank": observed_rank,
            "epsilons": args.epsilons,
            "dimensions": args.dimensions,
            "held_out_seeds": args.held_out_seeds,
            "noise_seeds": args.noise_seeds,
            "shots_per_query": args.shots,
            "max_queries": args.max_queries,
            "optimizer": args.optimizer,
            "target_infidelity": args.target_infidelity,
            "certification": (
                f"{args.certification_repeats} repeated queries, "
                "one-sided 95% Wilson upper bound"
            ),
        },
        "information_boundary": (
            "The optimizer receives only scalar finite-shot device losses. "
            "Exact fidelity is retained only for offline scoring."
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
            "single_qubit_runs.csv",
            "single_qubit_summary.csv",
            "single_qubit_queries_vs_dimension.png",
            "single_qubit_calibration.npz",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/"
            "run_single_qubit_closed_loop.py"
        ),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    progress(f"[4/5] wrote {args.output_dir}")
    progress(f"[5/5] complete in {report['wall_seconds']:.1f}s")


if __name__ == "__main__":
    main()
