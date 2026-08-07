"""Fresh worker for the longitudinal-Ising VQE holdout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any

import jax
import numpy as np

from vqetape.holdout import (
    LongitudinalIsingSpec,
    holdout_z2_applicability,
    longitudinal_energy,
    longitudinal_ground_energy,
)
from vqetape.optimizers import run_lbfgs


def _peak_rss_bytes() -> int:
    value = int(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    )
    return value if sys.platform == "darwin" else value * 1024


def run_holdout(
    spec: LongitudinalIsingSpec,
    *,
    target_energy_error: float,
    max_steps: int,
    seed: int,
) -> dict[str, Any]:
    """Compile and train the exact holdout ansatz."""

    started = time.perf_counter()
    rng = np.random.default_rng(seed)
    initial = rng.normal(
        0.0,
        0.15,
        size=spec.parameter_shape,
    )
    initial[:, 0, -1] = 0.0
    ground_energy = longitudinal_ground_energy(spec)

    function = jax.jit(
        jax.value_and_grad(
            lambda values: longitudinal_energy(
                values,
                spec,
            )
        )
    )
    compile_started = time.perf_counter()
    compiled = function.lower(initial).compile()
    compile_seconds = time.perf_counter() - compile_started
    optimization_started = time.perf_counter()
    evaluations = 0
    time_to_target = None
    trace = []

    def evaluate(parameters):
        energy, gradient = compiled(
            np.asarray(parameters)
        )
        jax.block_until_ready((energy, gradient))
        return float(np.asarray(energy)), np.asarray(gradient)

    def observe(
        evaluation,
        optimizer_step,
        parameters,
        energy,
        gradient,
        metric_condition,
    ):
        del parameters, metric_condition
        nonlocal evaluations, time_to_target
        evaluations += 1
        error = energy - ground_energy
        trace.append(
            {
                "evaluation": evaluation,
                "optimizer_step": optimizer_step,
                "energy": float(energy),
                "energy_error": float(error),
                "gradient_norm": float(
                    np.linalg.norm(gradient)
                ),
                "elapsed_seconds": (
                    time.perf_counter() - started
                ),
            }
        )
        reached = error <= target_energy_error
        if reached and time_to_target is None:
            time_to_target = (
                time.perf_counter() - started
            )
        return reached

    mask = np.ones(spec.parameter_shape)
    mask[:, 0, -1] = 0
    outcome = run_lbfgs(
        initial,
        evaluate,
        observe,
        max_steps=max_steps,
        mask=mask,
    )
    parameters = np.asarray(outcome.parameters)
    if not outcome.target_reached:
        energy, gradient = evaluate(parameters)
        reached = observe(
            outcome.evaluations + 1,
            outcome.steps,
            parameters,
            energy,
            gradient,
            None,
        )
    else:
        reached = True
    optimization_seconds = (
        time.perf_counter() - optimization_started
    )
    final_energy = trace[-1]["energy"]
    return {
        "spec": spec.to_dict(),
        "ansatz": "rzz-ry-rx",
        "target_energy_error": target_energy_error,
        "max_steps": max_steps,
        "seed": seed,
        "converged": bool(reached),
        "evaluations": evaluations,
        "optimizer_steps": outcome.steps,
        "compile_seconds": compile_seconds,
        "optimization_seconds": optimization_seconds,
        "time_to_target_seconds": time_to_target,
        "total_seconds": time.perf_counter() - started,
        "peak_rss_bytes": _peak_rss_bytes(),
        "ground_energy": ground_energy,
        "final_energy": final_energy,
        "final_energy_error": final_energy - ground_energy,
        "final_parameters": parameters.tolist(),
        "trace": trace,
        "z2_spatial_compression": (
            holdout_z2_applicability(spec)
        ),
        "optimizer_message": outcome.failure,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    request = json.loads(
        args.request.read_text(encoding="utf-8")
    )
    spec = LongitudinalIsingSpec.from_dict(
        request["spec"]
    )
    result = run_holdout(
        spec,
        target_energy_error=float(
            request["target_energy_error"]
        ),
        max_steps=int(request["max_steps"]),
        seed=int(request["seed"]),
    )
    result["worker_pid"] = os.getpid()
    result["parent_pid"] = os.getppid()
    temporary = args.output.with_suffix(
        args.output.suffix + ".tmp"
    )
    temporary.write_text(
        json.dumps(result, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
