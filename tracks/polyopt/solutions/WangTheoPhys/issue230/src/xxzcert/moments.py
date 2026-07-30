"""Translation-invariant Pauli moment relaxations with local stationarity."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import cvxpy as cp
import numpy as np

from .optimality import (
    contiguous_words,
    ground_optimality_matrix,
    stationarity_constraints,
)
from .pauli_words import GaussianFraction, PauliWord


def translation_canonical(word: PauliWord) -> PauliWord:
    if not word.support:
        return word
    return word.shifted(-min(word.support))


@dataclass(frozen=True)
class MomentCandidate:
    delta: float
    radius: int
    stationarity_radius: int
    raw_lower: float
    status: str
    moment_dimension: int
    variable_count: int
    min_moment_eigenvalue: float
    max_weight: int
    optimality_radius: int


def _coefficient_complex(value: GaussianFraction) -> complex:
    return complex(float(value.real), float(value.imag))


def solve_moment_relaxation(
    delta: float,
    radius: int,
    stationarity_radius: int = 0,
    max_weight: int | None = None,
    optimality_radius: int = 0,
    solver: str = "CLARABEL",
) -> MomentCandidate:
    """Solve a sound principal-moment relaxation on an infinite TI chain."""
    if radius < 2:
        raise ValueError("radius must be at least 2")
    if stationarity_radius < 0:
        raise ValueError("stationarity_radius must be nonnegative")
    if optimality_radius < 0:
        raise ValueError("optimality_radius must be nonnegative")
    if max_weight is None:
        max_weight = radius
    if max_weight < 1 or max_weight > radius:
        raise ValueError("max_weight must be between 1 and radius")
    basis = [PauliWord()] + contiguous_words(radius, max_weight=max_weight)
    required: set[PauliWord] = {PauliWord()}
    products: dict[tuple[int, int], tuple[GaussianFraction, PauliWord]] = {}
    for row, left in enumerate(basis):
        for col, right in enumerate(basis):
            phase, product = left.multiply(right)
            canonical = translation_canonical(product)
            products[(row, col)] = (phase, canonical)
            required.add(canonical)
    stationarity = (
        stationarity_constraints(
            Fraction(str(delta)), stationarity_radius
        )
        if stationarity_radius
        else []
    )
    for polynomial in stationarity:
        required.update(translation_canonical(word) for word in polynomial.terms)
    optimality_entries = (
        ground_optimality_matrix(
            Fraction(str(delta)), optimality_radius, max_weight=1
        )[1]
        if optimality_radius
        else []
    )
    for row in optimality_entries:
        for polynomial in row:
            required.update(
                translation_canonical(word) for word in polynomial.terms
            )
    objective_words = [
        translation_canonical(PauliWord.from_dict({0: letter, 1: letter}))
        for letter in ("X", "Y", "Z")
    ]
    required.update(objective_words)
    variables = {
        word: cp.Variable(name=f"m_{index}", complex=False)
        for index, word in enumerate(sorted(required))
    }
    entries: list[list[cp.Expression]] = []
    for row in range(len(basis)):
        entries_row: list[cp.Expression] = []
        for col in range(len(basis)):
            phase, word = products[(row, col)]
            entries_row.append(_coefficient_complex(phase) * variables[word])
        entries.append(entries_row)
    moment = cp.bmat(entries)
    constraints: list[cp.Constraint] = [
        variables[PauliWord()] == 1,
        moment >> 0,
    ]
    for polynomial in stationarity:
        expression: cp.Expression = cp.Constant(0j)
        for word, coefficient in polynomial.terms.items():
            expression += _coefficient_complex(coefficient) * variables[
                translation_canonical(word)
            ]
        constraints.extend([cp.real(expression) == 0, cp.imag(expression) == 0])
    if optimality_entries:
        optimality_cvx: list[list[cp.Expression]] = []
        for row in optimality_entries:
            cvx_row: list[cp.Expression] = []
            for polynomial in row:
                expression = cp.Constant(0j)
                for word, coefficient in polynomial.terms.items():
                    expression += _coefficient_complex(coefficient) * variables[
                        translation_canonical(word)
                    ]
                cvx_row.append(expression)
            optimality_cvx.append(cvx_row)
        optimality_matrix = cp.bmat(optimality_cvx)
        constraints.append(optimality_matrix >> 0)
    xx, yy, zz = (variables[word] for word in objective_words)
    objective = (xx + yy + float(delta) * zz) / 4
    problem = cp.Problem(cp.Minimize(objective), constraints)
    kwargs = {"max_iter": 500} if solver.upper() == "CLARABEL" else {}
    value = problem.solve(solver=solver, verbose=False, **kwargs)
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"moment relaxation failed: {problem.status}")
    matrix = np.asarray(moment.value, dtype=np.complex128)
    matrix = (matrix + matrix.conj().T) / 2
    return MomentCandidate(
        delta=float(delta),
        radius=radius,
        stationarity_radius=stationarity_radius,
        raw_lower=float(value),
        status=problem.status,
        moment_dimension=len(basis),
        variable_count=len(variables),
        min_moment_eigenvalue=float(np.linalg.eigvalsh(matrix)[0]),
        max_weight=max_weight,
        optimality_radius=optimality_radius,
    )
