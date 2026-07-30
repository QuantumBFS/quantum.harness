"""Numerical common-metric exclusion filter for general oddcycle atoms.

This module is a discovery filter, not an exact novelty certificate.  It
solves the homogeneous Lyapunov problem

    R - B.T R B >= t I,
    R - B R B.T >= t I,
    ||R||_F <= 1,

over real symmetric ``R``.  A strictly positive optimum places both ``B``
and ``B.T`` in one real split-contraction semigroup after a similarity
transform.  Such a point is therefore already covered by the known
semigroup mechanism and should be discarded before expensive exact work.

``cvxpy`` is imported lazily so the exact oracle/test suite does not acquire
a mandatory SDP dependency.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from math import isfinite

import numpy as np

from .symmetric_oddcycle_discovery import oddcycle_matrix


SCHEMA = "oddcycle-common-metric-sdp-v1"


def _float_list(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values]


def _solve_common_metric_sdp(
    matrices: Sequence[np.ndarray],
    *,
    solver: str = "CLARABEL",
    validation_tolerance: float = 1.0e-7,
    solver_options: dict[str, object] | None = None,
) -> dict[str, object]:
    if not isfinite(validation_tolerance) or validation_tolerance < 0.0:
        raise ValueError("validation_tolerance must be finite and nonnegative")
    if not matrices:
        raise ValueError("at least one matrix is required")
    try:
        import cvxpy as cp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "common_metric_sdp requires the optional cvxpy package"
        ) from error

    exact_matrices = tuple(np.asarray(matrix, dtype=float) for matrix in matrices)
    dimension = exact_matrices[0].shape[0]
    if any(
        matrix.shape != (dimension, dimension)
        or not np.all(np.isfinite(matrix))
        for matrix in exact_matrices
    ):
        raise ValueError("all matrices must be finite square matrices of one size")
    metric = cp.Variable((dimension, dimension), symmetric=True)
    margin = cp.Variable()
    identity = np.eye(dimension)
    gap_expressions = tuple(
        (
            metric - matrix.T @ metric @ matrix,
            metric - matrix @ metric @ matrix.T,
        )
        for matrix in exact_matrices
    )
    problem = cp.Problem(
        cp.Maximize(margin),
        [
            *(
                gap - margin * identity >> 0
                for pair in gap_expressions
                for gap in pair
            ),
            cp.norm(metric, "fro") <= 1.0,
        ],
    )
    options = {} if solver_options is None else dict(solver_options)
    problem.solve(solver=solver, **options)

    base = {
        "schema": SCHEMA,
        "method": "float64-cvxpy-common-lyapunov-sdp",
        "matrix_count": len(exact_matrices),
        "solver": solver,
        "solver_status": str(problem.status),
        "validation_tolerance": float(validation_tolerance),
    }
    if metric.value is None or margin.value is None:
        return {
            **base,
            "status": "solver-inconclusive",
            "objective_margin": None,
            "metric": None,
        }

    metric_value = np.asarray(metric.value, dtype=float)
    metric_value = 0.5 * (metric_value + metric_value.T)
    gap_eigenvalues = []
    for matrix in exact_matrices:
        forward_value = metric_value - matrix.T @ metric_value @ matrix
        transpose_value = metric_value - matrix @ metric_value @ matrix.T
        gap_eigenvalues.append(
            {
                "forward": _float_list(np.linalg.eigvalsh(forward_value)),
                "transpose": _float_list(np.linalg.eigvalsh(transpose_value)),
            }
        )
    metric_eigenvalues = np.linalg.eigvalsh(metric_value)
    verified_margin = float(
        min(
            min(record["forward"][0], record["transpose"][0])
            for record in gap_eigenvalues
        )
    )
    objective_margin = float(margin.value)
    strict = (
        problem.status in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}
        and objective_margin > validation_tolerance
        and verified_margin > validation_tolerance
    )
    if strict:
        status = "strict-common-metric-found"
    elif problem.status == cp.OPTIMAL:
        status = "no-strict-common-metric-numerically"
    else:
        status = "solver-inconclusive"

    positive_inertia = int(np.count_nonzero(metric_eigenvalues > validation_tolerance))
    negative_inertia = int(np.count_nonzero(metric_eigenvalues < -validation_tolerance))
    zero_inertia = dimension - positive_inertia - negative_inertia
    return {
        **base,
        "status": status,
        "objective_margin": objective_margin,
        "verified_margin": verified_margin,
        "metric_frobenius_norm": float(np.linalg.norm(metric_value, ord="fro")),
        "metric_eigenvalues": _float_list(metric_eigenvalues),
        "metric_inertia": {
            "positive": positive_inertia,
            "negative": negative_inertia,
            "zero": zero_inertia,
        },
        "metric_determinant": float(np.linalg.det(metric_value)),
        "gap_eigenvalues": gap_eigenvalues,
        "metric": [_float_list(row) for row in metric_value],
        "interpretation": (
            "known-common-split-contraction-class"
            if strict
            else "discovery-survivor-only-not-an-exact-no-go"
        ),
    }


def common_metric_sdp(
    p: float,
    q: float,
    r: float,
    *,
    solver: str = "CLARABEL",
    validation_tolerance: float = 1.0e-7,
    solver_options: dict[str, object] | None = None,
) -> dict[str, object]:
    """Maximize the normalized strict common-metric margin for one point."""

    result = _solve_common_metric_sdp(
        (oddcycle_matrix(p, q, r),),
        solver=solver,
        validation_tolerance=validation_tolerance,
        solver_options=solver_options,
    )
    gaps = result.pop("gap_eigenvalues", None)
    if gaps:
        result["forward_gap_eigenvalues"] = gaps[0]["forward"]
        result["transpose_gap_eigenvalues"] = gaps[0]["transpose"]
    result["parameters"] = {"p": float(p), "q": float(q), "r": float(r)}
    return result


def common_metric_sdp_for_points(
    points: Sequence[Sequence[float]],
    *,
    solver: str = "CLARABEL",
    validation_tolerance: float = 1.0e-7,
    solver_options: dict[str, object] | None = None,
) -> dict[str, object]:
    """Screen whether several oddcycle transpose pairs share one metric."""

    normalized_points = tuple(
        tuple(float(value) for value in point) for point in points
    )
    if not normalized_points or any(
        len(point) != 3 for point in normalized_points
    ):
        raise ValueError("points must be a nonempty sequence of (p,q,r) triples")
    result = _solve_common_metric_sdp(
        tuple(oddcycle_matrix(*point) for point in normalized_points),
        solver=solver,
        validation_tolerance=validation_tolerance,
        solver_options=solver_options,
    )
    result["points"] = [
        {"p": point[0], "q": point[1], "r": point[2]}
        for point in normalized_points
    ]
    return result


__all__ = ["SCHEMA", "common_metric_sdp", "common_metric_sdp_for_points"]


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Numerically screen oddcycle points for a common metric."
    )
    parser.add_argument(
        "--point",
        nargs=3,
        type=float,
        action="append",
        metavar=("P", "Q", "R"),
        required=True,
    )
    parser.add_argument("--solver", default="CLARABEL")
    parser.add_argument(
        "--joint",
        action="store_true",
        help="screen all --point values as one joint alphabet",
    )
    parser.add_argument("--summary", action="store_true")
    arguments = parser.parse_args()
    if arguments.joint:
        payload = common_metric_sdp_for_points(
            arguments.point,
            solver=arguments.solver,
        )
    else:
        payload = [
            common_metric_sdp(*point, solver=arguments.solver)
            for point in arguments.point
        ]
    if arguments.summary:
        records = payload if isinstance(payload, list) else [payload]
        payload = [
            {
                key: record.get(key)
                for key in (
                    "parameters",
                    "points",
                    "status",
                    "objective_margin",
                    "verified_margin",
                    "metric_inertia",
                )
                if key in record
            }
            for record in records
        ]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover - exercised as a CLI
    _main()
