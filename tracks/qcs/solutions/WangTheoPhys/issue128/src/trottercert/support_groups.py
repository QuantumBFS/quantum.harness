from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
import gzip
import json
from math import lcm
from typing import Any

from .anticommuting import (
    AnticommutingPartitionCertificate,
    certify_anticommuting_partition,
    symplectic_anticommutes,
)
from .intervals import RationalInterval
from .local_commutators import SymplecticPauli


def _support(pauli: SymplecticPauli) -> int:
    return pauli[0] | pauli[1]


def discover_support_partition(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    *,
    max_group_size: int = 10,
    discovery_scores: Mapping[SymplecticPauli, Fraction] | None = None,
) -> tuple[tuple[SymplecticPauli, ...], ...]:
    """Discover anticommuting groups without mixing Pauli supports."""

    if max_group_size < 1:
        raise ValueError("maximum group size must be positive")
    if discovery_scores is not None and set(discovery_scores) != set(
        coefficients
    ):
        raise ValueError("discovery scores must cover the coefficient map")
    buckets: dict[int, dict[SymplecticPauli, RationalInterval]] = {}
    for pauli, coefficient in coefficients.items():
        buckets.setdefault(_support(pauli), {})[pauli] = coefficient
    groups: list[tuple[SymplecticPauli, ...]] = []
    for support in sorted(buckets):
        bucket = buckets[support]
        ordered = tuple(
            sorted(
                bucket,
                key=lambda pauli: (
                    -(
                        abs(discovery_scores[pauli])
                        if discovery_scores is not None
                        else abs(bucket[pauli].midpoint())
                    ),
                    pauli,
                ),
            )
        )
        used: set[SymplecticPauli] = set()
        for position, pauli in enumerate(ordered):
            if pauli in used:
                continue
            group = [pauli]
            used.add(pauli)
            for candidate in ordered[position + 1 :]:
                if candidate in used:
                    continue
                if all(
                    symplectic_anticommutes(candidate, member)
                    for member in group
                ):
                    group.append(candidate)
                    used.add(candidate)
                    if len(group) == max_group_size:
                        break
            groups.append(tuple(group))
    return tuple(groups)


def certify_support_partition(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    groups: Sequence[Sequence[SymplecticPauli]],
    *,
    sqrt_decimal_places: int = 30,
) -> AnticommutingPartitionCertificate:
    """Verify coverage, equal supports, and pairwise anticommutation."""

    flattened = tuple(pauli for group in groups for pauli in group)
    if len(flattened) != len(set(flattened)):
        raise ValueError("partition coverage contains duplicate terms")
    if set(flattened) != set(coefficients):
        raise ValueError("partition coverage differs from coefficient map")
    for group in groups:
        if not group:
            raise ValueError("anticommuting group must be nonempty")
        supports = {_support(pauli) for pauli in group}
        if len(supports) != 1:
            raise ValueError("group members must have the same support")
    return certify_anticommuting_partition(
        coefficients,
        groups,
        sqrt_decimal_places=sqrt_decimal_places,
    )


