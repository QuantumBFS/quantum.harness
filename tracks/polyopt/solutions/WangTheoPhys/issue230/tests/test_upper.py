import numpy as np
import pytest

from xxzcert.upper import (
    block_product_energy,
    neel_state,
    optimize_block_state,
    repeated_supercell_energy,
)


def test_neel_product_energy():
    assert abs(block_product_energy(1.0, neel_state(2)) + 0.25) < 1e-12


def test_repeated_supercell_converges_to_per_block_energy():
    candidate = optimize_block_state(1.0, 4)
    per_block = repeated_supercell_energy(1.0, candidate.state, 1000)
    assert abs(per_block / 4 - candidate.raw_upper) < 1e-4


@pytest.mark.parametrize(
    ("delta", "exact"),
    [(0.0, -1 / np.pi), (0.5, -0.375), (1.0, 0.25 - np.log(2))],
)
def test_explicit_block_state_is_variational_upper(delta, exact):
    for sites in (2, 4, 6):
        candidate = optimize_block_state(delta, sites)
        assert candidate.raw_upper >= exact - 1e-12
        assert candidate.normalization_residual < 1e-12


def test_invalid_block_rejected():
    with pytest.raises(ValueError):
        optimize_block_state(1.0, 1)


def test_sparse_large_block_path_is_variational():
    candidate = optimize_block_state(1.0, 10)
    assert candidate.raw_upper >= 0.25 - np.log(2) - 1e-10
    assert candidate.raw_upper < -0.42
