from __future__ import annotations

import math
import sys

import numba
import numpy as np
import numpy.typing as npt

from .observables import BasicObservables


I64 = npt.NDArray[np.int64]
U8 = npt.NDArray[np.uint8]
F64 = npt.NDArray[np.float64]

_I64_C = numba.types.Array(numba.int64, 1, "C")
_U8_C = numba.types.Array(numba.uint8, 1, "C")
_F64_C = numba.types.Array(numba.float64, 1, "C")
_UNION_SIGNATURE = numba.boolean(
    _I64_C,
    _I64_C,
    _U8_C,
    _F64_C,
    _I64_C,
    numba.int64,
    numba.int64,
)
_SCAN_RESULT = numba.types.Tuple(
    (
        numba.int64,
        numba.int64,
        numba.int64,
        numba.int64,
        numba.int64,
        numba.float64,
        numba.float64,
        numba.float64,
        numba.boolean,
    )
)
_SCAN_SIGNATURE = _SCAN_RESULT(_I64_C, _I64_C, _U8_C, _F64_C, _I64_C)
_EPSILON = np.finfo(np.float64).eps
_MAX_INT64 = np.iinfo(np.int64).max


def allocate_union_find(length: int) -> tuple[I64, I64, U8, F64, I64]:
    if (
        isinstance(length, (bool, np.bool_))
        or not isinstance(length, (int, np.integer))
        or int(length) < 1
        or int(length) > min(sys.maxsize, _MAX_INT64)
    ):
        raise ValueError("length must be a positive addressable integer")
    length_value = int(length)

    parent = np.arange(length_value, dtype=np.int64)
    size = np.ones(length_value, dtype=np.int64)
    vertices = np.arange(length_value, dtype=np.int64)
    sector = np.minimum(3, (4 * vertices) // length_value)
    sector_mask = np.left_shift(
        np.uint8(1), sector.astype(np.uint8)
    ).astype(np.uint8)
    moments = np.asarray(
        (float(length_value), float(length_value)), dtype=np.float64
    )
    counts = np.asarray((0, length_value, 1), dtype=np.int64)
    validate_union_find_state(parent, size, sector_mask, moments, counts)
    return parent, size, sector_mask, moments, counts


def validate_union_find_state(
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
) -> None:
    arrays = (
        (parent, np.dtype(np.int64), "parent"),
        (size, np.dtype(np.int64), "size"),
        (sector_mask, np.dtype(np.uint8), "sector_mask"),
        (moments, np.dtype(np.float64), "moments"),
        (counts, np.dtype(np.int64), "counts"),
    )
    for array, dtype, name in arrays:
        if not isinstance(array, np.ndarray) or array.dtype != dtype:
            raise ValueError(f"{name} must be a {dtype.name} NumPy array")
        if array.ndim != 1:
            raise ValueError(f"{name} must be one-dimensional")
        if not array.flags.c_contiguous:
            raise ValueError(f"{name} must be C-contiguous")
        if not array.flags.writeable:
            raise ValueError(f"{name} must be writable")

    length = parent.size
    if length < 1:
        raise ValueError("parent must be nonempty")
    if size.shape != (length,):
        raise ValueError("size must have the same shape as parent")
    if sector_mask.shape != (length,):
        raise ValueError("sector_mask must have the same shape as parent")
    if moments.shape != (2,):
        raise ValueError("moments must have shape (2,)")
    if counts.shape != (3,):
        raise ValueError("counts must have shape (3,)")

    state_arrays = (parent, size, sector_mask, moments, counts)
    for left in range(len(state_arrays)):
        for right in range(left + 1, len(state_arrays)):
            if np.shares_memory(state_arrays[left], state_arrays[right]):
                raise ValueError("union-find arrays must not overlap or share memory")

    if np.any(parent < 0) or np.any(parent >= length):
        raise ValueError("parent contains an out-of-range index")
    if np.any(size < 1) or np.any(size > length):
        raise ValueError("size contains an out-of-range component size")
    if np.any(sector_mask == 0) or np.any(sector_mask > np.uint8(0b1111)):
        raise ValueError("sector_mask must contain nonzero four-bit masks")
    if not np.all(np.isfinite(moments)) or np.any(moments < 1.0):
        raise ValueError("moments must contain finite positive values")

    open_edges = int(counts[0])
    component_count = int(counts[1])
    largest_size = int(counts[2])
    maximum_edges = length * (length - 1) // 2
    if not 0 <= open_edges <= maximum_edges:
        raise ValueError("open_edges is outside the simple-graph range")
    if not 1 <= component_count <= length:
        raise ValueError("component_count is outside the valid range")
    if not 1 <= largest_size <= length:
        raise ValueError("largest_size is outside the valid range")


@numba.njit(
    _UNION_SIGNATURE, cache=True, boundscheck=True, fastmath=False
)
def union_incremental(
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
    left: int,
    right: int,
) -> bool:
    length = len(parent)
    if (
        len(size) != length
        or len(sector_mask) != length
        or len(moments) != 2
        or len(counts) != 3
    ):
        raise ValueError("union-find state arrays have inconsistent shapes")
    if (
        counts[0] < 0
        or counts[1] < 1
        or counts[1] > length
        or counts[2] < 1
        or counts[2] > length
        or not math.isfinite(moments[0])
        or not math.isfinite(moments[1])
    ):
        raise ValueError("union-find counters or moments are invalid")
    if left < 0 or left >= length or right < 0 or right >= length:
        raise ValueError("union endpoint is out of range")

    root_left = left
    steps = 0
    while parent[root_left] != root_left:
        ancestor = parent[root_left]
        if ancestor < 0 or ancestor >= length:
            raise ValueError("parent contains an out-of-range index")
        grandparent = parent[ancestor]
        if grandparent < 0 or grandparent >= length:
            raise ValueError("parent contains an out-of-range index")
        parent[root_left] = grandparent
        root_left = grandparent
        steps += 1
        if steps > length:
            raise ValueError("parent does not describe a forest")

    root_right = right
    steps = 0
    while parent[root_right] != root_right:
        ancestor = parent[root_right]
        if ancestor < 0 or ancestor >= length:
            raise ValueError("parent contains an out-of-range index")
        grandparent = parent[ancestor]
        if grandparent < 0 or grandparent >= length:
            raise ValueError("parent contains an out-of-range index")
        parent[root_right] = grandparent
        root_right = grandparent
        steps += 1
        if steps > length:
            raise ValueError("parent does not describe a forest")

    if root_left == root_right:
        return False

    size_left = size[root_left]
    size_right = size[root_right]
    if (
        size_left < 1
        or size_right < 1
        or size_left > length
        or size_right > length
        or size_left > length - size_right
    ):
        raise OverflowError("component sizes exceed the union-find length")
    if size_left < size_right or (
        size_left == size_right and root_left > root_right
    ):
        root_left, root_right = root_right, root_left
        size_left, size_right = size_right, size_left

    merged_size = size_left + size_right
    left_float = float(size_left)
    right_float = float(size_right)
    merged_float = float(merged_size)
    new_sum_sq = moments[0] + (
        merged_float * merged_float
        - left_float * left_float
        - right_float * right_float
    )
    new_sum_fourth = moments[1] + (
        merged_float**4 - left_float**4 - right_float**4
    )
    if not math.isfinite(new_sum_sq) or not math.isfinite(new_sum_fourth):
        raise OverflowError("component moments exceed float64")
    if counts[1] <= 1:
        raise ValueError("component_count cannot be decremented")

    parent[root_right] = root_left
    size[root_left] = merged_size
    sector_mask[root_left] = sector_mask[root_left] | sector_mask[root_right]
    moments[0] = new_sum_sq
    moments[1] = new_sum_fourth
    counts[1] -= 1
    if merged_size > counts[2]:
        counts[2] = merged_size
    return True


@numba.njit(
    _SCAN_SIGNATURE, cache=True, boundscheck=True, fastmath=False
)
def _scan_basic_observables_kernel(
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
) -> tuple[int, int, int, int, int, float, float, float, bool]:
    length = len(parent)
    component_count = 0
    largest_size = 0
    second_largest_size = 0
    sum_size = 0
    sum_size_sq = 0.0
    sum_size_fourth = 0.0
    four_sector_crossing = False

    for index in range(length):
        if parent[index] < 0 or parent[index] >= length:
            return (1, 0, 0, 0, 0, 0.0, 0.0, 0.0, False)
        if parent[index] != index:
            continue
        component_size = size[index]
        if component_size < 1 or component_size > length:
            return (2, 0, 0, 0, 0, 0.0, 0.0, 0.0, False)
        component_count += 1
        sum_size += component_size
        component_float = float(component_size)
        sum_size_sq += component_float * component_float
        sum_size_fourth += component_float**4

        if component_size > largest_size:
            second_largest_size = largest_size
            largest_size = component_size
        elif component_size > second_largest_size:
            second_largest_size = component_size
        if sector_mask[index] == np.uint8(0b1111):
            four_sector_crossing = True

    if component_count != counts[1] or sum_size != length:
        return (3, 0, 0, 0, 0, 0.0, 0.0, 0.0, False)
    if largest_size != counts[2]:
        return (4, 0, 0, 0, 0, 0.0, 0.0, 0.0, False)
    tolerance_sq = 32.0 * _EPSILON * max(1.0, sum_size_sq)
    tolerance_fourth = 32.0 * _EPSILON * max(1.0, sum_size_fourth)
    if (
        not math.isfinite(moments[0])
        or abs(moments[0] - sum_size_sq) > tolerance_sq
    ):
        return (5, 0, 0, 0, 0, 0.0, 0.0, 0.0, False)
    if (
        not math.isfinite(moments[1])
        or abs(moments[1] - sum_size_fourth) > tolerance_fourth
    ):
        return (6, 0, 0, 0, 0, 0.0, 0.0, 0.0, False)

    q_g = sum_size_fourth / (sum_size_sq * sum_size_sq)
    return (
        0,
        counts[0],
        component_count,
        largest_size,
        second_largest_size,
        sum_size_sq,
        sum_size_fourth,
        q_g,
        four_sector_crossing,
    )


def scan_basic_observables(
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
) -> BasicObservables:
    validate_union_find_state(parent, size, sector_mask, moments, counts)
    (
        status,
        open_edges,
        component_count,
        largest_size,
        second_largest_size,
        sum_size_sq,
        sum_size_fourth,
        q_g,
        four_sector_crossing,
    ) = _scan_basic_observables_kernel(
        parent, size, sector_mask, moments, counts
    )
    if status != 0:
        detail = {
            1: "parent index",
            2: "root size",
            3: "component count",
            4: "largest size",
            5: "sum-size-squared moment",
            6: "sum-size-fourth moment",
        }.get(int(status), "unknown state")
        raise RuntimeError(
            f"union-find checkpoint scan failed with status {status} "
            f"({detail}); "
            "incremental state does not match its exact root scan"
        )
    length = parent.size
    return BasicObservables(
        open_edges=int(open_edges),
        component_count=int(component_count),
        largest_size=int(largest_size),
        second_largest_size=int(second_largest_size),
        s1_fraction=float(largest_size) / float(length),
        s2_fraction=float(second_largest_size) / float(length),
        sum_size_sq=float(sum_size_sq),
        sum_size_fourth=float(sum_size_fourth),
        q_g=float(q_g),
        four_sector_crossing=bool(four_sector_crossing),
    )
