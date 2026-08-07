from __future__ import annotations

import numpy as np

from route_d_plus.train_dplus0 import (
    estimate_centering_whitening,
    raw_local_generators,
)
from route_d_plus.vmc import center_whiten_channels


def test_raw_local_generators_use_multiplet_invariant_contraction() -> None:
    rng = np.random.default_rng(81)
    channels = rng.normal(size=(7, 5, 4)) + 1.0j * rng.normal(
        size=(7, 5, 4)
    )
    local = raw_local_generators(channels)
    denominator = np.sum(np.abs(channels[..., 0]) ** 2, axis=1)
    expected = np.einsum(
        "sm,sma->sa",
        channels[..., 0].conj(),
        channels[..., 1:],
    ) / denominator[:, None]
    assert np.max(np.abs(local - expected)) < 1.0e-14


def test_centering_whitening_uses_ground_tower_mixture() -> None:
    rng = np.random.default_rng(82)
    ground = rng.normal(size=(512, 4)) + 1.0j * rng.normal(
        size=(512, 4)
    )
    tower = rng.normal(size=(512, 5, 4)) + 1.0j * rng.normal(
        size=(512, 5, 4)
    )
    ground[:, 0] += 3.0
    tower[..., 0] += 3.0
    mean, covariance, whitening = estimate_centering_whitening(
        ground, tower
    )
    assert mean.shape == (3,)
    assert covariance.shape == (3, 3)
    assert whitening.shape == (3, 3)
    identity = whitening @ covariance @ whitening.T
    assert np.max(np.abs(identity - np.eye(3))) < 1.0e-12
    transformed = center_whiten_channels(ground, mean, whitening)
    assert transformed.shape == ground.shape
