from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import factorial, lcm
from typing import Sequence

import numpy as np

from .higher_order import _multinomial, weak_compositions
from .intervals import (
    RationalInterval,
    cube_root_four_interval,
    outward_quantize,
)
from .local_commutators import (
    SymplecticDyadicLocalDensityEvaluator,
    SymplecticPauli,
)


@dataclass(frozen=True, slots=True)
class IntervalStage:
    fragment_index: int
    coefficient: RationalInterval


@dataclass(frozen=True)
class FourthOrderRationalCertificate:
    center: int
    root_interval: RationalInterval
    cell_density_upper: Fraction
    site_density_upper: Fraction
    theorem_terms: int
    paired_terms: int
    singleton_terms: int


@dataclass(frozen=True)
class FourthOrderPublishedTriangleCertificate:
    center: int
    root_interval: RationalInterval
    cell_density_upper: Fraction
    site_density_upper: Fraction
    theorem_terms: int
    expanded_commutator_keys: int


def _second_order_interval_stages(
    n_fragments: int,
    scale: RationalInterval,
) -> list[IntervalStage]:
    half = scale / 2
    stages = [
        IntervalStage(index, half)
        for index in range(n_fragments - 1)
    ]
    stages.append(IntervalStage(n_fragments - 1, scale))
    stages.extend(
        IntervalStage(index, half)
        for index in reversed(range(n_fragments - 1))
    )
    return stages


def _merge_interval_stages(
    stages: Sequence[IntervalStage],
) -> tuple[IntervalStage, ...]:
    merged: list[IntervalStage] = []
    for stage in stages:
        if merged and merged[-1].fragment_index == stage.fragment_index:
            previous = merged.pop()
            merged.append(
                IntervalStage(
                    stage.fragment_index,
                    previous.coefficient + stage.coefficient,
                )
            )
        else:
            merged.append(stage)
    return tuple(merged)


def fourth_order_suzuki_interval_stages(
    n_fragments: int = 4,
    *,
    decimal_digits: int = 24,
) -> tuple[tuple[IntervalStage, ...], RationalInterval]:
    root = cube_root_four_interval(decimal_digits)
    grid = 10**decimal_digits
    u = outward_quantize(
        RationalInterval.point(1) / (4 - root),
        grid,
    )
    scales = (u, u, 1 - 4 * u, u, u)
    stages: list[IntervalStage] = []
    for scale in scales:
        stages.extend(_second_order_interval_stages(n_fragments, scale))
    return _merge_interval_stages(stages), root


def _anticommutes(left: SymplecticPauli, right: SymplecticPauli) -> bool:
    return (
        ((left[0] & right[1]).bit_count() + (left[1] & right[0]).bit_count())
        & 1
    ) == 1


def _greedy_pairs(
    paulis: Sequence[SymplecticPauli],
    midpoint_coefficients: Sequence[int | Fraction],
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...]]:
    # Floating point is used only to choose a partition. Soundness does not
    # depend on that choice: every returned pair is checked exactly below.
    magnitudes = np.fromiter(
        (abs(float(value)) for value in midpoint_coefficients),
        dtype=np.float64,
        count=len(midpoint_coefficients),
    )
    order = np.argsort(-magnitudes, kind="stable")
    used = np.zeros(len(paulis), dtype=np.bool_)
    pairs: list[tuple[int, int]] = []
    singles: list[int] = []
    for position, index_value in enumerate(order):
        index = int(index_value)
        if used[index] or midpoint_coefficients[index] == 0:
            continue
        used[index] = True
        partner = None
        for candidate_value in order[position + 1 :]:
            candidate = int(candidate_value)
            if used[candidate] or midpoint_coefficients[candidate] == 0:
                continue
            if _anticommutes(paulis[index], paulis[candidate]):
                partner = candidate
                break
        if partner is None:
            singles.append(index)
        else:
            used[partner] = True
            pairs.append((index, partner))
    # Exactly-zero midpoint intervals are harmless singletons; including
    # them is necessary when a narrow interval still contains nonzero values.
    for index_value in order:
        index = int(index_value)
        if not used[index]:
            used[index] = True
            singles.append(index)
    return tuple(pairs), tuple(singles)


