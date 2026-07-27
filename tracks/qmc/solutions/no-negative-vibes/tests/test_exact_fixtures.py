from __future__ import annotations

import json
from pathlib import Path

import sympy as sp


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
