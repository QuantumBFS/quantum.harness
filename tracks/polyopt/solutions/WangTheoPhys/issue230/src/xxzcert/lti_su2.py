"""SU(2)-multiplicity-adapted LTI relaxation for the XXX chain."""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray
from scipy.linalg import null_space

from .lti_u1 import U1LTICandidate, _selection, sector_basis
from .model import finite_xxz


def _spin_lowering(
    sites: int, source_ones: int
) -> NDArray[np.float64]:
    """Matrix of S^- from k down-spins to k+1 down-spins."""
    source = sector_basis(sites, source_ones)
    target = sector_basis(sites, source_ones + 1)
    positions = {state: index for index, state in enumerate(target)}
    matrix = np.zeros((len(target), len(source)))
    for column, state in enumerate(source):
        for position in range(sites):
            mask = 1 << position
            if not state & mask:
                matrix[positions[state | mask], column] = 1
    return matrix


def su2_multiplicity_bases(
    sites: int,
) -> tuple[
    tuple[int, ...],
    tuple[tuple[NDArray[np.float64] | None, ...], ...],
]:
    """Return consistent |j,m,alpha> bases grouped by magnetization sector."""
    twice_js = tuple(range(sites % 2, sites + 1, 2))
    by_j: list[tuple[NDArray[np.float64] | None, ...]] = []
    for twice_j in twice_js:
        highest_ones = (sites - twice_j) // 2
        if highest_ones == 0:
            highest = np.ones((1, 1))
        else:
            raising = _spin_lowering(sites, highest_ones - 1).T
            highest = null_space(raising, rcond=1e-11)
        expected = len(sector_basis(sites, highest_ones)) - (
            len(sector_basis(sites, highest_ones - 1))
            if highest_ones
            else 0
        )
        if highest.shape[1] != expected:
            raise ArithmeticError("failed to resolve SU(2) multiplicity")
        sectors: list[NDArray[np.float64] | None] = [None] * (sites + 1)
        sectors[highest_ones] = highest
        current = highest
        j = twice_j / 2
        m = j
        for ones in range(highest_ones, sites - highest_ones):
            lowering = _spin_lowering(sites, ones)
            coefficient = np.sqrt((j + m) * (j - m + 1))
            current = lowering @ current / coefficient
            sectors[ones + 1] = current
            m -= 1
        by_j.append(tuple(sectors))
    return twice_js, tuple(by_j)


@dataclass(frozen=True)
class SU2LTICandidate:
    level: int
    raw_lower: float
    status: str
    solver: str
    dual_trace: float
    dual_sectors: tuple[NDArray[np.float64], ...]
    max_equality_residual: float
    minimum_multiplicity_eigenvalue: float
    multiplicity_dimensions: tuple[int, ...]


def lift_su2_dual_to_u1(candidate: SU2LTICandidate) -> U1LTICandidate:
    """Lift reduced SU(2) multipliers to magnetization-sector multipliers.

    The SU(2) compatibility equation for spin ``j`` is represented by its
    highest-weight block.  In a full U(1) formulation the same equation occurs
    in every magnetic component.  Distributing its multiplier uniformly over
    the ``2j+1`` components reproduces the reduced Lagrangian.  The returned
    floating-point matrices are only candidates: ``lti_u1_rational`` can
    rationalize them and verify the resulting full-sector slacks exactly.
    """
    reduced_sites = candidate.level - 1
    twice_js, bases_by_j = su2_multiplicity_bases(reduced_sites)
    if len(candidate.dual_sectors) != len(twice_js):
        raise ValueError("SU(2) dual sector count mismatch")
    lifted: list[NDArray[np.float64]] = []
    for ones in range(reduced_sites + 1):
        size = len(sector_basis(reduced_sites, ones))
        multiplier = np.zeros((size, size))
        for twice_j, sectors, dual in zip(
            twice_js,
            bases_by_j,
            candidate.dual_sectors,
            strict=True,
        ):
            basis = sectors[ones]
            if basis is None:
                continue
            if dual.shape != (basis.shape[1], basis.shape[1]):
                raise ValueError("SU(2) dual multiplicity mismatch")
            multiplier += basis @ dual @ basis.T / (twice_j + 1)
        lifted.append((multiplier + multiplier.T) / 2)
    return U1LTICandidate(
        delta=1.0,
        level=candidate.level,
        raw_lower=candidate.raw_lower,
        status=candidate.status,
        solver=f"{candidate.solver}+SU2-lift",
        dual_trace=candidate.dual_trace,
        dual_sectors=tuple(lifted),
        max_equality_residual=candidate.max_equality_residual,
        minimum_primal_eigenvalue=candidate.minimum_multiplicity_eigenvalue,
    )


