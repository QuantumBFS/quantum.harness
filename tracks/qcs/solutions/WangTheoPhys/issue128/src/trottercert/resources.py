from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


def ceil_nth_root_fraction(value: Fraction, degree: int) -> int:
    if value < 0 or degree <= 0:
        raise ValueError("requires a nonnegative value and positive degree")
    if value == 0:
        return 0
    low, high = 0, 1
    while high**degree * value.denominator < value.numerator:
        high *= 2
    while low + 1 < high:
        middle = (low + high) // 2
        if middle**degree * value.denominator >= value.numerator:
            high = middle
        else:
            low = middle
    return high


def required_steps(
    error_constant: Fraction,
    tolerance: Fraction,
    formula_order: int,
    time: Fraction = Fraction(1),
) -> int:
    target = error_constant * time ** (formula_order + 1) / tolerance
    return ceil_nth_root_fraction(target, formula_order)


def symmetric_group_exponentials(n_fragments: int, steps: int) -> int:
    if n_fragments < 2 or steps < 1:
        raise ValueError("requires at least two fragments and one step")
    return (2 * n_fragments - 2) * steps + 1


@dataclass(frozen=True)
class ResourceEstimate:
    steps: int
    group_exponentials: int
    local_propagators: int
    cnot_upper: int


def four_matching_resources(
    n_sites: int,
    steps: int,
    *,
    cnots_per_bond: int = 3,
) -> ResourceEstimate:
    groups = symmetric_group_exponentials(4, steps)
    local = groups * (n_sites // 2)
    return ResourceEstimate(steps, groups, local, local * cnots_per_bond)


def three_l_path_resources(
    n_sites: int,
    steps: int,
    *,
    cnots_per_cluster: int = 9,
) -> ResourceEstimate:
    groups = symmetric_group_exponentials(3, steps)
    local = groups * (n_sites // 3)
    return ResourceEstimate(steps, groups, local, local * cnots_per_cluster)


def fourth_order_four_matching_resources(
    n_sites: int,
    steps: int,
    *,
    stage_count: int = 31,
    cnots_per_bond: int = 3,
) -> ResourceEstimate:
    """Resources for a palindromic S4 macro-step with mergeable boundaries."""

    if stage_count < 1 or steps < 1:
        raise ValueError("stage_count and steps must be positive")
    groups = (stage_count - 1) * steps + 1
    local = groups * (n_sites // 2)
    return ResourceEstimate(steps, groups, local, local * cnots_per_bond)
