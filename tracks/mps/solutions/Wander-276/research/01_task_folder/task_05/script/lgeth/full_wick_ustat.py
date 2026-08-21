"""Gauge-invariant complete-Wick contractions across disorder realizations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .wick_channels import four_channel_tensor


@dataclass(frozen=True)
class ResponseFactors:
    """Ambient response ``A_m = X_m U^dagger`` stored as thin factors."""

    frame: np.ndarray
    channels: np.ndarray

    def __post_init__(self) -> None:
        frame = np.asarray(self.frame, dtype=complex)
        channels = np.asarray(self.channels, dtype=complex)
        if frame.ndim != 2 or min(frame.shape) < 1:
            raise ValueError("BPS frame has invalid dimensions")
        if channels.ndim != 3 or min(channels.shape) < 1:
            raise ValueError("response channels have invalid dimensions")
        if channels.shape[1:] != frame.shape:
            raise ValueError("response and BPS frame dimensions disagree")
        if not (
            np.all(np.isfinite(frame.real))
            and np.all(np.isfinite(frame.imag))
            and np.all(np.isfinite(channels.real))
            and np.all(np.isfinite(channels.imag))
        ):
            raise ValueError("response factors must be finite")
        gram = frame.conj().T @ frame
        if not np.allclose(
            gram,
            np.eye(frame.shape[1]),
            atol=2e-10,
            rtol=2e-10,
        ):
            raise ValueError("BPS frame is not orthonormal")
        object.__setattr__(self, "frame", frame)
        object.__setattr__(self, "channels", channels)

    @property
    def label_count(self) -> int:
        return int(self.channels.shape[0])

    @property
    def ambient_dimension(self) -> int:
        return int(self.frame.shape[0])

    @property
    def target_rank(self) -> int:
        return int(self.frame.shape[1])


def _validate_pair(
    first: ResponseFactors,
    second: ResponseFactors,
) -> None:
    if first.label_count != second.label_count:
        raise ValueError("response factors have different channel counts")
    if first.ambient_dimension != second.ambient_dimension:
        raise ValueError("response factors do not share an ambient Hilbert space")


def _normalizer(
    first: ResponseFactors,
    second: ResponseFactors,
) -> float:
    return float(np.sqrt(first.target_rank * second.target_rank))


def ambient_channels(factors: ResponseFactors) -> np.ndarray:
    """Materialize ``A_m = X_m U^dagger`` for reduced references only."""

    return np.einsum(
        "mai,bi->mab",
        factors.channels,
        factors.frame.conj(),
        optimize=True,
    )


def self_tensor(factors: ResponseFactors) -> np.ndarray:
    """Return the registered one-realization four-channel tensor."""

    return four_channel_tensor(factors.channels)


def dense_pairings(
    first: ResponseFactors,
    second: ResponseFactors,
) -> np.ndarray:
    """Return all three Wick pairings after materializing ambient operators."""

    _validate_pair(first, second)
    first_ambient = ambient_channels(first)
    second_ambient = ambient_channels(second)
    labels = first.label_count
    scale = _normalizer(first, second)
    result = np.empty((3, labels, labels, labels, labels), dtype=complex)
    for a in range(labels):
        first_dagger = first_ambient[a].conj().T
        for b in range(labels):
            first_target = first_dagger @ first_ambient[b]
            first_second_cross = first_dagger @ second_ambient[b]
            for c in range(labels):
                second_c_dagger = second_ambient[c].conj().T
                first_c_dagger = first_ambient[c].conj().T
                second_external = first_ambient[a].conj().T
                for d in range(labels):
                    result[0, a, b, c, d] = np.trace(
                        first_target
                        @ second_c_dagger
                        @ second_ambient[d]
                    ) / scale
                    result[1, a, b, c, d] = np.trace(
                        first_ambient[d]
                        @ second_external
                        @ second_ambient[b]
                        @ second_c_dagger
                    ) / scale
                    result[2, a, b, c, d] = np.trace(
                        first_second_cross
                        @ first_c_dagger
                        @ second_ambient[d]
                    ) / scale
    return result


def _cross_channel_grams(
    left: np.ndarray,
    right: np.ndarray,
    block_size: int,
) -> np.ndarray:
    left_values = np.asarray(left, dtype=complex)
    right_values = np.asarray(right, dtype=complex)
    if left_values.ndim != 3 or right_values.ndim != 3:
        raise ValueError("cross-channel factors must have rank three")
    if left_values.shape[1] != right_values.shape[1]:
        raise ValueError("cross-channel factors have different ambient dimensions")
    size = int(block_size)
    if size < 1:
        raise ValueError("block size must be positive")
    result = np.zeros(
        (
            left_values.shape[0],
            right_values.shape[0],
            left_values.shape[2],
            right_values.shape[2],
        ),
        dtype=complex,
    )
    for start in range(0, left_values.shape[1], size):
        stop = min(start + size, left_values.shape[1])
        result += np.einsum(
            "mai,naj->mnij",
            left_values[:, start:stop].conj(),
            right_values[:, start:stop],
            optimize=True,
        )
    return result


def factorized_pairings(
    first: ResponseFactors,
    second: ResponseFactors,
    block_size: int,
) -> np.ndarray:
    """Return complete pairings without forming an ambient square operator."""

    _validate_pair(first, second)
    size = int(block_size)
    if size < 1:
        raise ValueError("block size must be positive")
    first_grams = _cross_channel_grams(
        first.channels,
        first.channels,
        size,
    )
    second_grams = _cross_channel_grams(
        second.channels,
        second.channels,
        size,
    )
    first_second = _cross_channel_grams(
        first.channels,
        second.channels,
        size,
    )
    second_first = _cross_channel_grams(
        second.channels,
        first.channels,
        size,
    )
    overlap = first.frame.conj().T @ second.frame
    reverse_overlap = overlap.conj().T
    labels = first.label_count
    scale = _normalizer(first, second)
    result = np.empty((3, labels, labels, labels, labels), dtype=complex)
    for a in range(labels):
        for b in range(labels):
            for c in range(labels):
                for d in range(labels):
                    result[0, a, b, c, d] = np.trace(
                        first_grams[a, b]
                        @ overlap
                        @ second_grams[c, d]
                        @ reverse_overlap
                    ) / scale
                    result[1, a, b, c, d] = np.trace(
                        first_second[a, b] @ second_first[c, d]
                    ) / scale
                    result[2, a, b, c, d] = np.trace(
                        first_second[a, b]
                        @ reverse_overlap
                        @ first_second[c, d]
                        @ reverse_overlap
                    ) / scale
    return result


def streamed_pairings(
    first: ResponseFactors,
    second: ResponseFactors,
    block_size: int,
) -> np.ndarray:
    """Return complete pairings with only two full channel-Gram families."""

    _validate_pair(first, second)
    size = int(block_size)
    if size < 1:
        raise ValueError("block size must be positive")
    second_grams = _cross_channel_grams(
        second.channels,
        second.channels,
        size,
    )
    first_second = _cross_channel_grams(
        first.channels,
        second.channels,
        size,
    )
    overlap = first.frame.conj().T @ second.frame
    reverse_overlap = overlap.conj().T
    labels = first.label_count
    scale = _normalizer(first, second)
    result = np.empty((3, labels, labels, labels, labels), dtype=complex)
    for a in range(labels):
        for b in range(labels):
            first_gram = _cross_channel_grams(
                first.channels[a : a + 1],
                first.channels[b : b + 1],
                size,
            )[0, 0]
            for c in range(labels):
                for d in range(labels):
                    result[0, a, b, c, d] = np.trace(
                        first_gram
                        @ overlap
                        @ second_grams[c, d]
                        @ reverse_overlap
                    ) / scale
                    result[1, a, b, c, d] = np.trace(
                        first_second[a, b]
                        @ first_second[d, c].conj().T
                    ) / scale
                    result[2, a, b, c, d] = np.trace(
                        first_second[a, b]
                        @ reverse_overlap
                        @ first_second[c, d]
                        @ reverse_overlap
                    ) / scale
    return result


def symmetrized_pairings(
    first: ResponseFactors,
    second: ResponseFactors,
    block_size: int,
) -> np.ndarray:
    """Return the sum of the two ordered-pair Wick tensors."""

    return factorized_pairings(first, second, block_size) + factorized_pairings(
        second,
        first,
        block_size,
    )