def solve_su2_lti(
    level: int,
    solver: str = "SCS",
    *,
    solver_options: dict[str, float | int] | None = None,
) -> SU2LTICandidate:
    """Solve the XXX LTI relaxation in total-spin multiplicity spaces."""
    if level < 2:
        raise ValueError("level must be at least two")
    twice_js, bases_by_j = su2_multiplicity_bases(level)
    variables: list[cp.Variable] = []
    constraints: list[cp.Constraint] = []
    for twice_j, sectors in zip(twice_js, bases_by_j, strict=True):
        basis = next(item for item in sectors if item is not None)
        multiplicity = basis.shape[1]
        variable = cp.Variable(
            (multiplicity, multiplicity),
            symmetric=True,
            name=f"spin_{twice_j}_multiplicity",
        )
        variables.append(variable)
        constraints.append(variable >> 0)
    first_bond = np.kron(
        finite_xxz(1.0, 2, periodic=False).real,
        np.eye(1 << (level - 2)),
    )
    sector_components: list[
        list[tuple[NDArray[np.float64], cp.Variable, int]]
    ] = [[] for _ in range(level + 1)]
    objective_terms: list[cp.Expression] = []
    for variable, twice_j, sectors in zip(
        variables, twice_js, bases_by_j, strict=True
    ):
        weight = 1 / (twice_j + 1)
        for ones, basis in enumerate(sectors):
            if basis is None:
                continue
            sector_components[ones].append((basis, variable, twice_j))
            computational = sector_basis(level, ones)
            compressed = (
                basis.T
                @ first_bond[np.ix_(computational, computational)]
                @ basis
            )
            objective_terms.append(
                weight * cp.sum(cp.multiply(compressed, variable))
            )
    trace_constraint = cp.sum(
        cp.hstack([cp.sum(cp.diag(variable)) for variable in variables])
    ) == 1
    constraints.append(trace_constraint)
    compatibility: list[cp.Constraint] = []
    reduced_twice_js, reduced_bases_by_j = su2_multiplicity_bases(level - 1)
    for reduced_twice_j, reduced_sectors in zip(
        reduced_twice_js, reduced_bases_by_j, strict=True
    ):
        reduced_ones = (level - 1 - reduced_twice_j) // 2
        reduced_basis = reduced_sectors[reduced_ones]
        if reduced_basis is None:
            raise ArithmeticError("missing reduced highest-weight basis")
        multiplicity = reduced_basis.shape[1]
        left = cp.Constant(np.zeros((multiplicity, multiplicity)))
        right = cp.Constant(np.zeros((multiplicity, multiplicity)))
        for removed_bit in (0, 1):
            global_ones = reduced_ones + removed_bit
            first_selection = _selection(
                level, global_ones, "first", removed_bit
            )
            last_selection = _selection(
                level, global_ones, "last", removed_bit
            )
            for basis, variable, twice_j in sector_components[global_ones]:
                # Each m component of a spin-j irrep carries weight 1/(2j+1).
                weight = 1 / (twice_j + 1)
                left_map = reduced_basis.T @ first_selection.T @ basis
                right_map = reduced_basis.T @ last_selection.T @ basis
                left += weight * left_map @ variable @ left_map.T
                right += weight * right_map @ variable @ right_map.T
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
        raise RuntimeError(f"SU(2) LTI failed: {problem.status}")
    residual = max(
        abs(sum(float(np.trace(variable.value)) for variable in variables) - 1),
        *(float(np.linalg.norm(equation.violation())) for equation in compatibility),
    )
    minimum = min(
        float(np.linalg.eigvalsh(np.asarray(variable.value))[0])
        for variable in variables
    )
    duals = tuple(
        (
            np.asarray(equation.dual_value, dtype=float)
            + np.asarray(equation.dual_value, dtype=float).T
        )
        / 2
        for equation in compatibility
    )
    return SU2LTICandidate(
        level=level,
        raw_lower=float(value),
        status=problem.status,
        solver=solver,
        dual_trace=float(trace_constraint.dual_value),
        dual_sectors=duals,
        max_equality_residual=residual,
        minimum_multiplicity_eigenvalue=minimum,
        multiplicity_dimensions=tuple(variable.shape[0] for variable in variables),
    )
