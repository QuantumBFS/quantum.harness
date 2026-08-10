"""Joint SU(2)- and reflection-adapted LTI relaxation for the XXX chain."""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

from .lti_su2 import (
    SU2LTICandidate,
    lift_su2_dual_to_u1,
    su2_multiplicity_bases,
)
from .lti_u1 import U1LTICandidate, _selection, sector_basis
from .model import finite_xxz


@dataclass(frozen=True)
class SU2ParityBasis:
    """Reflection eigenspaces inside one SU(2) multiplicity space."""

    twice_j: int
    reflection: NDArray[np.float64]
    even: NDArray[np.float64]
    odd: NDArray[np.float64]


def _reflection_permutation(
    sites: int, ones: int
) -> NDArray[np.float64]:
    basis = sector_basis(sites, ones)
    positions = {state: index for index, state in enumerate(basis)}
    result = np.zeros((len(basis), len(basis)))
    for column, state in enumerate(basis):
        reflected = 0
        for position in range(sites):
            reflected |= ((state >> position) & 1) << (sites - 1 - position)
        result[positions[reflected], column] = 1
    return result


def su2_reflection_bases(
    sites: int,
) -> tuple[tuple[int, ...], tuple[SU2ParityBasis, ...]]:
    """Diagonalize spatial reflection in every spin multiplicity space."""
    twice_js, by_j = su2_multiplicity_bases(sites)
    result: list[SU2ParityBasis] = []
    for twice_j, sectors in zip(twice_js, by_j, strict=True):
        highest_ones = (sites - twice_j) // 2
        highest = sectors[highest_ones]
        if highest is None:
            raise ArithmeticError("missing SU(2) highest-weight basis")
        permutation = _reflection_permutation(sites, highest_ones)
        compressed = highest.T @ permutation @ highest
        compressed = (compressed + compressed.T) / 2
        values, vectors = np.linalg.eigh(compressed)
        if np.max(np.abs(np.abs(values) - 1)) > 1e-8:
            raise ArithmeticError("ambiguous SU(2) reflection eigenvalue")
        even = vectors[:, values > 0]
        odd = vectors[:, values < 0]
        result.append(
            SU2ParityBasis(
                twice_j=twice_j,
                reflection=compressed,
                even=even,
                odd=odd,
            )
        )
    return twice_js, tuple(result)


@dataclass(frozen=True)
class SU2ReflectionLTICandidate:
    level: int
    raw_lower: float
    status: str
    solver: str
    dual_trace: float
    dual_cross_blocks: tuple[NDArray[np.float64], ...]
    max_equality_residual: float
    minimum_block_eigenvalue: float
    block_dimensions: tuple[tuple[int, int], ...]
    compatibility_shapes: tuple[tuple[int, int], ...]


