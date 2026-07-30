from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

import numba
import numpy as np
import numpy.typing as npt


Phase = Literal["validation", "benchmark", "pilot", "confirmatory"]
U32 = npt.NDArray[np.uint32]

STREAM_ALIAS_COLUMN: int = 0
STREAM_ALIAS_THRESHOLD: int = 1
STREAM_EDGE_OFFSET: int = 2
STREAM_EXPONENTIAL: int = 3
STREAM_COUNT: int = 4

PHILOX_M0 = np.uint32(0xD2511F53)
PHILOX_M1 = np.uint32(0xCD9E8D57)
PHILOX_W0 = np.uint32(0x9E3779B9)
PHILOX_W1 = np.uint32(0xBB67AE85)
RNG_VERSION = "philox4x32-10/open32-v1/bounded-reject-v1"

_MASK32 = (1 << 32) - 1
_UINT64_LIMIT = 1 << 64
_STREAM_DOMAIN = b"challenge-194-philox-stream-v1\0"
_PHASES = frozenset(("validation", "benchmark", "pilot", "confirmatory"))


@dataclass(frozen=True)
class StreamIdentity:
    master_seed: int
    phase: Phase
    length: int
    sigma_grid_id: str
    replica: int
    stream_id: int


@dataclass(frozen=True)
class StreamMaterial:
    key: U32
    initial_counter: U32
    material_sha256: str


def _checked_int(value: object, name: str, upper_bound: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not 0 <= value < upper_bound:
        raise ValueError(f"{name} is outside its canonical range")
    return value


def _canonical_identity(identity: StreamIdentity) -> bytes:
    if not isinstance(identity, StreamIdentity):
        raise ValueError("identity must be a StreamIdentity")
    master_seed = _checked_int(
        identity.master_seed, "master_seed", _UINT64_LIMIT
    )
    replica = _checked_int(identity.replica, "replica", _UINT64_LIMIT)
    stream_id = _checked_int(identity.stream_id, "stream_id", STREAM_COUNT)
    length = _checked_int(identity.length, "length", _UINT64_LIMIT)
    if length < 2 or length % 2:
        raise ValueError("length must be even and at least two")
    if not isinstance(identity.phase, str) or identity.phase not in _PHASES:
        raise ValueError("phase is not in the frozen phase namespace")
    if (
        not isinstance(identity.sigma_grid_id, str)
        or not identity.sigma_grid_id
        or identity.sigma_grid_id != identity.sigma_grid_id.strip()
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in identity.sigma_grid_id
        )
    ):
        raise ValueError(
            "sigma_grid_id must be a trimmed nonempty string without "
            "control characters"
        )
    document = {
        "length": length,
        "master_seed": master_seed,
        "phase": identity.phase,
        "replica": replica,
        "sigma_grid_id": identity.sigma_grid_id,
        "stream_id": stream_id,
    }
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("sigma_grid_id must be valid UTF-8") from error


def derive_stream_material(identity: StreamIdentity) -> StreamMaterial:
    digest = hashlib.sha256(
        _STREAM_DOMAIN + _canonical_identity(identity)
    ).digest()
    key = np.frombuffer(digest[0:8], dtype="<u4").astype(np.uint32)
    initial_counter = np.frombuffer(digest[8:24], dtype="<u4").astype(np.uint32)
    key.setflags(write=False)
    initial_counter.setflags(write=False)
    return StreamMaterial(
        key=key,
        initial_counter=initial_counter,
        material_sha256=digest.hex(),
    )


def _checked_u32_array(
    value: np.ndarray, name: str, length: int
) -> np.ndarray:
    if (
        not isinstance(value, np.ndarray)
        or value.dtype != np.dtype(np.uint32)
        or value.shape != (length,)
        or not value.flags.c_contiguous
    ):
        raise ValueError(
            f"{name} must be a contiguous uint32 array with shape ({length},)"
        )
    return value


