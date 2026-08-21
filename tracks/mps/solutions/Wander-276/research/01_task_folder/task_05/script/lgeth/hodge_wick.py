"""Covariance-matched Gaussian nulls for exact/coexact response branches."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .hodge_response import HodgeSignature
from .wick_channels import (
    _fast_covariance_matched_r4,
    gaussian_r4_reference,
    sample_matched_gaussian_channels,
)


def _positive(values: np.ndarray, rtol: float = 1e-12) -> np.ndarray:
    spectrum = np.maximum(np.asarray(values, dtype=float), 0.0)
    if spectrum.ndim != 1 or spectrum.size == 0:
        return np.empty(0, dtype=float)
    largest = float(np.max(spectrum))
    if largest <= 0.0:
        return np.empty(0, dtype=float)
    return spectrum[spectrum > float(rtol) * largest]


def _haar_unitary(size: int, rng: np.random.Generator) -> np.ndarray:
    gaussian = rng.normal(size=(size, size)) + 1j * rng.normal(
        size=(size, size)
    )
    q, r = np.linalg.qr(gaussian)
    diagonal = np.diag(r)
    phases = np.ones(size, dtype=complex)
    nonzero = np.abs(diagonal) > np.finfo(float).tiny
    phases[nonzero] = diagonal[nonzero] / np.abs(diagonal[nonzero])
    return np.asarray(q * phases[None, :], dtype=complex)


def _sample_branch(
    target_eigenvalues: np.ndarray,
    external_eigenvalues: np.ndarray,
    channel_covariance: np.ndarray,
    channel_count: int,
    weight_fraction: float,
    rng: np.random.Generator,
) -> np.ndarray:
    target_full = np.maximum(np.asarray(target_eigenvalues, dtype=float), 0.0)
    external = _positive(external_eigenvalues)
    if target_full.ndim != 1 or target_full.size == 0 or external.size == 0:
        raise ValueError("nonzero Hodge branch has empty covariance support")
    if float(np.sum(target_full)) <= 0.0:
        raise ValueError("nonzero Hodge branch has zero target covariance")
    target_full = target_full / np.sum(target_full)
    external = external / np.sum(external)
    gaussian = (
        rng.normal(size=(channel_count, external.size, target_full.size))
        + 1j
        * rng.normal(size=(channel_count, external.size, target_full.size))
    ) / np.sqrt(2.0)
    local = (
        np.sqrt(external)[None, :, None]
        * gaussian
        * np.sqrt(target_full)[None, None, :]
    )
    target_rotation = _haar_unitary(target_full.size, rng)
    rotated = np.einsum(
        "mai,ij->maj",
        local,
        target_rotation,
        optimize=True,
    )
    label_covariance = np.asarray(channel_covariance, dtype=complex)
    if label_covariance.shape != (channel_count, channel_count):
        raise ValueError("Hodge branch channel covariance has the wrong shape")
    label_covariance = 0.5 * (label_covariance + label_covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(label_covariance)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    trace = float(np.sum(eigenvalues))
    if trace <= 0.0:
        raise ValueError("nonzero Hodge branch has zero channel covariance")
    label_root = (
        eigenvectors * np.sqrt(eigenvalues * channel_count / trace)[None, :]
    ) @ eigenvectors.conj().T
    correlated = np.einsum(
        "mn,nai->mai",
        label_root,
        rotated,
        optimize=True,
    )
    return np.sqrt(float(weight_fraction)) * correlated


def sample_hodge_gaussian_channels(
    signature: HodgeSignature,
    channel_count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw one response tensor from the safe two-branch Hodge signature."""

    labels = int(channel_count)
    if labels < 1 or labels != int(signature.channel_count):
        raise ValueError("channel count disagrees with the Hodge signature")
    weights = np.asarray(
        [signature.minus_weight, signature.plus_weight],
        dtype=float,
    )
    if np.any(weights < 0.0) or float(np.sum(weights)) <= 0.0:
        raise ValueError("Hodge branch weights must be nonnegative and nonzero")
    active = np.flatnonzero(weights > np.finfo(float).tiny * np.sum(weights))
    if active.size == 1:
        if int(active[0]) == 0:
            target = _positive(signature.minus_target_eigenvalues)
            external = _positive(signature.minus_external_eigenvalues)
        else:
            target = _positive(signature.plus_target_eigenvalues)
            external = _positive(signature.plus_external_eigenvalues)
        return sample_matched_gaussian_channels(
            target,
            external,
            labels,
            rng,
        )
    fractions = weights / np.sum(weights)
    minus = _sample_branch(
        signature.minus_target_eigenvalues,
        signature.minus_external_eigenvalues,
        signature.minus_channel_covariance,
        labels,
        float(fractions[0]),
        rng,
    )
    plus = _sample_branch(
        signature.plus_target_eigenvalues,
        signature.plus_external_eigenvalues,
        signature.plus_channel_covariance,
        labels,
        float(fractions[1]),
        rng,
    )
    if minus.shape[0] != plus.shape[0] or minus.shape[2] != plus.shape[2]:
        raise RuntimeError("Hodge branch samples do not share channel and target axes")
    return np.concatenate([minus, plus], axis=1)


def hodge_gaussian_r4_reference(
    signature: HodgeSignature,
    channel_count: int,
    samples: int,
    seed: int,
) -> np.ndarray:
    """Return deterministic finite-size R4 samples for one Hodge signature."""

    count = int(samples)
    labels = int(channel_count)
    if count < 1:
        raise ValueError("Hodge Gaussian reference requires at least one sample")
    weights = np.asarray(
        [signature.minus_weight, signature.plus_weight],
        dtype=float,
    )
    active = np.flatnonzero(weights > np.finfo(float).tiny * np.sum(weights))
    if active.size == 1:
        if int(active[0]) == 0:
            target = _positive(signature.minus_target_eigenvalues)
            external = _positive(signature.minus_external_eigenvalues)
        else:
            target = _positive(signature.plus_target_eigenvalues)
            external = _positive(signature.plus_external_eigenvalues)
        return gaussian_r4_reference(target, external, labels, count, int(seed))
    rng = np.random.default_rng(int(seed))
    result = np.empty(count, dtype=float)
    for sample in range(count):
        channels = sample_hodge_gaussian_channels(signature, labels, rng)
        result[sample] = _fast_covariance_matched_r4(channels)
    return result


def complete_realization_null(
    signatures: Sequence[HodgeSignature],
    samples: int,
    seed: int,
) -> np.ndarray:
    """Draw medians using one complete Gaussian tensor per realization."""

    records = tuple(signatures)
    count = int(samples)
    if not records or count < 1:
        raise ValueError("complete-realization null requires records and samples")
    labels = int(records[0].channel_count)
    if any(int(record.channel_count) != labels for record in records):
        raise ValueError("Hodge signatures have inconsistent channel counts")
    rng = np.random.default_rng(int(seed))
    result = np.empty(count, dtype=float)
    for sample in range(count):
        values = [
            _fast_covariance_matched_r4(
                sample_hodge_gaussian_channels(record, labels, rng)
            )
            for record in records
        ]
        result[sample] = float(np.median(values))
    return result
