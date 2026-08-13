from __future__ import annotations

import sympy as sp

from oracle.tn_novelty import (
    anticommutant_constraint_matrix,
    common_anticommutant_basis,
    diagonal_majorana_generators,
)


def _flatten(matrix: sp.Matrix) -> sp.Matrix:
    entries = [
        matrix[row, column]
        for row in range(matrix.rows)
        for column in range(matrix.cols)
    ]
    return sp.Matrix(entries)


def test_common_majorana_anticommutant_has_only_local_x_z_blocks() -> None:
    sites = 3
    constraints = sp.Matrix(anticommutant_constraint_matrix(sites))
    expected_basis = [
        sp.Matrix(matrix) for matrix in common_anticommutant_basis(sites)
    ]

    assert len(constraints.nullspace()) == 2 * sites
    assert sp.Matrix.hstack(*[_flatten(matrix) for matrix in expected_basis]).rank() == (
        2 * sites
    )
    for matrix in expected_basis:
        assert constraints * _flatten(matrix) == sp.zeros(constraints.rows, 1)


def test_local_anticommutant_cannot_square_antilinearly_to_minus_identity() -> None:
    a, b, a_bar, b_bar = sp.symbols("a b a_bar b_bar")
    block = sp.Matrix([[a, b], [b, -a]])
    conjugate_block = sp.Matrix([[a_bar, b_bar], [b_bar, -a_bar]])

    product = sp.expand(block * conjugate_block)
    assert product[0, 0] == a * a_bar + b * b_bar
    assert product[1, 1] == a * a_bar + b * b_bar

    # For a_bar=conjugate(a) and b_bar=conjugate(b), this diagonal is
    # |a|^2+|b|^2 >= 0, so it cannot equal the -1 required by K K_bar=-I.


def test_site_generators_are_exactly_skew_and_square_to_projectors() -> None:
    for generator in diagonal_majorana_generators(4):
        matrix = sp.Matrix(generator)
        square = matrix * matrix
        assert matrix.T == -matrix
        assert square.rank() == 2
        assert square.trace() == -2
        assert all(entry in (0, -1) for entry in square.diagonal())