def philox4x32_10_reference(counter: U32, key: U32) -> U32:
    counter = _checked_u32_array(counter, "counter", 4)
    key = _checked_u32_array(key, "key", 2)
    c0, c1, c2, c3 = (int(word) for word in counter)
    k0, k1 = (int(word) for word in key)
    multiplier0 = int(PHILOX_M0)
    multiplier1 = int(PHILOX_M1)
    Weyl0 = int(PHILOX_W0)
    Weyl1 = int(PHILOX_W1)
    for _ in range(10):
        product0 = multiplier0 * c0
        product1 = multiplier1 * c2
        low0 = product0 & _MASK32
        high0 = (product0 >> 32) & _MASK32
        low1 = product1 & _MASK32
        high1 = (product1 >> 32) & _MASK32
        c0, c1, c2, c3 = (
            (high1 ^ c1 ^ k0) & _MASK32,
            low1,
            (high0 ^ c3 ^ k1) & _MASK32,
            low0,
        )
        k0 = (k0 + Weyl0) & _MASK32
        k1 = (k1 + Weyl1) & _MASK32
    return np.asarray((c0, c1, c2, c3), dtype=np.uint32)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _multiply_high_low(
    multiplier: np.uint32, word: np.uint32
) -> tuple[np.uint32, np.uint32]:
    product = np.uint64(multiplier) * np.uint64(word)
    low = np.uint32(product & np.uint64(0xFFFFFFFF))
    high = np.uint32(product >> np.uint64(32))
    return high, low


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def philox4x32_10(counter: U32, key: U32, out: U32) -> None:
    c0 = counter[0]
    c1 = counter[1]
    c2 = counter[2]
    c3 = counter[3]
    k0 = key[0]
    k1 = key[1]
    for _ in range(10):
        high0, low0 = _multiply_high_low(np.uint32(0xD2511F53), c0)
        high1, low1 = _multiply_high_low(np.uint32(0xCD9E8D57), c2)
        c0, c1, c2, c3 = (
            np.uint32(high1 ^ c1 ^ k0),
            low1,
            np.uint32(high0 ^ c3 ^ k1),
            low0,
        )
        k0 = np.uint32(
            (np.uint64(k0) + np.uint64(0x9E3779B9))
            & np.uint64(0xFFFFFFFF)
        )
        k1 = np.uint32(
            (np.uint64(k1) + np.uint64(0xBB67AE85))
            & np.uint64(0xFFFFFFFF)
        )
    out[0] = c0
    out[1] = c1
    out[2] = c2
    out[3] = c3


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _increment_counter(counter: U32) -> None:
    carry = np.uint64(1)
    for index in range(4):
        total = np.uint64(counter[index]) + carry
        counter[index] = np.uint32(total & np.uint64(0xFFFFFFFF))
        carry = total >> np.uint64(32)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def next_u32(
    counter: U32,
    key: U32,
    block: U32,
    lane_and_valid: npt.NDArray[np.uint8],
    accounting: npt.NDArray[np.uint64],
) -> np.uint32:
    lane = lane_and_valid[0]
    valid = lane_and_valid[1]
    if valid > np.uint8(1) or lane > np.uint8(3):
        raise ValueError("lane_and_valid contains invalid state")
    if valid == np.uint8(0):
        if lane != np.uint8(0):
            raise ValueError("invalid lane for an empty block")
        philox4x32_10(counter, key, block)
        _increment_counter(counter)
        lane = np.uint8(0)
        valid = np.uint8(1)
        accounting[1] += np.uint64(1)

    word = block[lane]
    accounting[0] += np.uint64(1)
    lane += np.uint8(1)
    if lane == np.uint8(4):
        lane_and_valid[0] = np.uint8(0)
        lane_and_valid[1] = np.uint8(0)
    else:
        lane_and_valid[0] = lane
        lane_and_valid[1] = valid
    return word


def u32_to_open(word: np.uint32) -> float:
    if (
        isinstance(word, (bool, np.bool_))
        or not isinstance(word, (int, np.integer))
        or not 0 <= int(word) <= _MASK32
    ):
        raise ValueError("word must be an unsigned 32-bit integer")
    return (float(word) + 0.5) * (2.0**-32)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def uniform_open(
    counter: U32,
    key: U32,
    block: U32,
    lane_and_valid: npt.NDArray[np.uint8],
    accounting: npt.NDArray[np.uint64],
) -> float:
    word = next_u32(counter, key, block, lane_and_valid, accounting)
    return (float(word) + 0.5) * (2.0**-32)


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def bounded_u32(
    bound: int,
    counter: U32,
    key: U32,
    block: U32,
    lane_and_valid: npt.NDArray[np.uint8],
    accounting: npt.NDArray[np.uint64],
) -> np.uint32:
    if (
        bound < 1
        or bound > 0xFFFFFFFF
        or bound != np.floor(bound)
    ):
        raise ValueError("bound must be in [1, 2**32 - 1]")
    bound_u64 = np.uint64(bound)
    threshold = (
        np.uint64(1 << 32) - bound_u64
    ) % bound_u64
    while True:
        word = next_u32(
            counter, key, block, lane_and_valid, accounting
        )
        if np.uint64(word) < threshold:
            accounting[2] += np.uint64(1)
            continue
        return np.uint32(np.uint64(word) % bound_u64)