def _rational_pair_bound(
    coefficients: Sequence[RationalInterval],
    pairs: Sequence[tuple[int, int]],
    singles: Sequence[int],
) -> Fraction:
    total = sum((coefficients[index].abs_upper() for index in singles), Fraction())
    for first, second in pairs:
        left = coefficients[first]
        right = coefficients[second]
        # For a,b >= 0:
        # sqrt(a^2+b^2) <= a+b-(1/2)min(a,b).
        total += (
            left.abs_upper()
            + right.abs_upper()
            - min(left.abs_lower(), right.abs_lower()) / 2
        )
    return total


def _fixed_base_intervals(
    base: Sequence[RationalInterval],
    dyadic_denominator: int,
) -> tuple[int, tuple[tuple[int, int], ...]]:
    common = 1
    for interval in base:
        common = lcm(
            common,
            interval.lower.denominator,
            interval.upper.denominator,
        )
    endpoints = tuple(
        (
            interval.lower.numerator * (common // interval.lower.denominator),
            interval.upper.numerator * (common // interval.upper.denominator),
        )
        for interval in base
    )
    return common * dyadic_denominator, endpoints


def _fixed_linear_interval(
    numerators: Sequence[int],
    base_endpoints: Sequence[tuple[int, int]],
) -> tuple[int, int]:
    lower = upper = 0
    for numerator, (base_lower, base_upper) in zip(numerators, base_endpoints):
        if numerator >= 0:
            lower += numerator * base_lower
            upper += numerator * base_upper
        else:
            lower += numerator * base_upper
            upper += numerator * base_lower
    return lower, upper


def _fixed_abs_bounds(interval: tuple[int, int]) -> tuple[int, int]:
    lower, upper = interval
    absolute_upper = max(abs(lower), abs(upper))
    if lower <= 0 <= upper:
        return 0, absolute_upper
    return min(abs(lower), abs(upper)), absolute_upper


def _fixed_pair_bound_numerator(
    intervals: Sequence[tuple[int, int]],
    pairs: Sequence[tuple[int, int]],
    singles: Sequence[int],
) -> int:
    """Return the pair bound numerator over twice the common denominator."""

    absolute = tuple(_fixed_abs_bounds(interval) for interval in intervals)
    total = sum(2 * absolute[index][1] for index in singles)
    for first, second in pairs:
        first_lower, first_upper = absolute[first]
        second_lower, second_upper = absolute[second]
        total += (
            2 * first_upper
            + 2 * second_upper
            - min(first_lower, second_lower)
        )
    return total


def fourth_order_rational_pair_certificate(
    *,
    center: int = 17,
    decimal_digits: int = 24,
) -> FourthOrderRationalCertificate:
    """Build a fully rational S4 local-norm certificate."""

    stages_left, root = fourth_order_suzuki_interval_stages(
        4,
        decimal_digits=decimal_digits,
    )
    stages = tuple(reversed(stages_left))
    count = len(stages)
    if not 1 <= center <= count:
        raise ValueError("center must use one-based stage indexing")
    order = 4
    grouped: dict[
        tuple[tuple[int, ...], int],
        Fraction,
    ] = {}
    base_by_j: dict[int, tuple[RationalInterval, ...]] = {}
    theorem_terms = 0

    def collect(
        j: int,
        indices: tuple[int, ...],
        composition: tuple[int, ...],
    ) -> None:
        nonlocal theorem_terms
        theorem_terms += 1
        outer: list[int] = []
        scalar = RationalInterval.point(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            stage = stages[stage_index - 1]
            scalar *= stage.coefficient**power
            outer.extend([stage.fragment_index] * power)
        if j not in base_by_j:
            base = [RationalInterval.point(0) for _ in range(4)]
            for base_index in range(1, j):
                stage = stages[base_index - 1]
                base[stage.fragment_index] += stage.coefficient
            base_by_j[j] = tuple(base)
        key = (tuple(outer), j)
        grouped[key] = grouped.get(key, Fraction()) + scalar.abs_upper()

    for j in range(2, center + 1):
        indices = tuple(range(center, j - 1, -1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)
    for j in range(center + 1, count + 1):
        indices = tuple(range(center + 1, j + 1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)

    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    denominator = 1 << (order + 2)
    fixed_base = {
        j: _fixed_base_intervals(base, denominator)
        for j, base in base_by_j.items()
    }
    coefficient_cache: dict[
        tuple[int, tuple[int, int, int, int]],
        tuple[int, int],
    ] = {}
    total = Fraction()
    paired_terms = 0
    singleton_terms = 0
    for (outer, j), scalar_upper in grouped.items():
        operators = [evaluator.evaluate(outer + (base,)) for base in range(4)]
        paulis = tuple(sorted(set().union(*(operator.keys() for operator in operators))))
        common_denominator, base_endpoints = fixed_base[j]
        coefficients: list[tuple[int, int]] = []
        for pauli in paulis:
            numerators = tuple(
                operator.get(pauli, 0)
                for operator in operators
            )
            cache_key = (j, numerators)
            coefficient = coefficient_cache.get(cache_key)
            if coefficient is None:
                coefficient = _fixed_linear_interval(
                    numerators,
                    base_endpoints,
                )
                coefficient_cache[cache_key] = coefficient
            coefficients.append(coefficient)
        midpoint = tuple(
            coefficient[0] + coefficient[1]
            for coefficient in coefficients
        )
        pairs, singles = _greedy_pairs(paulis, midpoint)
        # The verifier checks every selected pair, rather than trusting the
        # discovery ordering.
        if any(not _anticommutes(paulis[a], paulis[b]) for a, b in pairs):
            raise ArithmeticError("invalid anticommuting pair")
        local_bound = Fraction(
            _fixed_pair_bound_numerator(coefficients, pairs, singles),
            2 * common_denominator,
        )
        total += scalar_upper * local_bound
        paired_terms += len(pairs)
        singleton_terms += len(singles)

    cell = total / factorial(order + 1)
    return FourthOrderRationalCertificate(
        center=center,
        root_interval=root,
        cell_density_upper=cell,
        site_density_upper=cell / 4,
        theorem_terms=theorem_terms,
        paired_terms=paired_terms,
        singleton_terms=singleton_terms,
    )


def fourth_order_published_triangle_certificate(
    *,
    center: int = 20,
    decimal_digits: int = 18,
) -> FourthOrderPublishedTriangleCertificate:
    """Instantiate the published high-order theorem with full triangle expansion.

    This intentionally expands every partial Hamiltonian sum before taking
    local Pauli-l1 norms.  It is the independently reproducible published
    baseline, not the strengthened candidate analysis.
    """

    stages_left, root = fourth_order_suzuki_interval_stages(
        4,
        decimal_digits=decimal_digits,
    )
    stages = tuple(reversed(stages_left))
    count = len(stages)
    if not 1 <= center <= count:
        raise ValueError("center must use one-based stage indexing")
    order = 4
    weights: dict[tuple[int, ...], Fraction] = {}
    theorem_terms = 0

    def collect(
        j: int,
        indices: tuple[int, ...],
        composition: tuple[int, ...],
    ) -> None:
        nonlocal theorem_terms
        theorem_terms += 1
        outer: list[int] = []
        scalar = RationalInterval.point(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            stage = stages[stage_index - 1]
            scalar *= stage.coefficient**power
            outer.extend([stage.fragment_index] * power)
        scalar_upper = scalar.abs_upper()
        for base_index in range(1, j):
            base_stage = stages[base_index - 1]
            key = tuple(outer) + (base_stage.fragment_index,)
            weights[key] = weights.get(key, Fraction()) + (
                scalar_upper * base_stage.coefficient.abs_upper()
            )

    for j in range(2, center + 1):
        indices = tuple(range(center, j - 1, -1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)
    for j in range(center + 1, count + 1):
        indices = tuple(range(center + 1, j + 1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)

    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    total = sum(
        (
            weight * evaluator.pauli_l1_density(key)
            for key, weight in weights.items()
        ),
        Fraction(),
    )
    cell = total / factorial(order + 1)
    return FourthOrderPublishedTriangleCertificate(
        center=center,
        root_interval=root,
        cell_density_upper=cell,
        site_density_upper=cell / 4,
        theorem_terms=theorem_terms,
        expanded_commutator_keys=len(weights),
    )
