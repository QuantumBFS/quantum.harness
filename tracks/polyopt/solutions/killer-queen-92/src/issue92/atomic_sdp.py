"""Smallest state-polynomial gap SDP: the U(1)-invariant atomic limit.

This is not an ordinary ground-energy SDP.  At fixed gamma it tests the lifted
gap inequality for a diagonal one-site state of the truncated matrix algebra.
It is exact for the non-degenerate atomic ground state, but it is explicitly
U(1)-restricted and contains no lattice hopping.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from time import perf_counter
from typing import Callable

import cvxpy as cp
import numpy as np

from .local_algebra import atomic_energies


FEASIBLE_STATUSES = {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}
INFEASIBLE_STATUSES = {cp.INFEASIBLE, cp.INFEASIBLE_INACCURATE}


@dataclass
class AtomicResult:
    nmax: int
    interaction: float
    mu: float
    gamma: float
    solver: str
    status: str
    classification: str
    objective: float | None
    solve_time_s: float
    num_iters: int | None
    moment_size: int
    offdiagonal_constraints: int
    moment_min_eigenvalue: float | None
    gap_min_eigenvalue: float | None
    normalization_residual: float | None
    probabilities: list[float] | None
    observable: str | None = None
    sense: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _classification(status: str) -> str:
    if status in FEASIBLE_STATUSES:
        return "FEASIBLE"
    if status in INFEASIBLE_STATUSES:
        return "INFEASIBLE"
    return "UNKNOWN"


def _model(
    nmax: int,
    gamma: float,
    interaction: float,
    mu: float,
) -> tuple[cp.Variable, cp.Variable, list[cp.Constraint], cp.Expression, cp.Expression]:
    if gamma < 0:
        raise ValueError("gamma must be nonnegative")
    energies = atomic_energies(nmax, interaction=interaction, mu=mu)
    dim = nmax + 1
    probabilities = cp.Variable(dim, name="p")
    lifted_products = cp.Variable((dim, dim), symmetric=True, name="P")
    ones = np.ones(dim)

    # Moment matrix for the commuting state symbols 1, p_0, ..., p_nmax.
    moment = cp.bmat(
        [
            [np.ones((1, 1)), cp.reshape(probabilities, (1, dim), order="C")],
            [cp.reshape(probabilities, (dim, 1), order="C"), lifted_products],
        ]
    )

    # For diagonal test operators, the lifted variance block is
    # gamma * (P - diag(p)).  Physical points have P = p p^T.
    diagonal_gap = gamma * (lifted_products - cp.diag(probabilities))
    constraints: list[cp.Constraint] = [
        probabilities >= 0,
        cp.sum(probabilities) == 1,
        moment >> 0,
        lifted_products @ ones == probabilities,
        cp.diag(lifted_products) <= probabilities,
        diagonal_gap >> 0,
    ]

    # E_rs, r != s, is an independent charged excitation.  Its gap entry is
    # p_s * (e_r - e_s - gamma), affine because gamma is fixed.
    for source in range(dim):
        for target in range(dim):
            if target != source:
                constraints.append(
                    probabilities[source]
                    * (energies[target] - energies[source] - gamma)
                    >= 0
                )
    return probabilities, lifted_products, constraints, moment, diagonal_gap


def solve_atomic_gap(
    nmax: int,
    gamma: float,
    *,
    interaction: float = 1.0,
    mu: float = 0.5,
    solver: str = "CLARABEL",
    observable: np.ndarray | None = None,
    sense: str = "feasibility",
    observable_name: str | None = None,
) -> AtomicResult:
    """Solve a fixed-gamma atomic state-polynomial relaxation."""
    probabilities, lifted_products, constraints, moment, diagonal_gap = _model(
        nmax, gamma, interaction, mu
    )
    if sense == "feasibility":
        objective = cp.Minimize(0)
    elif sense == "min":
        if observable is None:
            raise ValueError("observable is required for optimization")
        objective = cp.Minimize(observable @ probabilities)
    elif sense == "max":
        if observable is None:
            raise ValueError("observable is required for optimization")
        objective = cp.Maximize(observable @ probabilities)
    else:
        raise ValueError("sense must be feasibility, min, or max")

    problem = cp.Problem(objective, constraints)
    start = perf_counter()
    try:
        value = problem.solve(solver=solver, verbose=False)
        status = str(problem.status)
    except cp.error.SolverError:
        value = None
        status = "solver_error"
    elapsed = perf_counter() - start
    classification = _classification(status)

    moment_min = None
    gap_min = None
    residual = None
    p_value = None
    if classification == "FEASIBLE" and probabilities.value is not None:
        p_array = np.asarray(probabilities.value, dtype=float)
        p_value = p_array.tolist()
        p_matrix = np.asarray(lifted_products.value, dtype=float)
        moment_value = np.block([[np.ones((1, 1)), p_array[None, :]], [p_array[:, None], p_matrix]])
        moment_min = float(np.linalg.eigvalsh(0.5 * (moment_value + moment_value.T))[0])
        gap_value = gamma * (p_matrix - np.diag(p_array))
        gap_min = float(np.linalg.eigvalsh(0.5 * (gap_value + gap_value.T))[0])
        residual = float(
            max(abs(np.sum(p_array) - 1.0), np.max(abs(p_matrix @ np.ones(nmax + 1) - p_array)))
        )

    stats = problem.solver_stats
    return AtomicResult(
        nmax=nmax,
        interaction=interaction,
        mu=mu,
        gamma=gamma,
        solver=solver,
        status=status,
        classification=classification,
        objective=None if value is None or not np.isfinite(value) else float(value),
        solve_time_s=float(stats.solve_time if stats.solve_time is not None else elapsed),
        num_iters=stats.num_iters,
        moment_size=nmax + 2,
        offdiagonal_constraints=nmax * (nmax + 1),
        moment_min_eigenvalue=moment_min,
        gap_min_eigenvalue=gap_min,
        normalization_residual=residual,
        probabilities=p_value,
        observable=observable_name,
        sense=sense,
    )


def bisect_atomic_gap(
    nmax: int,
    *,
    interaction: float = 1.0,
    mu: float = 0.5,
    lower: float = 0.0,
    upper: float = 1.0,
    tolerance: float = 1e-6,
    max_steps: int = 60,
    solver: str = "CLARABEL",
    callback: Callable[[AtomicResult], None] | None = None,
) -> tuple[float, float, list[AtomicResult]]:
    """Bracket the largest feasible gamma without conflating UNKNOWN and infeasible."""
    history: list[AtomicResult] = []

    def evaluate(gamma: float) -> AtomicResult:
        result = solve_atomic_gap(
            nmax, gamma, interaction=interaction, mu=mu, solver=solver
        )
        history.append(result)
        if callback is not None:
            callback(result)
        return result

    low_result = evaluate(lower)
    high_result = evaluate(upper)
    if low_result.classification != "FEASIBLE":
        raise RuntimeError(f"lower bracket is {low_result.classification}: {low_result.status}")
    if high_result.classification != "INFEASIBLE":
        raise RuntimeError(f"upper bracket is {high_result.classification}: {high_result.status}")

    for _ in range(max_steps):
        if upper - lower <= tolerance:
            break
        midpoint = 0.5 * (lower + upper)
        result = evaluate(midpoint)
        if result.classification == "FEASIBLE":
            lower = midpoint
        elif result.classification == "INFEASIBLE":
            upper = midpoint
        else:
            break
    return lower, upper, history


def atomic_observables(nmax: int) -> dict[str, np.ndarray]:
    occupation = np.arange(nmax + 1, dtype=float)
    return {
        "rho0": occupation,
        "F0": (occupation - 1.0) ** 2,
    }
