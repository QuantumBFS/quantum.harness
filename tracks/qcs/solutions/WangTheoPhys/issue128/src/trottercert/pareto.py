from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .intervals import RationalInterval, nth_root_four_interval, outward_quantize
from .refined_error import defect_tail_site_bound
from .rigorous_fourth import IntervalStage


def _second_order_stages(
    n_fragments: int,
    scale: RationalInterval,
) -> tuple[IntervalStage, ...]:
    half = scale / 2
    return (
        *(IntervalStage(index, half) for index in range(n_fragments - 1)),
        IntervalStage(n_fragments - 1, scale),
        *(IntervalStage(index, half) for index in reversed(range(n_fragments - 1))),
    )


def _merge(stages: Sequence[IntervalStage]) -> tuple[IntervalStage, ...]:
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


def recursive_suzuki_interval_stages(
    order: int,
    n_fragments: int = 4,
    *,
    decimal_digits: int = 12,
) -> tuple[IntervalStage, ...]:
    """Return the standard five-copy Suzuki formula of even ``order``."""

    if order < 2 or order % 2:
        raise ValueError("Suzuki order must be a positive even integer")
    stages = _second_order_stages(n_fragments, RationalInterval.point(1))
    current_order = 2
    grid = 10**decimal_digits
    while current_order < order:
        next_order = current_order + 2
        root = nth_root_four_interval(next_order - 1, decimal_digits)
        scale = outward_quantize(
            RationalInterval.point(1) / (4 - root),
            grid,
        )
        copy_scales = (scale, scale, 1 - 4 * scale, scale, scale)
        composed: list[IntervalStage] = []
        for copy_scale in copy_scales:
            composed.extend(
                IntervalStage(
                    stage.fragment_index,
                    stage.coefficient * copy_scale,
                )
                for stage in stages
            )
        stages = _merge(composed)
        current_order = next_order
    return stages


@dataclass(frozen=True)
class PublishedSuzukiPoint:
    order: int
    steps: int
    stages_per_step: int
    group_exponentials: int
    global_error_bound: Fraction


def published_suzuki_tail_bound(
    stages: Sequence[IntervalStage],
    *,
    order: int,
    n_sites: int,
    steps: int,
) -> Fraction:
    """Rigorous generic locality bound using only the published formula order."""

    return Fraction(n_sites) * defect_tail_site_bound(
        stages,
        steps,
        first_omitted_degree=order,
    )


def minimum_published_suzuki_point(
    order: int,
    *,
    n_sites: int,
    tolerance: Fraction,
    n_fragments: int = 4,
    decimal_digits: int = 12,
) -> PublishedSuzukiPoint:
    stages = recursive_suzuki_interval_stages(
        order,
        n_fragments,
        decimal_digits=decimal_digits,
    )

    def bound(steps: int) -> Fraction:
        return published_suzuki_tail_bound(
            stages,
            order=order,
            n_sites=n_sites,
            steps=steps,
        )

    low = 1
    high = 1
    while True:
        try:
            accepted = bound(high) <= tolerance
        except ValueError:
            accepted = False
        if accepted:
            break
        high *= 2
    while low < high:
        middle = (low + high) // 2
        try:
            accepted = bound(middle) <= tolerance
        except ValueError:
            accepted = False
        if accepted:
            high = middle
        else:
            low = middle + 1

    groups = (len(stages) - 1) * low + 1
    return PublishedSuzukiPoint(
        order=order,
        steps=low,
        stages_per_step=len(stages),
        group_exponentials=groups,
        global_error_bound=bound(low),
    )
