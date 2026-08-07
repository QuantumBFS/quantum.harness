from __future__ import annotations

import numpy as np
import pytest

from oracle.families import available_cases, random_generator, structure_residual


@pytest.mark.parametrize(
    "case",
    [
        "so3",
        "o11",
        "o22",
        "sl2",
        "sl3",
        "sp2",
        "sp4",
        "u2",
        "u11",
        "su2",
        "su3",
        "su11",
        "su21",
        "usp2",
        "usp4",
    ],
)
def test_random_generator_satisfies_declared_lie_algebra(case: str) -> None:
    """Catches a projection that samples outside the advertised family."""
    generator = random_generator(case, np.random.default_rng(1234), scale=0.7)

    assert generator.shape == available_cases()[case].shape
    assert structure_residual(case, generator) < 1e-12


def test_random_generator_is_reproducible_from_seed() -> None:
    """Catches accidental use of global random state during a scan."""
    left = random_generator("su21", np.random.default_rng(99), scale=0.4)
    right = random_generator("su21", np.random.default_rng(99), scale=0.4)

    assert np.array_equal(left, right)