def _pair(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def canonical_gzip_bytes(payload: object) -> bytes:
    """Return deterministic gzip bytes for a canonical JSON payload."""

    compressed = bytearray(
        gzip.compress(_canonical_json_bytes(payload), compresslevel=9, mtime=0)
    )
    # CPython has changed how ``gzip.compress(..., mtime=0)`` chooses the
    # RFC 1952 OS header byte.  Python 3.14 emits 0xff here, whereas the
    # frozen schema-v3 sidecar was produced with 0x13 on macOS.  The byte has
    # no effect on decompression, but it is part of the proof artifact's
    # SHA-256.  Pin the historical canonical value explicitly so rebuilding
    # remains byte-for-byte stable across Python and platform upgrades.
    compressed[9] = 0x13
    return bytes(compressed)


def build_d5_payload(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    groups: Sequence[Sequence[SymplecticPauli]] | None = None,
) -> dict[str, object]:
    selected_groups = (
        discover_support_partition(coefficients, max_group_size=10)
        if groups is None
        else tuple(tuple(group) for group in groups)
    )
    certificate = certify_support_partition(coefficients, selected_groups)
    coefficient_denominator = 1
    for interval in certificate.coefficients:
        coefficient_denominator = lcm(
            coefficient_denominator,
            interval.lower.denominator,
            interval.upper.denominator,
        )
    sqrt_denominator = 1
    for group in certificate.groups:
        sqrt_denominator = lcm(sqrt_denominator, group.bound.denominator)
    return {
        "schema_version": 1,
        "kind": "issue128_exact_d5_support_partition",
        "coefficient_denominator": coefficient_denominator,
        "terms": [
            [
                pauli[0],
                pauli[1],
                interval.lower.numerator
                * (coefficient_denominator // interval.lower.denominator),
                interval.upper.numerator
                * (coefficient_denominator // interval.upper.denominator),
            ]
            for pauli, interval in zip(
                certificate.paulis,
                certificate.coefficients,
            )
        ],
        "sqrt_denominator": sqrt_denominator,
        "groups": [
            [
                list(group.term_indices),
                group.bound.numerator
                * (sqrt_denominator // group.bound.denominator),
            ]
            for group in certificate.groups
        ],
        "term_count": len(certificate.paulis),
        "group_count": len(certificate.groups),
        "cell_bound": _pair(certificate.bound),
        "site_bound": _pair(certificate.bound / 4),
    }


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _fraction_pair(value: object, *, field: str) -> Fraction:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must be a rational pair")
    numerator = _integer(value[0], field=f"{field} numerator")
    denominator = _integer(value[1], field=f"{field} denominator")
    if denominator <= 0:
        raise ValueError(f"{field} denominator must be positive")
    return Fraction(numerator, denominator)


def verify_d5_payload(
    payload: Mapping[str, object],
) -> AnticommutingPartitionCertificate:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported D5 sidecar schema")
    if payload.get("kind") != "issue128_exact_d5_support_partition":
        raise ValueError("unexpected D5 sidecar kind")
    coefficient_denominator = _integer(
        payload.get("coefficient_denominator"),
        field="coefficient denominator",
    )
    sqrt_denominator = _integer(
        payload.get("sqrt_denominator"),
        field="sqrt denominator",
    )
    if coefficient_denominator <= 0 or sqrt_denominator <= 0:
        raise ValueError("D5 sidecar denominators must be positive")
    raw_terms = payload.get("terms")
    raw_groups = payload.get("groups")
    if not isinstance(raw_terms, list) or not isinstance(raw_groups, list):
        raise ValueError("D5 sidecar terms and groups must be lists")

    paulis: list[SymplecticPauli] = []
    coefficients: dict[SymplecticPauli, RationalInterval] = {}
    for raw_term in raw_terms:
        if not isinstance(raw_term, list) or len(raw_term) != 4:
            raise ValueError("D5 sidecar term is malformed")
        pauli = (
            _integer(raw_term[0], field="term x mask"),
            _integer(raw_term[1], field="term z mask"),
        )
        if pauli in coefficients:
            raise ValueError("D5 sidecar contains duplicate terms")
        lower = _integer(raw_term[2], field="term lower numerator")
        upper = _integer(raw_term[3], field="term upper numerator")
        coefficients[pauli] = RationalInterval(
            Fraction(lower, coefficient_denominator),
            Fraction(upper, coefficient_denominator),
        )
        paulis.append(pauli)
    if paulis != sorted(paulis):
        raise ValueError("D5 sidecar terms are not canonically sorted")

    groups: list[tuple[SymplecticPauli, ...]] = []
    encoded_bounds: list[Fraction] = []
    for raw_group in raw_groups:
        if not isinstance(raw_group, list) or len(raw_group) != 2:
            raise ValueError("D5 sidecar group is malformed")
        indices = raw_group[0]
        if not isinstance(indices, list):
            raise ValueError("D5 sidecar group indices must be a list")
        try:
            group = tuple(
                paulis[_integer(index, field="group term index")]
                for index in indices
            )
        except IndexError as error:
            raise ValueError("D5 sidecar group index is out of range") from error
        groups.append(group)
        encoded_bounds.append(
            Fraction(
                _integer(raw_group[1], field="group bound numerator"),
                sqrt_denominator,
            )
        )

    certificate = certify_support_partition(coefficients, groups)
    if encoded_bounds != [group.bound for group in certificate.groups]:
        raise ValueError("D5 sidecar group bound mismatch")
    if _integer(payload.get("term_count"), field="term count") != len(paulis):
        raise ValueError("D5 sidecar term count mismatch")
    if _integer(payload.get("group_count"), field="group count") != len(groups):
        raise ValueError("D5 sidecar group count mismatch")
    if _fraction_pair(payload.get("cell_bound"), field="cell bound") != (
        certificate.bound
    ):
        raise ValueError("D5 sidecar cell bound mismatch")
    if _fraction_pair(payload.get("site_bound"), field="site bound") != (
        certificate.bound / 4
    ):
        raise ValueError("D5 sidecar site bound mismatch")
    return certificate


def decode_d5_gzip(raw: bytes) -> dict[str, object]:
    try:
        payload: Any = json.loads(gzip.decompress(raw))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("D5 sidecar is not canonical gzip JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("D5 sidecar root must be an object")
    if canonical_gzip_bytes(payload) != raw:
        raise ValueError("D5 sidecar bytes are not canonical")
    return payload
