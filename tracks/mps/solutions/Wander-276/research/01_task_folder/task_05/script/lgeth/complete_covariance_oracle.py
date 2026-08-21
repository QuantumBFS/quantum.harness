"""Explicit augmented-covariance oracles for complete Gaussian Wick moments."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .full_wick_ustat import ResponseFactors, ambient_channels, self_tensor


def realify_ambient_samples(
    samples: Sequence[ResponseFactors],
) -> np.ndarray:
    """Flatten ambient responses and concatenate real then imaginary parts."""

    records = tuple(samples)
    if not records:
        raise ValueError("augmented covariance requires at least one sample")
    labels = records[0].label_count
    ambient = records[0].ambient_dimension
    if any(
        record.label_count != labels
        or record.ambient_dimension != ambient
        for record in records
    ):
        raise ValueError("ambient response samples have inconsistent dimensions")
    complex_values = np.asarray(
        [ambient_channels(record).reshape(-1) for record in records],
        dtype=complex,
    )
    return np.concatenate(
        [complex_values.real, complex_values.imag],
        axis=1,
    )


def augmented_moments_from_real_covariance(
    real_covariance: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``E[z* z]`` and ``E[z z]`` from a real-augmented moment."""

    values = np.asarray(real_covariance, dtype=float)
    if (
        values.ndim != 2
        or values.shape[0] != values.shape[1]
        or values.shape[0] % 2
        or values.shape[0] < 2
    ):
        raise ValueError("real augmented covariance has invalid dimensions")
    if not np.all(np.isfinite(values)):
        raise ValueError("real augmented covariance must be finite")
    variables = values.shape[0] // 2
    xx = values[:variables, :variables]
    xy = values[:variables, variables:]
    yx = values[variables:, :variables]
    yy = values[variables:, variables:]
    covariance = xx + yy + 1j * (xy - yx)
    pseudocovariance = xx - yy + 1j * (xy + yx)
    return covariance, pseudocovariance


def _validate_augmented_moments(
    covariance: np.ndarray,
    pseudocovariance: np.ndarray,
    labels: int,
    ambient: int,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    ordinary = np.asarray(covariance, dtype=complex)
    improper = np.asarray(pseudocovariance, dtype=complex)
    channels = int(labels)
    dimension = int(ambient)
    variables = channels * dimension * dimension
    if channels < 1 or dimension < 1:
        raise ValueError("Gaussian moment dimensions must be positive")
    if ordinary.shape != (variables, variables):
        raise ValueError("ordinary covariance has the wrong shape")
    if improper.shape != (variables, variables):
        raise ValueError("pseudocovariance has the wrong shape")
    if not (
        np.all(np.isfinite(ordinary.real))
        and np.all(np.isfinite(ordinary.imag))
        and np.all(np.isfinite(improper.real))
        and np.all(np.isfinite(improper.imag))
    ):
        raise ValueError("augmented moments must be finite")
    return ordinary, improper, channels, dimension


def gaussian_pairings_from_augmented(
    covariance: np.ndarray,
    pseudocovariance: np.ndarray,
    *,
    labels: int,
    ambient: int,
    normalizer: float,
) -> np.ndarray:
    """Contract an arbitrary complex second moment into all three pairings."""

    ordinary, improper, channels, dimension = _validate_augmented_moments(
        covariance,
        pseudocovariance,
        labels,
        ambient,
    )
    scale = float(normalizer)
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("Gaussian moment normalizer must be positive")
    ordinary_six = ordinary.reshape(
        channels,
        dimension,
        dimension,
        channels,
        dimension,
        dimension,
    )
    improper_six = improper.reshape(
        channels,
        dimension,
        dimension,
        channels,
        dimension,
        dimension,
    )
    target = np.empty(
        (channels, channels, dimension, dimension),
        dtype=complex,
    )
    external = np.empty_like(target)
    for first in range(channels):
        for second in range(channels):
            target[first, second] = np.einsum(
                "xixj->ij",
                ordinary_six[first, :, :, second, :, :],
                optimize=True,
            )
            external[second, first] = np.einsum(
                "biai->ab",
                ordinary_six[first, :, :, second, :, :],
                optimize=True,
            )
    result = np.empty(
        (3, channels, channels, channels, channels),
        dtype=complex,
    )
    for a in range(channels):
        for b in range(channels):
            for c in range(channels):
                improper_ac = improper_six[a, :, :, c, :, :]
                for d in range(channels):
                    result[0, a, b, c, d] = np.trace(
                        target[a, b] @ target[c, d]
                    ) / scale
                    result[1, a, b, c, d] = np.trace(
                        external[d, a] @ external[b, c]
                    ) / scale
                    result[2, a, b, c, d] = np.einsum(
                        "aibj,ajbi->",
                        improper_ac.conj(),
                        improper_six[b, :, :, d, :, :],
                        optimize=True,
                    ) / scale
    return result


def leave_diagonal_augmented_wick(
    samples: Sequence[ResponseFactors],
    *,
    byte_limit: int = 1024**3,
) -> np.ndarray:
    """Return the exact ordered-pair Wick average through an independent oracle."""

    records = tuple(samples)
    if len(records) < 2:
        raise ValueError("leave-diagonal oracle requires at least two samples")
    labels = records[0].label_count
    ambient = records[0].ambient_dimension
    target_rank = records[0].target_rank
    if any(
        record.label_count != labels
        or record.ambient_dimension != ambient
        or record.target_rank != target_rank
        for record in records
    ):
        raise ValueError("oracle samples have inconsistent dimensions")
    real = realify_ambient_samples(records)
    augmented_variables = real.shape[1]
    estimated_bytes = 2 * augmented_variables**2 * np.dtype(float).itemsize
    if estimated_bytes > int(byte_limit):
        raise MemoryError(
            "explicit augmented covariance exceeds the registered byte limit"
        )
    total_real_second = real.T @ real
    total_covariance, total_pseudocovariance = (
        augmented_moments_from_real_covariance(total_real_second)
    )
    total_pairings = gaussian_pairings_from_augmented(
        total_covariance,
        total_pseudocovariance,
        labels=labels,
        ambient=ambient,
        normalizer=target_rank,
    )
    # For i=j every one of the three Wick contractions is the same cyclic
    # four-channel self tensor.  Using that exact identity avoids rebuilding
    # one rank-one augmented covariance per sample.
    diagonal_self = np.sum(
        np.asarray([self_tensor(record) for record in records]),
        axis=0,
    )
    diagonal_pairings = np.repeat(diagonal_self[None, ...], 3, axis=0)
    count = len(records)
    return (total_pairings - diagonal_pairings) / (count * (count - 1))


def _positive_root(matrix: np.ndarray, name: str) -> np.ndarray:
    values = np.asarray(matrix)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError(f"{name} has invalid dimensions")
    hermitian = 0.5 * (values + values.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    largest = max(float(np.max(eigenvalues)), 1.0)
    if float(np.min(eigenvalues)) < -1e-11 * largest:
        raise ValueError(f"{name} is not positive semidefinite")
    return (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))[None, :])


