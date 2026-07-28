from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import sympy as sp

from oracle.majorana import (
    canonical_reflection_structures,
    reflection_structure_residual,
    shared_reality_rotation,
    small_angle_negative_pair,
    spin_trace_weight,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "majorana_trace_certificates.json"
)


def _matrix(rows: list[list[str]]) -> sp.Matrix:
    return sp.Matrix([[sp.sympify(value) for value in row] for row in rows])


def _majorana_operators() -> list[sp.Matrix]:
    identity = sp.eye(2)
    pauli_x = sp.Matrix([[0, 1], [1, 0]])
    pauli_y = sp.Matrix([[0, -sp.I], [sp.I, 0]])
    pauli_z = sp.diag(1, -1)
    return [
        sp.kronecker_product(pauli_x, identity),
        sp.kronecker_product(pauli_y, identity),
        sp.kronecker_product(pauli_z, pauli_x),
        sp.kronecker_product(pauli_z, pauli_y),
    ]


def _quadratic_operator(generator: sp.Matrix) -> sp.Matrix:
    gamma = _majorana_operators()
    result = sp.zeros(4)
    for left in range(4):
        for right in range(left + 1, 4):
            result += (
                sp.Rational(1, 2)
                * generator[left, right]
                * gamma[left]
                * gamma[right]
            )
    return sp.simplify(result)


def test_opposite_cone_certificate_obeys_both_majorana_cones() -> None:
    case = json.loads(FIXTURE.read_text())["cases"][0]
    j1 = _matrix(case["j1"])
    j2_values = [_matrix(case["j2_first"]), _matrix(case["j2_second"])]
    generators = [
        _matrix(rows) for rows in case["generators_in_product_order"]
    ]

    assert j2_values[1] == -j2_values[0]
    for generator, j2 in zip(generators, j2_values):
        assert generator.T == -generator
        assert sp.simplify(
            j1.T * generator * j1 - generator.conjugate()
        ) == sp.zeros(4)
        cone_matrix = sp.simplify(
            sp.I * (j2 * generator - generator.conjugate() * j2)
        )
        assert cone_matrix.is_negative_semidefinite


def test_opposite_cone_certificate_has_exact_negative_spin_trace() -> None:
    case = json.loads(FIXTURE.read_text())["cases"][0]
    generators = [
        _matrix(rows) for rows in case["generators_in_product_order"]
    ]
    h_first, h_second = [
        _quadratic_operator(generator) for generator in generators
    ]
    even = [0, 3]
    odd = [1, 2]
    first_even = h_first.extract(even, even)
    second_even = h_second.extract(even, even)
    first_odd = h_first.extract(odd, odd)
    second_odd = h_second.extract(odd, odd)

    assert sp.simplify(first_even**2 + sp.pi**2 * sp.eye(2)) == sp.zeros(2)
    assert sp.simplify(second_even**2 - sp.eye(2)) == sp.zeros(2)
    assert sp.trace(second_even) == 0
    assert second_odd == -first_odd

    exact_weight = sp.sympify(case["expected_trace_weight"])
    derived_weight = 2 - 2 * sp.cosh(1)
    assert sp.simplify(exact_weight - derived_weight) == 0
    assert exact_weight.is_negative


def test_float_majorana_oracle_matches_exact_trace_certificate() -> None:
    case = json.loads(FIXTURE.read_text())["cases"][0]
    generators = [
        np.array(_matrix(rows).evalf(), dtype=complex)
        for rows in case["generators_in_product_order"]
    ]
    result = spin_trace_weight(generators)
    expected = complex(sp.N(sp.sympify(case["expected_trace_weight"]), 30))

    assert result.classification == case["expected_sign"]
    assert np.allclose(result.value, expected, rtol=1e-12, atol=1e-12)
    assert result.square_identity_residual < 1e-12


def test_small_angle_family_has_exact_negative_trace_formula() -> None:
    case = json.loads(FIXTURE.read_text())["cases"][1]
    q, theta = sp.symbols("q theta", positive=True, real=True)
    cosine = sp.cos(theta / 2)
    sine = sp.sin(theta / 2)

    # On the rank-one cone boundary, each odd-parity exponential is lower
    # triangular with off-diagonal magnitude 2*sinh(q).  The even sector
    # contributes -2, while the rotated odd sector gives the expression below.
    odd_trace = 2 * (cosine**2 + sine**2) - (
        8 * cosine * sine * sp.sinh(q) ** 2
    )
    derived_weight = sp.trigsimp(-2 + odd_trace)
    expected_weight = sp.sympify(
        case["expected_trace_weight"],
        locals={"q": q, "theta": theta},
    )

    assert sp.trigsimp(derived_weight - expected_weight) == 0


def test_small_angle_family_obeys_its_two_cone_constraints() -> None:
    angle = 0.137
    first, second = small_angle_negative_pair(angle=angle)
    j1, j2 = canonical_reflection_structures(2)
    rotation = shared_reality_rotation(2, angle=angle)
    rotated_j2 = rotation @ j2 @ rotation.T

    assert reflection_structure_residual(
        first,
        j1=j1,
        j2=j2,
        require_cone=True,
    ) < 1e-12
    assert reflection_structure_residual(
        second,
        j1=j1,
        j2=rotated_j2,
        require_cone=True,
    ) < 1e-12


def test_float_oracle_matches_small_angle_negative_family() -> None:
    q = 0.7
    for angle in [1e-6, 1e-3, 0.1, 1.0, 3.0]:
        generators = small_angle_negative_pair(angle=angle, q=q)
        result = spin_trace_weight(list(generators))
        expected = -4.0 * np.sin(angle) * np.sinh(q) ** 2

        assert result.classification == "negative"
        assert np.allclose(result.value, expected, rtol=1e-9, atol=1e-12)
        assert result.square_identity_residual < 1e-9
