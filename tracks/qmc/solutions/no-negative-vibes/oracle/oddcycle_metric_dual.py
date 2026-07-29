"""Numerical Gordan--Stiemke duals for the oddcycle common-metric test.

For matrices ``B_j`` a strict common metric would satisfy

    R - B_j.T R B_j > 0,    R - B_j R B_j.T > 0.

Such an ``R`` cannot exist if nonzero positive-semidefinite matrices
``X_j,Y_j`` obey the exact adjoint cancellation

    sum_j (X_j - B_j X_j B_j.T
           + Y_j - B_j.T Y_j B_j) = 0.

This module only discovers floating duals.  A publishable exclusion must
rationalize the matrices and replay positive semidefiniteness exactly.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from fractions import Fraction

import numpy as np

from .symmetric_oddcycle_discovery import oddcycle_matrix


SCHEMA = "oddcycle-common-metric-dual-v1"
EXACT_SCHEMA = "oddcycle-common-metric-exact-dual-v1"

# Frozen exact interior Gordan--Stiemke certificate for p=1/1000 and 4/5,
# with q=r=1.  The first two matrices multiply the forward gaps and the
# last two multiply the transpose gaps.
_EXACT_DUAL_MULTIPLIERS = (
    (
        317075419316288950000000000000000,
        (
            (8874132379336569839575664000, -3107696861654852228353632000, 4124269078667823387536592000, -1126794231746693781082919801500, 3058394571137196390481084000),
            (-3107696861654852228353632000, 1230188951834932531802656000, -1498706380549455679042240403, 404452630947577151968817224000, -1171010494532898475611016000),
            (4124269078667823387536592000, -1498706380549455679042240403, 2037007417275567036018916000, -538419227596258360397223194000, 1597166348890010851759458000),
            (-1126794231746693781082919801500, 404452630947577151968817224000, -538419227596258360397223194000, 146259412651418245613023104000000, -414699232575387406500214000000),
            (3058394571137196390481084000, -1171010494532898475611016000, 1597166348890010851759458000, -414699232575387406500214000000, 1519921114067587094498764000),
        ),
    ),
    (
        634150838632577900000000000000,
        (
            (608784805087274784000000, 23406507453928450289000000, -805371565063373933000000, -44356759169358766285577341, -3728806931159558052000000),
            (23406507453928450289000000, 2809617973578409037508000000, -90708935958003942816000000, -5327907051889011787756000000, -413187320419442456524000000),
            (-805371565063373933000000, -90708935958003942816000000, 3043924025436373920000000, 172013414979086755375000000, 13482046829328606154000000),
            (-44356759169358766285577341, -5327907051889011787756000000, 172013414979086755375000000, 10104172630759930386081000000, 783493361130549995450000000),
            (-3728806931159558052000000, -413187320419442456524000000, 13482046829328606154000000, 783493361130549995450000000, 61461899280269450068000000),
        ),
    ),
    (
        100_000_000,
        (
            (11364322, 5692648, 3053670, -31761, 19892867),
            (5692648, 2851610, 1529661, -15906, 9964821),
            (3053670, 1529661, 820568, -8538, 5345363),
            (-31761, -15906, -8538, 140, -55611),
            (19892867, 9964821, 5345363, -55611, 34821922),
        ),
    ),
    (
        100_000_000,
        (
            (460021, 218776, -109964, 32702, 793845),
            (218776, 104077, -52301, 15558, 377564),
            (-109964, -52301, 26319, -7826, -189772),
            (32702, 15558, -7826, 2377, 56421),
            (793845, 377564, -189772, 56421, 1370035),
        ),
    ),
)


def _bareiss_determinant(matrix: Sequence[Sequence[int]]) -> int:
    """Return an exact integer determinant using fraction-free elimination."""

    work = [list(map(int, row)) for row in matrix]
    size = len(work)
    if size == 0:
        return 1
    sign = 1
    previous = 1
    for pivot_index in range(size - 1):
        if work[pivot_index][pivot_index] == 0:
            swap = next(
                (
                    row
                    for row in range(pivot_index + 1, size)
                    if work[row][pivot_index] != 0
                ),
                None,
            )
            if swap is None:
                return 0
            work[pivot_index], work[swap] = work[swap], work[pivot_index]
            sign *= -1
        pivot = work[pivot_index][pivot_index]
        for row in range(pivot_index + 1, size):
            for column in range(pivot_index + 1, size):
                numerator = (
                    work[row][column] * pivot
                    - work[row][pivot_index] * work[pivot_index][column]
                )
                work[row][column] = numerator // previous
        previous = pivot
    return sign * work[-1][-1]


def _fraction_matmul(
    left: Sequence[Sequence[Fraction]],
    right: Sequence[Sequence[Fraction]],
) -> list[list[Fraction]]:
    return [
        [
            sum(
                (left[row][inner] * right[inner][column] for inner in range(5)),
                Fraction(0),
            )
            for column in range(5)
        ]
        for row in range(5)
    ]


def _fraction_transpose(
    matrix: Sequence[Sequence[Fraction]],
) -> list[list[Fraction]]:
    return [[matrix[column][row] for column in range(5)] for row in range(5)]


def exact_no_common_metric_certificate() -> dict[str, object]:
    """Replay the exact dual proving the leading pair has no common metric."""

    point_matrices = (
        (
            (0, 0, 2, 0, 0),
            (2, 0, 0, 0, 0),
            (0, 2, 0, Fraction(1, 1000), 0),
            (0, 0, 0, 1, 1),
            (0, 0, -1, 0, 1),
        ),
        (
            (0, 0, 2, 0, 0),
            (2, 0, 0, 0, 0),
            (0, 2, 0, Fraction(4, 5), 0),
            (0, 0, 0, 1, 1),
            (0, 0, -1, 0, 1),
        ),
    )
    matrices = [
        [[Fraction(entry) for entry in row] for row in matrix]
        for matrix in point_matrices
    ]
    multipliers = [
        [
            [Fraction(entry, denominator) for entry in row]
            for row in numerator
        ]
        for denominator, numerator in _EXACT_DUAL_MULTIPLIERS
    ]
    cancellation = [[Fraction(0) for _ in range(5)] for _ in range(5)]
    for index, matrix in enumerate(matrices):
        matrix_transpose = _fraction_transpose(matrix)
        forward = multipliers[index]
        transpose = multipliers[2 + index]
        forward_image = _fraction_matmul(
            _fraction_matmul(matrix, forward), matrix_transpose
        )
        transpose_image = _fraction_matmul(
            _fraction_matmul(matrix_transpose, transpose), matrix
        )
        for row in range(5):
            for column in range(5):
                cancellation[row][column] += (
                    forward[row][column]
                    - forward_image[row][column]
                    + transpose[row][column]
                    - transpose_image[row][column]
                )
    leading_minors = [
        [
            _bareiss_determinant(
                [list(row[:size]) for row in numerator[:size]]
            )
            for size in range(1, 6)
        ]
        for _, numerator in _EXACT_DUAL_MULTIPLIERS
    ]
    trace_sum = sum(
        (
            multipliers[block][index][index]
            for block in range(4)
            for index in range(5)
        ),
        Fraction(0),
    )
    cancellation_zero = all(
        entry == 0 for row in cancellation for entry in row
    )
    positive_definite = all(
        minor > 0 for record in leading_minors for minor in record
    )
    certified = (
        cancellation_zero
        and positive_definite
        and trace_sum == 1
    )
    return {
        "schema": EXACT_SCHEMA,
        "status": (
            "exact-no-common-metric-certificate"
            if certified
            else "certificate-replay-failed"
        ),
        "points": [
            {"p": "1/1000", "q": "1", "r": "1"},
            {"p": "4/5", "q": "1", "r": "1"},
        ],
        "cancellation_exact_zero": cancellation_zero,
        "all_multipliers_positive_definite": positive_definite,
        "normalization_trace": {
            "numerator": trace_sum.numerator,
            "denominator": trace_sum.denominator,
        },
        "leading_principal_minor_numerators": leading_minors,
        "interpretation": (
            "no real symmetric R can make all forward and transpose "
            "Lyapunov gaps positive definite"
        ),
    }


def common_metric_dual(
    points: Sequence[Sequence[float]],
    *,
    solver: str = "CLARABEL",
    objective_seed: int = 0,
    tie_transpose: bool = False,
    rational_denominator: int = 0,
) -> dict[str, object]:
    """Find a normalized floating PSD dual certificate, if one exists."""

    try:
        import cvxpy as cp
    except ImportError as error:  # pragma: no cover - optional dependency
        raise RuntimeError("common_metric_dual requires cvxpy") from error

    normalized_points = tuple(
        tuple(float(value) for value in point) for point in points
    )
    if not normalized_points or any(len(point) != 3 for point in normalized_points):
        raise ValueError("points must be a nonempty sequence of triples")
    matrices = tuple(oddcycle_matrix(*point) for point in normalized_points)
    dimension = matrices[0].shape[0]
    forward = tuple(
        cp.Variable((dimension, dimension), symmetric=True)
        for _ in matrices
    )
    transpose = tuple(
        cp.Variable((dimension, dimension), symmetric=True)
        for _ in matrices
    )
    cancellation = sum(
        (
            x - matrix @ x @ matrix.T
            + y - matrix.T @ y @ matrix
        )
        for matrix, x, y in zip(matrices, forward, transpose, strict=True)
    )
    variables = forward + transpose
    if objective_seed < 0:
        probes = tuple(np.zeros((dimension, dimension)) for _ in variables)
    else:
        rng = np.random.default_rng(objective_seed)
        probes = tuple(
            0.5 * (probe + probe.T)
            for probe in rng.standard_normal(
                (2 * len(matrices), dimension, dimension)
            )
        )
    objective = sum(
        cp.sum(cp.multiply(probe, variable))
        for probe, variable in zip(probes, variables, strict=True)
    )
    constraints = [
        *(variable >> 0 for variable in variables),
        cancellation == 0,
        sum(cp.trace(variable) for variable in variables) == 1,
    ]
    if tie_transpose:
        constraints.extend(
            x == y for x, y in zip(forward, transpose, strict=True)
        )
    problem = cp.Problem(
        cp.Maximize(objective),
        constraints,
    )
    problem.solve(solver=solver)
    base = {
        "schema": SCHEMA,
        "points": [list(point) for point in normalized_points],
        "solver": solver,
        "solver_status": str(problem.status),
        "objective_seed": int(objective_seed),
        "tie_transpose": bool(tie_transpose),
    }
    if any(variable.value is None for variable in variables):
        return {**base, "status": "no-dual-found"}

    values = tuple(
        0.5 * (
            np.asarray(variable.value, dtype=float)
            + np.asarray(variable.value, dtype=float).T
        )
        for variable in variables
    )
    split = len(matrices)
    residual = sum(
        (
            x - matrix @ x @ matrix.T
            + y - matrix.T @ y @ matrix
        )
        for matrix, x, y in zip(
            matrices, values[:split], values[split:], strict=True
        )
    )
    records = []
    for kind, point, value in (
        *(
            ("forward", point, value)
            for point, value in zip(
                normalized_points, values[:split], strict=True
            )
        ),
        *(
            ("transpose", point, value)
            for point, value in zip(
                normalized_points, values[split:], strict=True
            )
        ),
    ):
        eigenvalues, eigenvectors = np.linalg.eigh(value)
        rank_one_vector = (
            eigenvectors[:, -1] * np.sqrt(max(0.0, eigenvalues[-1]))
        )
        nonzero = np.flatnonzero(np.abs(rank_one_vector) > 1.0e-12)
        if len(nonzero) and rank_one_vector[nonzero[0]] < 0.0:
            rank_one_vector = -rank_one_vector
        records.append(
            {
                "kind": kind,
                "point": list(point),
                "trace": float(np.trace(value)),
                "eigenvalues": eigenvalues.tolist(),
                "numerical_rank_1e-7": int(
                    np.count_nonzero(eigenvalues > 1.0e-7)
                ),
                "rank_one_vector": rank_one_vector.tolist(),
                "matrix": value.tolist(),
            }
        )
    result = {
        **base,
        "status": "floating-dual-found",
        "normalization_trace": float(sum(np.trace(value) for value in values)),
        "cancellation_frobenius_residual": float(
            np.linalg.norm(residual, ord="fro")
        ),
        "minimum_multiplier_eigenvalue": float(
            min(np.linalg.eigvalsh(value)[0] for value in values)
        ),
        "multipliers": records,
    }
    if rational_denominator > 0:
        result["rational_certificate"] = _rationalize_dual(
            normalized_points,
            values,
            denominator=rational_denominator,
        )
    return result


def _rationalize_dual(
    points: Sequence[Sequence[float]],
    values: Sequence[np.ndarray],
    *,
    denominator: int,
) -> dict[str, object]:
    """Project a numerical interior dual to the exact rational affine space."""

    if denominator < 1:
        raise ValueError("denominator must be positive")
    try:
        import sympy as sp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("exact dual rationalization requires sympy") from error

    point_count = len(points)
    if len(values) != 2 * point_count:
        raise ValueError("expected forward and transpose values for every point")
    dimension = values[0].shape[0]
    if dimension != 5:
        raise ValueError("the exact oddcycle rationalizer expects dimension five")

    def rational(value: float):
        return sp.Rational(str(float(value)))

    matrices = tuple(
        sp.Matrix(
            [
                [0, 0, 2, 0, 0],
                [2, 0, 0, 0, 0],
                [0, 2, 0, rational(point[0]), 0],
                [0, 0, 0, 1, rational(point[1])],
                [0, 0, -rational(point[2]), 0, 1],
            ]
        )
        for point in points
    )
    coordinates = tuple(
        (block, row, column)
        for block in range(2 * point_count)
        for row in range(dimension)
        for column in range(row, dimension)
    )
    rows = tuple(
        (row, column)
        for row in range(dimension)
        for column in range(row, dimension)
    )
    columns = []
    for block, row, column in coordinates:
        basis = sp.zeros(dimension)
        basis[row, column] = 1
        basis[column, row] = 1
        if row == column:
            basis[row, column] = 1
        point_index = block % point_count
        matrix = matrices[point_index]
        if block < point_count:
            contribution = basis - matrix * basis * matrix.T
        else:
            contribution = basis - matrix.T * basis * matrix
        columns.append(
            sp.Matrix(
                [contribution[i, j] for i, j in rows]
                + [1 if row == column else 0]
            )
        )
    system = sp.Matrix.hstack(*columns)
    target = sp.Matrix([0] * len(rows) + [1])
    _, pivot_columns = system.rref()
    if len(pivot_columns) != system.rows:
        raise RuntimeError("dual affine constraints do not have full row rank")
    free_columns = tuple(
        column
        for column in range(system.cols)
        if column not in pivot_columns
    )
    exact_vector = [sp.Integer(0)] * system.cols
    for column in free_columns:
        block, row, col = coordinates[column]
        numerator = int(round(float(values[block][row, col]) * denominator))
        exact_vector[column] = sp.Rational(numerator, denominator)
    pivot_matrix = system[:, list(pivot_columns)]
    free_matrix = system[:, list(free_columns)]
    free_vector = sp.Matrix([exact_vector[column] for column in free_columns])
    pivot_values = pivot_matrix.inv() * (target - free_matrix * free_vector)
    for column, value in zip(pivot_columns, pivot_values, strict=True):
        exact_vector[column] = sp.factor(value)

    exact_multipliers = [sp.zeros(dimension) for _ in values]
    for coordinate, value in zip(coordinates, exact_vector, strict=True):
        block, row, column = coordinate
        exact_multipliers[block][row, column] = value
        exact_multipliers[block][column, row] = value
    cancellation = sp.zeros(dimension)
    for index, matrix in enumerate(matrices):
        x = exact_multipliers[index]
        y = exact_multipliers[point_count + index]
        cancellation += (
            x - matrix * x * matrix.T
            + y - matrix.T * y * matrix
        )
    trace_sum = sum(
        sp.trace(multiplier) for multiplier in exact_multipliers
    )
    multiplier_records = []
    all_positive = True
    for multiplier in exact_multipliers:
        leading_minors = [
            sp.factor(multiplier[:size, :size].det())
            for size in range(1, dimension + 1)
        ]
        positive = all(minor > 0 for minor in leading_minors)
        all_positive = all_positive and positive
        common_denominator = sp.ilcm(
            *[
                int(sp.denom(entry))
                for entry in multiplier
            ]
        )
        numerator_matrix = multiplier * common_denominator
        multiplier_records.append(
            {
                "positive_definite_by_sylvester": positive,
                "denominator": int(common_denominator),
                "numerator": [
                    [int(numerator_matrix[row, column]) for column in range(dimension)]
                    for row in range(dimension)
                ],
                "leading_principal_minors": [
                    {
                        "numerator": int(sp.numer(minor)),
                        "denominator": int(sp.denom(minor)),
                    }
                    for minor in leading_minors
                ],
            }
        )
    return {
        "projection_denominator": int(denominator),
        "cancellation_exact_zero": cancellation == sp.zeros(dimension),
        "normalization_trace": {
            "numerator": int(sp.numer(trace_sum)),
            "denominator": int(sp.denom(trace_sum)),
        },
        "all_multipliers_positive_definite": all_positive,
        "multipliers": multiplier_records,
    }


__all__ = [
    "EXACT_SCHEMA",
    "SCHEMA",
    "common_metric_dual",
    "exact_no_common_metric_certificate",
]


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--point",
        nargs=3,
        type=float,
        action="append",
        metavar=("P", "Q", "R"),
    )
    parser.add_argument("--solver", default="CLARABEL")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--tie-transpose", action="store_true")
    parser.add_argument("--rational-denominator", type=int, default=0)
    parser.add_argument("--exact-leading-pair", action="store_true")
    parser.add_argument("--summary", action="store_true")
    arguments = parser.parse_args()
    if arguments.exact_leading_pair:
        print(
            json.dumps(
                exact_no_common_metric_certificate(),
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
        return
    if not arguments.point:
        parser.error("at least one --point is required")
    payload = common_metric_dual(
        arguments.point,
        solver=arguments.solver,
        objective_seed=arguments.seed,
        tie_transpose=arguments.tie_transpose,
        rational_denominator=arguments.rational_denominator,
    )
    if arguments.summary and payload["status"] == "floating-dual-found":
        rational_certificate = payload.get("rational_certificate")
        payload = {
            key: payload[key]
            for key in (
                "schema",
                "points",
                "solver_status",
                "objective_seed",
                "tie_transpose",
                "status",
                "normalization_trace",
                "cancellation_frobenius_residual",
                "minimum_multiplier_eigenvalue",
            )
        } | {
            "ranks": [
                record["numerical_rank_1e-7"]
                for record in payload["multipliers"]
            ],
            "traces": [
                record["trace"] for record in payload["multipliers"]
            ],
        }
        if rational_certificate is not None:
            payload["rational_certificate"] = {
                key: rational_certificate[key]
                for key in (
                    "projection_denominator",
                    "cancellation_exact_zero",
                    "normalization_trace",
                    "all_multipliers_positive_definite",
                )
            } | {
                "matrix_denominators": [
                    record["denominator"]
                    for record in rational_certificate["multipliers"]
                ],
                "smallest_leading_minor_approximations": [
                    min(
                        item["numerator"] / item["denominator"]
                        for item in record["leading_principal_minors"]
                    )
                    for record in rational_certificate["multipliers"]
                ],
                "multipliers": [
                    {
                        "denominator": record["denominator"],
                        "numerator": record["numerator"],
                    }
                    for record in rational_certificate["multipliers"]
                ],
            }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":  # pragma: no cover - CLI
    _main()
