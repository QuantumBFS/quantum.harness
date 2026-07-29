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


def common_metric_sdp(
    p: float,
    q: float,
    r: float,
    *,
    solver: str = "CLARABEL",
    validation_tolerance: float = 1.0e-7,
    solver_options: dict[str, object] | None = None,
) -> dict[str, object]:
    """Maximize the normalized strict common-metric margin.

    The result is deliberately labelled numerical.  A positive margin is a
    reliable *reduction* witness after direct residual validation.  A zero
    margin is only a survivor filter and must be followed by an exact dual or
    algebraic no-go before any novelty claim.
    """

    if not isfinite(validation_tolerance) or validation_tolerance < 0.0:
        raise ValueError("validation_tolerance must be finite and nonnegative")
    try:
        import cvxpy as cp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "common_metric_sdp requires the optional cvxpy package"
        ) from error

    matrix = oddcycle_matrix(p, q, r)
    dimension = matrix.shape[0]
    metric = cp.Variable((dimension, dimension), symmetric=True)
    margin = cp.Variable()
    identity = np.eye(dimension)
    forward_gap = metric - matrix.T @ metric @ matrix
    transpose_gap = metric - matrix @ metric @ matrix.T
    problem = cp.Problem(
        cp.Maximize(margin),
        [
            forward_gap - margin * identity >> 0,
            transpose_gap - margin * identity >> 0,
            cp.norm(metric, "fro") <= 1.0,
        ],
    )
    options = {} if solver_options is None else dict(solver_options)
    problem.solve(solver=solver, **options)

    base = {
        "schema": SCHEMA,
        "method": "float64-cvxpy-common-lyapunov-sdp",
        "parameters": {"p": float(p), "q": float(q), "r": float(r)},
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
    forward_value = metric_value - matrix.T @ metric_value @ matrix
    transpose_value = metric_value - matrix @ metric_value @ matrix.T
    forward_eigenvalues = np.linalg.eigvalsh(forward_value)
    transpose_eigenvalues = np.linalg.eigvalsh(transpose_value)
    metric_eigenvalues = np.linalg.eigvalsh(metric_value)
    verified_margin = float(
        min(forward_eigenvalues[0], transpose_eigenvalues[0])
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
        "forward_gap_eigenvalues": _float_list(forward_eigenvalues),
        "transpose_gap_eigenvalues": _float_list(transpose_eigenvalues),
        "metric": [_float_list(row) for row in metric_value],
        "interpretation": (
            "known-common-split-contraction-class"
            if strict
            else "discovery-survivor-only-not-an-exact-no-go"
        ),
    }


__all__ = ["SCHEMA", "common_metric_sdp"]


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
    arguments = parser.parse_args()
    payload = [
        common_metric_sdp(*point, solver=arguments.solver)
        for point in arguments.point
    ]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover - exercised as a CLI
    _main()
