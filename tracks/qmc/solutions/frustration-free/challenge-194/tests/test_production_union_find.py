from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import numba
import numpy as np
import pytest

from long_range_percolation.observables import BasicObservables
from long_range_percolation.production_union_find import (
    _scan_basic_observables_kernel,
    allocate_union_find,
    scan_basic_observables,
    union_incremental,
    validate_union_find_state,
)
from long_range_percolation.union_find import UnionFind


def _expected_masks(length: int) -> np.ndarray:
    return np.asarray(
        [1 << min(3, (4 * index) // length) for index in range(length)],
        dtype=np.uint8,
    )


def _assert_matches_day0(
    state: tuple[np.ndarray, ...], reference: UnionFind
) -> BasicObservables:
    summary = scan_basic_observables(*state)
    labels = reference.labels()
    roots, sizes = np.unique(labels, return_counts=True)
    order = sorted(
        zip(sizes.tolist(), roots.tolist()), key=lambda item: (-item[0], item[1])
    )
    expected_masks = []
    vertex_masks = _expected_masks(labels.size)
    for root in roots:
        expected_masks.append(
            int(np.bitwise_or.reduce(vertex_masks[labels == root]))
        )

    expected_sum2 = float(sum(int(value) ** 2 for value in sizes))
    expected_sum4 = float(sum(int(value) ** 4 for value in sizes))
    assert summary.component_count == sizes.size
    assert summary.largest_size == order[0][0]
    assert summary.second_largest_size == (
        order[1][0] if len(order) > 1 else 0
    )
    assert summary.s1_fraction == order[0][0] / labels.size
    assert summary.s2_fraction == (
        order[1][0] / labels.size if len(order) > 1 else 0.0
    )
    assert summary.sum_size_sq == expected_sum2
    assert summary.sum_size_fourth == expected_sum4
    assert summary.q_g == expected_sum4 / expected_sum2**2
    assert summary.four_sector_crossing is (0b1111 in expected_masks)
    return summary


def test_allocate_union_find_has_fixed_array_schema_and_quarter_masks():
    state = allocate_union_find(8)
    parent, size, sector_mask, moments, counts = state
    assert [array.dtype for array in state] == [
        np.dtype(np.int64),
        np.dtype(np.int64),
        np.dtype(np.uint8),
        np.dtype(np.float64),
        np.dtype(np.int64),
    ]
    assert [array.shape for array in state] == [(8,), (8,), (8,), (2,), (3,)]
    assert all(array.flags.c_contiguous for array in state)
    assert all(array.flags.writeable for array in state)
    np.testing.assert_array_equal(parent, np.arange(8, dtype=np.int64))
    np.testing.assert_array_equal(size, np.ones(8, dtype=np.int64))
    np.testing.assert_array_equal(sector_mask, [1, 1, 2, 2, 4, 4, 8, 8])
    np.testing.assert_array_equal(moments, [8.0, 8.0])
    np.testing.assert_array_equal(counts, [0, 8, 1])


@pytest.mark.parametrize("length", [True, 0, -1, 2.0])
def test_allocate_union_find_rejects_invalid_lengths(length):
    with pytest.raises(ValueError, match="length"):
        allocate_union_find(length)


def test_incremental_state_matches_day0_after_every_unique_edge():
    state = allocate_union_find(8)
    reference = UnionFind(8)
    edges = [
        (0, 1),
        (2, 3),
        (1, 2),
        (4, 5),
        (6, 7),
        (5, 6),
        (0, 7),
        (1, 6),
    ]
    expected_merges = [True, True, True, True, True, True, True, False]
    for index, ((left, right), expected_merged) in enumerate(
        zip(edges, expected_merges), start=1
    ):
        state[4][0] += 1
        merged = union_incremental(*state, left, right)
        assert merged is expected_merged
        assert reference.union(left, right) is expected_merged
        summary = _assert_matches_day0(state, reference)
        assert summary.open_edges == index


def test_duplicate_accounting_is_owned_by_the_unique_insertion_caller():
    state = allocate_union_find(4)
    state[4][0] += 1
    assert union_incremental(*state, 0, 1) is True
    before = tuple(array.copy() for array in state)
    assert union_incremental(*state, 0, 1) is False
    assert state[4][0] == 1
    for actual, expected in zip(state, before):
        np.testing.assert_array_equal(actual, expected)


def test_equal_size_union_uses_smaller_root_and_path_halving():
    state = allocate_union_find(4)
    assert union_incremental(*state, 1, 0) is True
    assert union_incremental(*state, 3, 2) is True
    assert union_incremental(*state, 2, 0) is True
    assert state[0].tolist() == [0, 0, 0, 2]

    parent = np.asarray([0, 0, 1, 2], dtype=np.int64)
    size = np.asarray([4, 1, 1, 1], dtype=np.int64)
    sector_mask = np.asarray([15, 2, 4, 8], dtype=np.uint8)
    moments = np.asarray([16.0, 256.0], dtype=np.float64)
    counts = np.asarray([3, 1, 4], dtype=np.int64)
    assert (
        union_incremental(
            parent, size, sector_mask, moments, counts, 3, 0
        )
        is False
    )
    np.testing.assert_array_equal(parent, [0, 0, 1, 1])


def test_scan_uses_size_then_smallest_root_ties_and_exact_basic_schema():
    state = allocate_union_find(8)
    for left, right in [(1, 0), (3, 2), (4, 5)]:
        state[4][0] += 1
        union_incremental(*state, left, right)
    summary = scan_basic_observables(*state)
    assert summary == BasicObservables(
        open_edges=3,
        component_count=5,
        largest_size=2,
        second_largest_size=2,
        s1_fraction=0.25,
        s2_fraction=0.25,
        sum_size_sq=14.0,
        sum_size_fourth=50.0,
        q_g=50.0 / 14.0**2,
        four_sector_crossing=False,
    )


def test_four_sector_indicator_requires_one_component_with_all_bits():
    disconnected = allocate_union_find(8)
    disconnected[4][0] = 2
    union_incremental(*disconnected, 0, 2)
    union_incremental(*disconnected, 4, 6)
    assert scan_basic_observables(*disconnected).four_sector_crossing is False

    crossing = allocate_union_find(8)
    for edge in [(0, 2), (2, 4), (4, 6)]:
        crossing[4][0] += 1
        union_incremental(*crossing, *edge)
    assert scan_basic_observables(*crossing).four_sector_crossing is True


def test_l2_and_power_of_two_boundary_moments_do_not_integer_overflow():
    state = allocate_union_find(2)
    state[4][0] = 1
    union_incremental(*state, 0, 1)
    summary = scan_basic_observables(*state)
    assert summary.sum_size_sq == 4.0
    assert summary.sum_size_fourth == 16.0
    assert summary.second_largest_size == 0

    length = 2**18
    large = allocate_union_find(length)
    assert large[3].tolist() == [float(length), float(length)]
    half = length // 2
    large[0][:half] = 0
    large[0][half:] = half
    large[1][0] = half
    large[1][half] = half
    large[2][0] = np.uint8(0b0011)
    large[2][half] = np.uint8(0b1100)
    large[3][:] = [2.0 * float(half) ** 2, 2.0 * float(half) ** 4]
    large[4][:] = [length - 2, 2, half]
    assert union_incremental(*large, 0, half) is True
    boundary = scan_basic_observables(*large)
    assert boundary.sum_size_sq == float(length) ** 2
    assert boundary.sum_size_fourth == float(length) ** 4
    assert boundary.q_g == 1.0


@pytest.mark.parametrize(
    ("index", "replacement", "message"),
    [
        (0, np.arange(4, dtype=np.int32), "parent"),
        (1, np.ones((2, 2), dtype=np.int64), "size"),
        (2, np.ones(8, dtype=np.uint8)[::2], "sector_mask"),
        (3, np.ones(3, dtype=np.float64), "moments"),
        (4, np.ones(4, dtype=np.int64), "counts"),
    ],
)
def test_state_validation_rejects_wrong_dtype_shape_or_contiguity(
    index, replacement, message
):
    state = list(allocate_union_find(4))
    state[index] = replacement
    with pytest.raises(ValueError, match=message):
        validate_union_find_state(*state)
    with pytest.raises(ValueError, match=message):
        scan_basic_observables(*state)


def test_state_validation_rejects_overlap_invalid_values_and_moment_drift():
    state = list(allocate_union_find(4))
    state[1] = state[0]
    with pytest.raises(ValueError, match="overlap|share"):
        validate_union_find_state(*state)

    state = list(allocate_union_find(4))
    state[4][0] = -1
    with pytest.raises(ValueError, match="open_edges"):
        validate_union_find_state(*state)

    state = list(allocate_union_find(4))
    state[3][0] += 1.0e-10
    with pytest.raises(RuntimeError, match="moment"):
        scan_basic_observables(*state)


def test_incremental_rejects_out_of_range_endpoints_without_mutation():
    state = allocate_union_find(4)
    before = tuple(array.copy() for array in state)
    with pytest.raises(ValueError, match="range"):
        union_incremental(*state, -1, 2)
    with pytest.raises(ValueError, match="range"):
        union_incremental(*state, 1, 4)
    for actual, expected in zip(state, before):
        np.testing.assert_array_equal(actual, expected)


def test_numba_dispatchers_have_nopython_signatures_and_compiled_parity():
    if numba.config.DISABLE_JIT:
        pytest.skip("nopython signatures do not exist with JIT disabled")
    compiled_state = allocate_union_find(8)
    python_state = allocate_union_find(8)
    for left, right in [
        (0, 1),
        (2, 3),
        (1, 2),
        (4, 5),
        (6, 7),
        (5, 6),
        (0, 7),
        (1, 6),
    ]:
        compiled_state[4][0] += 1
        python_state[4][0] += 1
        compiled_merged = union_incremental(
            *compiled_state, left, right
        )
        python_merged = union_incremental.py_func(
            *python_state, left, right
        )
        assert compiled_merged is python_merged
        for actual, expected in zip(compiled_state, python_state):
            np.testing.assert_array_equal(actual, expected)
        assert _scan_basic_observables_kernel(
            *compiled_state
        ) == _scan_basic_observables_kernel.py_func(*python_state)

    @numba.njit(cache=False, boundscheck=True, fastmath=False)
    def compiled_step(parent, size, sector_mask, moments, counts):
        counts[0] += 1
        merged = union_incremental(
            parent, size, sector_mask, moments, counts, 0, 3
        )
        scan = _scan_basic_observables_kernel(
            parent, size, sector_mask, moments, counts
        )
        return merged, scan

    state = allocate_union_find(4)
    merged, scan = compiled_step(*state)
    assert merged is True
    assert scan[0] == 0
    assert scan[1:5] == (1, 3, 2, 1)
    assert union_incremental.nopython_signatures
    assert _scan_basic_observables_kernel.nopython_signatures
    assert compiled_step.nopython_signatures


def test_disabled_jit_matches_expected_python_semantics():
    project = Path(__file__).resolve().parents[1]
    script = """
import json
from long_range_percolation.production_union_find import (
    allocate_union_find, scan_basic_observables, union_incremental,
)
state = allocate_union_find(4)
for left, right in ((0, 1), (2, 3), (0, 2)):
    state[4][0] += 1
    union_incremental(*state, left, right)
summary = scan_basic_observables(*state)
print(json.dumps([
    state[0].tolist(), state[1].tolist(), state[2].tolist(),
    state[3].tolist(), state[4].tolist(), summary.__dict__,
], sort_keys=True))
"""
    environment = os.environ.copy()
    environment["NUMBA_DISABLE_JIT"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload[:5] == [
        [0, 0, 0, 2],
        [4, 1, 2, 1],
        [15, 2, 12, 8],
        [16.0, 256.0],
        [3, 1, 4],
    ]
    assert payload[5] == {
        "component_count": 1,
        "four_sector_crossing": True,
        "largest_size": 4,
        "open_edges": 3,
        "q_g": 1.0,
        "s1_fraction": 1.0,
        "s2_fraction": 0.0,
        "second_largest_size": 0,
        "sum_size_fourth": 256.0,
        "sum_size_sq": 16.0,
    }