def lift_su2_reflection_dual_to_u1(
    candidate: SU2ReflectionLTICandidate,
) -> U1LTICandidate:
    """Lift a joint-symmetry dual into the ordinary U(1) LTI dual.

    If ``D`` is the right boundary marginal of a reflection-invariant global
    state, the ordinary compatibility residual is ``R D R - D``.  A joint
    cross-parity multiplier therefore becomes minus one half of its symmetric
    completion in the ordinary left-minus-right convention.  The joint
    objective uses the mean of the first and last bonds; half of the open
    reduced Hamiltonian telescopes that objective back to the first-bond
    convention used by :mod:`lti_u1`.
    """
    reduced_sites = candidate.level - 1
    twice_js, parity_by_j = su2_reflection_bases(reduced_sites)
    if len(candidate.dual_cross_blocks) != len(twice_js):
        raise ValueError("SU(2) reflection dual sector count mismatch")
    compatibility_duals: list[NDArray[np.float64]] = []
    for parity, cross_dual in zip(
        parity_by_j, candidate.dual_cross_blocks, strict=True
    ):
        expected = (parity.even.shape[1], parity.odd.shape[1])
        if cross_dual.shape != expected:
            raise ValueError("SU(2) reflection dual shape mismatch")
        symmetric_cross = (
            parity.even @ cross_dual @ parity.odd.T
            + parity.odd @ cross_dual.T @ parity.even.T
        ) / 2
        compatibility_duals.append(-symmetric_cross / 2)
    su2_candidate = SU2LTICandidate(
        level=candidate.level,
        raw_lower=candidate.raw_lower,
        status=candidate.status,
        solver=f"{candidate.solver}+reflection-lift",
        dual_trace=candidate.dual_trace,
        dual_sectors=tuple(compatibility_duals),
        max_equality_residual=candidate.max_equality_residual,
        minimum_multiplicity_eigenvalue=candidate.minimum_block_eigenvalue,
        multiplicity_dimensions=tuple(
            even + odd for even, odd in candidate.block_dimensions
        ),
    )
    lifted = lift_su2_dual_to_u1(su2_candidate)
    reduced_hamiltonian = finite_xxz(
        1.0, reduced_sites, periodic=False
    ).real
    corrected: list[NDArray[np.float64]] = []
    for ones, multiplier in enumerate(lifted.dual_sectors):
        basis = sector_basis(reduced_sites, ones)
        correction = reduced_hamiltonian[np.ix_(basis, basis)] / 2
        corrected.append(
            (
                multiplier
                + correction
                + multiplier.T
                + correction.T
            )
            / 2
        )
    return U1LTICandidate(
        delta=1.0,
        level=candidate.level,
        raw_lower=candidate.raw_lower,
        status=candidate.status,
        solver=f"{candidate.solver}+SU2-reflection-lift",
        dual_trace=candidate.dual_trace,
        dual_sectors=tuple(corrected),
        max_equality_residual=candidate.max_equality_residual,
        minimum_primal_eigenvalue=candidate.minimum_block_eigenvalue,
    )


