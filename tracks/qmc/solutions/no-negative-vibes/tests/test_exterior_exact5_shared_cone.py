from __future__ import annotations

import sympy as sp

from oracle.exterior_exact5_shared_cone import (
    exact_simplicial_certificate,
    signed_monomial_triage,
)


def test_signed_monomial_triage_requires_one_exact_gauge_for_both_atoms() -> None:
    """Catches accepting atom-wise gauges or missing a shared sign conflict."""
    upper = sp.ImmutableMatrix([[1, -2], [0, 1]])
    lower = upper.T

    hit = signed_monomial_triage((upper, lower))
    assert hit["status"] == "exact-certificate"
    assert hit["diagonal"] == [1, -1]
    assert hit["minimum_entry"] == {"numerator": 0, "denominator": 1}

    conflict = signed_monomial_triage(
        (
            sp.ImmutableMatrix([[1, 2], [0, 1]]),
            sp.ImmutableMatrix([[1, -2], [0, 1]]),
        )
    )
    assert conflict == {
        "status": "restricted-obstruction",
        "class": "positive-diagonal-and-signed-monomial",
        "witness": {
            "kind": "conflicting-entry-sign",
            "row": 0,
            "column": 1,
            "first_atom": 0,
            "second_atom": 1,
        },
    }


def test_simplicial_certificate_rationalizes_then_replays_both_atoms_exactly() -> None:
    """Catches trusting a floating margin without exact rational replay."""
    transform = sp.ImmutableMatrix([[1, sp.Rational(1, 2)], [0, 1]])
    nonnegative = sp.ImmutableMatrix([[2, 1], [0, 3]])
    atoms = (
        sp.ImmutableMatrix(transform * nonnegative * transform.inv()),
        sp.ImmutableMatrix(transform * nonnegative.T * transform.inv()),
    )

    certificate = exact_simplicial_certificate(
        atoms,
        [[1.0, 0.50000000000001], [0.0, 1.0]],
        max_denominator=32,
    )

    assert certificate is not None
    assert certificate["status"] == "exact-certificate"
    assert certificate["method"] == "rationalized-common-simplicial"
    assert certificate["transform"] == [
        [
            {"numerator": 1, "denominator": 1},
            {"numerator": 1, "denominator": 2},
        ],
        [
            {"numerator": 0, "denominator": 1},
            {"numerator": 1, "denominator": 1},
        ],
    ]
    assert certificate["minimum_entry"] == {"numerator": 0, "denominator": 1}
