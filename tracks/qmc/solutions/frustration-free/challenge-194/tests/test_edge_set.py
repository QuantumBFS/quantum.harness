from __future__ import annotations

import copy

import numba
import numpy as np
import pytest

from long_range_percolation.edge_set import (
    allocate_edge_set,
    build_class_start,
    edge_set_insert,
    edge_set_insert_kernel,
    encode_edge_id,
    validate_edge_set_state,
)


_MASK64 = (1 << 64) - 1


def _splitmix64_reference(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & _MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK64
    return (value ^ (value >> 31)) & _MASK64


def _reference_insert_all(
    values: np.ndarray, expected_size: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    capacity = 2
    while 10 * expected_size > 7 * capacity:
        capacity *= 2
    keys = np.zeros(capacity, dtype=np.uint64)
    occupied = np.zeros(capacity, dtype=np.uint8)
    size = 0
    total_probes = 0
    max_probe = 0
    rehashes = 0

    for raw_value in values:
        value = int(raw_value)
        while True:
            slot = _splitmix64_reference(value) & (capacity - 1)
            probe = 1
            while occupied[slot]:
                total_probes += 1
                max_probe = max(max_probe, probe)
                if int(keys[slot]) == value:
                    break
                slot = (slot + 1) & (capacity - 1)
                probe += 1
            else:
                total_probes += 1
                max_probe = max(max_probe, probe)
                if 10 * (size + 1) <= 7 * capacity:
                    keys[slot] = np.uint64(value)
                    occupied[slot] = np.uint8(1)
                    size += 1
                    break

                old_keys = keys
                old_occupied = occupied
                capacity *= 2
                keys = np.zeros(capacity, dtype=np.uint64)
                occupied = np.zeros(capacity, dtype=np.uint8)
                rehashes += 1
                for old_slot in range(old_keys.size):
                    if not old_occupied[old_slot]:
                        continue
                    old_value = int(old_keys[old_slot])
                    new_slot = _splitmix64_reference(old_value) & (capacity - 1)
                    rehash_probe = 1
                    while occupied[new_slot]:
                        total_probes += 1
                        max_probe = max(max_probe, rehash_probe)
                        new_slot = (new_slot + 1) & (capacity - 1)
                        rehash_probe += 1
                    total_probes += 1
                    max_probe = max(max_probe, rehash_probe)
                    keys[new_slot] = old_keys[old_slot]
                    occupied[new_slot] = np.uint8(1)
                continue
            break

    diagnostics = np.asarray(
        (capacity, size, total_probes, max_probe, rehashes),
        dtype=np.uint64,
    )
    return keys, occupied, diagnostics


def _insert_all(
    values: np.ndarray, expected_size: int = 1
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    keys, occupied, diagnostics = allocate_edge_set(expected_size)
    for value in values:
        keys, occupied, inserted = edge_set_insert(
            keys, occupied, diagnostics, value
        )
        assert inserted
    return keys, occupied, diagnostics


def test_edge_set_accepts_entire_uint64_domain_without_sentinel_collision():
    values = np.array([0, 1, 2**63, 2**64 - 2, 2**64 - 1], np.uint64)
    keys, occupied, diagnostics = allocate_edge_set(1)
    validate_edge_set_state(keys, occupied, diagnostics)
    for value in values:
        keys, occupied, inserted = edge_set_insert(
            keys, occupied, diagnostics, value
        )
        assert inserted
    for value in values:
        keys, occupied, inserted = edge_set_insert(
            keys, occupied, diagnostics, value
        )
        assert not inserted
    assert int(diagnostics[1]) == len(values)
    assert int(occupied.sum()) == len(values)
    assert int(diagnostics[0]) & (int(diagnostics[0]) - 1) == 0
    assert diagnostics[1] / diagnostics[0] <= 0.70


def test_growth_and_exact_probe_diagnostics_match_reference():
    collision_bucket = [
        value
        for value in range(10_000)
        if _splitmix64_reference(value) & 15 == 3
    ][:12]
    values = np.asarray(
        collision_bucket + collision_bucket[:3], dtype=np.uint64
    )
    actual_keys, actual_occupied, actual_diagnostics = _insert_all(
        values[:12], expected_size=1
    )
    for value in values[12:]:
        actual_keys, actual_occupied, inserted = edge_set_insert(
            actual_keys, actual_occupied, actual_diagnostics, value
        )
        assert not inserted

    expected_keys, expected_occupied, expected_diagnostics = (
        _reference_insert_all(values, expected_size=1)
    )
    np.testing.assert_array_equal(actual_keys, expected_keys)
    np.testing.assert_array_equal(actual_occupied, expected_occupied)
    np.testing.assert_array_equal(actual_diagnostics, expected_diagnostics)
    assert int(actual_diagnostics[1]) == 12
    assert int(actual_diagnostics[2]) >= int(actual_diagnostics[1])
    assert int(actual_diagnostics[3]) > 1
    assert int(actual_diagnostics[4]) > 0


def test_growth_is_deterministic_and_does_not_consume_rng():
    values = np.arange(10_000, dtype=np.uint64) * np.uint64(
        0x9E3779B97F4A7C15
    )
    np.random.seed(194)
    rng_state = copy.deepcopy(np.random.get_state())
    first = _insert_all(values)
    after_first = copy.deepcopy(np.random.get_state())
    second = _insert_all(values)
    after_second = copy.deepcopy(np.random.get_state())

    np.testing.assert_array_equal(first[0], second[0])
    np.testing.assert_array_equal(first[1], second[1])
    np.testing.assert_array_equal(first[2], second[2])
    for actual in (after_first, after_second):
        assert actual[0] == rng_state[0]
        np.testing.assert_array_equal(actual[1], rng_state[1])
        assert actual[2:] == rng_state[2:]


@pytest.mark.parametrize("expected_size", (-1, True, 1.0, 2**63))
def test_allocate_edge_set_rejects_invalid_or_unallocatable_sizes(expected_size):
    with pytest.raises(ValueError):
        allocate_edge_set(expected_size)


def test_insert_rejects_invalid_capacity_and_load_without_mutation():
    malformed_states = (
        (
            np.zeros(3, dtype=np.uint64),
            np.zeros(3, dtype=np.uint8),
            np.asarray((3, 0, 0, 0, 0), dtype=np.uint64),
        ),
        (
            np.zeros(4, dtype=np.uint64),
            np.zeros(2, dtype=np.uint8),
            np.asarray((4, 0, 0, 0, 0), dtype=np.uint64),
        ),
        (
            np.zeros(4, dtype=np.uint64),
            np.ones(4, dtype=np.uint8),
            np.asarray((4, 4, 0, 0, 0), dtype=np.uint64),
        ),
        (
            np.zeros(4, dtype=np.uint64),
            np.asarray((0, 2, 0, 0), dtype=np.uint8),
            np.asarray((4, 2, 0, 0, 0), dtype=np.uint64),
        ),
    )
    for keys, occupied, diagnostics in malformed_states:
        old_keys = keys.copy()
        old_occupied = occupied.copy()
        old_diagnostics = diagnostics.copy()
        with pytest.raises(ValueError):
            edge_set_insert(keys, occupied, diagnostics, np.uint64(7))
        np.testing.assert_array_equal(keys, old_keys)
        np.testing.assert_array_equal(occupied, old_occupied)
        np.testing.assert_array_equal(diagnostics, old_diagnostics)


def test_host_state_validation_rejects_wrong_dtype_dimension_and_layout():
    keys, occupied, diagnostics = allocate_edge_set(2)
    invalid_states = (
        (keys.astype(np.int64), occupied, diagnostics),
        (keys, occupied.astype(np.int8), diagnostics),
        (keys, occupied, diagnostics.astype(np.int64)),
        (keys.reshape(2, 2), occupied, diagnostics),
        (keys, occupied.reshape(2, 2), diagnostics),
        (keys, occupied, diagnostics.reshape(1, 5)),
        (np.zeros(8, dtype=np.uint64)[::2], occupied, diagnostics),
        (keys, np.zeros(8, dtype=np.uint8)[::2], diagnostics),
        (keys, occupied, np.zeros(10, dtype=np.uint64)[::2]),
    )
    for invalid in invalid_states:
        with pytest.raises(ValueError):
            validate_edge_set_state(*invalid)
        with pytest.raises(ValueError):
            edge_set_insert(*invalid, np.uint64(1))


def test_host_state_validation_rejects_readonly_and_aliased_arrays():
    keys, occupied, diagnostics = allocate_edge_set(2)
    for index in range(3):
        state = [keys.copy(), occupied.copy(), diagnostics.copy()]
        state[index].setflags(write=False)
        with pytest.raises(ValueError, match="writable"):
            validate_edge_set_state(*state)

    shared = np.zeros(4 * np.dtype(np.uint64).itemsize, dtype=np.uint8)
    aliased_keys = shared.view(np.uint64)
    aliased_occupied = shared[:4]
    aliased_diagnostics = np.asarray((4, 0, 0, 0, 0), dtype=np.uint64)
    with pytest.raises(ValueError, match="overlap"):
        validate_edge_set_state(
            aliased_keys, aliased_occupied, aliased_diagnostics
        )


def test_host_state_validation_rejects_inconsistent_diagnostics_and_corruption():
    keys, occupied, diagnostics = allocate_edge_set(2)
    invalid_diagnostics = (
        np.asarray((8, 0, 0, 0, 0), dtype=np.uint64),
        np.asarray((4, 1, 0, 0, 0), dtype=np.uint64),
        np.asarray((4, 0, 0, 1, 0), dtype=np.uint64),
        np.asarray((4, 0, 0, 0, 1), dtype=np.uint64),
    )
    for invalid in invalid_diagnostics:
        with pytest.raises(ValueError):
            validate_edge_set_state(keys, occupied, invalid)

    invalid_occupied = occupied.copy()
    invalid_occupied[0] = np.uint8(2)
    with pytest.raises(ValueError, match="zero or one"):
        validate_edge_set_state(keys, invalid_occupied, diagnostics)


def test_host_checked_insert_rejects_full_or_corrupt_state_without_hanging():
    keys = np.arange(4, dtype=np.uint64)
    occupied = np.ones(4, dtype=np.uint8)
    diagnostics = np.asarray((4, 4, 4, 1, 0), dtype=np.uint64)
    before = (keys.copy(), occupied.copy(), diagnostics.copy())
    with pytest.raises(ValueError, match="load"):
        edge_set_insert(keys, occupied, diagnostics, np.uint64(99))
    for actual, expected in zip(
        (keys, occupied, diagnostics), before, strict=True
    ):
        np.testing.assert_array_equal(actual, expected)


def test_each_probe_checked_add_fails_before_wrap_without_partial_mutation():
    capacity = 16
    collision_values = [
        value
        for value in range(100_000)
        if _splitmix64_reference(value) & (2 * capacity - 1) == 7
    ][:12]
    required_before_final_insert = 12 + sum(range(1, 12))
    assert required_before_final_insert > 2 * capacity + 1
    assert len(collision_values) == 12
    keys, occupied, diagnostics = allocate_edge_set(11)
    for value in collision_values[:11]:
        keys, occupied, inserted = edge_set_insert(
            keys, occupied, diagnostics, np.uint64(value)
        )
        assert inserted
    diagnostics[2] = np.uint64(_MASK64 - (2 * capacity + 1))
    before = (keys.copy(), occupied.copy(), diagnostics.copy())

    with pytest.raises(OverflowError, match="probe"):
        edge_set_insert_kernel(
            keys,
            occupied,
            diagnostics,
            np.uint64(collision_values[11]),
        )

    for actual, expected in zip(
        (keys, occupied, diagnostics), before, strict=True
    ):
        np.testing.assert_array_equal(actual, expected)


def test_class_starts_and_edge_ids_cover_exact_disjoint_range():
    for length in (2, 8, 256):
        multiplicity = np.full(length // 2, length, dtype=np.uint64)
        multiplicity[-1] = np.uint64(length // 2)
        class_start = build_class_start(multiplicity)
        assert class_start.dtype == np.dtype(np.uint64)
        assert class_start.flags.c_contiguous
        assert class_start.shape == (length // 2 + 1,)
        expected = 0
        encoded = []
        for distance_index, count in enumerate(multiplicity):
            assert int(class_start[distance_index]) == expected
            class_ids = [
                int(encode_edge_id(class_start, distance_index, offset))
                for offset in range(int(count))
            ]
            assert class_ids == list(range(expected, expected + int(count)))
            encoded.extend(class_ids)
            expected += int(count)
        assert int(class_start[-1]) == expected
        assert encoded == list(range(length * (length - 1) // 2))


def test_edge_id_rejects_oversized_offsets_for_middle_and_final_classes():
    class_start = build_class_start(
        np.asarray((4, 4, 2), dtype=np.uint64)
    )
    with pytest.raises(ValueError, match="offset"):
        encode_edge_id(class_start, 1, 4)
    with pytest.raises(ValueError, match="offset"):
        encode_edge_id(class_start, 2, 2)


def test_class_start_and_edge_id_validation_fail_closed():
    with pytest.raises(ValueError):
        build_class_start(np.asarray((1, 0), dtype=np.uint64))
    with pytest.raises(ValueError):
        build_class_start(
            np.asarray((2**64 - 1, 1), dtype=np.uint64)
        )
    class_start = build_class_start(np.asarray((4, 2), dtype=np.uint64))
    for distance_index, offset in (
        (-1, 0),
        (2, 0),
        (0, -1),
        (True, 0),
        (0.0, 0),
        (0, True),
        (0, 1.0),
    ):
        with pytest.raises(ValueError):
            encode_edge_id(class_start, distance_index, offset)
    with pytest.raises(ValueError):
        encode_edge_id(
            np.asarray((0, 4, 3), dtype=np.uint64), 0, 1
        )


def test_canonical_prefix_bounds_make_edge_id_addition_overflow_unreachable():
    class_start = build_class_start(
        np.asarray((_MASK64,), dtype=np.uint64)
    )
    assert int(encode_edge_id(class_start, 0, _MASK64 - 1)) == _MASK64 - 1
    with pytest.raises(ValueError, match="offset"):
        encode_edge_id(class_start, 0, _MASK64)
    with pytest.raises(ValueError):
        encode_edge_id(
            np.asarray((0, _MASK64, 0), dtype=np.uint64), 1, 0
        )


def test_edge_set_insert_kernel_matches_python_and_compiles_nopython():
    if numba.config.DISABLE_JIT:
        return
    values = np.asarray((0, 7, 2**63, 7, 2**64 - 1), dtype=np.uint64)
    compiled = allocate_edge_set(1)
    python = allocate_edge_set(1)
    compiled_results = []
    python_results = []
    for value in values:
        compiled_keys, compiled_occupied, inserted = edge_set_insert_kernel(
            compiled[0], compiled[1], compiled[2], value
        )
        compiled = (compiled_keys, compiled_occupied, compiled[2])
        compiled_results.append(inserted)
        python_keys, python_occupied, inserted = edge_set_insert_kernel.py_func(
            python[0], python[1], python[2], value
        )
        python = (python_keys, python_occupied, python[2])
        python_results.append(inserted)

    assert compiled_results == python_results
    for actual, expected in zip(compiled, python, strict=True):
        np.testing.assert_array_equal(actual, expected)
    assert edge_set_insert_kernel.nopython_signatures
