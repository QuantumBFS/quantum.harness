from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import hashlib
import json
import math
import re
import sys
from typing import Literal, Protocol, Sequence

import numpy as np
import numpy.typing as npt

from .counter_rng import (
    StreamIdentity,
    derive_stream_material,
    philox4x32_10_reference,
    u32_to_open,
)
from .union_find import UnionFind


Phase = Literal["validation", "benchmark", "pilot", "confirmatory"]
F64 = npt.NDArray[np.float64]
U32 = npt.NDArray[np.uint32]
U64 = npt.NDArray[np.uint64]

_CLASS_COLUMN_STREAM = 0
_CLASS_THRESHOLD_STREAM = 1
_OFFSET_STREAM = 2
_EXPONENTIAL_STREAM = 3
_STREAM_COUNT = 4
_UINT64_LIMIT = 1 << 64
_MASK32 = (1 << 32) - 1
_PHASES = frozenset(("validation", "benchmark", "pilot", "confirmatory"))
_HEX256 = re.compile(r"[0-9a-f]{64}")
_REQUEST_DOMAIN = b"challenge-194-trajectory-request-v1\0"
_PREFIX_REL_TOL = 8.0 * np.finfo(np.float64).eps
_MINIMUM_OPEN_HAZARD = -math.log(
    u32_to_open(np.uint32(_MASK32))
)


def _frozen_copy(array: np.ndarray, dtype: np.dtype) -> np.ndarray:
    copy = np.array(array, dtype=dtype, order="C", copy=True)
    copy.setflags(write=False)
    return copy


@dataclass(frozen=True)
class TrajectoryRequest:
    length: int
    sigma: float
    sigma_grid_id: str
    kappas: F64
    master_seed: int
    phase: Phase
    replica: int
    kernel_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kappas, np.ndarray)
            or self.kappas.dtype != np.dtype(np.float64)
            or self.kappas.ndim != 1
            or not self.kappas.flags.c_contiguous
        ):
            raise ValueError(
                "kappas must be a C-contiguous one-dimensional float64 array"
            )
        object.__setattr__(
            self,
            "kappas",
            _frozen_copy(self.kappas, np.dtype(np.float64)),
        )


