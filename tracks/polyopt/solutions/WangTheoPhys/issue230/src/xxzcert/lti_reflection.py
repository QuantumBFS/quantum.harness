"""Reflection-parity and U(1)-blocked LTI relaxation."""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

from .lti_u1 import _selection, sector_basis
from .model import finite_xxz


def _reverse_bits(state: int, sites: int) -> int:
    reversed_state = 0
    for _ in range(sites):
        reversed_state = (reversed_state << 1) | (state & 1)
        state >>= 1
    return reversed_state


def reflection_bases(
    sites: int, ones: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Integer-column bases for even and odd reflection parity."""
    basis = sector_basis(sites, ones)
    positions = {state: index for index, state in enumerate(basis)}
    visited: set[int] = set()
    plus_columns: list[NDArray[np.float64]] = []
    minus_columns: list[NDArray[np.float64]] = []
    for state in basis:
        if state in visited:
            continue
        reflected = _reverse_bits(state, sites)
        visited.add(state)
        visited.add(reflected)
        first = positions[state]
        second = positions[reflected]
        plus = np.zeros(len(basis))
        plus[first] = 1
        if second != first:
            plus[second] = 1
            minus = np.zeros(len(basis))
            minus[first] = 1
            minus[second] = -1
            minus_columns.append(minus)
        plus_columns.append(plus)
    plus_matrix = np.column_stack(plus_columns)
    minus_matrix = (
        np.column_stack(minus_columns)
        if minus_columns
        else np.zeros((len(basis), 0))
    )
    return plus_matrix, minus_matrix


@dataclass(frozen=True)
class ReflectionLTICandidate:
    delta: float
    level: int
    raw_lower: float
    status: str
    solver: str
    dual_trace: float
    dual_sectors: tuple[NDArray[np.float64], ...]
    max_equality_residual: float
    minimum_parity_eigenvalue: float


def solve_reflection_lti(
    delta: float,
    level: int,
    solver: str = "SCS",
    *,
    solver_options: dict[str, float | int] | None = None,
) -> ReflectionLTICandidate:
    """Solve LTI after exact U(1) and reflection-parity reduction."""
    if level < 2:
        raise ValueError("level must be at least 2")
    first_bond = np.kron(
        finite_xxz(delta, 2, periodic=False).real,
        np.eye(1 << (level - 2)),
    )
    last_bond = np.kron(
        np.eye(1 << (level - 2)),
        finite_xxz(delta, 2, periodic=False).real,
    )
    objective_full = (first_bond + last_bond) / 2
    sector_components: list[
        list[tuple[NDArray[np.float64], cp.Variable]]
    ] = []
    parity_variables: list[cp.Variable] = []
    objective_terms: list[cp.Expression] = []
    trace_terms: list[cp.Expression] = []
    constraints: list[cp.Constraint] = []
    for ones in range(level + 1):
        basis = sector_basis(level, ones)
        plus, minus = reflection_bases(level, ones)
        plus_variable = cp.Variable(
            (plus.shape[1], plus.shape[1]),
            symmetric=True,
            name=f"rho_{ones}_plus",
        )
        parity_variables.append(plus_variable)
        constraints.append(plus_variable >> 0)
        components = [(plus, plus_variable)]
        objective_sector = objective_full[np.ix_(basis, basis)]
        objective_terms.append(
            cp.sum(
                cp.multiply(plus.T @ objective_sector @ plus, plus_variable)
            )
        )
        trace_terms.append(
            cp.sum(cp.multiply(plus.T @ plus, plus_variable))
        )
        if minus.shape[1]:
            minus_variable = cp.Variable(
                (minus.shape[1], minus.shape[1]),
                symmetric=True,
                name=f"rho_{ones}_minus",
            )
            parity_variables.append(minus_variable)
            constraints.append(minus_variable >> 0)
            components.append((minus, minus_variable))
            objective_terms.append(
                cp.sum(
                    cp.multiply(
                        minus.T @ objective_sector @ minus, minus_variable
                    )
                )
            )
            trace_terms.append(
                cp.sum(cp.multiply(minus.T @ minus, minus_variable))
            )
        sector_components.append(components)
    trace_constraint = (
        cp.sum(cp.hstack(trace_terms)) == 1
    )
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
            for parity_basis, variable in sector_components[global_ones]:
                left_map = first_selection.T @ parity_basis
                right_map = last_selection.T @ parity_basis
                left += left_map @ variable @ left_map.T
                right += right_map @ variable @ right_map.T
        equation = left == right
        compatibility.append(equation)
        constraints.append(equation)
    problem = cp.Problem(
        cp.Minimize(cp.sum(cp.hstack(objective_terms))), constraints
    )
    value = problem.solve(
        solver=solver, verbose=False, **dict(solver_options or {})
    )
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"reflection LTI failed: {problem.status}")
    residual = max(
        abs(
            sum(
                float(
                    np.sum(
                        (basis.T @ basis)
                        * np.asarray(variable.value)
                    )
                )
                for components in sector_components
                for basis, variable in components
            )
            - 1
        ),
        *(float(np.linalg.norm(equation.violation())) for equation in compatibility),
    )
    minimum = min(
        float(np.linalg.eigvalsh(np.asarray(variable.value))[0])
        for variable in parity_variables
    )
    duals = tuple(
        (
            np.asarray(equation.dual_value, dtype=float)
            + np.asarray(equation.dual_value, dtype=float).T
        )
        / 2
        for equation in compatibility
    )
    return ReflectionLTICandidate(
        delta=float(delta),
        level=level,
        raw_lower=float(value),
        status=problem.status,
        solver=solver,
        dual_trace=float(trace_constraint.dual_value),
        dual_sectors=duals,
        max_equality_residual=residual,
        minimum_parity_eigenvalue=minimum,
    )
