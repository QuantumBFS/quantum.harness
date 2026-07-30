"""Baseline locally translation-invariant semidefinite relaxation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

from .model import local_xxz, partial_trace_edge


@dataclass(frozen=True)
class LTICandidate:
    delta: float
    level: int
    raw_lower: float
    rho: NDArray[np.complex128]
    status: str
    solver: str
    trace_residual: float
    lti_residual: float
    min_eigenvalue: float
    dual_trace: float | None
    dual_lti: NDArray[np.complex128] | None
    solver_stats: dict[str, Any]


def _cp_trace_edge(expr: cp.Expression, sites: int, edge: str) -> cp.Expression:
    axis = 0 if edge == "left" else sites - 1
    return cp.partial_trace(expr, [2] * sites, axis=axis)


def _first_two_marginal(expr: cp.Expression, sites: int) -> cp.Expression:
    result = expr
    active = sites
    while active > 2:
        result = cp.partial_trace(result, [2] * active, axis=active - 1)
        active -= 1
    return result


def solve_lti(
    delta: float, level: int, solver: str = "CLARABEL"
) -> LTICandidate:
    """Solve the level-``n`` LTI relaxation with one n-site density matrix."""
    if level < 2:
        raise ValueError("LTI level must be at least 2")
    dim = 1 << level
    rho = cp.Variable((dim, dim), hermitian=True, name=f"rho_{level}")
    constraints: list[cp.Constraint] = [rho >> 0, cp.trace(rho) == 1]
    lti_constraint: cp.Constraint | None = None
    if level > 2:
        lti_constraint = (
            _cp_trace_edge(rho, level, "left")
            == _cp_trace_edge(rho, level, "right")
        )
        constraints.append(lti_constraint)
    rho2 = _first_two_marginal(rho, level)
    objective = cp.real(cp.trace(local_xxz(delta) @ rho2))
    problem = cp.Problem(cp.Minimize(objective), constraints)
    solve_kwargs: dict[str, Any] = {}
    if solver.upper() == "SCS":
        solve_kwargs.update(eps=1e-8, max_iters=200_000)
    value = problem.solve(solver=solver, verbose=False, **solve_kwargs)
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"LTI solve failed with status {problem.status}")
    matrix = np.asarray(rho.value, dtype=np.complex128)
    matrix = (matrix + matrix.conj().T) / 2
    trace_residual = abs(float(np.trace(matrix).real) - 1.0)
    if level > 2:
        left = partial_trace_edge(matrix, "left")
        right = partial_trace_edge(matrix, "right")
        lti_residual = float(np.linalg.norm(left - right, ord="fro"))
    else:
        lti_residual = 0.0
    stats = problem.solver_stats
    stats_dict = {
        "solve_time": stats.solve_time,
        "num_iters": stats.num_iters,
        "solver_name": stats.solver_name,
    }
    return LTICandidate(
        delta=float(delta),
        level=level,
        raw_lower=float(value),
        rho=matrix,
        status=problem.status,
        solver=solver,
        trace_residual=trace_residual,
        lti_residual=lti_residual,
        min_eigenvalue=float(np.linalg.eigvalsh(matrix)[0]),
        dual_trace=float(np.real(constraints[1].dual_value))
        if constraints[1].dual_value is not None
        else None,
        dual_lti=np.asarray(lti_constraint.dual_value, dtype=np.complex128)
        if lti_constraint is not None and lti_constraint.dual_value is not None
        else None,
        solver_stats=stats_dict,
    )
