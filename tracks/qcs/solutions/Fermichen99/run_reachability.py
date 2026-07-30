#!/usr/bin/env python3
"""Map when the model Hessian subspace survives drift mismatch.

This script is deliberately a privileged diagnostic, not a deployable
closed-loop controller.  Gradients of each simulated true device are used only
to answer a structural question: if black-box calibration later fails, was the
target unreachable inside the model-derived subspace, or did the optimizer
simply fail to find it?
"""

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

from landscapes import (
    explicit_hessian,
    hessian_subspace,
    random_subspace,
    subspace_metrics,
)
from optimizers import (
    DifferentiableResult,
    optimize_differentiable,
    optimize_differentiable_subspace,
)
from sim_to_real import (
    make_demo_problem,
    make_drift_perturbation,
    make_loss,
    with_drift_mismatch,
)


METHOD_ORDER = ("full_40", "model_top_15", "top_15_plus_5", "random_15", "bottom_15")


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
        default=Path("tracks/qcs/results/sim-to-real-reachability-v1"),
    )
    parser.add_argument(
        "--epsilons",
        type=float,
        nargs="+",
        default=[0.0, 0.003, 0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0],
    )
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--maxiter", type=int, default=1000)
    parser.add_argument("--gtol", type=float, default=1e-7)
    parser.add_argument("--perturbation-seed", type=int, default=113)
    parser.add_argument("--random-seed", type=int, default=191)
    parser.add_argument("--target-infidelity", type=float, default=1e-3)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def random_orthogonal_extension(
    basis: np.ndarray,
    extra_dimension: int,
    *,
    seed: int,
) -> np.ndarray:
    """Add seeded random directions orthogonal to an existing basis."""

    if extra_dimension <= 0:
        raise ValueError("extra_dimension must be positive")
    ambient_dimension = basis.shape[0]
    rng = np.random.default_rng(seed)
    candidates = rng.normal(
        size=(ambient_dimension, extra_dimension + basis.shape[1])
    )
    # ``einsum(..., optimize=False)`` avoids a spurious overflow warning in
    # some macOS Accelerate/NumPy matmul builds while performing the same two
    # small dense contractions.
    coefficients = np.einsum(
        "ik,ij->kj", basis, candidates, optimize=False
    )
    candidates -= np.einsum(
        "ik,kj->ij", basis, coefficients, optimize=False
    )
    extension, _ = np.linalg.qr(candidates)
    extension = extension[:, :extra_dimension]
    combined = np.column_stack([basis, extension])
    orthonormal, _ = np.linalg.qr(combined)
    return orthonormal[:, : basis.shape[1] + extra_dimension]


def classify_region(
    warm_loss: float,
    method_losses: dict[str, float],
    *,
    target: float,
) -> str:
    """Classify the first observed geometric failure mechanism."""

    if warm_loss <= target:
        return "A: open-loop transfer"
    if method_losses["model_top_15"] <= target:
        return "B: fixed top-15 calibrates"
    if method_losses["top_15_plus_5"] <= target:
        return "C1: five safety directions required"
    if method_losses["full_40"] <= target:
        return "C2: fixed-subspace breakdown"
    return "D: full parameterization fails"


def result_record(result: DifferentiableResult) -> dict[str, object]:
    return {
        "loss": result.loss,
        "success": result.success,
        "iterations": result.iterations,
        "evaluations": result.evaluations,
        "message": result.message,
    }


