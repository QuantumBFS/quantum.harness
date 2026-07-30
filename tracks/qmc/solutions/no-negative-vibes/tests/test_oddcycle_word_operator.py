import sympy as sp

from oracle.fock_basis import one_body_operator
from oracle.oddcycle_word_operator import (
    NormalOrderedLabel,
    normal_ordered_coordinates,
    normal_ordered_labels,
    normal_ordered_monomial,
    reconstruct_normal_ordered,
)


def test_five_mode_basis_has_252_labels_and_unit_sector_pivots():
    labels = normal_ordered_labels(5)
    assert len(labels) == 252
    assert len(set(labels)) == 252
    for label in labels:
        operator = normal_ordered_monomial(5, label)
        row = sum(1 << index for index in label.create)
        column = sum(1 << index for index in label.annihilate)
        assert operator[row, column] in {-1, 1}


def test_exact_normal_ordered_coordinates_round_trip():
    one_body = sp.ImmutableMatrix(
        [[1, 2, 0, 0, 0], [3, -1, 0, 0, 0], *([0] * 5 for _ in range(3))]
    )
    density_01 = normal_ordered_monomial(
        5, NormalOrderedLabel(create=(0, 1), annihilate=(0, 1))
    )
    operator = one_body_operator(one_body) + sp.Rational(7, 5) * density_01
    coordinates = normal_ordered_coordinates(operator, 5)
    assert reconstruct_normal_ordered(coordinates, 5) == operator
    assert all(
        value == 0 for label, value in coordinates.items() if label.body_order > 2
    )
