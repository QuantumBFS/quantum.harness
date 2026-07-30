#!/usr/bin/env python3
"""Reproduce and numerically calibrate the starting CNOT-control notebook."""

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

from landscapes import (
    endpoint_jacobian,
    explicit_hessian,
    hessian_subspace,
    jacobian_subspace,
    krylov_hessian_eigensystem,
    sorted_eigensystem,
    subspace_metrics,
)
from optimizers import optimize_differentiable
from sim_to_real import (
    fourier_controls,
    gate_fidelity,
    make_demo_problem,
    make_loss,
    phase_aligned_unitary_distance,
    propagate_expm,
    propagate_odeint,
    unitarity_defect,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tracks/qcs/results/sim-to-real-calibration-v1"),
    )
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--maxiter", type=int, default=1000)
    parser.add_argument("--gtol", type=float, default=1e-7)
    parser.add_argument(
        "--skip-ode-optimization",
        action="store_true",
        help="Only compare ODE propagation at the expm optimum.",
    )
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def timed_value(function, *args, **kwargs):
    start = time.perf_counter()
    value = function(*args, **kwargs)
    if hasattr(value, "block_until_ready"):
        value.block_until_ready()
    return value, time.perf_counter() - start


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    problem = make_demo_problem()

    progress(
        f"[1/7] setup d={problem.dim}, controls={problem.n_ctrl}, "
        f"basis={problem.n_basis}, params={problem.n_params}, device={jax.devices()}"
    )
    expm_loss = make_loss(problem, integrator="expm", n_steps=args.n_steps)
    compiled_loss = jax.jit(expm_loss)
    _, compile_seconds = timed_value(compiled_loss, problem.initial_params)
    _, warm_seconds = timed_value(compiled_loss, problem.initial_params)
    progress(
        f"      JIT compile+first={compile_seconds:.3f}s, warm={warm_seconds:.6f}s"
    )

    progress("[2/7] optimize the structure-preserving model")
    start = time.perf_counter()
    expm_result = optimize_differentiable(
        expm_loss,
        problem.initial_params,
        method="BFGS",
        gtol=args.gtol,
        maxiter=args.maxiter,
    )
    expm_opt_seconds = time.perf_counter() - start
    progress(
        f"      loss={expm_result.loss:.6e}, success={expm_result.success}, "
        f"nfev={expm_result.evaluations}, wall={expm_opt_seconds:.2f}s"
    )

    ode_result = None
    ode_opt_seconds = None
    if not args.skip_ode_optimization:
        progress("[3/7] reproduce notebook-style ODE optimization")
        ode_loss = make_loss(
            problem, integrator="odeint", rtol=1e-9, atol=1e-9
        )
        start = time.perf_counter()
        ode_result = optimize_differentiable(
            ode_loss,
            problem.initial_params,
            method="BFGS",
            gtol=args.gtol,
            maxiter=args.maxiter,
        )
        ode_opt_seconds = time.perf_counter() - start
        progress(
            f"      loss={ode_result.loss:.6e}, success={ode_result.success}, "
            f"nfev={ode_result.evaluations}, wall={ode_opt_seconds:.2f}s"
        )
    else:
        progress("[3/7] ODE optimization skipped by request")

    progress("[4/7] integrator and unitarity calibration")
    theta_star = jnp.asarray(expm_result.params)
    unitary = propagate_expm(problem, theta_star, n_steps=args.n_steps)
    unitary_refined = propagate_expm(problem, theta_star, n_steps=2 * args.n_steps)
    unitary_ode = propagate_odeint(
        problem, theta_star, rtol=1e-10, atol=1e-10
    )
    loss_at_steps = 1.0 - float(gate_fidelity(unitary, problem.target))
    loss_at_refined_steps = 1.0 - float(
        gate_fidelity(unitary_refined, problem.target)
    )
    loss_at_ode = 1.0 - float(gate_fidelity(unitary_ode, problem.target))
    unitary_defect_value = float(unitarity_defect(unitary))
    refined_difference = float(
        phase_aligned_unitary_distance(unitary, unitary_refined)
    )
    ode_difference = float(
        phase_aligned_unitary_distance(unitary_refined, unitary_ode)
    )
    progress(
        f"      ||U†U-I||F={unitary_defect_value:.3e}, "
        f"loss({args.n_steps})={loss_at_steps:.3e}, "
        f"loss({2 * args.n_steps})={loss_at_refined_steps:.3e}, "
        f"loss(ode)={loss_at_ode:.3e}"
    )

    progress("[5/7] explicit Hessian and endpoint Jacobian")
    hessian, hessian_seconds = timed_value(
        explicit_hessian, expm_loss, theta_star
    )
    eigenvalues, eigenvectors = sorted_eigensystem(hessian)
    jacobian, jacobian_seconds = timed_value(
        endpoint_jacobian, problem, theta_star, n_steps=args.n_steps
    )
    singular_values, jacobian_basis = jacobian_subspace(jacobian, 15)
    _, hessian_basis = hessian_subspace(hessian, 15)
    krylov_start = time.perf_counter()
    krylov_eigenvalues, krylov_basis = krylov_hessian_eigensystem(
        expm_loss,
        theta_star,
        15,
        tolerance=1e-8,
    )
    krylov_seconds = time.perf_counter() - krylov_start
    agreement = subspace_metrics(hessian_basis, jacobian_basis)
    krylov_agreement = subspace_metrics(hessian_basis, krylov_basis)
    progress(
        f"      Hessian={hessian_seconds:.2f}s, Jacobian={jacobian_seconds:.2f}s, "
        f"HVP-Krylov={krylov_seconds:.2f}s, "
        f"H/J overlap={agreement.mean_overlap:.6f}, "
        f"H/K overlap={krylov_agreement.mean_overlap:.6f}"
    )

    progress("[6/7] render controls and spectra")
    times = np.linspace(0.0, problem.t_final, 101)
    controls = np.stack(
        [
            np.asarray(fourier_controls(problem, jnp.asarray(time), theta_star))
            for time in times
        ]
    )
    fig, axis = plt.subplots(figsize=(7, 4))
    for index in range(problem.n_ctrl):
        axis.plot(times, controls[:, index], label=f"u{index}")
    axis.set(xlabel="t", ylabel="control field", title="Optimized CNOT controls")
    axis.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "control_fields.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7, 4))
    axis.semilogy(
        np.arange(1, problem.n_params + 1),
        np.maximum(np.abs(np.asarray(eigenvalues)), 1e-18),
        "o-",
        label="|Hessian eigenvalue|",
    )
    axis.axvline(15.5, color="black", linestyle="--", label="d²−1 = 15")
    axis.set(
        xlabel="descending index",
        ylabel="magnitude",
        title="Control-landscape Hessian spectrum",
    )
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.output_dir / "hessian_spectrum.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7, 4))
    axis.semilogy(
        np.arange(1, singular_values.size + 1),
        np.maximum(np.asarray(singular_values), 1e-18),
        "o-",
    )
    axis.set(
        xlabel="descending index",
        ylabel="singular value",
        title="Phase-gauged endpoint Jacobian",
    )
    fig.tight_layout()
    fig.savefig(args.output_dir / "endpoint_jacobian_spectrum.png", dpi=180)
    plt.close(fig)

    np.savez(
        args.output_dir / "calibration_data.npz",
        theta_star=np.asarray(theta_star),
        hessian=np.asarray(hessian),
        hessian_eigenvalues=np.asarray(eigenvalues),
        hessian_eigenvectors=np.asarray(eigenvectors),
        endpoint_jacobian=np.asarray(jacobian),
        endpoint_singular_values=np.asarray(singular_values),
        krylov_eigenvalues=np.asarray(krylov_eigenvalues),
        krylov_eigenvectors=np.asarray(krylov_basis),
        times=times,
        controls=controls,
    )

    eigenvalue_15 = float(eigenvalues[14])
    eigenvalue_16 = float(eigenvalues[15])
    spectral_gap = (
        abs(eigenvalue_15) / max(abs(eigenvalue_16), np.finfo(float).tiny)
    )
    report = {
        "schema_version": 1,
        "run": "sim-to-real-calibration-v1",
        "setup": {
            "dim": problem.dim,
            "target": "CNOT",
            "t_final": problem.t_final,
            "n_ctrl": problem.n_ctrl,
            "n_basis": problem.n_basis,
            "n_params": problem.n_params,
            "seed": problem.seed,
            "integrator": "midpoint product of exponentials",
            "n_steps": args.n_steps,
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
        "optimization": {
            "expm": {
                "loss": expm_result.loss,
                "success": expm_result.success,
                "iterations": expm_result.iterations,
                "evaluations": expm_result.evaluations,
                "message": expm_result.message,
                "wall_seconds": expm_opt_seconds,
            },
            "odeint": (
                None
                if ode_result is None
                else {
                    "loss": ode_result.loss,
                    "success": ode_result.success,
                    "iterations": ode_result.iterations,
                    "evaluations": ode_result.evaluations,
                    "message": ode_result.message,
                    "wall_seconds": ode_opt_seconds,
                }
            ),
        },
        "timing": {
            "jit_compile_and_first_seconds": compile_seconds,
            "jit_warm_seconds": warm_seconds,
            "hessian_seconds": hessian_seconds,
            "jacobian_seconds": jacobian_seconds,
            "hvp_krylov_seconds": krylov_seconds,
        },
        "verification": {
            "unitarity_defect_fro": unitary_defect_value,
            "loss_at_n_steps": loss_at_steps,
            "loss_at_2n_steps": loss_at_refined_steps,
            "loss_at_odeint": loss_at_ode,
            "step_refinement_difference_fro": refined_difference,
            "ode_vs_expm_difference_fro": ode_difference,
            "lambda15": eigenvalue_15,
            "lambda16": eigenvalue_16,
            "lambda15_to_lambda16_magnitude_ratio": spectral_gap,
            "hessian_jacobian_mean_overlap": agreement.mean_overlap,
            "hessian_jacobian_minimum_overlap": agreement.minimum_overlap,
            "hessian_jacobian_largest_angle_degrees": (
                agreement.largest_angle_degrees
            ),
            "explicit_krylov_mean_overlap": krylov_agreement.mean_overlap,
            "explicit_krylov_minimum_overlap": (
                krylov_agreement.minimum_overlap
            ),
            "explicit_krylov_largest_angle_degrees": (
                krylov_agreement.largest_angle_degrees
            ),
        },
        "artifacts": [
            "control_fields.png",
            "hessian_spectrum.png",
            "endpoint_jacobian_spectrum.png",
            "calibration_data.npz",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/run_calibration.py "
            f"--n-steps {args.n_steps}"
        ),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    progress(
        f"[7/7] complete: {args.output_dir}/run.json "
        f"(lambda15/lambda16={spectral_gap:.2e})"
    )


if __name__ == "__main__":
    main()
