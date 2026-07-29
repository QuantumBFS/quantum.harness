from __future__ import annotations

from bisect import bisect_left, bisect_right
import math
from typing import Protocol, Sequence

import numpy as np

from .counter_rng import (
    StreamIdentity,
    derive_stream_material,
    philox4x32_10_reference,
    u32_to_open,
)
from .trajectory import (
    F64,
    U32,
    U64,
    TrajectoryDiagnostics,
    TrajectoryRequest,
    TrajectoryResult,
    _request_digest,
    _validate_event_time_resolution,
    _validate_kernel,
    validate_trajectory_request,
)
from .union_find import UnionFind


_CLASS_COLUMN_STREAM = 0
_CLASS_THRESHOLD_STREAM = 1
_OFFSET_STREAM = 2
_EXPONENTIAL_STREAM = 3
_STREAM_COUNT = 4
_UINT64_LIMIT = 1 << 64
_MASK32 = (1 << 32) - 1
_PREFIX_REL_TOL = 8.0 * np.finfo(np.float64).eps
_MINIMUM_OPEN_HAZARD = -math.log(
    u32_to_open(np.uint32(_MASK32))
)


class _Streams(Protocol):
    terminal_counters: U32
    draw_counts: U64

    @property
    def minimum_exponential_hazard(self) -> float: ...

    def uniform(self, stream_id: int) -> float: ...

    def bounded(self, stream_id: int, bound: int) -> int: ...


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


def _compensated_hazard_add(
    high: float, low: float, increment: float
) -> tuple[float, float]:
    summed = high + increment
    virtual_increment = summed - high
    error = (high - (summed - virtual_increment)) + (
        increment - virtual_increment
    )
    residual = low + error
    next_high = summed + residual
    next_low = residual - (next_high - summed)
    return next_high, next_low


def _hazard_pair_greater_than_scalar(
    high: float, low: float, scalar: float
) -> bool:
    return high > scalar or (high == scalar and low > 0.0)


def _hazard_pair_at_least_scalar(
    high: float, low: float, scalar: float
) -> bool:
    return high > scalar or (high == scalar and low >= 0.0)


def _run_poisson_with_streams(
    request: TrajectoryRequest,
    kernel: F64,
    streams: _Streams,
) -> TrajectoryDiagnostics:
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
    current_hazard_high = 0.0
    current_hazard_low = 0.0
    terminal_hazard = kappa_max * total_rate

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
            next_hazard_high, next_hazard_low = _compensated_hazard_add(
                current_hazard_high, current_hazard_low, hazard
            )
            if (
                not math.isfinite(hazard)
                or hazard <= 0.0
                or not math.isfinite(next_hazard_high)
            ):
                raise ValueError("event hazard failed finite strict advancement")
            if _hazard_pair_greater_than_scalar(
                next_hazard_high, next_hazard_low, terminal_hazard
            ):
                break

            while (
                checkpoint_index < request.kappas.size
                and _hazard_pair_greater_than_scalar(
                    next_hazard_high,
                    next_hazard_low,
                    float(request.kappas[checkpoint_index]) * total_rate,
                )
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
            event_times.append(
                next_hazard_high / total_rate
                + next_hazard_low / total_rate
            )
            if edge_id in open_edge_ids:
                duplicate_count += 1
            else:
                open_edge_ids.add(edge_id)
            current_hazard_high = next_hazard_high
            current_hazard_low = next_hazard_low

            while (
                checkpoint_index < request.kappas.size
                and _hazard_pair_at_least_scalar(
                    current_hazard_high,
                    current_hazard_low,
                    float(request.kappas[checkpoint_index]) * total_rate,
                )
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
    return TrajectoryDiagnostics(
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


def run_poisson_reference_with_diagnostics(
    request: TrajectoryRequest,
    kernel: F64,
) -> TrajectoryDiagnostics:
    validate_trajectory_request(request)
    _validate_kernel(request, kernel)
    streams = _build_reference_streams(request)
    return _run_poisson_with_streams(request, kernel, streams)