def solve_su2_reflection_lti(
    level: int,
    solver: str = "SCS",
    *,
    solver_options: dict[str, float | int | bool] | None = None,
) -> SU2ReflectionLTICandidate:
    """Solve XXX LTI using total-spin and spatial-reflection blocks."""
    if level < 2:
        raise ValueError("level must be at least two")
    twice_js, bases_by_j = su2_multiplicity_bases(level)
    parity_twice_js, parity_by_j = su2_reflection_bases(level)
    if twice_js != parity_twice_js:
        raise ArithmeticError("inconsistent SU(2) parity sectors")

    variables: list[
        tuple[
            cp.Variable | None,
            cp.Variable | None,
        ]
    ] = []
    constraints: list[cp.Constraint] = []
    for parity in parity_by_j:
        parity_variables: list[cp.Variable | None] = []
        for label, transform in (("even", parity.even), ("odd", parity.odd)):
            dimension = transform.shape[1]
            if dimension == 0:
                parity_variables.append(None)
                continue
            variable = cp.Variable(
                (dimension, dimension),
                symmetric=True,
                name=f"spin_{parity.twice_j}_{label}",
            )
            constraints.append(variable >> 0)
            parity_variables.append(variable)
        variables.append((parity_variables[0], parity_variables[1]))

    two_site = finite_xxz(1.0, 2, periodic=False).real
    first_bond = np.kron(two_site, np.eye(1 << (level - 2)))
    last_bond = np.kron(np.eye(1 << (level - 2)), two_site)
    objective_full = (first_bond + last_bond) / 2

    sector_components: list[
        list[
            tuple[
                NDArray[np.float64],
                cp.Variable,
                int,
            ]
        ]
    ] = [[] for _ in range(level + 1)]
    objective_terms: list[cp.Expression] = []
    active_variables: list[cp.Variable] = []
    for twice_j, sectors, parity, parity_variables in zip(
        twice_js,
        bases_by_j,
        parity_by_j,
        variables,
        strict=True,
    ):
        weight = 1 / (twice_j + 1)
        for transform, variable in zip(
            (parity.even, parity.odd), parity_variables, strict=True
        ):
            if variable is None:
                continue
            active_variables.append(variable)
            for ones, basis in enumerate(sectors):
                if basis is None:
                    continue
                adapted = basis @ transform
                sector_components[ones].append(
                    (adapted, variable, twice_j)
                )
                computational = sector_basis(level, ones)
                compressed = (
                    adapted.T
                    @ objective_full[np.ix_(computational, computational)]
                    @ adapted
                )
                objective_terms.append(
                    weight * cp.sum(cp.multiply(compressed, variable))
                )

    trace_constraint = cp.sum(
        cp.hstack([cp.trace(variable) for variable in active_variables])
    ) == 1
    constraints.append(trace_constraint)

    reduced_twice_js, reduced_bases_by_j = su2_multiplicity_bases(
        level - 1
    )
    parity_reduced_twice_js, reduced_parity_by_j = su2_reflection_bases(
        level - 1
    )
    if reduced_twice_js != parity_reduced_twice_js:
        raise ArithmeticError("inconsistent reduced SU(2) parity sectors")
    compatibility: list[cp.Constraint | None] = []
    compatibility_shapes: list[tuple[int, int]] = []
    for reduced_twice_j, reduced_sectors, reduced_parity in zip(
        reduced_twice_js,
        reduced_bases_by_j,
        reduced_parity_by_j,
        strict=True,
    ):
        even_dimension = reduced_parity.even.shape[1]
        odd_dimension = reduced_parity.odd.shape[1]
        compatibility_shapes.append((even_dimension, odd_dimension))
        if even_dimension == 0 or odd_dimension == 0:
            compatibility.append(None)
            continue
        reduced_ones = (level - 1 - reduced_twice_j) // 2
        reduced_basis = reduced_sectors[reduced_ones]
        if reduced_basis is None:
            raise ArithmeticError("missing reduced highest-weight basis")
        reduced_even = reduced_basis @ reduced_parity.even
        reduced_odd = reduced_basis @ reduced_parity.odd
        cross: cp.Expression = cp.Constant(
            np.zeros((even_dimension, odd_dimension))
        )
        for removed_bit in (0, 1):
            global_ones = reduced_ones + removed_bit
            selection = _selection(
                level, global_ones, "last", removed_bit
            )
            for basis, variable, twice_j in sector_components[global_ones]:
                weight = 1 / (twice_j + 1)
                even_map = reduced_even.T @ selection.T @ basis
                odd_map = reduced_odd.T @ selection.T @ basis
                cross += weight * even_map @ variable @ odd_map.T
        equation = cross == 0
        compatibility.append(equation)
        constraints.append(equation)

    problem = cp.Problem(
        cp.Minimize(cp.sum(cp.hstack(objective_terms))), constraints
    )
    value = problem.solve(
        solver=solver,
        verbose=False,
        **dict(solver_options or {}),
    )
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(
            f"SU(2) reflection LTI failed: {problem.status}"
        )
    residuals = [
        abs(
            sum(
                float(np.trace(np.asarray(variable.value)))
                for variable in active_variables
            )
            - 1
        )
    ]
    residuals.extend(
        float(np.linalg.norm(equation.violation()))
        for equation in compatibility
        if equation is not None
    )
    minimum = min(
        float(np.linalg.eigvalsh(np.asarray(variable.value))[0])
        for variable in active_variables
    )
    dual_cross_blocks = tuple(
        np.zeros(shape)
        if equation is None
        else np.asarray(equation.dual_value, dtype=float)
        for equation, shape in zip(
            compatibility, compatibility_shapes, strict=True
        )
    )
    return SU2ReflectionLTICandidate(
        level=level,
        raw_lower=float(value),
        status=problem.status,
        solver=solver,
        dual_trace=float(trace_constraint.dual_value),
        dual_cross_blocks=dual_cross_blocks,
        max_equality_residual=max(residuals),
        minimum_block_eigenvalue=minimum,
        block_dimensions=tuple(
            (parity.even.shape[1], parity.odd.shape[1])
            for parity in parity_by_j
        ),
        compatibility_shapes=tuple(compatibility_shapes),
    )
