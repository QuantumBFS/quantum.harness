"""U(1)-sector-blocked local translation-invariant relaxation."""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

from .model import finite_xxz


def sector_basis(sites: int, ones: int) -> tuple[int, ...]:
    return tuple(state for state in range(1 << sites) if state.bit_count() == ones)


def _selection(
    sites: int, global_ones: int, remove: str, removed_bit: int
) -> NDArray[np.float64]:
    """Map a reduced-sector basis into a fixed global sector."""
    reduced_ones = global_ones - removed_bit
    if reduced_ones < 0 or reduced_ones > sites - 1:
        return np.zeros((0, 0))
    global_basis = sector_basis(sites, global_ones)
    global_positions = {state: index for index, state in enumerate(global_basis)}
    reduced_basis = sector_basis(sites - 1, reduced_ones)
    matrix = np.zeros((len(global_basis), len(reduced_basis)))
    for column, reduced in enumerate(reduced_basis):
        if remove == "first":
            state = (removed_bit << (sites - 1)) | reduced
        elif remove == "last":
            state = (reduced << 1) | removed_bit
        else:
            raise ValueError("remove must be first or last")
        matrix[global_positions[state], column] = 1
    return matrix


@dataclass(frozen=True)
class U1LTICandidate:
    delta: float
    level: int
    raw_lower: float
    status: str
    solver: str
    dual_trace: float
    dual_sectors: tuple[NDArray[np.float64], ...]
    max_equality_residual: float
    minimum_primal_eigenvalue: float


def solve_u1_lti(
    delta: float,
    level: int,
    solver: str = "CLARABEL",
    *,
    solver_options: dict[str, float | int] | None = None,
) -> U1LTICandidate:
    """Solve the level-n LTI relaxation in fixed-magnetization blocks."""
    if level < 2:
        raise ValueError("level must be at least 2")
    # Only the first bond enters the energy-density objective.
    first_bond = finite_xxz(delta, 2, periodic=False).real
    objective_full = np.kron(first_bond, np.eye(1 << (level - 2)))
    blocks: list[cp.Variable] = []
    objective_terms = []
    for ones in range(level + 1):
        basis = sector_basis(level, ones)
        block = cp.Variable((len(basis), len(basis)), symmetric=True, name=f"rho_{ones}")
        blocks.append(block)
        objective_terms.append(
            cp.sum(cp.multiply(objective_full[np.ix_(basis, basis)], block))
        )
    constraints: list[cp.Constraint] = [block >> 0 for block in blocks]
    trace_constraint = sum(cp.trace(block) for block in blocks) == 1
    constraints.append(trace_constraint)
    compatibility: list[cp.Constraint] = []
    for reduced_ones in range(level):
        size = len(sector_basis(level - 1, reduced_ones))
        left = cp.Constant(np.zeros((size, size)))
        right = cp.Constant(np.zeros((size, size)))
        for removed_bit in (0, 1):
            global_ones = reduced_ones + removed_bit
            first_selection = _selection(
                level, global_ones, "first", removed_bit
            )
            last_selection = _selection(
                level, global_ones, "last", removed_bit
            )
            block = blocks[global_ones]
            left += first_selection.T @ block @ first_selection
            right += last_selection.T @ block @ last_selection
        equation = left == right
        compatibility.append(equation)
        constraints.append(equation)
    problem = cp.Problem(cp.Minimize(cp.sum(cp.hstack(objective_terms))), constraints)
    options = dict(solver_options or {})
    value = problem.solve(solver=solver, verbose=False, **options)
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"U(1) LTI relaxation failed: {problem.status}")
    block_values = [np.asarray(block.value, dtype=float) for block in blocks]
    minimum = min(float(np.linalg.eigvalsh(value)[0]) for value in block_values)
    residual = max(
        [abs(sum(float(np.trace(value)) for value in block_values) - 1)]
        + [float(np.linalg.norm(equation.violation())) for equation in compatibility]
    )
    duals = tuple(
        (np.asarray(equation.dual_value, dtype=float)
         + np.asarray(equation.dual_value, dtype=float).T)
        / 2
        for equation in compatibility
    )
    return U1LTICandidate(
        delta=float(delta),
        level=level,
        raw_lower=float(value),
        status=problem.status,
        solver=solver,
        dual_trace=float(trace_constraint.dual_value),
        dual_sectors=duals,
        max_equality_residual=residual,
        minimum_primal_eigenvalue=minimum,
    )
