"""Reduced-label complete-covariance protocol tests for v12."""

from __future__ import annotations

import numpy as np

from lgeth.full_wick_ustat import ResponseFactors
from run_cross_complete_covariance_v12 import (
    complete_covariance_summary,
    fixed_invariant_direction,
    lattice_susy_panel_ensemble,
)


def _orthonormal_frame(ambient: int, rank: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame, _ = np.linalg.qr(
        rng.normal(size=(ambient, rank)) + 1j * rng.normal(size=(ambient, rank))
    )
    return frame


def test_fixed_direction_is_normalized_and_not_data_fitted() -> None:
    first = fixed_invariant_direction(2)
    second = fixed_invariant_direction(2)
    assert np.array_equal(first, second)
    assert first.shape == (2, 2, 2, 2)
    assert np.isclose(np.linalg.norm(first), 1.0, atol=2e-14)
    assert np.count_nonzero(first) > 1


def test_complete_summary_uses_every_unordered_pair() -> None:
    frame = _orthonormal_frame(7, 3, seed=17)
    rng = np.random.default_rng(19)
    samples = tuple(
        ResponseFactors(
            frame=frame,
            channels=rng.normal(size=(2, 7, 3))
            + 1j * rng.normal(size=(2, 7, 3)),
        )
        for _ in range(6)
    )
    result = complete_covariance_summary(samples, block_size=3)
    assert result["realization_count"] == 6
    assert result["unordered_pair_count"] == 15
    assert result["pairing_count"] == 3
    assert np.isfinite(result["normalized_cumulant_norm"])
    assert np.isfinite(result["directional_estimate"])
    assert result["standard_error"] > 0.0
    assert all(result["checks"].values())


def test_lattice_panel_ensemble_is_deterministic_and_audited() -> None:
    first = lattice_susy_panel_ensemble(1, count=6)
    second = lattice_susy_panel_ensemble(1, count=6)
    assert len(first) == len(second) == 6
    for left, right in zip(first, second, strict=True):
        assert np.array_equal(left.frame, right.frame)
        assert np.array_equal(left.channels, right.channels)
        assert left.label_count == 2
        assert left.target_rank == 2
    result = complete_covariance_summary(first, block_size=2, oracle=True)
    assert result["oracle_relative_error"] < 2e-10
    assert all(result["checks"].values())