def main() -> None:
    args = parse_args()
    if not args.calibration.exists():
        raise FileNotFoundError(
            f"calibration file not found: {args.calibration}; run run_calibration.py"
        )
    if any(epsilon < 0.0 for epsilon in args.epsilons):
        raise ValueError("epsilons must be non-negative")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    model_eigenvectors = np.asarray(
        calibration["hessian_eigenvectors"], dtype=np.float64
    )
    top_15 = model_eigenvectors[:, :15]
    bottom_15 = model_eigenvectors[:, -15:]
    random_15 = np.asarray(
        random_subspace(theta_star.size, 15, seed=args.random_seed)
    )
    top_15_plus_5 = random_orthogonal_extension(
        top_15, 5, seed=args.random_seed + 1
    )

    bases: dict[str, np.ndarray | None] = {
        "full_40": None,
        "model_top_15": top_15,
        "top_15_plus_5": top_15_plus_5,
        "random_15": random_15,
        "bottom_15": bottom_15,
    }

    problem = make_demo_problem()
    perturbation = make_drift_perturbation(
        problem, seed=args.perturbation_seed
    )
    progress(
        f"[1/4] setup: {len(args.epsilons)} epsilons, "
        f"p={problem.n_params}, n_steps={args.n_steps}, device={jax.devices()}"
    )

    records: list[dict[str, object]] = []
    parameter_results: dict[str, np.ndarray] = {}
    total_start = time.perf_counter()
    for epsilon_index, epsilon in enumerate(args.epsilons, start=1):
        true_problem = with_drift_mismatch(problem, perturbation, epsilon)
        true_loss = make_loss(
            true_problem, integrator="expm", n_steps=args.n_steps
        )
        compiled_true_loss = jax.jit(true_loss)
        warm_loss = float(compiled_true_loss(jnp.asarray(theta_star)))
        progress(
            f"[2/4] epsilon={epsilon:g} ({epsilon_index}/{len(args.epsilons)}): "
            f"warm loss={warm_loss:.6e}"
        )

        hessian_start = time.perf_counter()
        true_hessian = explicit_hessian(true_loss, jnp.asarray(theta_star))
        _, true_top_15 = hessian_subspace(true_hessian, 15)
        overlap = subspace_metrics(top_15, true_top_15)
        hessian_seconds = time.perf_counter() - hessian_start
        progress(
            f"      top-15 overlap mean={overlap.mean_overlap:.6f}, "
            f"max angle={overlap.largest_angle_degrees:.2f}°"
        )

        method_results: dict[str, dict[str, object]] = {}
        method_losses: dict[str, float] = {}
        for method in METHOD_ORDER:
            method_start = time.perf_counter()
            basis = bases[method]
            if basis is None:
                result = optimize_differentiable(
                    true_loss,
                    theta_star,
                    method="BFGS",
                    gtol=args.gtol,
                    maxiter=args.maxiter,
                )
            else:
                result = optimize_differentiable_subspace(
                    true_loss,
                    theta_star,
                    basis,
                    method="BFGS",
                    gtol=args.gtol,
                    maxiter=args.maxiter,
                )
            method_seconds = time.perf_counter() - method_start
            record = result_record(result)
            record["wall_seconds"] = method_seconds
            method_results[method] = record
            method_losses[method] = result.loss
            parameter_results[f"epsilon_{epsilon:g}__{method}"] = result.params
            progress(
                f"      {method:>15}: loss={result.loss:.6e}, "
                f"nfev={result.evaluations}, wall={method_seconds:.2f}s"
            )

        region = classify_region(
            warm_loss,
            method_losses,
            target=args.target_infidelity,
        )
        progress(f"      region={region}")
        records.append(
            {
                "epsilon": epsilon,
                "warm_loss": warm_loss,
                "hessian_seconds": hessian_seconds,
                "model_true_top15_overlap": {
                    "mean": overlap.mean_overlap,
                    "minimum": overlap.minimum_overlap,
                    "largest_angle_degrees": overlap.largest_angle_degrees,
                },
                "methods": method_results,
                "region": region,
            }
        )

    progress("[3/4] save tables, arrays, and diagnostic plots")
    csv_path = args.output_dir / "reachability.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "epsilon",
            "warm_loss",
            "top15_overlap_mean",
            "top15_largest_angle_degrees",
            *[f"{method}_loss" for method in METHOD_ORDER],
            "region",
        ]
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        for record in records:
            overlap = record["model_true_top15_overlap"]
            methods = record["methods"]
            writer.writerow(
                {
                    "epsilon": record["epsilon"],
                    "warm_loss": record["warm_loss"],
                    "top15_overlap_mean": overlap["mean"],
                    "top15_largest_angle_degrees": overlap[
                        "largest_angle_degrees"
                    ],
                    **{
                        f"{method}_loss": methods[method]["loss"]
                        for method in METHOD_ORDER
                    },
                    "region": record["region"],
                }
            )

    epsilons = np.asarray([record["epsilon"] for record in records])
    np.savez(
        args.output_dir / "reachability_data.npz",
        epsilons=epsilons,
        theta_star=theta_star,
        perturbation=np.asarray(perturbation),
        model_top_15=top_15,
        model_bottom_15=bottom_15,
        random_15=random_15,
        top_15_plus_5=top_15_plus_5,
        **parameter_results,
    )

    fig, axis = plt.subplots(figsize=(7.5, 4.5))
    axis.semilogy(
        epsilons,
        np.maximum([record["warm_loss"] for record in records], 1e-16),
        "o-",
        label="open loop",
    )
    styles = {
        "full_40": ("s-", "full 40"),
        "model_top_15": ("^-", "model top 15"),
        "top_15_plus_5": ("D-", "top 15 + 5 safety"),
        "random_15": ("x--", "random 15"),
        "bottom_15": ("v--", "bottom 15"),
    }
    for method, (style, label) in styles.items():
        axis.semilogy(
            epsilons,
            np.maximum(
                [record["methods"][method]["loss"] for record in records],
                1e-16,
            ),
            style,
            label=label,
        )
    axis.axhline(
        args.target_infidelity,
        color="black",
        linestyle=":",
        label=f"target {args.target_infidelity:g}",
    )
    axis.set(
        xlabel="relative drift mismatch ε",
        ylabel="privileged optimized infidelity 1−F",
        title="Reachability inside fixed model-derived subspaces",
    )
    axis.legend(fontsize=8, ncol=2)
    axis.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "reachability_vs_epsilon.png", dpi=180)
    plt.close(fig)

    fig, left_axis = plt.subplots(figsize=(7.5, 4.5))
    overlaps = [
        record["model_true_top15_overlap"]["mean"] for record in records
    ]
    angles = [
        record["model_true_top15_overlap"]["largest_angle_degrees"]
        for record in records
    ]
    left_axis.plot(epsilons, overlaps, "o-", color="tab:blue")
    left_axis.set(
        xlabel="relative drift mismatch ε",
        ylabel="mean squared principal-angle cosine",
        ylim=(0.0, 1.02),
    )
    right_axis = left_axis.twinx()
    right_axis.plot(epsilons, angles, "s--", color="tab:red")
    right_axis.set_ylabel("largest principal angle (degrees)")
    left_axis.set_title("Rotation of the true-device active subspace")
    left_axis.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "subspace_rotation_vs_epsilon.png", dpi=180)
    plt.close(fig)

    report = {
        "schema_version": 1,
        "run": "sim-to-real-reachability-v1",
        "purpose": (
            "Privileged gradient-based reachability diagnostic; not a "
            "black-box calibration result."
        ),
        "setup": {
            "dim": problem.dim,
            "target": "CNOT",
            "n_params": problem.n_params,
            "n_steps": args.n_steps,
            "epsilons": args.epsilons,
            "mismatch": "H0_true = H0 + epsilon * V",
            "perturbation_seed": args.perturbation_seed,
            "perturbation_normalization": "traceless Hermitian; ||V||F=||H0||F",
            "random_subspace_seed": args.random_seed,
            "target_infidelity": args.target_infidelity,
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
        "records": records,
        "artifacts": [
            "reachability.csv",
            "reachability_data.npz",
            "reachability_vs_epsilon.png",
            "subspace_rotation_vs_epsilon.png",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/run_reachability.py "
            f"--n-steps {args.n_steps}"
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
