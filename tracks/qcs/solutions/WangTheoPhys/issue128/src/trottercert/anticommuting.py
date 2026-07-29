from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

from .intervals import RationalInterval
from .local_commutators import SymplecticPauli


@dataclass(frozen=True)
class AnticommutingGroupCertificate:
    term_indices: tuple[int, ...]
    bound: Fraction


@dataclass(frozen=True)
class AnticommutingPartitionCertificate:
    paulis: tuple[SymplecticPauli, ...]
    coefficients: tuple[RationalInterval, ...]
    groups: tuple[AnticommutingGroupCertificate, ...]
    bound: Fraction


def symplectic_anticommutes(
    left: SymplecticPauli,
    right: SymplecticPauli,
) -> bool:
    left_x, left_z = left
    right_x, right_z = right
    return bool(
        (
            (left_x & right_z).bit_count()
            + (left_z & right_x).bit_count()
        )
        & 1
    )


def sqrt_fraction_upper(
    value: Fraction,
    *,
    decimal_places: int = 30,
) -> Fraction:
    if value < 0:
        raise ValueError("cannot bound the square root of a negative value")
    if decimal_places < 0:
        raise ValueError("decimal places must be nonnegative")
    if value == 0:
        return Fraction()
    scale = 10**decimal_places
    quotient = value.numerator * scale * scale // value.denominator
    root = isqrt(quotient)
    candidate = Fraction(root, scale)
    if candidate * candidate < value:
        candidate = Fraction(root + 1, scale)
    if candidate * candidate < value:
        raise ArithmeticError("outward square-root rounding failed")
    return candidate


def discover_anticommuting_partition(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    *,
    max_group_size: int = 10,
) -> tuple[tuple[SymplecticPauli, ...], ...]:
    if max_group_size < 1:
        raise ValueError("maximum group size must be positive")
    ordered = tuple(
        sorted(
            coefficients,
            key=lambda pauli: (
                -float(coefficients[pauli].abs_upper()),
                pauli,
            ),
        )
    )
    used: set[SymplecticPauli] = set()
    groups: list[tuple[SymplecticPauli, ...]] = []
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


def certify_anticommuting_partition(
    coefficients: Mapping[SymplecticPauli, RationalInterval],
    groups: Sequence[Sequence[SymplecticPauli]],
    *,
    sqrt_decimal_places: int = 30,
) -> AnticommutingPartitionCertificate:
    paulis = tuple(sorted(coefficients))
    index = {pauli: offset for offset, pauli in enumerate(paulis)}
    flattened = tuple(pauli for group in groups for pauli in group)
    if len(flattened) != len(set(flattened)):
        raise ValueError("partition coverage contains duplicate terms")
    if set(flattened) != set(paulis):
        raise ValueError("partition coverage differs from coefficient map")

    certified_groups: list[AnticommutingGroupCertificate] = []
    for group in groups:
        if not group:
            raise ValueError("anticommuting group must be nonempty")
        for left_position, left in enumerate(group):
            for right in group[left_position + 1 :]:
                if not symplectic_anticommutes(left, right):
                    raise ValueError("group members do not anticommute")
        squared = sum(
            (
                coefficients[pauli].abs_upper() ** 2
                for pauli in group
            ),
            Fraction(),
        )
        bound = sqrt_fraction_upper(
            squared,
            decimal_places=sqrt_decimal_places,
        )
        certified_groups.append(
            AnticommutingGroupCertificate(
                tuple(index[pauli] for pauli in group),
                bound,
            )
        )

    return AnticommutingPartitionCertificate(
        paulis=paulis,
        coefficients=tuple(coefficients[pauli] for pauli in paulis),
        groups=tuple(certified_groups),
        bound=sum(
            (group.bound for group in certified_groups),
            Fraction(),
        ),
    )
