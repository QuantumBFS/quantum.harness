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
def _validate_state(keys: U64, occupied: U8, diagnostics: U64) -> None:
    if diagnostics.ndim != 1 or len(diagnostics) != 5:
        raise ValueError("diagnostics must have shape (5,)")
    if keys.ndim != 1 or occupied.ndim != 1:
        raise ValueError("keys and occupied must be one-dimensional")

    capacity = len(keys)
    if (
        capacity < 2
        or capacity != len(occupied)
        or capacity & (capacity - 1)
        or diagnostics[0] != np.uint64(capacity)
    ):
        raise ValueError("edge-set capacity state is invalid")

    occupied_count = np.uint64(0)
    for slot in range(capacity):
        marker = occupied[slot]
        if marker > np.uint8(1):
            raise ValueError("occupied must contain only zero or one")
        occupied_count += np.uint64(marker)
    if occupied_count != diagnostics[1]:
        raise ValueError("edge-set size does not match occupancy")
    if np.uint64(10) * diagnostics[1] > np.uint64(7 * capacity):
        raise ValueError("edge-set load exceeds 0.70")

    maximum_increment = np.uint64(2 * capacity + 1)
    if diagnostics[2] > np.uint64(0xFFFFFFFFFFFFFFFF) - maximum_increment:
        raise ValueError("probe diagnostics would overflow")
    if diagnostics[4] == np.uint64(0xFFFFFFFFFFFFFFFF):
        raise ValueError("rehash diagnostics would overflow")


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _record_probe(diagnostics: U64, probe: int) -> None:
    diagnostics[2] += np.uint64(1)
    if np.uint64(probe) > diagnostics[3]:
        diagnostics[3] = np.uint64(probe)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _rehash(
    old_keys: U64, old_occupied: U8, diagnostics: U64
) -> tuple[U64, U8]:
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
            _record_probe(diagnostics, probe)
            slot = (slot + np.uint64(1)) & np.uint64(mask)
            probe += 1
        _record_probe(diagnostics, probe)
        keys[slot] = value
        occupied[slot] = np.uint8(1)

    diagnostics[0] = np.uint64(capacity)
    diagnostics[4] += np.uint64(1)
    return keys, occupied


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def edge_set_insert(
    keys: U64,
    occupied: U8,
    diagnostics: U64,
    value: np.uint64,
) -> tuple[U64, U8, bool]:
    _validate_state(keys, occupied, diagnostics)

    while True:
        capacity = len(keys)
        mask = capacity - 1
        slot = _splitmix64(value) & np.uint64(mask)
        probe = 1
        while occupied[slot] != np.uint8(0):
            _record_probe(diagnostics, probe)
            if keys[slot] == value:
                return keys, occupied, False
            slot = (slot + np.uint64(1)) & np.uint64(mask)
            probe += 1

        _record_probe(diagnostics, probe)
        if np.uint64(10) * (diagnostics[1] + np.uint64(1)) <= np.uint64(
            7 * capacity
        ):
            keys[slot] = value
            occupied[slot] = np.uint8(1)
            diagnostics[1] += np.uint64(1)
            return keys, occupied, True

        keys, occupied = _rehash(keys, occupied, diagnostics)


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

    class_start = np.empty(multiplicity.size, dtype=np.uint64)
    running = 0
    for index, raw_count in enumerate(multiplicity):
        count = int(raw_count)
        if count < 1:
            raise ValueError("class multiplicities must be positive")
        class_start[index] = np.uint64(running)
        if running > _MAX_UINT64 - count:
            raise ValueError("class-start prefix sum exceeds uint64")
        running += count
    return class_start


def encode_edge_id(
    class_start: U64, distance_index: int, offset: int
) -> np.uint64:
    if (
        not isinstance(class_start, np.ndarray)
        or class_start.dtype != np.dtype(np.uint64)
        or class_start.ndim != 1
        or not class_start.flags.c_contiguous
        or class_start.size < 1
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
        or not 0 <= int(distance_index) < class_start.size
    ):
        raise ValueError("distance_index is outside class_start")
    if (
        isinstance(offset, (bool, np.bool_))
        or not isinstance(offset, (int, np.integer))
        or int(offset) < 0
    ):
        raise ValueError("offset must be a nonnegative integer")

    start = int(class_start[int(distance_index)])
    offset_value = int(offset)
    if offset_value > _MAX_UINT64 - start:
        raise ValueError("encoded edge ID exceeds uint64")
    return np.uint64(start + offset_value)
