from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lrtfim.couplings import (  # noqa: E402
    direct_image_sum,
    periodic_coupling,
    periodic_couplings,
)


def test_hurwitz_formula_is_periodic() -> None:
    length = 32
    sigma = 1.75
    for distance in range(1, length):
        assert periodic_coupling(distance, length, sigma) == pytest.approx(
            periodic_coupling(length - distance, length, sigma),
            rel=2e-14,
        )


def test_vector_matches_scalar_values() -> None:
    length = 16
    sigma = 2.0
    expected = np.array(
        [periodic_coupling(r, length, sigma) for r in range(1, length)]
    )
    np.testing.assert_allclose(periodic_couplings(length, sigma), expected, rtol=0, atol=0)


def test_hurwitz_formula_matches_direct_image_sum() -> None:
    length = 12
    sigma = 1.6
    for distance in (1, 3, length // 2, length - 1):
        exact = periodic_coupling(distance, length, sigma)
        truncated = direct_image_sum(distance, length, sigma, image_cutoff=1_000_000)
        assert truncated == pytest.approx(exact, rel=2e-10)


@pytest.mark.parametrize(
    ("distance", "length", "sigma"),
    [(0, 8, 1.0), (8, 8, 1.0), (1, 1, 1.0), (1, 8, 0.0)],
)
def test_invalid_parameters_are_rejected(
    distance: int, length: int, sigma: float
) -> None:
    with pytest.raises(ValueError):
        periodic_coupling(distance, length, sigma)


def test_couplings_are_positive() -> None:
    assert np.all(periodic_couplings(64, 1.75) > 0)
