from __future__ import annotations

from hashlib import sha256
import math

import numba
import numpy as np
import pytest

from long_range_percolation.alias import build_distance_alias, draw_alias
from long_range_percolation.counter_rng import (
    STREAM_ALIAS_COLUMN,
    STREAM_ALIAS_THRESHOLD,
    StreamIdentity,
    derive_stream_material,
    next_u32,
    u32_to_open,
)
from long_range_percolation.kernel import (
    kernel_weight_sum,
    periodic_kernel,
)
from long_range_percolation.model import distance_classes


def digest(array: np.ndarray) -> str:
    return sha256(array.tobytes()).hexdigest()


def _draw_alias_reference(
    probability: np.ndarray,
    alias: np.ndarray,
    column_word: np.uint32,
    threshold_word: np.uint32,
) -> int:
    column = (int(column_word) * len(probability)) >> 32
    if u32_to_open(threshold_word) <= probability[column]:
        return column
    return int(alias[column])


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _compiled_frequency_draws(
    probability: np.ndarray,
    alias: np.ndarray,
    sample_count: int,
    column_counter: np.ndarray,
    column_key: np.ndarray,
    threshold_counter: np.ndarray,
    threshold_key: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    class_count = len(probability)
    counts = np.zeros(class_count, dtype=np.uint64)
    column_block = np.zeros(4, dtype=np.uint32)
    column_lane = np.zeros(2, dtype=np.uint8)
    column_accounting = np.zeros(3, dtype=np.uint64)
    threshold_block = np.zeros(4, dtype=np.uint32)
    threshold_lane = np.zeros(2, dtype=np.uint8)
    threshold_accounting = np.zeros(3, dtype=np.uint64)
    rejection_threshold = (
        np.uint64(1 << 32) - np.uint64(class_count)
    ) % np.uint64(class_count)

    for _ in range(sample_count):
        while True:
            column_word = next_u32(
                column_counter,
                column_key,
                column_block,
                column_lane,
                column_accounting,
            )
            product = np.uint64(column_word) * np.uint64(class_count)
            low = product & np.uint64(0xFFFFFFFF)
            if low < rejection_threshold:
                column_accounting[2] += np.uint64(1)
                continue
            break
        threshold_word = next_u32(
            threshold_counter,
            threshold_key,
            threshold_block,
            threshold_lane,
            threshold_accounting,
        )
        selected = draw_alias(
            probability, alias, column_word, threshold_word
        )
        counts[selected] += np.uint64(1)

    return counts, np.asarray(
        (
            column_accounting[0],
            column_accounting[2],
            threshold_accounting[0],
        ),
        dtype=np.uint64,
    )


def test_alias_table_is_deterministic_defensive_and_read_only():
    kernel = periodic_kernel(256, 0.9)
    first = build_distance_alias(256, 0.9, kernel, digest(kernel))
    second = build_distance_alias(
        256, 0.9, kernel.copy(), first.kernel_sha256
    )

    np.testing.assert_array_equal(first.probability, second.probability)
    np.testing.assert_array_equal(first.alias, second.alias)
    np.testing.assert_array_equal(first.multiplicity, second.multiplicity)
    np.testing.assert_array_equal(first.class_weight, second.class_weight)
    assert first.kernel_sha256 == digest(kernel)
    for array in (
        first.probability,
        first.alias,
        first.multiplicity,
        first.class_weight,
    ):
        assert array.flags.c_contiguous
        assert not array.flags.writeable

    kernel[:] = 1.0
    assert first.kernel_sha256 != digest(kernel)
    assert not np.all(first.class_weight == first.multiplicity)


def test_alias_invariants_cover_antipodal_class_and_finite_extremes():
    for length, sigma in [
        (2, 1.0),
        (256, math.ulp(1.0)),
        (256, 96.0),
    ]:
        kernel = periodic_kernel(length, sigma)
        table = build_distance_alias(length, sigma, kernel, digest(kernel))
        expected_multiplicity = np.asarray(
            [item.multiplicity for item in distance_classes(length)],
            dtype=np.uint64,
        )
        expected_weight = expected_multiplicity * kernel

        assert table.probability.dtype == np.dtype(np.float64)
        assert table.alias.dtype == np.dtype(np.int64)
        assert table.multiplicity.dtype == np.dtype(np.uint64)
        assert table.class_weight.dtype == np.dtype(np.float64)
        assert np.all(
            (0.0 <= table.probability) & (table.probability <= 1.0)
        )
        assert np.all(
            (0 <= table.alias) & (table.alias < length // 2)
        )
        np.testing.assert_array_equal(
            table.multiplicity, expected_multiplicity
        )
        np.testing.assert_array_equal(table.class_weight, expected_weight)
        assert int(table.multiplicity[-1]) == length // 2
        assert int(table.multiplicity.sum()) == length * (length - 1) // 2
        assert table.total_rate == math.fsum(
            float(value) for value in table.class_weight
        )
        assert table.total_rate == pytest.approx(
            kernel_weight_sum(length, sigma), rel=2e-13
        )
        assert abs(table.normalized_residual) <= 8 * np.finfo(float).eps
        implied_probability = np.zeros(length // 2, dtype=np.float64)
        for column in range(length // 2):
            implied_probability[column] += (
                table.probability[column] / (length // 2)
            )
            implied_probability[table.alias[column]] += (
                1.0 - table.probability[column]
            ) / (length // 2)
        np.testing.assert_allclose(
            implied_probability,
            table.class_weight / table.total_rate,
            rtol=2e-13,
            atol=0.0,
        )


@pytest.mark.parametrize(
    ("replacement", "message"),
    (
        (np.ones(3, dtype=np.float64), "shape"),
        (np.asarray((1.0, np.nan), dtype=np.float64), "finite positive"),
        (np.asarray((1.0, 0.0), dtype=np.float64), "finite positive"),
        (np.asarray((1.0, np.inf), dtype=np.float64), "finite positive"),
    ),
)
def test_alias_builder_rejects_invalid_kernel_values(
    replacement: np.ndarray, message: str
):
    with pytest.raises(ValueError, match=message):
        build_distance_alias(4, 1.0, replacement, digest(replacement))


def test_alias_builder_rejects_kernel_digest_mismatch():
    kernel = periodic_kernel(8, 0.9)
    with pytest.raises(ValueError, match="SHA-256"):
        build_distance_alias(8, 0.9, kernel, "0" * 64)


def test_draw_alias_matches_python_at_boundaries_and_compiles_nopython():
    probability = np.asarray((0.0, 0.5, 1.0), dtype=np.float64)
    alias = np.asarray((2, 0, 1), dtype=np.int64)
    cases = (
        (np.uint32(0), np.uint32(0)),
        (np.uint32(0x55555555), np.uint32(0x7FFFFFFF)),
        (np.uint32(0xAAAAAAAA), np.uint32(0xFFFFFFFF)),
        (np.uint32(0xFFFFFFFF), np.uint32(0xFFFFFFFF)),
    )
    for column_word, threshold_word in cases:
        assert draw_alias(
            probability, alias, column_word, threshold_word
        ) == _draw_alias_reference(
            probability, alias, column_word, threshold_word
        )
    if not numba.config.DISABLE_JIT:
        assert draw_alias.nopython_signatures


def test_fixed_philox_alias_frequencies_pass_one_simultaneous_threshold():
    length = 256
    sigma = 0.9
    sample_count = 2_000_000
    kernel = periodic_kernel(length, sigma)
    table = build_distance_alias(length, sigma, kernel, digest(kernel))
    column_material = derive_stream_material(
        StreamIdentity(
            194,
            "validation",
            length,
            "alias-sigma-0.9",
            0,
            STREAM_ALIAS_COLUMN,
        )
    )
    threshold_material = derive_stream_material(
        StreamIdentity(
            194,
            "validation",
            length,
            "alias-sigma-0.9",
            0,
            STREAM_ALIAS_THRESHOLD,
        )
    )
    observed, accounting = _compiled_frequency_draws(
        table.probability,
        table.alias,
        sample_count,
        column_material.initial_counter.copy(),
        column_material.key,
        threshold_material.initial_counter.copy(),
        threshold_material.key,
    )
    expected = table.class_weight / table.total_rate
    absolute_error = np.abs(observed / sample_count - expected)
    epsilon = math.sqrt(
        math.log(2 * len(expected) / 0.001) / (2 * sample_count)
    )
    evidence = [
        {
            "class": index + 1,
            "observed_count": int(observed[index]),
            "expected_probability": float(expected[index]),
            "absolute_error": float(absolute_error[index]),
            "threshold": epsilon,
            "margin": float(epsilon - absolute_error[index]),
        }
        for index in range(len(expected))
    ]

    assert int(accounting[0]) == sample_count + int(accounting[1])
    assert int(accounting[2]) == sample_count
    assert float(absolute_error.max()) <= epsilon, evidence
    if not numba.config.DISABLE_JIT:
        assert _compiled_frequency_draws.nopython_signatures
