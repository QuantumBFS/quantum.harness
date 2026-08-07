from __future__ import annotations

from fractions import Fraction

import pytest

from trottercert.intervals import RationalInterval
from trottercert.support_groups import (
    build_d5_payload,
    canonical_gzip_bytes,
    certify_support_partition,
    decode_d5_gzip,
    discover_support_partition,
    verify_d5_payload,
)


def test_support_certificate_rejects_cross_support_pair() -> None:
    coefficients = {
        (1, 0): RationalInterval.point(1),
        (2, 0): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="same support"):
        certify_support_partition(coefficients, (((1, 0), (2, 0)),))


def test_support_certificate_rejects_commuting_pair() -> None:
    coefficients = {
        (3, 0): RationalInterval.point(1),
        (0, 3): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="anticommute"):
        certify_support_partition(coefficients, (((3, 0), (0, 3)),))


def test_discovery_and_certification_cover_each_term_once() -> None:
    coefficients = {
        (3, 0): RationalInterval.point(Fraction(3, 7)),
        (1, 2): RationalInterval.point(Fraction(-2, 9)),
        (2, 1): RationalInterval.point(Fraction(5, 11)),
        (4, 0): RationalInterval.point(Fraction(1, 13)),
    }
    groups = discover_support_partition(coefficients, max_group_size=3)
    certificate = certify_support_partition(coefficients, groups)
    flattened = [pauli for group in groups for pauli in group]
    assert sorted(flattened) == sorted(coefficients)
    assert certificate.bound <= sum(
        (coefficient.abs_upper() for coefficient in coefficients.values()),
        Fraction(),
    )


def test_discovery_scores_require_exact_coverage() -> None:
    coefficients = {
        (1, 2): RationalInterval.point(1),
        (2, 1): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="scores.*cover"):
        discover_support_partition(
            coefficients,
            discovery_scores={(1, 2): Fraction(1)},
        )


def test_support_certificate_rejects_missing_coverage() -> None:
    coefficients = {
        (1, 2): RationalInterval.point(1),
        (2, 1): RationalInterval.point(1),
    }
    with pytest.raises(ValueError, match="coverage"):
        certify_support_partition(coefficients, (((1, 2),),))


def test_d5_sidecar_is_deterministic_and_rejects_missing_term() -> None:
    coefficients = {
        (1, 2): RationalInterval.point(Fraction(3, 7)),
        (2, 1): RationalInterval.point(Fraction(-2, 9)),
    }
    first = build_d5_payload(coefficients)
    second = build_d5_payload(coefficients)
    encoded = canonical_gzip_bytes(first)
    assert encoded == canonical_gzip_bytes(second)
    assert encoded[9] == 0x13
    assert decode_d5_gzip(encoded) == first
    verify_d5_payload(first)
    groups = first["groups"]
    assert isinstance(groups, list)
    first_group = groups[0]
    assert isinstance(first_group, list)
    indices = first_group[0]
    assert isinstance(indices, list)
    indices.pop()
    with pytest.raises(ValueError, match="coverage"):
        verify_d5_payload(first)
