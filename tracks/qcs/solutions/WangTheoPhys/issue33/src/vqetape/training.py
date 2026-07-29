"""Measured end-to-solution VQE training."""

from __future__ import annotations

import resource
import sys
import time
from typing import Any

import jax
import numpy as np

from vqetape.ground_state import tfim_ground_energy
from vqetape.initialization import initialize_parameters
from vqetape.optimizers import (
    OptimizerOutcome,
    OptimizerUnavailable,
    active_parameter_mask,
    pure_state_qgt,
    run_adam,
    run_lbfgs,
    run_natural_gradient,
)
from vqetape.programs import build_value_and_grad
from vqetape.spatial_programs import (
    build_spatial_value_and_grad,
)
from vqetape.spec import ProgramConfig
from vqetape.training_spec import (
    ParametersPayload,
    VQEStep,
    VQETrainingRequest,
    VQETrainingResult,
)


def _peak_rss_bytes() -> int:
    peak = int(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    )
    return peak if sys.platform == "darwin" else peak * 1024


def _parameter_payload(
    parameters: np.ndarray,
) -> ParametersPayload:
    return tuple(
        (
            tuple(float(value) for value in layer[0]),
            tuple(float(value) for value in layer[1]),
        )
        for layer in np.asarray(parameters)
    )


def _build_executable(request: VQETrainingRequest):
    if isinstance(request.program, ProgramConfig):
        return build_value_and_grad(
            request.spec,
            request.program,
        )
    return build_spatial_value_and_grad(
        request.spec,
        request.program,
    )


def train_vqe(
    request: VQETrainingRequest,
) -> VQETrainingResult:
    """Compile and run one complete measured VQE optimization."""

    initial, provenance = initialize_parameters(request)
    ground_energy = (
        request.ground_energy
        if request.ground_energy is not None
        else tfim_ground_energy(request.spec)
    )
    target_energy = (
        ground_energy + request.target_energy_error
    )

    executable = _build_executable(request)
    compile_started = time.perf_counter()
    compiled = executable.lower(initial).compile()
    compile_seconds = time.perf_counter() - compile_started

    optimization_started = time.perf_counter()
    first_started = time.perf_counter()
    first_energy, first_gradient = compiled(initial)
    jax.block_until_ready((first_energy, first_gradient))
    first_execute_seconds = (
        time.perf_counter() - first_started
    )
    initial_evaluation = (
        float(np.asarray(first_energy)),
        np.asarray(first_gradient),
    )
    cached_first = [initial_evaluation]
    trace: list[VQEStep] = []
    time_to_target: float | None = None
    last_parameters = np.array(initial, copy=True)

    def evaluate(
        parameters: np.ndarray,
    ) -> tuple[float, np.ndarray]:
        if cached_first:
            return cached_first.pop()
        device_parameters = np.asarray(
            parameters,
            dtype=initial.dtype,
        )
        energy, gradient = compiled(device_parameters)
        jax.block_until_ready((energy, gradient))
        return (
            float(np.asarray(energy)),
            np.asarray(gradient),
        )

    def observe(
        evaluation: int,
        optimizer_step: int,
        parameters: np.ndarray,
        energy: float,
        gradient: np.ndarray,
        metric_condition: float | None,
    ) -> bool:
        nonlocal time_to_target, last_parameters
        elapsed = time.perf_counter() - optimization_started
        energy_error = energy - ground_energy
        last_parameters = np.array(parameters, copy=True)
        trace.append(
            VQEStep(
                evaluation=evaluation,
                optimizer_step=optimizer_step,
                energy=float(energy),
                energy_error=float(energy_error),
                gradient_norm=float(
                    np.linalg.norm(gradient)
                ),
                elapsed_seconds=elapsed,
                metric_condition=metric_condition,
            )
        )
        reached = bool(
            np.isfinite(energy_error)
            and energy_error
            <= request.target_energy_error
        )
        if reached and time_to_target is None:
            time_to_target = compile_seconds + elapsed
        return reached

    mask = active_parameter_mask(request.spec)
    outcome: OptimizerOutcome | None = None
    failure: str | None = None
    skipped = False
    try:
        if request.optimizer == "adam":
            outcome = run_adam(
                initial,
                evaluate,
                observe,
                max_steps=request.max_steps,
                learning_rate=request.learning_rate,
                mask=mask,
            )
        elif request.optimizer == "lbfgs":
            outcome = run_lbfgs(
                initial,
                evaluate,
                observe,
                max_steps=request.max_steps,
                mask=mask,
            )
        else:
            outcome = run_natural_gradient(
                initial,
                evaluate,
                lambda parameters: pure_state_qgt(
                    np.asarray(
                        parameters,
                        dtype=initial.dtype,
                    ),
                    request.spec,
                ),
                observe,
                max_steps=request.max_steps,
                learning_rate=request.learning_rate,
                damping=request.damping,
                mask=mask,
            )
    except OptimizerUnavailable as exc:
        failure = str(exc)
        skipped = True
    except (
        FloatingPointError,
        ValueError,
        np.linalg.LinAlgError,
    ) as exc:
        failure = f"{type(exc).__name__}: {exc}"

    optimization_seconds = (
        time.perf_counter() - optimization_started
    )
    if outcome is not None:
        final_parameters = outcome.parameters
        converged = outcome.target_reached
        evaluations = outcome.evaluations
        optimizer_steps = outcome.steps
        if outcome.failure is not None:
            failure = outcome.failure
        elif not converged:
            failure = (
                "target not reached within max_steps"
            )
    else:
        final_parameters = last_parameters
        converged = False
        evaluations = len(trace)
        optimizer_steps = (
            trace[-1].optimizer_step if trace else 0
        )

    final_energy = (
        trace[-1].energy
        if trace
        else float(initial_evaluation[0])
    )
    return VQETrainingResult(
        request=request,
        converged=converged,
        evaluations=evaluations,
        optimizer_steps=optimizer_steps,
        compile_seconds=compile_seconds,
        first_execute_seconds=first_execute_seconds,
        optimization_seconds=optimization_seconds,
        time_to_target_seconds=time_to_target,
        total_seconds=(
            compile_seconds + optimization_seconds
        ),
        peak_rss_bytes=_peak_rss_bytes(),
        ground_energy=float(ground_energy),
        target_energy=float(target_energy),
        final_energy=float(final_energy),
        final_parameters=_parameter_payload(
            final_parameters
        ),
        trace=tuple(trace),
        initialization_provenance=provenance,
        failure=failure,
        skipped=skipped,
    )
