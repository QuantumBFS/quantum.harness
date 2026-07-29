from fractions import Fraction

import pytest

from trottercert.anticommuting import (
    certify_anticommuting_partition,
    discover_anticommuting_partition,
    sqrt_fraction_upper,
    symplectic_anticommutes,
)
from trottercert.intervals import RationalInterval


def test_symplectic_anticommutation() -> None:
    x = (1, 0)
    y = (1, 1)
    z = (0, 1)
    assert symplectic_anticommutes(x, y)
    assert symplectic_anticommutes(y, z)
    assert symplectic_anticommutes(z, x)
    assert not symplectic_anticommutes(x, x)


def test_rational_square_root_is_outward() -> None:
    bound = sqrt_fraction_upper(Fraction(2), decimal_places=12)
    assert bound * bound >= 2
    assert bound - Fraction(1414213562373, 10**12) <= Fraction(1, 10**12)


def test_exact_group_bound_uses_euclidean_norm() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(1),
        (1, 1): RationalInterval.point(2),
        (0, 1): RationalInterval.point(2),
    }
    certificate = certify_anticommuting_partition(
        coefficients,
        (((1, 0), (1, 1), (0, 1)),),
    )
    assert certificate.bound == 3
    assert certificate.groups[0].term_indices == (1, 2, 0)


def test_corrupt_commuting_group_is_rejected() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(1),
        (2, 0): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="do not anticommute"):
        certify_anticommuting_partition(
            coefficients,
            (((1, 0), (2, 0)),),
        )


def test_partition_coverage_rejects_duplicates_and_omissions() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(1),
        (1, 1): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="coverage contains duplicate"):
        certify_anticommuting_partition(
            coefficients,
            (((1, 0),), ((1, 0), (1, 1))),
        )
    with pytest.raises(ValueError, match="coverage differs"):
        certify_anticommuting_partition(
            coefficients,
            (((1, 0),),),
        )


def test_discovery_is_deterministic_and_covers_terms() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(3),
        (1, 1): RationalInterval.point(2),
        (0, 1): RationalInterval.point(1),
    }
    first = discover_anticommuting_partition(
        coefficients,
        max_group_size=3,
    )
    second = discover_anticommuting_partition(
        coefficients,
        max_group_size=3,
    )
    assert first == second
    certificate = certify_anticommuting_partition(coefficients, first)
    assert set(certificate.paulis) == set(coefficients)
    assert certificate.bound == sqrt_fraction_upper(Fraction(14))
