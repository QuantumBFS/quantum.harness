"""Finite-size Gaussian nulls conditioned on safe Hodge signatures."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from lgeth.hodge_response import HodgeSignature
from lgeth.hodge_wick import (
    complete_realization_null,
    hodge_gaussian_r4_reference,
    sample_hodge_gaussian_channels,
)
from lgeth.wick_channels import gaussian_r4_reference


def _signature(minus_weight: float, plus_weight: float) -> HodgeSignature:
    minus_target = np.asarray([0.42, 0.27, 0.18, 0.09, 0.04])
    plus_target = np.asarray([0.36, 0.25, 0.20, 0.12, 0.07])
    minus_external = np.asarray([0.51, 0.31, 0.18])
    plus_external = np.asarray([0.40, 0.28, 0.20, 0.12])
    total = minus_weight + plus_weight
    balance = 0.0 if total == 0 else 4.0 * minus_weight * plus_weight / total**2
    return HodgeSignature(
        channel_count=8,
        target_rank=5,
        minus_weight=minus_weight,
        plus_weight=plus_weight,
        hodge_balance=balance,
        minus_channel_covariance=np.eye(8),
        plus_channel_covariance=np.eye(8),
        minus_target_eigenvalues=minus_target,
        plus_target_eigenvalues=plus_target,
        minus_external_eigenvalues=minus_external,
        plus_external_eigenvalues=plus_external,
        minus_target_effective_rank=3.5,
        plus_target_effective_rank=4.0,
        minus_external_effective_rank=2.5,
        plus_external_effective_rank=3.2,
        minus_target_entropy=0.8,
        plus_target_entropy=0.9,
        minus_external_entropy=0.8,
        plus_external_entropy=0.9,
        orthogonality_relative_error=0.0,
    )


def test_one_sided_hodge_reference_is_exact_existing_regression() -> None:
    signature = _signature(1.0, 0.0)
    observed = hodge_gaussian_r4_reference(signature, 8, 32, 89)
    expected = gaussian_r4_reference(
        signature.minus_target_eigenvalues,
        signature.minus_external_eigenvalues,
        8,
        32,
        89,
    )
    assert np.array_equal(observed, expected)


def test_two_sided_sampler_has_direct_sum_shape_and_is_deterministic() -> None:
    signature = _signature(0.4, 0.6)
    first = sample_hodge_gaussian_channels(
        signature,
        8,
        np.random.default_rng(97),
    )
    second = sample_hodge_gaussian_channels(
        signature,
        8,
        np.random.default_rng(97),
    )
    assert first.shape == (8, 7, 5)
    assert np.array_equal(first, second)
    assert np.all(np.isfinite(first.real))
    assert np.all(np.isfinite(first.imag))


def test_common_branch_weight_rescaling_does_not_change_null_draws() -> None:
    signature = _signature(0.4, 0.6)
    scaled = replace(signature, minus_weight=4.0, plus_weight=6.0)
    first = sample_hodge_gaussian_channels(
        signature,
        8,
        np.random.default_rng(101),
    )
    second = sample_hodge_gaussian_channels(
        scaled,
        8,
        np.random.default_rng(101),
    )
    assert np.array_equal(first, second)


def test_branch_channel_covariance_changes_two_sided_null_draw() -> None:
    signature = _signature(0.4, 0.6)
    covariance = np.full((8, 8), 0.15, dtype=complex)
    np.fill_diagonal(covariance, 1.0)
    correlated = replace(signature, plus_channel_covariance=covariance)
    first = sample_hodge_gaussian_channels(
        signature,
        8,
        np.random.default_rng(102),
    )
    second = sample_hodge_gaussian_channels(
        correlated,
        8,
        np.random.default_rng(102),
    )
    assert not np.allclose(first, second)


def test_hodge_r4_and_complete_realization_nulls_are_reproducible() -> None:
    first_signature = _signature(0.45, 0.55)
    second_signature = _signature(0.30, 0.70)
    first = hodge_gaussian_r4_reference(first_signature, 8, 24, 103)
    second = hodge_gaussian_r4_reference(first_signature, 8, 24, 103)
    assert np.array_equal(first, second)
    assert np.all(np.isfinite(first))
    aggregate_first = complete_realization_null(
        [first_signature, second_signature],
        samples=20,
        seed=107,
    )
    aggregate_second = complete_realization_null(
        [first_signature, second_signature],
        samples=20,
        seed=107,
    )
    assert aggregate_first.shape == (20,)
    assert np.array_equal(aggregate_first, aggregate_second)
