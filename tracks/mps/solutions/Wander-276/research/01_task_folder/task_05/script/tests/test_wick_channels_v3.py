"""Tests for gauge-invariant four-channel Wick statistics."""

from __future__ import annotations

import numpy as np
import pytest

from lgeth.wick_channels import (
    channel_covariance,
    covariance_matched_wick,
    external_covariance_eigenvalues,
    fourier_density_panel,
    gaussian_r4_reference,
    local_density_panels,
    sample_matched_gaussian_channels,
    whiten_channel_labels,
)


def _synthetic_channels(
    seed: int,
    channels: int = 8,
    ambient: int = 20,
    rank: int = 5,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (
        rng.normal(size=(channels, ambient, rank))
        + 1j * rng.normal(size=(channels, ambient, rank))
    ) / np.sqrt(2.0 * ambient)


def _seeded_unitary(dimension: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(dimension, dimension))
    matrix = matrix + 1j * rng.normal(size=matrix.shape)
    unitary, _ = np.linalg.qr(matrix)
    return unitary


def test_local_panels_are_mean_zero_distinct_site_densities() -> None:
    panels = local_density_panels(
        length=4,
        panel_size=8,
        panels=6,
        seed=71,
    )
    assert panels.shape == (6, 8, 16)
    np.testing.assert_allclose(np.sum(panels, axis=-1), 0.0, atol=1e-14)
    assert np.all(
        np.count_nonzero(np.abs(panels) > 1e-14, axis=-1) == 16
    )
    assert np.array_equal(
        panels,
        local_density_panels(4, 8, 6, 71),
    )


def test_fourier_panel_is_not_a_relabeling_of_local_panel() -> None:
    local = local_density_panels(4, 8, 1, 71)[0]
    fourier = fourier_density_panel(4, 8)
    assert fourier.shape == local.shape
    assert np.linalg.matrix_rank(
        np.concatenate([local, fourier], axis=0)
    ) > 8


def test_channel_label_whitening_sets_covariance_to_identity() -> None:
    channels = _synthetic_channels(seed=9)
    whitened = whiten_channel_labels(channels, rtol=1e-12)
    covariance = channel_covariance(whitened.channels)
    np.testing.assert_allclose(
        covariance,
        np.eye(channels.shape[0]),
        atol=1e-10,
    )


def test_singular_channel_support_fails_closed() -> None:
    channels = _synthetic_channels(seed=9)
    channels[1] = channels[0]
    with pytest.raises(ValueError, match="channel-label support"):
        whiten_channel_labels(channels, rtol=1e-10)


def test_isotropic_wick_coefficients_reduce_to_known_limits() -> None:
    rng = np.random.default_rng(12)
    channels = (
        rng.normal(size=(16, 20, 5))
        + 1j * rng.normal(size=(16, 20, 5))
    ) / np.sqrt(40.0)
    result = covariance_matched_wick(channels)
    assert result.A_left == pytest.approx(1.0, rel=0.08)
    assert result.B_right == pytest.approx(5.0 / 20.0, rel=0.25)


def test_gram_reduction_matches_explicit_external_covariance() -> None:
    channels = _synthetic_channels(seed=17, channels=4, ambient=9, rank=3)
    explicit = np.mean(
        np.einsum(
            "mai,mbi->mab",
            channels,
            channels.conj(),
            optimize=True,
        ),
        axis=0,
    )
    explicit_values = np.linalg.eigvalsh(explicit)
    explicit_values = explicit_values[explicit_values > 1e-12]
    reduced = external_covariance_eigenvalues(channels)
    np.testing.assert_allclose(
        reduced,
        explicit_values,
        rtol=1e-10,
        atol=1e-12,
    )


def test_r4_is_invariant_under_target_external_and_label_unitaries() -> None:
    channels = _synthetic_channels(seed=21)
    reference = covariance_matched_wick(channels).R4
    label = _seeded_unitary(channels.shape[0], seed=22)
    external = _seeded_unitary(channels.shape[1], seed=23)
    target = _seeded_unitary(channels.shape[2], seed=24)
    transformed = np.einsum(
        "mn,ab,nbj,jk->mak",
        label,
        external,
        channels,
        target,
        optimize=True,
    )
    observed = covariance_matched_wick(transformed).R4
    assert observed == pytest.approx(reference, abs=2e-10)


def test_matched_gaussian_reference_is_seed_reproducible() -> None:
    physical = covariance_matched_wick(_synthetic_channels(seed=31))
    first = gaussian_r4_reference(
        physical.left_eigenvalues,
        physical.right_eigenvalues,
        channel_count=8,
        samples=64,
        seed=32,
    )
    second = gaussian_r4_reference(
        physical.left_eigenvalues,
        physical.right_eigenvalues,
        channel_count=8,
        samples=64,
        seed=32,
    )
    np.testing.assert_array_equal(first, second)
    assert np.all(np.isfinite(first))
    assert np.quantile(first, 0.025) < np.quantile(first, 0.975)


def test_matched_gaussian_sampler_has_requested_shape() -> None:
    rng = np.random.default_rng(41)
    sample = sample_matched_gaussian_channels(
        left_eigenvalues=np.array([0.4, 0.6]),
        right_eigenvalues=np.array([0.2, 0.3, 0.5]),
        channel_count=5,
        rng=rng,
    )
    assert sample.shape == (5, 3, 2)
    assert np.all(np.isfinite(sample))


def test_fast_gaussian_reference_estimator_matches_full_result() -> None:
    channels = _synthetic_channels(seed=51)
    physical = covariance_matched_wick(channels)
    reference = gaussian_r4_reference(
        physical.left_eigenvalues,
        physical.right_eigenvalues,
        channel_count=8,
        samples=1,
        seed=52,
    )
    rng = np.random.default_rng(52)
    sample = sample_matched_gaussian_channels(
        physical.left_eigenvalues,
        physical.right_eigenvalues,
        channel_count=8,
        rng=rng,
    )
    assert reference[0] == pytest.approx(
        covariance_matched_wick(sample).R4,
        abs=2e-10,
    )
