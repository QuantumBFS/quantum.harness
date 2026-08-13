from collections import Counter

import sympy as sp

from oracle.oddcycle_local_targets import first_target_library
from oracle.oddcycle_word_operator import (
    NormalOrderedLabel,
    normal_ordered_coordinates,
)


def _target(family: str, **parameters: sp.Rational):
    return next(
        target
        for target in first_target_library()
        if target.family == family and dict(target.parameters) == parameters
    )


def test_first_target_library_is_exact_local_and_interacting():
    targets = first_target_library()
    assert Counter(target.family for target in targets) == {
        "path-t-v": 18,
        "ring-frustrated-t-v": 18,
        "path-correlated-hop": 6,
        "path-pair-hop": 6,
    }
    assert len({target.target_id for target in targets}) == len(targets)
    assert tuple(target.target_id for target in first_target_library()) == tuple(
        target.target_id for target in targets
    )

    for target in targets:
        assert target.formula
        assert all(
            isinstance(value, sp.Rational) for _, value in target.parameters
        )
        assert isinstance(target.hamiltonian, sp.ImmutableSparseMatrix)
        assert target.hamiltonian == target.hamiltonian.T
        coordinates = normal_ordered_coordinates(target.hamiltonian, 5)
        assert any(
            value != 0 and label.body_order == 2
            for label, value in coordinates.items()
        )
        assert all(
            value == 0 or target.locality.allows_support(label.support)
            for label, value in coordinates.items()
            if label.body_order > 0
        )


def test_named_target_formulas_have_the_declared_exact_coefficients():
    path = normal_ordered_coordinates(
        _target("path-t-v", t=sp.Rational(1, 2), V=sp.Rational(-2)).hamiltonian,
        5,
    )
    assert path[NormalOrderedLabel((0,), (1,))] == sp.Rational(-1, 2)
    assert path[NormalOrderedLabel((0, 1), (0, 1))] == sp.Rational(-2)
    assert path[NormalOrderedLabel((0,), (4,))] == 0

    ring = normal_ordered_coordinates(
        _target(
            "ring-frustrated-t-v",
            t=sp.Rational(2),
            V=sp.Rational(1, 2),
        ).hamiltonian,
        5,
    )
    assert ring[NormalOrderedLabel((0,), (1,))] == sp.Rational(-2)
    assert ring[NormalOrderedLabel((0,), (4,))] == sp.Rational(2)
    assert ring[NormalOrderedLabel((0, 4), (0, 4))] == sp.Rational(1, 2)

    correlated = normal_ordered_coordinates(
        _target("path-correlated-hop", J=sp.Rational(-1, 2)).hamiltonian,
        5,
    )
    assert correlated[
        NormalOrderedLabel(create=(0, 1), annihilate=(1, 2))
    ] == sp.Rational(-1, 2)
    assert correlated[
        NormalOrderedLabel(create=(1, 2), annihilate=(0, 1))
    ] == sp.Rational(-1, 2)

    pair = _target("path-pair-hop", J=sp.Rational(2))
    pair_coordinates = normal_ordered_coordinates(pair.hamiltonian, 5)
    assert pair.locality.name == "path-arc4-target"
    assert pair.locality.allowed_supports == (
        frozenset((0, 1, 2, 3)),
        frozenset((1, 2, 3, 4)),
    )
    assert pair_coordinates[
        NormalOrderedLabel(create=(0, 1), annihilate=(2, 3))
    ] == sp.Rational(2)
    assert pair_coordinates[
        NormalOrderedLabel(create=(2, 3), annihilate=(0, 1))
    ] == sp.Rational(2)
