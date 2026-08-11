"""Finite-period unitary dynamics and transported charge."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

import numpy as np
from scipy.sparse.linalg import expm_multiply

from .diagonalization import EDEngine


@dataclass(frozen=True)
class RealTimeChargeResult:
    period: float
    n_steps: int
    times: np.ndarray
    midpoint_phi: np.ndarray
    currents: np.ndarray
    cumulative_charge: np.ndarray
    norms: np.ndarray
    charge: float
    maximum_norm_error: float
    final_ground_state_fidelity: float
    final_state: np.ndarray


@dataclass(frozen=True)
class TimeStepConvergenceResult:
    coarse: RealTimeChargeResult
    fine: RealTimeChargeResult
    charge_difference: float


@dataclass(frozen=True)
class AdaptiveTimeStepResult(TimeStepConvergenceResult):
    refinement_count: int


def evolve_pump_cycle(
    engine: EDEngine,
    *,
    period: float,
    n_steps: int,
    direction: int = 1,
    norm_tolerance: float = 1e-9,
) -> RealTimeChargeResult:
    """Evolve one cycle with midpoint Magnus steps and integrate dH/dtheta."""
    if not np.isfinite(period) or period <= 0.0:
        raise ValueError("period must be positive and finite")
    if not isinstance(n_steps, int) or isinstance(n_steps, bool) or n_steps < 2:
        raise ValueError("n_steps must be an integer of at least 2")
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    if not np.isfinite(norm_tolerance) or norm_tolerance <= 0.0:
        raise ValueError("norm_tolerance must be positive and finite")

    initial = engine.vertex(Fraction(0), Fraction(0)).state
    state = np.asarray(initial, dtype=np.complex128).copy()
    dt = period / n_steps
    times = np.linspace(0.0, period, n_steps + 1)
    midpoint_phi = direction * 2.0 * np.pi * (
        np.arange(n_steps) + 0.5
    ) / n_steps
    currents = np.empty(n_steps, dtype=np.float64)
    cumulative_charge = np.zeros(n_steps + 1, dtype=np.float64)
    norms = np.empty(n_steps + 1, dtype=np.float64)
    norms[0] = np.linalg.norm(state)
    maximum_norm_error = abs(norms[0] - 1.0)

    for index, phi in enumerate(midpoint_phi):
        sparse_hamiltonian = engine.model.hamiltonian(phi, 0.0).tocsr()
        midpoint_state = expm_multiply(
            (-0.5j * dt) * sparse_hamiltonian,
            state,
        )
        current_operator = engine.model.current(phi, theta=0.0).tocsr()
        current = float(
            np.vdot(midpoint_state, current_operator @ midpoint_state).real
        )
        state = expm_multiply(
            (-0.5j * dt) * sparse_hamiltonian,
            midpoint_state,
        )
        if not np.all(np.isfinite(state)) or not np.isfinite(current):
            raise RuntimeError("real-time evolution produced non-finite values")

        currents[index] = current
        cumulative_charge[index + 1] = cumulative_charge[index] + dt * current
        norms[index + 1] = np.linalg.norm(state)
        maximum_norm_error = max(
            maximum_norm_error,
            abs(np.linalg.norm(midpoint_state) - 1.0),
            abs(norms[index + 1] - 1.0),
        )

    if maximum_norm_error > norm_tolerance:
        raise RuntimeError(
            f"real-time norm drift {maximum_norm_error:.3e} exceeds tolerance"
        )
    return RealTimeChargeResult(
        period=float(period),
        n_steps=n_steps,
        times=times,
        midpoint_phi=midpoint_phi,
        currents=currents,
        cumulative_charge=cumulative_charge,
        norms=norms,
        charge=float(cumulative_charge[-1]),
        maximum_norm_error=float(maximum_norm_error),
        final_ground_state_fidelity=float(abs(np.vdot(initial, state)) ** 2),
        final_state=state,
    )


def check_time_step_convergence(
    engine: EDEngine,
    *,
    period: float,
    steps: Sequence[int] = (200, 400),
    direction: int = 1,
) -> TimeStepConvergenceResult:
    if len(steps) != 2 or int(steps[0]) >= int(steps[1]):
        raise ValueError("steps must contain two increasing values")
    coarse = evolve_pump_cycle(
        engine,
        period=period,
        n_steps=int(steps[0]),
        direction=direction,
    )
    fine = evolve_pump_cycle(
        engine,
        period=period,
        n_steps=int(steps[1]),
        direction=direction,
    )
    return TimeStepConvergenceResult(
        coarse=coarse,
        fine=fine,
        charge_difference=abs(fine.charge - coarse.charge),
    )


def converge_time_steps(
    engine: EDEngine,
    *,
    period: float,
    initial_steps: int,
    charge_tolerance: float,
    max_refinements: int = 3,
    direction: int = 1,
) -> AdaptiveTimeStepResult:
    """Double nested time steps until transported charge is stable."""
    if not isinstance(initial_steps, int) or initial_steps < 2:
        raise ValueError("initial_steps must be an integer of at least 2")
    if not np.isfinite(charge_tolerance) or charge_tolerance <= 0.0:
        raise ValueError("charge_tolerance must be positive and finite")
    if not isinstance(max_refinements, int) or max_refinements < 1:
        raise ValueError("max_refinements must be a positive integer")

    coarse = evolve_pump_cycle(
        engine,
        period=period,
        n_steps=initial_steps,
        direction=direction,
    )
    for refinement in range(1, max_refinements + 1):
        fine = evolve_pump_cycle(
            engine,
            period=period,
            n_steps=coarse.n_steps * 2,
            direction=direction,
        )
        difference = abs(fine.charge - coarse.charge)
        if difference <= charge_tolerance:
            return AdaptiveTimeStepResult(
                coarse=coarse,
                fine=fine,
                charge_difference=difference,
                refinement_count=refinement,
            )
        coarse = fine
    raise RuntimeError(
        f"real-time charge did not converge after {max_refinements} refinements"
    )
