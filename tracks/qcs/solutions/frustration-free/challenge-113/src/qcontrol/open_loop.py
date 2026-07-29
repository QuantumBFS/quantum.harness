from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import jax
import jax.numpy as jnp
import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from qcontrol.objectives import normalized_infidelity
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


_ACCEPTANCE_LOSS = 1e-8


@dataclass(frozen=True)
class StartDiagnostic:
    index: int
    loss: float
    gradient_norm: float
    success: bool
    status: int
    message: str
    evaluations: int


@dataclass(frozen=True)
class OpenLoopResult:
    normalized_pulse: tuple[float, ...]
    loss: float
    gradient_norm: float
    starts: int
    evaluations: int


class OpenLoopAcceptanceError(RuntimeError):
    def __init__(self, diagnostics: tuple[StartDiagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        details = "; ".join(
            (
                f"start {item.index}: loss={item.loss:.17g}, "
                f"gradient_norm={item.gradient_norm:.17g}, "
                f"success={item.success}, status={item.status}, "
                f"evaluations={item.evaluations}, message={item.message!r}"
            )
            for item in diagnostics
        )
        super().__init__(
            f"no open-loop start reached loss <= {_ACCEPTANCE_LOSS:.0e}; {details}"
        )


def _validate_inputs(
    system: ControlSystem,
    space: PulseSpace,
    seed: object,
    starts: object,
) -> tuple[int, int]:
    if not isinstance(system, ControlSystem):
        raise ValueError("system must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if (
        isinstance(starts, (bool, np.bool_))
        or not isinstance(starts, Integral)
        or starts <= 0
    ):
        raise ValueError("starts must be a positive integer")
    return int(seed), int(starts)


def optimize_open_loop(
    system: ControlSystem,
    space: PulseSpace,
    seed: int,
    starts: int = 5,
) -> OpenLoopResult:
    seed, starts = _validate_inputs(system, space, seed, starts)
    parameter_count = space.parameter_count

    value_and_gradient = jax.jit(
        jax.value_and_grad(
            lambda pulse: normalized_infidelity(pulse, system, space)
        )
    )
    compiled = value_and_gradient.lower(
        jnp.zeros(parameter_count, dtype=jnp.float64)
    ).compile()

    rng = np.random.default_rng(seed)
    initial_points = [np.zeros(parameter_count, dtype=np.float64)]
    initial_points.extend(
        rng.uniform(-1.0, 1.0, parameter_count).astype(np.float64)
        for _ in range(starts - 1)
    )

    diagnostics: list[StartDiagnostic] = []
    candidates: list[
        tuple[float, float, int, tuple[float, ...], StartDiagnostic]
    ] = []
    total_evaluations = 0

    for start_index, initial in enumerate(initial_points):
        start_evaluations = 0

        def scipy_objective(
            pulse: NDArray[np.float64],
        ) -> tuple[float, NDArray[np.float64]]:
            nonlocal start_evaluations, total_evaluations
            start_evaluations += 1
            total_evaluations += 1
            value, gradient = compiled(jnp.asarray(pulse, dtype=jnp.float64))
            return (
                float(value),
                np.ascontiguousarray(np.asarray(gradient, dtype=np.float64)),
            )

        optimization = minimize(
            scipy_objective,
            np.ascontiguousarray(initial, dtype=np.float64),
            method="L-BFGS-B",
            jac=True,
            bounds=[(-1.0, 1.0)] * parameter_count,
            options={
                "ftol": 1e-15,
                "gtol": 1e-10,
                "maxiter": 2000,
                "maxls": 50,
            },
        )
        pulse = np.ascontiguousarray(optimization.x, dtype=np.float64)
        gradient = np.ascontiguousarray(optimization.jac, dtype=np.float64)
        loss = float(optimization.fun)
        gradient_norm = float(np.linalg.norm(gradient))
        diagnostic = StartDiagnostic(
            index=start_index,
            loss=loss,
            gradient_norm=gradient_norm,
            success=bool(optimization.success),
            status=int(optimization.status),
            message=str(optimization.message),
            evaluations=start_evaluations,
        )
        diagnostics.append(diagnostic)
        candidates.append(
            (
                loss,
                gradient_norm,
                start_index,
                tuple(float(value) for value in pulse),
                diagnostic,
            )
        )

    accepted = [candidate for candidate in candidates if candidate[0] <= _ACCEPTANCE_LOSS]
    if not accepted:
        raise OpenLoopAcceptanceError(tuple(diagnostics))

    loss, gradient_norm, _, normalized_pulse, _ = min(accepted, key=lambda item: item[:3])
    return OpenLoopResult(
        normalized_pulse=normalized_pulse,
        loss=loss,
        gradient_norm=gradient_norm,
        starts=starts,
        evaluations=total_evaluations,
    )
