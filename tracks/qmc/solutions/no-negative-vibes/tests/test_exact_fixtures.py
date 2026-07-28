from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import sympy as sp

from oracle.weights import classify_product


FIXTURE = Path(__file__).parents[1] / "fixtures" / "exact_certificates.json"


def _matrix(rows: list[list[str]]) -> sp.Matrix:
    return sp.Matrix([[sp.sympify(value) for value in row] for row in rows])


def test_exact_certificate_fixture_has_correct_products_and_weights() -> None:
    """Catches a corrupted machine-readable certificate before it seeds tests."""
    data = json.loads(FIXTURE.read_text())
    ids: set[str] = set()

    for case in data["cases"]:
        assert case["id"] not in ids
        ids.add(case["id"])
        matrix = _matrix(case["matrix"])
        expected_det = sp.sympify(case["expected_determinant"])
        expected_weight = sp.sympify(case["expected_weight"])

        assert sp.simplify(matrix.det() - expected_det) == 0
        assert sp.simplify((sp.eye(matrix.rows) + matrix).det() - expected_weight) == 0

        if "factors_in_product_order" in case:
            product = sp.eye(matrix.rows)
            for factor in case["factors_in_product_order"]:
                product *= _matrix(factor)
            assert sp.simplify(product - matrix) == sp.zeros(matrix.rows)

        if "metric" in case:
            metric = _matrix(case["metric"])
            adjoint = matrix.T if case["family"].startswith("O(") else matrix.conjugate().T
            assert sp.simplify(adjoint * metric * matrix - metric) == sp.zeros(matrix.rows)

        if "symplectic_form" in case:
            form = _matrix(case["symplectic_form"])
            assert sp.simplify(matrix.T * form * matrix - form) == sp.zeros(matrix.rows)


def test_az_depth_three_certificates_have_positive_slice_factors() -> None:
    """Catches an exact final matrix whose factors do not belong to the AZ slice class."""
    data = json.loads(FIXTURE.read_text())
    expected_ids = {
        "az_ai_three_spd_negative",
        "az_aiii_three_spd_negative",
        "az_ci_three_spd_negative",
        "az_a_d_three_spd_complex",
        "az_c_three_spd_complex",
    }
    cases = {case["id"]: case for case in data["cases"]}
    assert expected_ids <= cases.keys()

    for case_id in expected_ids:
        case = cases[case_id]
        constraints = case["slice_factor_constraints"]
        factors = [_matrix(rows) for rows in case["factors_in_product_order"]]
        for factor in factors:
            assert factor == factor.conjugate().T
            assert factor.is_positive_definite

            if "trs_operator" in constraints:
                operator = _matrix(constraints["trs_operator"])
                assert sp.simplify(
                    operator * factor.conjugate() * operator.conjugate().T
                    - factor
                ) == sp.zeros(factor.rows)
            if "phs_operator" in constraints:
                operator = _matrix(constraints["phs_operator"])
                assert sp.simplify(
                    operator * factor.conjugate() * operator.conjugate().T
                    - factor.inv()
                ) == sp.zeros(factor.rows)
            if "chiral_operator" in constraints:
                operator = _matrix(constraints["chiral_operator"])
                assert sp.simplify(
                    operator * factor * operator.conjugate().T - factor.inv()
                ) == sp.zeros(factor.rows)


def test_float_oracle_classifies_every_exact_fixture_consistently() -> None:
    """Catches exact certificates that the production float path misclassifies."""
    data = json.loads(FIXTURE.read_text())
    for case in data["cases"]:
        exact_matrix = _matrix(case["matrix"])
        matrix = np.array(exact_matrix.evalf(), dtype=complex)
        result = classify_product(matrix)
        assert result.classification == case["expected_sign"], case["id"]


def test_mixed_split_cone_certificate_has_exact_slice_membership() -> None:
    data = json.loads(FIXTURE.read_text())
    case = next(
        item
        for item in data["cases"]
        if item["id"] == "mixed_split_cones_rational_angle_negative"
    )

    for generator_rows, metric_rows, factor_rows in zip(
        case["slice_generators"],
        case["slice_metrics"],
        case["factors_in_product_order"],
        strict=True,
    ):
        generator = _matrix(generator_rows)
        metric = _matrix(metric_rows)
        factor = _matrix(factor_rows)
        cone = generator.T * metric + metric * generator

        assert generator**2 == sp.zeros(generator.rows)
        assert factor == sp.eye(generator.rows) + generator
        assert cone == cone.T
        assert all(entry >= 0 for entry in cone.diagonal())
        assert all(eigenvalue >= 0 for eigenvalue in cone.eigenvals())
