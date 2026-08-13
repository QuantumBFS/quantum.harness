"""Exact common-indefinite-metric contraction certificate for ``B(z)``.

This module deliberately contains no numerical optimization.  It replays the
fixed rational reflector discovered for the continuum oddcycle alphabet and
uses Sylvester's criterion plus degree-two Bernstein coefficients on
``z in [99/100, 101/100]``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sympy as sp


SCHEMA = "oddcycle-wei-common-r-contraction-v1"
Z_MIN = sp.Rational(99, 100)
Z_MAX = sp.Rational(101, 100)


def baseline_matrix(z: sp.Expr) -> sp.ImmutableMatrix:
    """Return the exact continuum atom ``B(z)``."""

    return sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, 1, 0],
            [0, 0, 0, 1, 1],
            [0, 0, -z, 0, 1],
        ]
    )


def common_metric() -> sp.ImmutableMatrix:
    """Return ``R = 2 w w^T / 83 - I`` for ``w=(4,4,1,-5,5)``."""

    w = sp.ImmutableMatrix([4, 4, 1, -5, 5])
    return sp.ImmutableMatrix(2 * w * w.T / 83 - sp.eye(5))


def _leading_principal_minors(matrix: sp.MatrixBase) -> tuple[sp.Expr, ...]:
    return tuple(
        sp.factor(matrix[:size, :size].det())
        for size in range(1, matrix.rows + 1)
    )


def _quadratic_bernstein_coefficients(
    polynomial: sp.Expr,
    *,
    z: sp.Symbol,
) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    """Return degree-two Bernstein coefficients after ``z=.99+.02t``."""

    t = sp.symbols("t", real=True)
    power = sp.Poly(
        sp.expand(polynomial.subs(z, Z_MIN + (Z_MAX - Z_MIN) * t)),
        t,
    )
    if power.degree() > 2:
        raise ValueError("only degree-at-most-two polynomials are supported")
    c0 = power.nth(0)
    c1 = power.nth(1)
    c2 = power.nth(2)
    return tuple(
        sp.factor(value)
        for value in (c0, c0 + c1 / 2, c0 + c1 + c2)
    )


def exact_common_metric_certificate() -> dict[str, object]:
    """Replay the uniform common-``R`` contraction certificate exactly."""

    z = sp.symbols("z", real=True)
    matrix = baseline_matrix(z)
    metric = common_metric()
    identity = sp.eye(5)
    if metric.T != metric or sp.ImmutableMatrix(metric * metric) != identity:
        raise RuntimeError("stored metric is not a symmetric involution")
    if metric.det() != 1 or metric.trace() != -3:
        raise RuntimeError("stored metric does not have signature (1,4)")

    deficits = (
        sp.ImmutableMatrix(metric - matrix.T * metric * matrix),
        sp.ImmutableMatrix(metric - matrix * metric * matrix.T),
    )
    minors = tuple(_leading_principal_minors(item) for item in deficits)
    expected = (
        (
            sp.Rational(153, 83),
            sp.Rational(41769, 6889),
            -3 * (1727 * z**2 - 48480 * z - 4491) / 6889,
            -(25487 * z**2 - 106080 * z + 40329) / 6889,
            -3 * (16493 * z**2 - 51480 * z + 18964) / 6889,
        ),
        (
            sp.Rational(273, 83),
            sp.Rational(41769, 6889),
            sp.Rational(153732, 6889),
            sp.Rational(192843, 6889),
            -3 * (16493 * z**2 - 51480 * z + 18964) / 6889,
        ),
    )
    if any(
        sp.simplify(actual - target) != 0
        for actual_group, expected_group in zip(minors, expected, strict=True)
        for actual, target in zip(actual_group, expected_group, strict=True)
    ):
        raise RuntimeError("leading-principal-minor identity changed")

    varying_indices = ((2, 3, 4), (4,))
    bernstein = tuple(
        tuple(
            _quadratic_bernstein_coefficients(group[index], z=z)
            for index in indices
        )
        for group, indices in zip(minors, varying_indices, strict=True)
    )
    minimum_coefficients = tuple(
        min(coefficients)
        for group in bernstein
        for coefficients in group
    )
    if min(minimum_coefficients) <= 0:
        raise RuntimeError("a Bernstein positivity margin is not strict")

    expected_varying_minima = (
        sp.Rational(1523807019, 68890000),
        sp.Rational(397103913, 68890000),
        sp.Rational(475092321, 68890000),
        sp.Rational(475092321, 68890000),
    )
    if minimum_coefficients != expected_varying_minima:
        raise RuntimeError("stored Bernstein margins changed")

    return {
        "schema": SCHEMA,
        "interval": (Z_MIN, Z_MAX),
        "metric": metric,
        "metric_signature": (1, 4),
        "leading_principal_minors": minors,
        "bernstein_coefficients": bernstein,
        "minimum_varying_bernstein_coefficients": minimum_coefficients,
        "conclusion": (
            "R-B(z).T*R*B(z) and R-B(z)*R*B(z).T are positive definite "
            "for every z in [99/100,101/100]"
        ),
    }


__all__: Sequence[str] = (
    "SCHEMA",
    "Z_MIN",
    "Z_MAX",
    "baseline_matrix",
    "common_metric",
    "exact_common_metric_certificate",
)
