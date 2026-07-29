"""Numerical common-quadratic contraction bounds for oddcycle alphabets."""

from __future__ import annotations

import argparse
import json
import warnings
from collections.abc import Sequence
from math import isfinite, sqrt

import numpy as np

from .symmetric_oddcycle_discovery import (
    compound_matrix,
    oddcycle_matrix,
)


SCHEMA = "oddcycle-exterior-common-quadratic-v1"


def _float_rows(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def _validated_points(
    points: Sequence[Sequence[float]],
) -> tuple[tuple[float, float, float], ...]:
    if not points:
        raise ValueError("points must be nonempty")
    validated = []
    for point in points:
        if len(point) != 3:
            raise ValueError("every point must contain p, q, and r")
        values = tuple(float(value) for value in point)
        if not all(isfinite(value) for value in values):
            raise ValueError("point coordinates must be finite")
        validated.append(values)
    return tuple(validated)


def _direct_gamma(
    atoms: tuple[np.ndarray, ...],
    metric: np.ndarray,
) -> float:
    eigenvalues, eigenvectors = np.linalg.eigh(metric)
    inverse_square_root = (
        eigenvectors
        @ np.diag(1.0 / np.sqrt(eigenvalues))
        @ eigenvectors.T
    )
    maximum = 0.0
    for atom in atoms:
        conjugated = (
            inverse_square_root
            @ (atom.T @ metric @ atom)
            @ inverse_square_root
        )
        maximum = max(maximum, float(np.linalg.eigvalsh(conjugated)[-1]))
    return sqrt(max(0.0, maximum))


def _solve_grade(
    cp,
    atoms: tuple[np.ndarray, ...],
    *,
    grade: int,
    solver: str,
    epsilon: float,
    gamma_tolerance: float,
    validation_tolerance: float,
    max_bisection_steps: int,
    solver_options: dict[str, object],
) -> dict[str, object]:
    dimension = atoms[0].shape[0]
    identity = np.eye(dimension)
    metric_variable = cp.Variable((dimension, dimension), symmetric=True)
    gamma_squared = cp.Parameter(nonneg=True)
    constraints = [
        cp.trace(metric_variable) == 1.0,
        metric_variable - epsilon * identity >> 0,
    ]
    constraints.extend(
        gamma_squared * metric_variable
        - atom.T @ metric_variable @ atom
        - epsilon * identity
        >> 0
        for atom in atoms
    )
    problem = cp.Problem(cp.Minimize(0.0), constraints)

    def solve_at(gamma: float) -> tuple[bool, np.ndarray | None, str, float]:
        gamma_squared.value = float(gamma * gamma)
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Solution may be inaccurate.*",
                    category=UserWarning,
                )
                problem.solve(
                    solver=solver,
                    warm_start=True,
                    **solver_options,
                )
        except cp.error.SolverError:
            return False, None, "solver-error", float("-inf")
        status = str(problem.status)
        if metric_variable.value is None:
            return False, None, status, float("-inf")
        metric = np.asarray(metric_variable.value, dtype=float)
        metric = 0.5 * (metric + metric.T)
        trace = float(np.trace(metric))
        if not isfinite(trace) or trace <= 0.0:
            return False, None, status, float("-inf")
        metric /= trace
        metric_minimum = float(np.linalg.eigvalsh(metric)[0])
        gaps = tuple(
            gamma * gamma * metric - atom.T @ metric @ atom
            for atom in atoms
        )
        minimum_gap = min(
            float(np.linalg.eigvalsh(0.5 * (gap + gap.T))[0])
            for gap in gaps
        )
        feasible = (
            status in {str(cp.OPTIMAL), str(cp.OPTIMAL_INACCURATE)}
            and metric_minimum >= epsilon - validation_tolerance
            and minimum_gap >= epsilon - validation_tolerance
        )
        return feasible, metric if feasible else None, status, minimum_gap

    upper = max(float(np.linalg.norm(atom, ord=2)) for atom in atoms)
    upper = sqrt(upper * upper + dimension * epsilon) + 1.0e-3
    feasible, best_metric, solver_status, _ = solve_at(upper)
    expansion_steps = 0
    while not feasible and expansion_steps < 12:
        upper *= 2.0
        feasible, best_metric, solver_status, _ = solve_at(upper)
        expansion_steps += 1
    if not feasible or best_metric is None:
        return {
            "status": "solver-inconclusive",
            "grade": grade,
            "dimension": dimension,
            "atom_count": len(atoms),
            "solver": solver,
            "solver_status": solver_status,
        }

    best_solver_status = solver_status
    lower = 0.0
    bisection_steps = 0
    while (
        upper - lower > gamma_tolerance
        and bisection_steps < max_bisection_steps
    ):
        midpoint = 0.5 * (lower + upper)
        midpoint_feasible, midpoint_metric, solver_status, _ = solve_at(
            midpoint
        )
        if midpoint_feasible and midpoint_metric is not None:
            upper = midpoint
            best_metric = midpoint_metric
            best_solver_status = solver_status
        else:
            lower = midpoint
        bisection_steps += 1

    metric = 0.5 * (best_metric + best_metric.T)
    metric /= float(np.trace(metric))
    metric_eigenvalues = np.linalg.eigvalsh(metric)
    metric_condition = float(metric_eigenvalues[-1] / metric_eigenvalues[0])
    direct_gamma = _direct_gamma(atoms, metric)
    gamma_upper = max(float(upper), direct_gamma)
    verified_gaps = tuple(
        gamma_upper * gamma_upper * metric - atom.T @ metric @ atom
        for atom in atoms
    )
    minimum_gap = min(
        float(np.linalg.eigvalsh(0.5 * (gap + gap.T))[0])
        for gap in verified_gaps
    )
    prefactor = float(dimension * sqrt(metric_condition))
    return {
        "status": "numerical-feasible-common-metric",
        "grade": grade,
        "dimension": dimension,
        "atom_count": len(atoms),
        "normalization_per_letter": 8.0,
        "solver": solver,
        "solver_status": best_solver_status,
        "epsilon": epsilon,
        "gamma_tolerance": gamma_tolerance,
        "gamma_lower": float(lower),
        "gamma_upper": gamma_upper,
        "direct_metric_gamma": direct_gamma,
        "bisection_steps": bisection_steps,
        "upper_expansion_steps": expansion_steps,
        "minimum_verified_gap_eigenvalue": minimum_gap,
        "metric_eigenvalues": [
            float(value) for value in metric_eigenvalues
        ],
        "metric_condition_number": metric_condition,
        "metric": _float_rows(metric),
        "prefactor": prefactor,
    }