@dataclass(frozen=True)
class TrajectoryResult:
    request_sha256: str
    observables: F64
    terminal_counters: U32
    draw_counts: U64
    event_count: int
    duplicate_count: int
    hash_diagnostics: U64

    def __post_init__(self) -> None:
        if not isinstance(self.request_sha256, str) or _HEX256.fullmatch(
            self.request_sha256
        ) is None:
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        arrays = (
            (
                self.observables,
                np.dtype(np.float64),
                2,
                "observables",
            ),
            (
                self.terminal_counters,
                np.dtype(np.uint32),
                2,
                "terminal_counters",
            ),
            (self.draw_counts, np.dtype(np.uint64), 2, "draw_counts"),
            (
                self.hash_diagnostics,
                np.dtype(np.uint64),
                1,
                "hash_diagnostics",
            ),
        )
        for value, dtype, ndim, name in arrays:
            if (
                not isinstance(value, np.ndarray)
                or value.dtype != dtype
                or value.ndim != ndim
                or not value.flags.c_contiguous
            ):
                raise ValueError(
                    f"{name} must be a C-contiguous {ndim}-dimensional "
                    f"{dtype.name} array"
                )
        if self.observables.shape[1:] != (10,):
            raise ValueError("observables must have shape (n_kappa, 10)")
        if self.terminal_counters.shape != (_STREAM_COUNT, 4):
            raise ValueError("terminal_counters must have shape (4, 4)")
        if self.draw_counts.shape != (_STREAM_COUNT, 3):
            raise ValueError("draw_counts must have shape (4, 3)")
        if self.hash_diagnostics.shape != (5,):
            raise ValueError("hash_diagnostics must have shape (5,)")
        for value, name in (
            (self.event_count, "event_count"),
            (self.duplicate_count, "duplicate_count"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative Python integer")
        if self.duplicate_count > self.event_count:
            raise ValueError("duplicate_count cannot exceed event_count")
        if not np.all(np.isfinite(self.observables)):
            raise ValueError("observables must be finite")
        for name, value, dtype in (
            ("observables", self.observables, np.dtype(np.float64)),
            (
                "terminal_counters",
                self.terminal_counters,
                np.dtype(np.uint32),
            ),
            ("draw_counts", self.draw_counts, np.dtype(np.uint64)),
            (
                "hash_diagnostics",
                self.hash_diagnostics,
                np.dtype(np.uint64),
            ),
        ):
            object.__setattr__(self, name, _frozen_copy(value, dtype))


@dataclass(frozen=True)
class _ReferenceRun:
    result: TrajectoryResult
    event_times: tuple[float, ...]
    edge_ids_by_checkpoint: tuple[frozenset[int], ...]


class _Streams(Protocol):
    terminal_counters: U32
    draw_counts: U64

    @property
    def minimum_exponential_hazard(self) -> float: ...

    def uniform(self, stream_id: int) -> float: ...

    def bounded(self, stream_id: int, bound: int) -> int: ...


def validate_trajectory_request(request: TrajectoryRequest) -> None:
    if not isinstance(request, TrajectoryRequest):
        raise ValueError("request must be a TrajectoryRequest")
    if (
        isinstance(request.length, bool)
        or not isinstance(request.length, int)
        or request.length < 2
        or request.length % 2
        or request.length > sys.maxsize
    ):
        raise ValueError("length must be an even addressable Python integer")
    if (
        isinstance(request.sigma, bool)
        or not isinstance(request.sigma, (int, float))
    ):
        raise ValueError("sigma must be a finite positive real number")
    sigma = float(request.sigma)
    exponent = 1.0 + sigma
    if (
        not math.isfinite(sigma)
        or sigma <= 0.0
        or not math.isfinite(exponent)
        or exponent <= 1.0
    ):
        raise ValueError(
            "sigma must be finite, positive, and satisfy 1.0 + sigma > 1.0"
        )
    if (
        not isinstance(request.kappas, np.ndarray)
        or request.kappas.dtype != np.dtype(np.float64)
        or request.kappas.ndim != 1
        or not request.kappas.flags.c_contiguous
        or request.kappas.size < 1
        or np.any(~np.isfinite(request.kappas))
        or np.any(request.kappas < 0.0)
        or (
            request.kappas.size > 1
            and np.any(request.kappas[1:] <= request.kappas[:-1])
        )
    ):
        raise ValueError(
            "kappas must be finite, nonnegative, sorted, unique float64 values"
        )
    for value, name in (
        (request.master_seed, "master_seed"),
        (request.replica, "replica"),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < _UINT64_LIMIT
        ):
            raise ValueError(f"{name} must fit uint64")
    if not isinstance(request.phase, str) or request.phase not in _PHASES:
        raise ValueError("phase is not in the frozen phase namespace")
    if (
        not isinstance(request.sigma_grid_id, str)
        or not request.sigma_grid_id
        or request.sigma_grid_id != request.sigma_grid_id.strip()
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in request.sigma_grid_id
        )
    ):
        raise ValueError(
            "sigma_grid_id must be trimmed, nonempty, and contain no controls"
        )
    try:
        request.sigma_grid_id.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("sigma_grid_id must be valid UTF-8") from error
    if (
        not isinstance(request.kernel_sha256, str)
        or _HEX256.fullmatch(request.kernel_sha256) is None
    ):
        raise ValueError("kernel_sha256 must be a lowercase SHA-256 digest")


def _validate_kernel(request: TrajectoryRequest, kernel: F64) -> None:
    if (
        not isinstance(kernel, np.ndarray)
        or kernel.dtype != np.dtype(np.float64)
        or kernel.shape != (request.length // 2,)
        or not kernel.flags.c_contiguous
    ):
        raise ValueError(
            "kernel must be a C-contiguous float64 array with exact shape"
        )
    if np.any(~np.isfinite(kernel)) or np.any(kernel <= 0.0):
        raise ValueError("kernel must contain finite positive values")
    actual = hashlib.sha256(kernel.tobytes(order="C")).hexdigest()
    if actual != request.kernel_sha256:
        raise ValueError("kernel digest does not match kernel_sha256")


def _compensated_prefix(
    weights: Sequence[float],
) -> tuple[tuple[float, ...], float, int]:
    running = 0.0
    correction = 0.0
    previous = 0.0
    cumulative: list[float] = []
    operations = 0
    for value in weights:
        weight = float(value)
        if not math.isfinite(weight) or weight <= 0.0:
            raise ValueError("class weights must be finite and positive")
        combined = running + weight
        if abs(running) >= abs(weight):
            correction += (running - combined) + weight
        else:
            correction += (weight - combined) + running
        running = combined
        prefix = running + correction
        operations += 1
        if not math.isfinite(prefix) or prefix < previous:
            raise ValueError(
                "compensated class prefix must be finite and monotone"
            )
        cumulative.append(prefix)
        previous = prefix
    if not cumulative:
        raise ValueError("at least one class weight is required")

    exact_total = math.fsum(float(value) for value in weights)
    approximate_total = cumulative[-1]
    tolerance = _PREFIX_REL_TOL * abs(exact_total)
    if (
        not math.isfinite(exact_total)
        or exact_total <= 0.0
        or abs(approximate_total - exact_total) > tolerance
    ):
        raise ValueError(
            "compensated class total disagrees with the reference sum"
        )
    if len(cumulative) > 1 and exact_total < cumulative[-2]:
        raise ValueError("reference class total violates prefix monotonicity")
    cumulative[-1] = exact_total
    return tuple(cumulative), exact_total, operations


def _class_data(length: int, kernel: F64) -> tuple[
    tuple[int, ...], tuple[int, ...], tuple[float, ...], float
]:
    multiplicities = tuple(
        length if distance < length // 2 else length // 2
        for distance in range(1, length // 2 + 1)
    )
    weights = tuple(
        float(multiplicity) * float(kernel[index])
        for index, multiplicity in enumerate(multiplicities)
    )
    cumulative, total_rate, _ = _compensated_prefix(weights)
    starts = [0]
    for multiplicity in multiplicities:
        starts.append(starts[-1] + multiplicity)
    if starts[-1] >= _UINT64_LIMIT:
        raise ValueError("the canonical edge count must fit uint64")
    return multiplicities, tuple(starts), cumulative, total_rate


def _validate_event_time_resolution(
    kappa_max: float,
    total_rate: float,
    minimum_hazard: float,
) -> None:
    if not math.isfinite(minimum_hazard) or minimum_hazard <= 0.0:
        raise ValueError("minimum exponential hazard must be finite and positive")
    terminal_hazard = kappa_max * total_rate
    if not math.isfinite(terminal_hazard):
        raise ValueError("largest coupling times total rate must be finite")
    if terminal_hazard < minimum_hazard:
        return
    minimum_delta = minimum_hazard / total_rate
    if (
        minimum_delta == 0.0
        or minimum_delta <= math.ulp(kappa_max)
    ):
        raise ValueError(
            "total rate is too large to preserve float64 event ordering"
        )


def _request_digest(request: TrajectoryRequest) -> str:
    document = {
        "kernel_sha256": request.kernel_sha256,
        "kappas_le_f64": request.kappas.astype("<f8", copy=False).tobytes().hex(),
        "length": request.length,
        "master_seed": request.master_seed,
        "phase": request.phase,
        "replica": request.replica,
        "sigma": request.sigma,
        "sigma_grid_id": request.sigma_grid_id,
    }
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(_REQUEST_DOMAIN + encoded).hexdigest()


class _ReferenceWordStream:
    def __init__(self, identity: StreamIdentity):
        material = derive_stream_material(identity)
        self.key = np.array(material.key, dtype=np.uint32, copy=True)
        self.counter = np.array(
            material.initial_counter, dtype=np.uint32, copy=True
        )
        self.block = np.zeros(4, dtype=np.uint32)
        self.lane = 4
        self.accounting = np.zeros(3, dtype=np.uint64)

    def _increment_counter(self) -> None:
        carry = 1
        for index in range(4):
            total = int(self.counter[index]) + carry
            self.counter[index] = np.uint32(total & _MASK32)
            carry = total >> 32

    def next_word(self) -> np.uint32:
        if self.lane == 4:
            self.block[:] = philox4x32_10_reference(self.counter, self.key)
            self._increment_counter()
            self.lane = 0
            self.accounting[1] += np.uint64(1)
        word = self.block[self.lane]
        self.lane += 1
        self.accounting[0] += np.uint64(1)
        return word

    def uniform(self) -> float:
        return u32_to_open(self.next_word())

    def bounded(self, bound: int) -> int:
        if isinstance(bound, bool) or not isinstance(bound, int):
            raise ValueError("bound must be a Python integer")
        if not 1 <= bound <= _MASK32:
            raise ValueError("bound must be in [1, 2**32 - 1]")
        threshold = ((1 << 32) - bound) % bound
        while True:
            word = int(self.next_word())
            if word < threshold:
                self.accounting[2] += np.uint64(1)
                continue
            return word % bound


class _ReferenceStreams:
    def __init__(self, request: TrajectoryRequest):
        self._streams = tuple(
            _ReferenceWordStream(
                StreamIdentity(
                    master_seed=request.master_seed,
                    phase=request.phase,
                    length=request.length,
                    sigma_grid_id=request.sigma_grid_id,
                    replica=request.replica,
                    stream_id=stream_id,
                )
            )
            for stream_id in range(_STREAM_COUNT)
        )

    def uniform(self, stream_id: int) -> float:
        if not 0 <= stream_id < _STREAM_COUNT:
            raise ValueError("stream_id is outside the frozen namespace")
        return self._streams[stream_id].uniform()

    def bounded(self, stream_id: int, bound: int) -> int:
        if stream_id != _OFFSET_STREAM:
            raise ValueError("bounded draws are restricted to the offset stream")
        return self._streams[stream_id].bounded(bound)

    @property
    def minimum_exponential_hazard(self) -> float:
        return _MINIMUM_OPEN_HAZARD

    @property
    def terminal_counters(self) -> U32:
        return np.stack([stream.counter for stream in self._streams])

    @property
    def draw_counts(self) -> U64:
        return np.stack([stream.accounting for stream in self._streams])


def _build_reference_streams(request: TrajectoryRequest) -> _ReferenceStreams:
    validate_trajectory_request(request)
    return _ReferenceStreams(request)


def _decode_edge(
    edge_id: int,
    length: int,
    starts: tuple[int, ...],
) -> tuple[int, int]:
    class_index = bisect_right(starts, edge_id) - 1
    if not 0 <= class_index < len(starts) - 1:
        raise RuntimeError("stored edge identifier is outside all classes")
    offset = edge_id - starts[class_index]
    distance = class_index + 1
    multiplicity = starts[class_index + 1] - starts[class_index]
    if not 0 <= offset < multiplicity:
        raise RuntimeError("stored edge offset is outside its class")
    if distance == length // 2 and offset >= length // 2:
        raise RuntimeError("antipodal offset is outside its half-ring")
    left = offset
    right = (offset + distance) % length
    return (left, right) if left < right else (right, left)


def _checkpoint(
    length: int,
    open_edge_ids: set[int],
    starts: tuple[int, ...],
) -> tuple[float, ...]:
    connectivity = UnionFind(length)
    for edge_id in sorted(open_edge_ids):
        left, right = _decode_edge(edge_id, length, starts)
        connectivity.union(left, right)
    labels = connectivity.labels()
    sizes_by_label: dict[int, int] = {}
    masks_by_label: dict[int, int] = {}
    for vertex, label_value in enumerate(labels.tolist()):
        label = int(label_value)
        sizes_by_label[label] = sizes_by_label.get(label, 0) + 1
        sector = min(3, (4 * vertex) // length)
        masks_by_label[label] = masks_by_label.get(label, 0) | (1 << sector)
    sizes = sorted(sizes_by_label.values(), reverse=True)
    largest = sizes[0]
    second_largest = sizes[1] if len(sizes) > 1 else 0
    sum_size_sq = math.fsum(float(size) ** 2 for size in sizes)
    sum_size_fourth = math.fsum(float(size) ** 4 for size in sizes)
    q_g = sum_size_fourth / (sum_size_sq * sum_size_sq)
    return (
        float(len(open_edge_ids)),
        float(len(sizes)),
        float(largest),
        float(second_largest),
        float(largest) / float(length),
        float(second_largest) / float(length),
        sum_size_sq,
        sum_size_fourth,
        q_g,
        float(any(mask == 0b1111 for mask in masks_by_label.values())),
    )


def _checked_stream_arrays(streams: _Streams) -> tuple[U32, U64]:
    terminal = streams.terminal_counters
    counts = streams.draw_counts
    if (
        not isinstance(terminal, np.ndarray)
        or terminal.dtype != np.dtype(np.uint32)
        or terminal.shape != (_STREAM_COUNT, 4)
        or not terminal.flags.c_contiguous
    ):
        raise ValueError("stream terminal counters violate the fixed contract")
    if (
        not isinstance(counts, np.ndarray)
        or counts.dtype != np.dtype(np.uint64)
        or counts.shape != (_STREAM_COUNT, 3)
        or not counts.flags.c_contiguous
    ):
        raise ValueError("stream draw counts violate the fixed contract")
    return terminal, counts


def _run_poisson_with_streams(
    request: TrajectoryRequest,
    kernel: F64,
    streams: _Streams,
) -> _ReferenceRun:
    validate_trajectory_request(request)
    _validate_kernel(request, kernel)
    multiplicities, starts, cumulative, total_rate = _class_data(
        request.length, kernel
    )
    kappa_max = float(request.kappas[-1])
    minimum_hazard = getattr(
        streams,
        "minimum_exponential_hazard",
        _MINIMUM_OPEN_HAZARD,
    )
    _validate_event_time_resolution(
        kappa_max,
        total_rate,
        float(minimum_hazard),
    )

    rows: list[tuple[float, ...]] = []
    snapshots: list[frozenset[int]] = []
    open_edge_ids: set[int] = set()
    event_times: list[float] = []
    event_count = 0
    duplicate_count = 0
    checkpoint_index = 0
    current_kappa = 0.0

    while (
        checkpoint_index < request.kappas.size
        and request.kappas[checkpoint_index] == 0.0
    ):
        rows.append(_checkpoint(request.length, open_edge_ids, starts))
        snapshots.append(frozenset(open_edge_ids))
        checkpoint_index += 1

    if kappa_max > 0.0:
        while True:
            exponential_uniform = streams.uniform(_EXPONENTIAL_STREAM)
            if not 0.0 < exponential_uniform < 1.0:
                raise ValueError("exponential stream must produce open uniforms")
            hazard = -math.log(exponential_uniform)
            remaining_kappa = kappa_max - current_kappa
            terminal_hazard = remaining_kappa * total_rate
            if hazard > terminal_hazard:
                break
            delta = hazard / total_rate
            next_kappa = current_kappa + delta
            if (
                not math.isfinite(delta)
                or delta <= 0.0
                or not math.isfinite(next_kappa)
                or next_kappa <= current_kappa
            ):
                raise ValueError("event time failed finite strict advancement")

            while (
                checkpoint_index < request.kappas.size
                and request.kappas[checkpoint_index] < next_kappa
            ):
                rows.append(_checkpoint(request.length, open_edge_ids, starts))
                snapshots.append(frozenset(open_edge_ids))
                checkpoint_index += 1

            column_uniform = streams.uniform(_CLASS_COLUMN_STREAM)
            class_uniform = streams.uniform(_CLASS_THRESHOLD_STREAM)
            if not 0.0 < column_uniform < 1.0:
                raise ValueError("class-column stream must produce open uniforms")
            if not 0.0 < class_uniform < 1.0:
                raise ValueError("class stream must produce open uniforms")
            target = class_uniform * total_rate
            class_index = bisect_left(cumulative, target)
            if class_index == len(cumulative):
                class_index = len(cumulative) - 1
            offset = streams.bounded(
                _OFFSET_STREAM, multiplicities[class_index]
            )
            if not 0 <= offset < multiplicities[class_index]:
                raise ValueError("offset stream returned an out-of-range value")
            edge_id = starts[class_index] + offset
            event_count += 1
            event_times.append(next_kappa)
            if edge_id in open_edge_ids:
                duplicate_count += 1
            else:
                open_edge_ids.add(edge_id)
            current_kappa = next_kappa

            while (
                checkpoint_index < request.kappas.size
                and request.kappas[checkpoint_index] <= current_kappa
            ):
                rows.append(_checkpoint(request.length, open_edge_ids, starts))
                snapshots.append(frozenset(open_edge_ids))
                checkpoint_index += 1

    while checkpoint_index < request.kappas.size:
        rows.append(_checkpoint(request.length, open_edge_ids, starts))
        snapshots.append(frozenset(open_edge_ids))
        checkpoint_index += 1

    terminal_counters, draw_counts = _checked_stream_arrays(streams)
    result = TrajectoryResult(
        request_sha256=_request_digest(request),
        observables=np.asarray(rows, dtype=np.float64).reshape(-1, 10),
        terminal_counters=terminal_counters,
        draw_counts=draw_counts,
        event_count=event_count,
        duplicate_count=duplicate_count,
        hash_diagnostics=np.zeros(5, dtype=np.uint64),
    )
    return _ReferenceRun(
        result=result,
        event_times=tuple(event_times),
        edge_ids_by_checkpoint=tuple(snapshots),
    )


def run_poisson_reference(
    request: TrajectoryRequest,
    kernel: F64,
) -> TrajectoryResult:
    validate_trajectory_request(request)
    _validate_kernel(request, kernel)
    streams = _build_reference_streams(request)
    return _run_poisson_with_streams(request, kernel, streams).result
