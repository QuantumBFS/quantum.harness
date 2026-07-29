"""Measurement helpers independent of the benchmark transport."""

from __future__ import annotations

from statistics import median


def median_and_mad(values: list[float] | tuple[float, ...]) -> tuple[float, float]:
    """Return median and median absolute deviation."""

    if not values:
        raise ValueError("at least one value is required")
    center = float(median(values))
    deviation = float(median(abs(value - center) for value in values))
    return center, deviation