def proper_complex_gaussian_samples(
    covariance: np.ndarray,
    count: int,
    seed: int,
) -> np.ndarray:
    """Draw proper complex samples with registered ``E[z* z]`` covariance."""

    ordinary = np.asarray(covariance, dtype=complex)
    number = int(count)
    if number < 1:
        raise ValueError("proper Gaussian sample count must be positive")
    # ``E[z* z]`` is the transpose of the conventional column covariance.
    root = _positive_root(ordinary.T, "complex covariance")
    rng = np.random.default_rng(int(seed))
    standard = (
        rng.normal(size=(number, ordinary.shape[0]))
        + 1j * rng.normal(size=(number, ordinary.shape[0]))
    ) / np.sqrt(2.0)
    return np.asarray(standard @ root.T, dtype=complex)


def complex_samples_from_real_covariance(
    real_covariance: np.ndarray,
    count: int,
    seed: int,
) -> np.ndarray:
    """Draw generally improper complex samples from a real covariance."""

    values = np.asarray(real_covariance, dtype=float)
    number = int(count)
    if values.shape[0] % 2:
        raise ValueError("real covariance dimension must be even")
    if number < 1:
        raise ValueError("improper Gaussian sample count must be positive")
    root = _positive_root(values, "real covariance")
    rng = np.random.default_rng(int(seed))
    real_samples = rng.normal(size=(number, values.shape[0])) @ root.T
    variables = values.shape[0] // 2
    return np.asarray(
        real_samples[:, :variables] + 1j * real_samples[:, variables:],
        dtype=complex,
    )


def scale_mixture_samples(
    samples: np.ndarray,
    seed: int,
) -> np.ndarray:
    """Preserve the population second moment while changing the fourth moment."""

    values = np.asarray(samples, dtype=complex)
    if values.ndim < 2 or values.shape[0] < 1:
        raise ValueError("scale mixture requires a nonempty sample array")
    rng = np.random.default_rng(int(seed))
    raw_scales = rng.choice(
        np.asarray([0.5, 1.5], dtype=float),
        size=values.shape[0],
    )
    scales = raw_scales / np.sqrt(np.mean(raw_scales**2))
    reshape = (values.shape[0],) + (1,) * (values.ndim - 1)
    return values * scales.reshape(reshape)
