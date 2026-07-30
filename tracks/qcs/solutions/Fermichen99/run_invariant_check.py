#!/usr/bin/env python3
"""Check that the active Hessian rank follows d²−1 for d=2 and d=4."""

from __future__ import annotations

import argparse
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

from landscapes import endpoint_jacobian, explicit_hessian, sorted_eigensystem
from optimizers import optimize_differentiable
from sim_to_real import (
    ControlProblem,
    make_demo_problem,
    make_loss,
    make_single_qubit_problem,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tracks/qcs/results/sim-to-real-invariant-v1"),
    )
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--maxiter", type=int, default=1000)
    parser.add_argument("--gtol", type=float, default=1e-7)
    parser.add_argument(
        "--relative-rank-threshold",
        type=float,
        default=1e-6,
    )
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def analyze_problem(
    name: str,
    problem: ControlProblem,
    *,
    n_steps: int,
    maxiter: int,
    gtol: float,
    relative_rank_threshold: float,
) -> tuple[dict[str, object], np.ndarray]:
    expected_rank = problem.dim**2 - 1
    loss = make_loss(problem, integrator="expm", n_steps=n_steps)
    start = time.perf_counter()
    optimization = optimize_differentiable(
        loss,
        problem.initial_params,
        method="BFGS",
        gtol=gtol,
        maxiter=maxiter,
    )
    optimization_seconds = time.perf_counter() - start
    theta_star = jnp.asarray(optimization.params)

    start = time.perf_counter()
    hessian = explicit_hessian(loss, theta_star)
    eigenvalues, _ = sorted_eigensystem(hessian)
    hessian_seconds = time.perf_counter() - start
    magnitudes = np.abs(np.asarray(eigenvalues))
    threshold = relative_rank_threshold * float(np.max(magnitudes))
    observed_rank = int(np.count_nonzero(magnitudes > threshold))

    start = time.perf_counter()
    jacobian = endpoint_jacobian(
        problem, theta_star, n_steps=n_steps
    )
    singular_values = np.linalg.svd(
        np.asarray(jacobian), compute_uv=False
    )
    jacobian_seconds = time.perf_counter() - start
    jacobian_threshold = (
        relative_rank_threshold * float(np.max(singular_values))
    )
    jacobian_rank = int(
        np.count_nonzero(singular_values > jacobian_threshold)
    )

    lambda_expected = float(magnitudes[expected_rank - 1])
    lambda_next = (
        None
        if expected_rank == magnitudes.size
        else float(magnitudes[expected_rank])
    )
    spectral_gap = (
        None
        if lambda_next is None
        else lambda_expected / max(lambda_next, np.finfo(float).tiny)
    )
    record = {
        "name": name,
        "dim": problem.dim,
        "n_params": problem.n_params,
        "expected_rank_d2_minus_1": expected_rank,
        "observed_hessian_rank": observed_rank,
        "observed_endpoint_jacobian_rank": jacobian_rank,
        "relative_rank_threshold": relative_rank_threshold,
        "optimization": {
            "loss": optimization.loss,
            "success": optimization.success,
            "iterations": optimization.iterations,
            "evaluations": optimization.evaluations,
            "wall_seconds": optimization_seconds,
        },
        "hessian_seconds": hessian_seconds,
        "jacobian_seconds": jacobian_seconds,
        "lambda_at_expected_rank": lambda_expected,
        "lambda_after_expected_rank": lambda_next,
        "spectral_gap": spectral_gap,
        "endpoint_singular_values": singular_values.tolist(),
    }
    return record, magnitudes


def main() -> None:
    args = parse_args()
    if args.relative_rank_threshold <= 0.0:
        raise ValueError("relative rank threshold must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    problems = [
        ("single-qubit X", make_single_qubit_problem()),
        ("two-qubit CNOT", make_demo_problem()),
    ]
    records: list[dict[str, object]] = []
    spectra: dict[str, np.ndarray] = {}
    total_start = time.perf_counter()
    progress(
        f"[1/3] invariant check: n_steps={args.n_steps}, "
        f"device={jax.devices()}"
    )
    for index, (name, problem) in enumerate(problems, start=1):
        progress(
            f"[2/3] {name} ({index}/{len(problems)}): "
            f"d={problem.dim}, p={problem.n_params}, "
            f"prediction={problem.dim**2 - 1}"
        )
        record, magnitudes = analyze_problem(
            name,
            problem,
            n_steps=args.n_steps,
            maxiter=args.maxiter,
            gtol=args.gtol,
            relative_rank_threshold=args.relative_rank_threshold,
        )
        records.append(record)
        spectra[name] = magnitudes
        progress(
            f"      loss={record['optimization']['loss']:.3e}, "
            f"Hessian rank={record['observed_hessian_rank']}, "
            f"Jacobian rank={record['observed_endpoint_jacobian_rank']}"
        )

    fig, axis = plt.subplots(figsize=(7.5, 4.6))
    markers = ["o-", "s-"]
    for (name, problem), marker in zip(problems, markers, strict=True):
        magnitudes = spectra[name]
        normalized = magnitudes / max(float(np.max(magnitudes)), 1e-300)
        axis.semilogy(
            np.arange(1, magnitudes.size + 1),
            np.maximum(normalized, 1e-18),
            marker,
            label=f"{name}: d²−1={problem.dim**2 - 1}",
        )
        axis.axvline(
            problem.dim**2 - 0.5,
            linestyle=":",
            alpha=0.5,
        )
    axis.axhline(
        args.relative_rank_threshold,
        color="black",
        linestyle="--",
        label="rank threshold",
    )
    axis.set(
        xlabel="descending Hessian eigenvalue index",
        ylabel="|λᵢ| / max |λ|",
        title="Active control-landscape rank across Hilbert-space sizes",
    )
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.output_dir / "hessian_rank_invariant.png", dpi=180)
    plt.close(fig)

    np.savez(
        args.output_dir / "invariant_spectra.npz",
        single_qubit=spectra["single-qubit X"],
        two_qubit=spectra["two-qubit CNOT"],
    )
    report = {
        "schema_version": 1,
        "run": "sim-to-real-invariant-v1",
        "setup": {
            "n_steps": args.n_steps,
            "relative_rank_threshold": args.relative_rank_threshold,
            "dtype": "complex128",
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
            "hessian_rank_invariant.png",
            "invariant_spectra.npz",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/"
            "run_invariant_check.py"
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
