"""Finite-ring long-range coupling utilities."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.special import zeta


def periodic_coupling(distance: int, length: int, sigma: float) -> float:
    """Return the exact Hurwitz-zeta coupling for a finite periodic chain.

    The convention is

    ``sum(n in Z, abs(distance + n * length)**(-1 - sigma))``.
    """
    _validate_length_sigma(length, sigma)
    if not isinstance(distance, (int, np.integer)) or not 1 <= distance < length:
        raise ValueError("distance must be an integer with 1 <= distance < length")

    exponent = 1.0 + float(sigma)
    scaled_distance = float(distance) / length
    return float(
        length**(-exponent)
        * (
            zeta(exponent, scaled_distance)
            + zeta(exponent, 1.0 - scaled_distance)
        )
    )


def periodic_couplings(length: int, sigma: float) -> NDArray[np.float64]:
    """Return periodic couplings for separations 1 through ``length - 1``."""
    _validate_length_sigma(length, sigma)
    distances = np.arange(1, length, dtype=float)
    exponent = 1.0 + float(sigma)
    scaled_distances = distances / length
    values = length**(-exponent) * (
        zeta(exponent, scaled_distances)
        + zeta(exponent, 1.0 - scaled_distances)
    )
    return np.asarray(values, dtype=float)


def direct_image_sum(
    distance: int,
    length: int,
    sigma: float,
    *,
    image_cutoff: int,
) -> float:
    """Return a symmetrically truncated direct periodic-image sum."""
    _validate_length_sigma(length, sigma)
    if not isinstance(distance, (int, np.integer)) or not 1 <= distance < length:
        raise ValueError("distance must be an integer with 1 <= distance < length")
    if not isinstance(image_cutoff, (int, np.integer)) or image_cutoff < 0:
        raise ValueError("image_cutoff must be a non-negative integer")

    images = np.arange(-image_cutoff, image_cutoff + 1, dtype=float)
    separations = np.abs(float(distance) + images * length)
    return float(np.sum(separations ** (-1.0 - float(sigma))))


def _validate_length_sigma(length: int, sigma: float) -> None:
    if not isinstance(length, (int, np.integer)) or length < 2:
        raise ValueError("length must be an integer >= 2")
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be finite and positive")
