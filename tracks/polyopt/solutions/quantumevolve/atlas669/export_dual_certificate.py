"""Export exact-rational dual certificate for atlas-669 at level 2.

Uses the complete degree-2 square-free basis (29x29 moment matrix).
The numerical SDP gives value = 2.0000000027, so we target upper = 2
and verify the rationalized dual is positive definite.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import cvxpy as cp
import numpy as np

# Allow both package and direct-script imports.
try:
    from .problem import EDGES, PROBLEM_ID, VERTICES
    from .theta_relaxation import _entry_label, basis_subsets
except ImportError:
    from problem import EDGES, PROBLEM_ID, VERTICES
    from theta_relaxation import _entry_label, basis_subsets


def _build_model(order: int = 2) -> dict[str, object]:
    """Build the moment-matrix model for the complete basis through `order`."""
    basis = tuple(
        sorted(basis_subsets(len(VERTICES), order), key=lambda item: (len(item), item))
    )
    groups: dict[object, list[tuple[int, int, int]]] = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col], len(VERTICES), EDGES)
            if label is not None:
                groups[label].append((row, col, sign))
    labels = tuple(groups)
    matrices: list[np.ndarray] = []
    for label in labels:
        matrix = np.zeros((len(basis), len(basis)))
        for row, col, sign in groups[label]:
            matrix[row, col] = sign
            matrix[col, row] = sign
        matrices.append(matrix)
    basis_index = {word: index for index, word in enumerate(basis)}
    objective = np.zeros((len(basis), len(basis)))
    for vertex in VERTICES:
        singleton = basis_index[(vertex,)]
        objective[singleton, singleton] = 1.0
    coefficients = np.asarray(
        [np.sum(objective * matrix) for matrix in matrices], dtype=float
    )
    normalization = labels.index(((0,) * len(VERTICES), 0))
    return {
        "basis": basis,
        "groups": groups,
        "labels": labels,
        "matrices": matrices,
        "coefficients": coefficients,
        "normalization": normalization,
    }


def _solve_interior_dual(
    model: dict[str, object], upper: Fraction
) -> tuple[float, np.ndarray, float]:
    matrices = model["matrices"]
    coefficients = model["coefficients"]
    normalization = model["normalization"]
    size = len(model["basis"])
    dual = cp.Variable((size, size), symmetric=True)
    margin = cp.Variable()
    constraints = [
        dual - margin * np.eye(size) >> 0,
        cp.sum(cp.multiply(matrices[normalization], dual)) <= float(upper),
    ]
    constraints.extend(
        cp.sum(cp.multiply(matrix, dual)) == -coefficients[index]
        for index, matrix in enumerate(matrices)
        if index != normalization
    )
    problem = cp.Problem(cp.Maximize(margin), constraints)
    value = problem.solve(
        solver="CLARABEL",
        tol_gap_abs=1e-12,
        tol_gap_rel=1e-12,
        tol_feas=1e-12,
        max_iter=2000,
    )
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        raise RuntimeError(f"interior dual solve failed: {problem.status}")
    actual_upper = float(
        np.sum(matrices[normalization] * np.asarray(dual.value, dtype=float))
    )
    return float(value), np.asarray(dual.value, dtype=float), actual_upper


def _rationalize(
    model: dict[str, object],
    numeric: np.ndarray,
    upper: Fraction,
    denominator: int,
) -> list[list[Fraction]]:
    size = numeric.shape[0]
    rational = [
        [Fraction(round(float(numeric[row, col]) * denominator), denominator) for col in range(size)]
        for row in range(size)
    ]
    for row in range(size):
        for col in range(row):
            rational[row][col] = rational[col][row]

    groups = model["groups"]
    labels = model["labels"]
    coefficients = model["coefficients"]
    normalization = model["normalization"]
    targets = [Fraction(-int(round(value))) for value in coefficients]
    targets[normalization] = upper
    for index, label in enumerate(labels):
        members = groups[label]
        current = Fraction(0)
        for row, col, sign in members:
            current += sign * (
                rational[row][col] if row == col else 2 * rational[row][col]
            )
        row, col, sign = min(members, key=lambda item: 0 if item[0] == item[1] else 1)
        coefficient = Fraction(sign if row == col else 2 * sign)
        rational[row][col] += (targets[index] - current) / coefficient
        rational[col][row] = rational[row][col]
    return rational


def _exact_ldl(matrix: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[Fraction]]:
    size = len(matrix)
    lower = [
        [Fraction(int(row == col)) for col in range(size)] for row in range(size)
    ]
    diagonal: list[Fraction] = []
    for row in range(size):
        pivot = matrix[row][row] - sum(
            lower[row][index] ** 2 * diagonal[index] for index in range(row)
        )
        if pivot <= 0:
            raise ValueError(f"rational dual is not positive definite at pivot {row}")
        diagonal.append(pivot)
        for target_row in range(row + 1, size):
            lower[target_row][row] = (
                matrix[target_row][row]
                - sum(
                    lower[target_row][index]
                    * lower[row][index]
                    * diagonal[index]
                    for index in range(row)
                )
            ) / pivot
    return lower, diagonal


def _fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def export(
    exact_output: Path,
    numeric_output: Path,
    upper: Fraction = Fraction(2),
    denominator: int = 10_000_000,
    order: int = 2,
) -> dict[str, object]:
    model = _build_model(order)
    margin, interior_matrix, actual_upper = _solve_interior_dual(model, upper)
    rational = _rationalize(model, interior_matrix, upper, denominator)
    _, pivots = _exact_ldl(rational)

    exact_payload = {
        "schema_version": 1,
        "problem_id": PROBLEM_ID,
        "certificate_type": "exact-rational-dual-sohs",
        "source": f"complete-level-{order}-basis",
        "graph": {
            "vertex_count": len(VERTICES),
            "edges": [list(edge) for edge in sorted(EDGES)],
        },
        "basis": [list(word) for word in model["basis"]],
        "objective": "sum_i <A_i>^2",
        "upper_bound": {
            "fraction": _fraction_text(upper),
            "decimal": float(upper),
        },
        "dual_matrix": [
            [_fraction_text(value) for value in row] for row in rational
        ],
        "proof_identity": (
            "For every feasible moment matrix M=sum_l x_l B_l with x_0=1, "
            "trace(Z M)=upper_bound-objective. Exact LDL proves Z is positive "
            "definite, hence trace(Z M)>=0 and objective<=upper_bound."
        ),
        "exact_checks": {
            "affine_constraints": True,
            "ldl_positive_pivots": len(pivots),
            "minimum_ldl_pivot": _fraction_text(min(pivots)),
            "rounding_denominator": denominator,
        },
        "numeric_provenance": {
            "solver": "Clarabel via CVXPY",
            "interior_margin": margin,
            "interior_upper_value": actual_upper,
            "hierarchy_order": order,
        },
    }
    numeric_payload = {
        "schema_version": 1,
        "problem_id": PROBLEM_ID,
        "basis": [list(word) for word in model["basis"]],
        "interior_target_upper": float(upper),
        "interior_margin": margin,
        "interior_dual_matrix": interior_matrix.tolist(),
        "interior_dual_eigenvalues": np.linalg.eigvalsh(interior_matrix).tolist(),
    }
    exact_output.parent.mkdir(parents=True, exist_ok=True)
    numeric_output.parent.mkdir(parents=True, exist_ok=True)
    exact_output.write_text(
        json.dumps(exact_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    numeric_output.write_text(
        json.dumps(numeric_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return exact_payload


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-output", type=Path, default=Path("certificates/dual_certificate_exact.json"))
    parser.add_argument("--numeric-output", type=Path, default=Path("certificates/dual_certificate_numeric.json"))
    parser.add_argument("--upper", default="2")
    parser.add_argument("--denominator", type=int, default=10_000_000)
    parser.add_argument("--order", type=int, default=2)
    args = parser.parse_args()
    payload = export(
        args.exact_output,
        args.numeric_output,
        Fraction(args.upper),
        args.denominator,
        args.order,
    )
    print(
        json.dumps(
            {
                "upper_bound": payload["upper_bound"],
                "exact_checks": payload["exact_checks"],
                "exact_output": str(args.exact_output),
                "numeric_output": str(args.numeric_output),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
