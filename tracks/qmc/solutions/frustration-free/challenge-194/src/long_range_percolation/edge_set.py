from __future__ import annotations

import sys

import numba
import numpy as np
import numpy.typing as npt


U8 = npt.NDArray[np.uint8]
U64 = npt.NDArray[np.uint64]

_MAX_UINT64 = (1 << 64) - 1
_MAX_CAPACITY = 1 << ((sys.maxsize // np.dtype(np.uint64).itemsize).bit_length() - 1)
_LOW32 = np.uint64(0xFFFFFFFF)


def validate_edge_set_state(
    keys: U64, occupied: U8, diagnostics: U64
) -> None:
    arrays = (
        (keys, np.dtype(np.uint64), "keys"),
        (occupied, np.dtype(np.uint8), "occupied"),
        (diagnostics, np.dtype(np.uint64), "diagnostics"),
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

    if diagnostics.shape != (5,):
        raise ValueError("diagnostics must have shape (5,)")
    if (
        np.shares_memory(keys, occupied)
        or np.shares_memory(keys, diagnostics)
        or np.shares_memory(occupied, diagnostics)
    ):
        raise ValueError("edge-set arrays must not overlap or share memory")

    capacity = keys.size
    if (
        capacity < 2
        or capacity != occupied.size
        or capacity & (capacity - 1)
        or int(diagnostics[0]) != capacity
    ):
        raise ValueError("edge-set capacity state is invalid")
    if np.any(occupied > np.uint8(1)):
        raise ValueError("occupied must contain only zero or one")

    occupied_count = int(np.count_nonzero(occupied))
    size = int(diagnostics[1])
    if occupied_count != size:
        raise ValueError("edge-set size does not match occupied count")
    if 10 * size > 7 * capacity:
        raise ValueError("edge-set load exceeds 0.70")

    total_probes = int(diagnostics[2])
    max_probe = int(diagnostics[3])
    rehashes = int(diagnostics[4])
    if max_probe > total_probes:
        raise ValueError("max_probe exceeds total_probes")
    if size > total_probes:
        raise ValueError("size exceeds total_probes")
    if size == 0 and (total_probes != 0 or max_probe != 0 or rehashes != 0):
        raise ValueError("empty edge-set diagnostics are inconsistent")


def allocate_edge_set(expected_size: int) -> tuple[U64, U8, U64]:
    if (
        isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
        or expected_size < 0
    ):
        raise ValueError("expected_size must be a nonnegative integer")

    capacity = 2
    while 10 * expected_size > 7 * capacity:
        if capacity >= _MAX_CAPACITY:
            raise ValueError("edge-set capacity exceeds the addressable range")
        capacity *= 2

    keys = np.zeros(capacity, dtype=np.uint64)
    occupied = np.zeros(capacity, dtype=np.uint8)
    diagnostics = np.asarray(
        (capacity, 0, 0, 0, 0), dtype=np.uint64
    )
    validate_edge_set_state(keys, occupied, diagnostics)
    return keys, occupied, diagnostics


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _add_u64(left: np.uint64, right: np.uint64) -> np.uint64:
    low_sum = (left & _LOW32) + (right & _LOW32)
    low = low_sum & _LOW32
    carry = low_sum >> np.uint64(32)
    high = (
        (left >> np.uint64(32))
        + (right >> np.uint64(32))
        + carry
    ) & _LOW32
    return np.uint64((high << np.uint64(32)) | low)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _multiply_u64(left: np.uint64, right: np.uint64) -> np.uint64:
    left_low = left & _LOW32
    right_low = right & _LOW32
    low_product = left_low * right_low
    cross = (
        ((left >> np.uint64(32)) * right_low & _LOW32)
        + (left_low * (right >> np.uint64(32)) & _LOW32)
    ) & _LOW32
    low = low_product & _LOW32
    high = ((low_product >> np.uint64(32)) + cross) & _LOW32
    return np.uint64((high << np.uint64(32)) | low)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _splitmix64(value: np.uint64) -> np.uint64:
    value = _add_u64(value, np.uint64(0x9E3779B97F4A7C15))
    value = _multiply_u64(
        value ^ (value >> np.uint64(30)),
        np.uint64(0xBF58476D1CE4E5B9),
    )
    value = _multiply_u64(
        value ^ (value >> np.uint64(27)),
        np.uint64(0x94D049BB133111EB),
    )
    return np.uint64(value ^ (value >> np.uint64(31)))


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _checked_probe(
    total_probes: np.uint64, max_probe: np.uint64, probe: int
) -> tuple[np.uint64, np.uint64]:
    if total_probes == np.uint64(0xFFFFFFFFFFFFFFFF):
        raise OverflowError("probe diagnostics exceed uint64")
    total_probes += np.uint64(1)
    if np.uint64(probe) > max_probe:
        max_probe = np.uint64(probe)
    return total_probes, max_probe


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _rehash_local(
    old_keys: U64,
    old_occupied: U8,
    total_probes: np.uint64,
    max_probe: np.uint64,
) -> tuple[U64, U8, np.uint64, np.uint64]:
    old_capacity = len(old_keys)
    if old_capacity >= _MAX_CAPACITY:
        raise ValueError("edge-set capacity exceeds the addressable range")
    capacity = old_capacity * 2
    keys = np.zeros(capacity, dtype=np.uint64)
    occupied = np.zeros(capacity, dtype=np.uint8)
    mask = capacity - 1

    for old_slot in range(old_capacity):
        if old_occupied[old_slot] == np.uint8(0):
            continue
        value = old_keys[old_slot]
        slot = _splitmix64(value) & np.uint64(mask)
        probe = 1
        while occupied[slot] != np.uint8(0):
            total_probes, max_probe = _checked_probe(
                total_probes, max_probe, probe
            )
            slot = (slot + np.uint64(1)) & np.uint64(mask)
            probe += 1
        total_probes, max_probe = _checked_probe(
            total_probes, max_probe, probe
        )
        keys[slot] = value
        occupied[slot] = np.uint8(1)

    return keys, occupied, total_probes, max_probe


_U64_C = numba.types.Array(numba.uint64, 1, "C")
_U8_C = numba.types.Array(numba.uint8, 1, "C")
_INSERT_RESULT = numba.types.Tuple((_U64_C, _U8_C, numba.boolean))
_INSERT_SIGNATURE = _INSERT_RESULT(
    _U64_C, _U8_C, _U64_C, numba.uint64
)


@numba.njit(
    _INSERT_SIGNATURE, cache=True, boundscheck=True, fastmath=False
)
def edge_set_insert_kernel(
    keys: U64,
    occupied: U8,
    diagnostics: U64,
    value: np.uint64,
) -> tuple[U64, U8, bool]:
    size = diagnostics[1]
    total_probes = diagnostics[2]
    max_probe = diagnostics[3]
    rehashes = diagnostics[4]

    while True:
        capacity = len(keys)
        mask = capacity - 1
        slot = _splitmix64(value) & np.uint64(mask)
        probe = 1
        while occupied[slot] != np.uint8(0):
            total_probes, max_probe = _checked_probe(
                total_probes, max_probe, probe
            )
            if keys[slot] == value:
                diagnostics[2] = total_probes
                diagnostics[3] = max_probe
                return keys, occupied, False
            slot = (slot + np.uint64(1)) & np.uint64(mask)
            probe += 1

        total_probes, max_probe = _checked_probe(
            total_probes, max_probe, probe
        )
        if np.uint64(10) * (size + np.uint64(1)) <= np.uint64(
            7 * capacity
        ):
            keys[slot] = value
            occupied[slot] = np.uint8(1)
            diagnostics[0] = np.uint64(capacity)
            diagnostics[1] = size + np.uint64(1)
            diagnostics[2] = total_probes
            diagnostics[3] = max_probe
            diagnostics[4] = rehashes
            return keys, occupied, True

        if rehashes == np.uint64(0xFFFFFFFFFFFFFFFF):
            raise OverflowError("rehash diagnostics exceed uint64")
        keys, occupied, total_probes, max_probe = _rehash_local(
            keys, occupied, total_probes, max_probe
        )
        rehashes += np.uint64(1)


def edge_set_insert(
    keys: U64,
    occupied: U8,
    diagnostics: U64,
    value: np.uint64,
) -> tuple[U64, U8, bool]:
    validate_edge_set_state(keys, occupied, diagnostics)
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        or not 0 <= int(value) <= _MAX_UINT64
    ):
        raise ValueError("value must be an integer in the uint64 range")
    return edge_set_insert_kernel(
        keys, occupied, diagnostics, np.uint64(value)
    )


def build_class_start(multiplicity: U64) -> U64:
    if (
        not isinstance(multiplicity, np.ndarray)
        or multiplicity.dtype != np.dtype(np.uint64)
        or multiplicity.ndim != 1
        or not multiplicity.flags.c_contiguous
        or multiplicity.size < 1
    ):
        raise ValueError(
            "multiplicity must be a nonempty contiguous uint64 array"
        )

    class_start = np.empty(multiplicity.size + 1, dtype=np.uint64)
    class_start[0] = np.uint64(0)
    running = 0
    for index, raw_count in enumerate(multiplicity):
        count = int(raw_count)
        if count < 1:
            raise ValueError("class multiplicities must be positive")
        if running > _MAX_UINT64 - count:
            raise ValueError("class-start prefix sum exceeds uint64")
        running += count
        class_start[index + 1] = np.uint64(running)
    return class_start


def encode_edge_id(
    class_start: U64, distance_index: int, offset: int
) -> np.uint64:
    if (
        not isinstance(class_start, np.ndarray)
        or class_start.dtype != np.dtype(np.uint64)
        or class_start.ndim != 1
        or not class_start.flags.c_contiguous
        or class_start.size < 2
        or int(class_start[0]) != 0
    ):
        raise ValueError(
            "class_start must be a nonempty canonical contiguous uint64 array"
        )
    previous = -1
    for raw_start in class_start:
        start = int(raw_start)
        if start <= previous:
            raise ValueError("class_start must be strictly increasing")
        previous = start
    if (
        isinstance(distance_index, (bool, np.bool_))
        or not isinstance(distance_index, (int, np.integer))
        or not 0 <= int(distance_index) < class_start.size - 1
    ):
        raise ValueError("distance_index is outside class_start")
    if (
        isinstance(offset, (bool, np.bool_))
        or not isinstance(offset, (int, np.integer))
        or int(offset) < 0
    ):
        raise ValueError("offset must be a nonnegative integer")

    start = int(class_start[int(distance_index)])
    stop = int(class_start[int(distance_index) + 1])
    offset_value = int(offset)
    if offset_value >= stop - start:
        raise ValueError("offset is outside the selected distance class")
    if start > _MAX_UINT64 - offset_value:
        raise ValueError("encoded edge ID exceeds uint64")
    return np.uint64(start + offset_value)
