#!/usr/bin/env python3
"""Device-triggered hybrid loop with fixed-dimensional relinearization."""

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

from landscapes import endpoint_jacobian, stacked_jacobian_subspace
from optimizers import (
    certify_reported_target,
    optimize_black_box_scipy,
    optimize_coordinate_scans,
)
from sim_to_real import (
    BlackBoxDevice,
    make_demo_problem,
    make_drift_perturbation,
    make_fidelity,
    with_drift_mismatch,
)

warnings.filterwarnings(
    "ignore",
    message=".*(divide by zero|overflow|invalid value).*matmul",
    category=RuntimeWarning,
)


TRAINING_SEEDS = [307, 401, 509, 601, 701]
HELD_OUT_SEEDS = [113, 211, 419, 523, 631]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path(
            "tracks/qcs/results/sim-to-real-calibration-v1/"
            "calibration_data.npz"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "tracks/qcs/results/sim-to-real-adaptive-hybrid-v1"
        ),
    )
    parser.add_argument(
        "--epsilons",
        type=float,
        nargs="+",
        default=[0.1, 0.3, 0.5],
    )
    parser.add_argument("--training-epsilon", type=float, default=0.35)
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
    parser.add_argument("--noise-seeds", type=int, default=3)
    parser.add_argument("--shots", type=int, default=65536)
    parser.add_argument("--max-queries", type=int, default=700)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--n-steps", type=int, default=128)
    parser.add_argument("--ensemble-n-steps", type=int, default=48)
    parser.add_argument("--nominal-dimension", type=int, default=15)
    parser.add_argument("--recovery-dimension", type=int, default=20)
    parser.add_argument(
        "--recovery-optimization-caps",
        type=int,
        nargs="+",
        default=[323, 513, 693],
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


def ensemble_basis(
    models: list,
    params: np.ndarray,
    *,
    dimension: int,
    n_steps: int,
) -> np.ndarray:
    jacobians = np.stack(
        [
            np.asarray(endpoint_jacobian(model, params, n_steps=n_steps))
            for model in models
        ]
    )
    _, basis = stacked_jacobian_subspace(
        jacobians,
        dimension,
        normalize_blocks=True,
    )
    return basis


def summarize(
    records: list[dict[str, object]],
    *,
    max_queries: int,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for epsilon in sorted(
        {float(record["epsilon"]) for record in records}
    ):
        selected = [
            record
            for record in records
            if float(record["epsilon"]) == epsilon
        ]
        censored = [
            float(
                record["certified_query_to_target"]
                if record["certified_query_to_target"] is not None
                else max_queries + 1
            )
            for record in selected
        ]
        stage_counts = {
            stage: sum(str(record["stop_stage"]) == stage for record in selected)
            for stage in [
                "nominal_coordinate",
                "relinearized_1",
                "relinearized_2",
                "relinearized_3",
                "failed",
            ]
        }
        summaries.append(
            {
                "epsilon": epsilon,
                "method": "adaptive_hybrid_k15_to_k20",
                "maximum_dimension": 20,
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
                "censored_certified_query_q25": float(
                    np.quantile(censored, 0.25)
                ),
                "censored_certified_query_median": float(
                    np.median(censored)
                ),
                "censored_certified_query_q75": float(
                    np.quantile(censored, 0.75)
                ),
                "best_exact_infidelity_median": float(
                    np.median(
                        [
                            float(record["best_exact_infidelity"])
                            for record in selected
                        ]
                    )
                ),
                **{
                    f"stopped_{stage}": count
                    for stage, count in stage_counts.items()
                },
            }
        )
    return summaries


def plot_results(
    summaries: list[dict[str, object]],
    records: list[dict[str, object]],
    *,
    output: Path,
) -> None:
    epsilons = [float(row["epsilon"]) for row in summaries]
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.3))
    axes[0].plot(
        epsilons,
        [
            float(row["certified_success_rate"])
            for row in summaries
        ],
        "o-",
        color="tab:blue",
    )
    axes[0].set(
        xlabel="held-out mismatch ε",
        ylabel="certified success rate",
        ylim=(-0.03, 1.03),
        title="adaptive hybrid reliability",
    )

    stage_order = [
        "nominal_coordinate",
        "relinearized_1",
        "relinearized_2",
        "relinearized_3",
        "failed",
    ]
    stage_labels = [
        "nominal\nscan",
        "updated\nstage 1",
        "updated\nstage 2",
        "updated\nstage 3",
        "failed",
    ]
    bottoms = np.zeros(len(epsilons), dtype=np.float64)
    colors = ["#2878b5", "#42a36f", "#1c8060", "#7656a8", "#c84c4c"]
    for stage, label, color in zip(
        stage_order,
        stage_labels,
        colors,
        strict=True,
    ):
        counts = np.asarray(
            [
                sum(
                    float(record["epsilon"]) == epsilon
                    and str(record["stop_stage"]) == stage
                    for record in records
                )
                for epsilon in epsilons
            ],
            dtype=np.float64,
        )
        axes[1].bar(
            epsilons,
            counts,
            bottom=bottoms,
            width=0.08,
            color=color,
            label=label,
        )
        bottoms += counts
    axes[1].set(
        xlabel="held-out mismatch ε",
        ylabel="number of paired runs",
        title="where the device-visible loop stopped",
    )
    axes[1].legend(
        fontsize=8,
        ncol=1,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
    )
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_args()
    if set(args.training_seeds) & set(args.held_out_seeds):
        raise ValueError("training and held-out seeds must be disjoint")
    if sorted(args.recovery_optimization_caps) != list(
        args.recovery_optimization_caps
    ):
        raise ValueError("recovery caps must be sorted")
    if (
        args.recovery_optimization_caps[-1]
        + args.certification_repeats
        > args.max_queries
    ):
        raise ValueError("recovery and certification exceed query budget")

    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    nominal_basis = np.asarray(
        calibration["hessian_eigenvectors"],
        dtype=np.float64,
    )[:, : args.nominal_dimension]
    problem = make_demo_problem()
    training_models = [problem]
    for seed in args.training_seeds:
        training_models.append(
            with_drift_mismatch(
                problem,
                make_drift_perturbation(problem, seed=seed),
                args.training_epsilon,
            )
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    total_runs = (
        len(args.epsilons)
        * len(args.held_out_seeds)
        * args.noise_seeds
    )
    progress(
        f"[1/4] {total_runs} adaptive runs: nominal-{args.nominal_dimension} "
        f"scan → relinearized-{args.recovery_dimension} COBYQA"
    )
    total_start = time.perf_counter()
    records: list[dict[str, object]] = []
    completed = 0
    for epsilon_index, epsilon in enumerate(args.epsilons):
        for drift_index, drift_seed in enumerate(args.held_out_seeds):
            true_problem = with_drift_mismatch(
                problem,
                make_drift_perturbation(problem, seed=drift_seed),
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
            warm_infidelity = 1.0 - float(
                exact_fidelity(theta_star)
            )
            for noise_seed in range(args.noise_seeds):
                device_seed = (
                    args.seed
                    + 100000 * epsilon_index
                    + 1000 * drift_index
                    + noise_seed
                )
                device = BlackBoxDevice(
                    exact_fidelity,
                    shots=args.shots,
                    seed=device_seed,
                )
                current = theta_star.copy()
                stage_trace: list[str] = []
                coordinate = optimize_coordinate_scans(
                    device,
                    current,
                    basis=nominal_basis,
                    max_queries=args.max_queries,
                    target_infidelity=args.target_infidelity,
                    max_cycles=1,
                    initial_step=0.3,
                    step_decay=0.5,
                    scan_points=5,
                    certification_repeats=args.certification_repeats,
                )
                current = coordinate.params
                certified_query = coordinate.certified_query_to_target
                if certified_query is not None:
                    stop_stage = "nominal_coordinate"
                    stage_trace.append(
                        f"nominal:{device.query_count}:certified"
                    )
                else:
                    stage_trace.append(
                        f"nominal:{device.query_count}:failed"
                    )
                    stop_stage = "failed"
                    for stage_index, optimization_cap in enumerate(
                        args.recovery_optimization_caps,
                        start=1,
                    ):
                        basis = ensemble_basis(
                            training_models,
                            current,
                            dimension=args.recovery_dimension,
                            n_steps=args.ensemble_n_steps,
                        )
                        result = optimize_black_box_scipy(
                            device,
                            current,
                            basis=basis,
                            method="COBYQA",
                            max_queries=optimization_cap,
                            target_infidelity=args.target_infidelity,
                            optimizer_options={
                                "initial_tr_radius": (
                                    0.25 / stage_index
                                ),
                                "final_tr_radius": 1e-6,
                            },
                            allow_existing_history=True,
                        )
                        current = result.params
                        certification_cap = min(
                            args.max_queries,
                            optimization_cap
                            + args.certification_repeats,
                        )
                        certified = certify_reported_target(
                            device,
                            current,
                            target_infidelity=args.target_infidelity,
                            repeats=args.certification_repeats,
                            z_score=1.96,
                            max_queries=certification_cap,
                        )
                        stage_trace.append(
                            f"updated{stage_index}:"
                            f"{device.query_count}:"
                            f"{'certified' if certified else 'failed'}"
                        )
                        if certified:
                            certified_query = device.query_count
                            stop_stage = f"relinearized_{stage_index}"
                            break

                latent_query = next(
                    (
                        record.query
                        for record in device.history
                        if 1.0 - record.exact_fidelity
                        <= args.target_infidelity
                    ),
                    None,
                )
                best_infidelity = 1.0 - max(
                    record.exact_fidelity for record in device.history
                )
                records.append(
                    {
                        "epsilon": epsilon,
                        "perturbation_seed": drift_seed,
                        "noise_seed": noise_seed,
                        "device_seed": device_seed,
                        "warm_infidelity": warm_infidelity,
                        "nominal_dimension": args.nominal_dimension,
                        "maximum_dimension": args.recovery_dimension,
                        "stop_stage": stop_stage,
                        "stage_trace": "|".join(stage_trace),
                        "best_exact_infidelity": best_infidelity,
                        "latent_success": latent_query is not None,
                        "query_to_latent_target": latent_query,
                        "certified_success": certified_query is not None,
                        "certified_query_to_target": certified_query,
                        "queries_used": device.query_count,
                        "shots_used": device.shot_count,
                    }
                )
                completed += 1
                progress(
                    f"      {completed:>2}/{total_runs} ε={epsilon:g} "
                    f"drift={drift_seed} noise={noise_seed} "
                    f"stop={stop_stage} q={device.query_count} "
                    f"best={best_infidelity:.2e}"
                )

    summaries = summarize(records, max_queries=args.max_queries)
    write_csv(args.output_dir / "adaptive_hybrid_runs.csv", records)
    write_csv(args.output_dir / "adaptive_hybrid_summary.csv", summaries)
    plot_results(
        summaries,
        records,
        output=args.output_dir / "adaptive_hybrid_stages.png",
    )
    report = {
        "schema_version": 1,
        "run": "sim-to-real-adaptive-hybrid-v1",
        "setup": {
            "target": "two-qubit CNOT",
            "epsilons": args.epsilons,
            "training_epsilon": args.training_epsilon,
            "training_seeds": args.training_seeds,
            "held_out_seeds": args.held_out_seeds,
            "noise_seeds": args.noise_seeds,
            "shots_per_query": args.shots,
            "max_queries": args.max_queries,
            "nominal_dimension": args.nominal_dimension,
            "recovery_dimension": args.recovery_dimension,
            "recovery_optimization_caps": (
                args.recovery_optimization_caps
            ),
            "certification": (
                f"{args.certification_repeats} repeated queries, "
                "one-sided 95% Wilson upper bound"
            ),
        },
        "trigger": (
            "A failed finite-shot certificate triggers model-side "
            "relinearization and the next COBYQA stage. A passed "
            "certificate stops immediately."
        ),
        "information_boundary": (
            "Every trigger uses only repeated scalar device measurements. "
            "Every basis update uses only the predeclared training models at "
            "the device-selected current pulse. Held-out device Jacobians, "
            "epsilon, and exact fidelity are unavailable to the loop."
        ),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "jax": jax.__version__,
            "numpy": np.__version__,
            "devices": [str(device) for device in jax.devices()],
        },
        "wall_seconds": time.perf_counter() - total_start,
        "artifacts": [
            "adaptive_hybrid_runs.csv",
            "adaptive_hybrid_summary.csv",
            "adaptive_hybrid_stages.png",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/"
            "run_adaptive_hybrid_closed_loop.py"
        ),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    progress(f"[3/4] wrote {args.output_dir}")
    progress(f"[4/4] complete in {report['wall_seconds']:.1f}s")


if __name__ == "__main__":
    main()