def common_quadratic_exterior_contraction(
    points: Sequence[Sequence[float]],
    *,
    grades: Sequence[int] = (1, 2, 3),
    solver: str = "CLARABEL",
    epsilon: float = 1.0e-7,
    gamma_tolerance: float = 2.0e-3,
    validation_tolerance: float = 2.0e-6,
    max_bisection_steps: int = 32,
    max_tail_length: int = 100_000,
    solver_options: dict[str, object] | None = None,
) -> dict[str, object]:
    """Find grade-wise common quadratic metrics for a finite point alphabet."""

    validated = _validated_points(points)
    selected_grades = tuple(int(grade) for grade in grades)
    if (
        not selected_grades
        or len(set(selected_grades)) != len(selected_grades)
        or any(grade not in {1, 2, 3} for grade in selected_grades)
    ):
        raise ValueError("grades must be a nonempty subset of (1, 2, 3)")
    if (
        not isfinite(epsilon)
        or not 0.0 < epsilon < 0.1
        or not isfinite(gamma_tolerance)
        or gamma_tolerance <= 0.0
        or not isfinite(validation_tolerance)
        or validation_tolerance < 0.0
    ):
        raise ValueError("invalid SDP epsilon or numerical tolerance")
    if (
        not isinstance(max_bisection_steps, int)
        or isinstance(max_bisection_steps, bool)
        or max_bisection_steps < 1
        or not isinstance(max_tail_length, int)
        or isinstance(max_tail_length, bool)
        or max_tail_length < 1
    ):
        raise ValueError("iteration limits must be positive integers")
    try:
        import cvxpy as cp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "common quadratic exterior contraction requires cvxpy"
        ) from error

    matrices = tuple(oddcycle_matrix(*point) for point in validated)
    one_particle_alphabet = tuple(
        atom
        for matrix in matrices
        for atom in (matrix, matrix.T)
    )
    options = {} if solver_options is None else dict(solver_options)
    grade_results: dict[str, object] = {}
    for grade in selected_grades:
        normalized_atoms = tuple(
            compound_matrix(atom, grade) / 8.0
            for atom in one_particle_alphabet
        )
        grade_results[str(grade)] = _solve_grade(
            cp,
            normalized_atoms,
            grade=grade,
            solver=solver,
            epsilon=epsilon,
            gamma_tolerance=gamma_tolerance,
            validation_tolerance=validation_tolerance,
            max_bisection_steps=max_bisection_steps,
            solver_options=options,
        )

    feasible_records = tuple(
        grade_results[str(grade)] for grade in selected_grades
    )
    all_feasible = all(
        record["status"] == "numerical-feasible-common-metric"
        for record in feasible_records
    )
    minimum_length: int | None = None
    bound_at_length: float | None = None
    bound_at_previous: float | None = None
    if all_feasible and all(
        float(record["gamma_upper"]) < 1.0
        for record in feasible_records
    ):
        for length in range(1, max_tail_length + 1):
            bound = float(
                sum(
                    float(record["prefactor"])
                    * float(record["gamma_upper"]) ** length
                    for record in feasible_records
                )
            )
            if bound < 2.0:
                minimum_length = length
                bound_at_length = bound
                if length > 1:
                    bound_at_previous = float(
                        sum(
                            float(record["prefactor"])
                            * float(record["gamma_upper"]) ** (length - 1)
                            for record in feasible_records
                        )
                    )
                break

    return {
        "schema": SCHEMA,
        "status": (
            "numerical-common-quadratic-discovery"
            if all_feasible
            else "solver-inconclusive"
        ),
        "claim_scope": "numerical-discovery-only",
        "points": [list(point) for point in validated],
        "alphabet_size": len(one_particle_alphabet),
        "alphabet": "each B(p,q,r) and its transpose",
        "determinant_growth_normalization": 8.0,
        "grades": grade_results,
        "tail_bound": {
            "criterion": "sum_k prefactor_k * gamma_k**N < 2",
            "interpretation": (
                "grade1+grade2+grade3 bounded by grade4 loop "
                "plus determinant sector"
            ),
            "minimum_integer_N": minimum_length,
            "bound_at_N": bound_at_length,
            "bound_at_previous_N": bound_at_previous,
            "max_tail_length": max_tail_length,
        },
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--point",
        nargs=3,
        type=float,
        action="append",
        required=True,
        metavar=("P", "Q", "R"),
    )
    parser.add_argument("--solver", default="CLARABEL")
    parser.add_argument("--epsilon", type=float, default=1.0e-7)
    parser.add_argument("--gamma-tolerance", type=float, default=2.0e-3)
    arguments = parser.parse_args()
    result = common_quadratic_exterior_contraction(
        arguments.point,
        solver=arguments.solver,
        epsilon=arguments.epsilon,
        gamma_tolerance=arguments.gamma_tolerance,
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    _main()


__all__ = ["SCHEMA", "common_quadratic_exterior_contraction"]
