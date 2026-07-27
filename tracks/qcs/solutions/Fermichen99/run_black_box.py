#!/usr/bin/env python3
"""Compare simple query-only calibration baselines at one drift mismatch."""

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
from optimizers import optimize_black_box_scipy, optimize_spsa
from sim_to_real import (
    BlackBoxDevice,
    make_demo_problem,
    make_drift_perturbation,
    make_fidelity,
    with_drift_mismatch,
)

# JAX/XLA can leave IEEE floating-point status flags set on macOS.  NumPy and
# SciPy's small BLAS calls then emit false ``encountered in matmul`` warnings
# even though all inputs and outputs are finite.  We validate bases below and
# suppress only this narrow warning text.
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
        "--reachability",
        type=Path,
        default=Path(
            "tracks/qcs/results/sim-to-real-reachability-v1/"
            "reachability_data.npz"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tracks/qcs/results/sim-to-real-black-box-v1"),
    )
    parser.add_argument("--epsilon", type=float, default=0.3)
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--max-queries", type=int, default=1000)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    parser.add_argument("--random-trials", type=int, default=5)
    parser.add_argument("--spsa-trials", type=int, default=5)
    parser.add_argument(
        "--shots",
        type=int,
        default=None,
        help="Shots per device query; omit for the noiseless screening run.",
    )
    parser.add_argument("--perturbation-seed", type=int, default=113)
    parser.add_argument("--random-seed", type=int, default=191)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    args = parse_args()
    if args.epsilon < 0.0:
        raise ValueError("epsilon must be non-negative")
    if args.random_trials <= 0 or args.spsa_trials <= 0:
        raise ValueError("trial counts must be positive")
    if not args.calibration.exists():
        raise FileNotFoundError(f"missing calibration: {args.calibration}")
    if not args.reachability.exists():
        raise FileNotFoundError(f"missing reachability data: {args.reachability}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    calibration = np.load(args.calibration)
    reachability = np.load(args.reachability)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    fixed_bases: dict[str, np.ndarray | None] = {
        "full_40": None,
        "model_top_15": np.asarray(reachability["model_top_15"]),
        "top_15_plus_5": np.asarray(reachability["top_15_plus_5"]),
        "bottom_15": np.asarray(reachability["model_bottom_15"]),
    }
    for name, basis in fixed_bases.items():
        if basis is not None and not np.isfinite(basis).all():
            raise FloatingPointError(f"non-finite values in basis {name}")

    problem = make_demo_problem()
    perturbation = make_drift_perturbation(
        problem, seed=args.perturbation_seed
    )
    true_problem = with_drift_mismatch(
        problem, perturbation, args.epsilon
    )
    exact_fidelity = jax.jit(
        make_fidelity(
            true_problem, integrator="expm", n_steps=args.n_steps
        )
    )
    # Compile once before the first counted device query.
    exact_fidelity(theta_star).block_until_ready()

    records: list[dict[str, object]] = []
    histories: list[dict[str, object]] = []

    def run_trial(
        *,
        family: str,
        subspace: str,
        trial: int,
        seed: int,
        basis: np.ndarray | None,
    ) -> None:
        device = BlackBoxDevice(
            exact_fidelity,
            shots=args.shots,
            seed=seed,
        )
        start = time.perf_counter()
        if family == "COBYQA":
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
        elif family == "SPSA":
            result = optimize_spsa(
                device,
                theta_star,
                basis=basis,
                iterations=max(1, (args.max_queries - 1) // 2),
                learning_rate=0.3,
                perturbation=0.1,
                stability=10.0,
                seed=seed,
                target_infidelity=args.target_infidelity,
            )
        else:
            raise ValueError(f"unknown family: {family}")
        wall_seconds = time.perf_counter() - start
        best_infidelity = 1.0 - result.best_exact_fidelity
        record = {
            "family": family,
            "subspace": subspace,
            "trial": trial,
            "seed": seed,
            "dimension": theta_star.size if basis is None else basis.shape[1],
            "best_exact_infidelity": best_infidelity,
            "query_count": result.query_count,
            "shot_count": result.shot_count,
            "query_to_target": result.query_to_target,
            "optimizer_success": result.optimizer_success,
            "message": result.message,
            "wall_seconds": wall_seconds,
        }
        records.append(record)
        run_id = f"{family}:{subspace}:{trial}"
        histories.extend(
            {
                "run_id": run_id,
                "query": item.query,
                "reported_infidelity": 1.0 - item.reported_fidelity,
                "exact_infidelity": 1.0 - item.exact_fidelity,
            }
            for item in device.history
        )
        progress(
            f"      {family:>6} {subspace:>15} trial={trial}: "
            f"best={best_infidelity:.3e}, "
            f"q_target={result.query_to_target}, q={result.query_count}"
        )

    total_start = time.perf_counter()
    progress(
        f"[1/4] exact black-box setup: epsilon={args.epsilon:g}, "
        f"budget={args.max_queries}, shots={args.shots}, device={jax.devices()}"
    )
    progress("[2/4] deterministic COBYQA baselines")
    for index, (name, basis) in enumerate(fixed_bases.items()):
        run_trial(
            family="COBYQA",
            subspace=name,
            trial=0,
            seed=args.random_seed + index,
            basis=basis,
        )
    for trial in range(args.random_trials):
        seed = args.random_seed + 100 + trial
        basis = np.asarray(
            random_subspace(theta_star.size, 15, seed=seed)
        )
        run_trial(
            family="COBYQA",
            subspace="random_15",
            trial=trial,
            seed=seed,
            basis=basis,
        )

    progress("[3/4] two-query SPSA baselines")
    for subspace in ("full_40", "model_top_15"):
        basis = fixed_bases[subspace]
        for trial in range(args.spsa_trials):
            seed = args.random_seed + 200 + trial
            run_trial(
                family="SPSA",
                subspace=subspace,
                trial=trial,
                seed=seed,
                basis=basis,
            )

    summary_path = args.output_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(records[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(records)
    history_path = args.output_dir / "query_history.csv"
    with history_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(histories[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(histories)

    labels = [f"{r['family']}\n{r['subspace']}\n#{r['trial']}" for r in records]
    values = np.maximum(
        [float(record["best_exact_infidelity"]) for record in records],
        1e-16,
    )
    colors = [
        "tab:blue" if record["family"] == "COBYQA" else "tab:orange"
        for record in records
    ]
    fig, axis = plt.subplots(figsize=(max(9, 0.52 * len(records)), 5))
    axis.bar(np.arange(len(records)), values, color=colors)
    axis.axhline(
        args.target_infidelity,
        color="black",
        linestyle=":",
        label=f"target {args.target_infidelity:g}",
    )
    axis.set_yscale("log")
    axis.set(
        ylabel="best latent exact infidelity 1−F",
        title=f"Query-only calibration at drift mismatch ε={args.epsilon:g}",
    )
    axis.set_xticks(np.arange(len(records)), labels, rotation=60, ha="right")
    axis.legend()
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "black_box_baselines.png", dpi=180)
    plt.close(fig)

    report = {
        "schema_version": 1,
        "run": "sim-to-real-black-box-v1",
        "setup": {
            "epsilon": args.epsilon,
            "mismatch": "H0_true = H0 + epsilon * V",
            "perturbation_seed": args.perturbation_seed,
            "n_steps": args.n_steps,
            "max_queries": args.max_queries,
            "shots_per_query": args.shots,
            "target_infidelity": args.target_infidelity,
            "random_trials": args.random_trials,
            "spsa_trials": args.spsa_trials,
        },
        "black_box_boundary": (
            "Optimizers receive only reported scalar infidelity. Exact "
            "fidelity in this report is latent simulation-only diagnostics."
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
        "records": records,
        "artifacts": [
            "summary.csv",
            "query_history.csv",
            "black_box_baselines.png",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/run_black_box.py "
            f"--epsilon {args.epsilon} --max-queries {args.max_queries}"
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
