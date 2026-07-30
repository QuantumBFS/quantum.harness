from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import multiprocessing
import os
import subprocess
import sys

import numba
import numpy as np
import pytest
from scipy.stats import norm

import long_range_percolation.poisson_sweep as poisson_sweep_module
from long_range_percolation.alias import AliasTable, build_distance_alias
from long_range_percolation.counter_rng import (
    STREAM_ALIAS_COLUMN,
    STREAM_ALIAS_THRESHOLD,
    STREAM_EDGE_OFFSET,
    STREAM_EXPONENTIAL,
    StreamIdentity,
    derive_stream_material,
)
from long_range_percolation.kernel import periodic_kernel
from long_range_percolation.poisson_reference import (
    TrajectoryRequest,
    run_poisson_reference,
)
from long_range_percolation.poisson_sweep import (
    _run_poisson_kernel,
    assert_nopython_signatures,
    run_poisson_numba,
)


def _digest(values: np.ndarray) -> str:
    return hashlib.sha256(values.tobytes(order="C")).hexdigest()


def _case(
    *,
    length: int = 8,
    sigma: float = 1.0,
    kappas: tuple[float, ...] = (0.0, 0.1, 0.4),
    seed: int = 194,
    replica: int = 7,
    kernel: np.ndarray | None = None,
) -> tuple[TrajectoryRequest, np.ndarray, AliasTable]:
    values = periodic_kernel(length, sigma) if kernel is None else kernel
    request = TrajectoryRequest(
        length=length,
        sigma=sigma,
        sigma_grid_id=f"task-7-sigma-{sigma!r}",
        kappas=np.asarray(kappas, dtype=np.float64),
        master_seed=seed,
        phase="validation",
        replica=replica,
        kernel_sha256=_digest(values),
    )
    table = build_distance_alias(length, sigma, values, request.kernel_sha256)
    return request, values, table


def _assert_result_equal(left, right, *, include_hash: bool = True) -> None:
    assert left.request_sha256 == right.request_sha256
    assert left.event_count == right.event_count
    assert left.duplicate_count == right.duplicate_count
    fields = [
        "observables",
        "terminal_counters",
        "draw_counts",
    ]
    if include_hash:
        fields.append("hash_diagnostics")
    for field in fields:
        np.testing.assert_array_equal(getattr(left, field), getattr(right, field))


def _run_replica_in_spawned_process(replica: int):
    return run_poisson_numba(*_case(replica=replica))


class _AuditWordStream:
    def __init__(self, identity: StreamIdentity, counter_delta: int = 0):
        material = derive_stream_material(identity)
        self.key = [int(value) for value in material.key]
        self.counter = [int(value) for value in material.initial_counter]
        carry = counter_delta
        for index in range(4):
            total = self.counter[index] + carry
            self.counter[index] = total & 0xFFFFFFFF
            carry = total >> 32
        self.block = [0, 0, 0, 0]
        self.lane = 4
        self.accounting = [0, 0, 0]

    def _generate(self) -> None:
        c0, c1, c2, c3 = self.counter
        k0, k1 = self.key
        for _ in range(10):
            product0 = 0xD2511F53 * c0
            product1 = 0xCD9E8D57 * c2
            c0, c1, c2, c3 = (
                ((product1 >> 32) ^ c1 ^ k0) & 0xFFFFFFFF,
                product1 & 0xFFFFFFFF,
                ((product0 >> 32) ^ c3 ^ k1) & 0xFFFFFFFF,
                product0 & 0xFFFFFFFF,
            )
            k0 = (k0 + 0x9E3779B9) & 0xFFFFFFFF
            k1 = (k1 + 0xBB67AE85) & 0xFFFFFFFF
        self.block[:] = (c0, c1, c2, c3)
        carry = 1
        for index in range(4):
            total = self.counter[index] + carry
            self.counter[index] = total & 0xFFFFFFFF
            carry = total >> 32
        self.lane = 0
        self.accounting[1] += 1

    def word(self) -> int:
        if self.lane == 4:
            self._generate()
        value = self.block[self.lane]
        self.lane += 1
        self.accounting[0] += 1
        return value

    def uniform(self) -> float:
        return (float(self.word()) + 0.5) * (2.0**-32)

    def bounded(self, bound: int) -> int:
        threshold = ((1 << 32) - bound) % bound
        while True:
            word = self.word()
            if word < threshold:
                self.accounting[2] += 1
                continue
            return word % bound


class _AuditEdgeSet:
    def __init__(self):
        self.keys = [0, 0]
        self.occupied = [False, False]
        self.size = 0
        self.total_probes = 0
        self.max_probe = 0
        self.rehashes = 0

    @staticmethod
    def _mix(value: int) -> int:
        mask = (1 << 64) - 1
        value = (value + 0x9E3779B97F4A7C15) & mask
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
        return (value ^ (value >> 31)) & mask

    def _probe(self, probe: int) -> None:
        self.total_probes += 1
        self.max_probe = max(self.max_probe, probe)

    def _grow(self) -> None:
        old_keys = self.keys
        old_occupied = self.occupied
        capacity = 2 * len(old_keys)
        self.keys = [0] * capacity
        self.occupied = [False] * capacity
        for old_slot, is_occupied in enumerate(old_occupied):
            if not is_occupied:
                continue
            value = old_keys[old_slot]
            slot = self._mix(value) & (capacity - 1)
            probe = 1
            while self.occupied[slot]:
                self._probe(probe)
                slot = (slot + 1) & (capacity - 1)
                probe += 1
            self._probe(probe)
            self.keys[slot] = value
            self.occupied[slot] = True
        self.rehashes += 1

    def insert(self, value: int) -> bool:
        while True:
            capacity = len(self.keys)
            slot = self._mix(value) & (capacity - 1)
            probe = 1
            while self.occupied[slot]:
                self._probe(probe)
                if self.keys[slot] == value:
                    return False
                slot = (slot + 1) & (capacity - 1)
                probe += 1
            self._probe(probe)
            if 10 * (self.size + 1) <= 7 * capacity:
                self.keys[slot] = value
                self.occupied[slot] = True
                self.size += 1
                return True
            self._grow()

    @property
    def diagnostics(self) -> np.ndarray:
        return np.asarray(
            (
                len(self.keys),
                self.size,
                self.total_probes,
                self.max_probe,
                self.rehashes,
            ),
            dtype=np.uint64,
        )


@dataclass(frozen=True)
class _AuditRun:
    observables: np.ndarray
    terminal_counters: np.ndarray
    draw_counts: np.ndarray
    event_times: tuple[float, ...]
    event_ids: tuple[int, ...]
    duplicate_flags: tuple[bool, ...]
    edge_sets: tuple[frozenset[int], ...]
    edge_set_sha256: str
    hash_diagnostics: np.ndarray


def _audit_observables(
    length: int, edge_ids: set[int], starts: np.ndarray
) -> tuple[float, ...]:
    parent = list(range(length))
    sizes = [1] * length
    masks = [1 << min(3, (4 * vertex) // length) for vertex in range(length)]

    def root(vertex: int) -> int:
        while parent[vertex] != vertex:
            vertex = parent[vertex]
        return vertex

    for edge_id in sorted(edge_ids):
        selected = 0
        while not int(starts[selected]) <= edge_id < int(starts[selected + 1]):
            selected += 1
        offset = edge_id - int(starts[selected])
        left = offset
        right = (offset + selected + 1) % length
        left_root = root(left)
        right_root = root(right)
        if left_root == right_root:
            continue
        if sizes[left_root] < sizes[right_root] or (
            sizes[left_root] == sizes[right_root] and left_root > right_root
        ):
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        sizes[left_root] += sizes[right_root]
        masks[left_root] |= masks[right_root]

    root_sizes = [sizes[index] for index in range(length) if parent[index] == index]
    largest = max(root_sizes)
    second = sorted(root_sizes, reverse=True)[1] if len(root_sizes) > 1 else 0
    sum_sq = math.fsum(float(value) ** 2 for value in root_sizes)
    sum_fourth = math.fsum(float(value) ** 4 for value in root_sizes)
    return (
        float(len(edge_ids)),
        float(len(root_sizes)),
        float(largest),
        float(second),
        float(largest) / float(length),
        float(second) / float(length),
        sum_sq,
        sum_fourth,
        sum_fourth / (sum_sq * sum_sq),
        float(
            any(
                parent[index] == index and masks[index] == 0b1111
                for index in range(length)
            )
        ),
    )


def _run_independent_audit(
    request: TrajectoryRequest,
    table: AliasTable,
    *,
    counter_deltas: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> _AuditRun:
    streams = [
        _AuditWordStream(
            StreamIdentity(
                request.master_seed,
                request.phase,
                request.length,
                request.sigma_grid_id,
                request.replica,
                stream_id,
            ),
            counter_deltas[stream_id],
        )
        for stream_id in range(4)
    ]
    starts = np.empty(table.multiplicity.size + 1, dtype=np.uint64)
    starts[0] = 0
    for index, value in enumerate(table.multiplicity):
        starts[index + 1] = starts[index] + value
    edge_table = _AuditEdgeSet()
    open_ids: set[int] = set()
    rows: list[tuple[float, ...]] = []
    snapshots: list[frozenset[int]] = []
    event_times: list[float] = []
    event_ids: list[int] = []
    duplicate_flags: list[bool] = []
    checkpoint = 0
    current = 0.0
    kappa_max = float(request.kappas[-1])

    def checkpoint_row() -> None:
        rows.append(_audit_observables(request.length, open_ids, starts))
        snapshots.append(frozenset(open_ids))

    while checkpoint < request.kappas.size and request.kappas[checkpoint] == 0.0:
        checkpoint_row()
        checkpoint += 1
    if kappa_max > 0.0:
        while True:
            hazard = -math.log(streams[STREAM_EXPONENTIAL].uniform())
            terminal_hazard = (kappa_max - current) * float(table.total_rate)
            if hazard > terminal_hazard:
                break
            next_kappa = current + hazard / float(table.total_rate)
            while (
                checkpoint < request.kappas.size
                and request.kappas[checkpoint] < next_kappa
            ):
                checkpoint_row()
                checkpoint += 1

            class_count = table.probability.size
            rejection_threshold = ((1 << 32) - class_count) % class_count
            while True:
                column_word = streams[STREAM_ALIAS_COLUMN].word()
                product = column_word * class_count
                if (product & 0xFFFFFFFF) < rejection_threshold:
                    streams[STREAM_ALIAS_COLUMN].accounting[2] += 1
                    continue
                column = product >> 32
                break
            threshold = (
                float(streams[STREAM_ALIAS_THRESHOLD].word()) + 0.5
            ) * (2.0**-32)
            selected = (
                column
                if threshold <= float(table.probability[column])
                else int(table.alias[column])
            )
            offset = streams[STREAM_EDGE_OFFSET].bounded(
                int(table.multiplicity[selected])
            )
            edge_id = int(starts[selected]) + offset
            inserted = edge_table.insert(edge_id)
            if inserted:
                open_ids.add(edge_id)
            event_times.append(next_kappa)
            event_ids.append(edge_id)
            duplicate_flags.append(not inserted)
            current = next_kappa
            while (
                checkpoint < request.kappas.size
                and request.kappas[checkpoint] <= current
            ):
                checkpoint_row()
                checkpoint += 1
    while checkpoint < request.kappas.size:
        checkpoint_row()
        checkpoint += 1

    encoded_edges = np.asarray(sorted(open_ids), dtype="<u8").tobytes()
    return _AuditRun(
        observables=np.asarray(rows, dtype=np.float64),
        terminal_counters=np.asarray(
            [stream.counter for stream in streams], dtype=np.uint32
        ),
        draw_counts=np.asarray(
            [stream.accounting for stream in streams], dtype=np.uint64
        ),
        event_times=tuple(event_times),
        event_ids=tuple(event_ids),
        duplicate_flags=tuple(duplicate_flags),
        edge_sets=tuple(snapshots),
        edge_set_sha256=hashlib.sha256(encoded_edges).hexdigest(),
        hash_diagnostics=edge_table.diagnostics,
    )


@numba.njit(cache=True, boundscheck=True, fastmath=False)
def _run_scripted_events(
    length: int,
    kappas: np.ndarray,
    interarrival: np.ndarray,
    class_index: np.ndarray,
    offsets: np.ndarray,
    multiplicity: np.ndarray,
    class_start: np.ndarray,
) -> tuple[np.ndarray, int, int]:
    """Test-only event semantics, independent of random class selection."""
    open_ids = np.zeros(int(class_start[-1]), dtype=np.uint8)
    parent = np.arange(length, dtype=np.int64)
    size = np.ones(length, dtype=np.int64)
    output = np.zeros((len(kappas), 3), dtype=np.int64)
    event_count = 0
    duplicate_count = 0
    open_count = 0
    checkpoint = 0
    current = 0.0

    while checkpoint < len(kappas) and kappas[checkpoint] == 0.0:
        output[checkpoint, 0] = open_count
        output[checkpoint, 1] = length
        output[checkpoint, 2] = 1
        checkpoint += 1

    for event in range(len(interarrival)):
        next_time = current + interarrival[event]
        while checkpoint < len(kappas) and kappas[checkpoint] < next_time:
            components = 0
            largest = 0
            for vertex in range(length):
                if parent[vertex] == vertex:
                    components += 1
                    largest = max(largest, size[vertex])
            output[checkpoint, 0] = open_count
            output[checkpoint, 1] = components
            output[checkpoint, 2] = largest
            checkpoint += 1
        if next_time > kappas[-1]:
            break

        selected = class_index[event]
        offset = offsets[event]
        edge_id = int(class_start[selected]) + offset
        event_count += 1
        if open_ids[edge_id]:
            duplicate_count += 1
        else:
            open_ids[edge_id] = 1
            open_count += 1
            distance = selected + 1
            left = offset
            right = (offset + distance) % length
            while parent[left] != left:
                left = parent[left]
            while parent[right] != right:
                right = parent[right]
            if left != right:
                if size[left] < size[right]:
                    left, right = right, left
                parent[right] = left
                size[left] += size[right]
        current = next_time
        while checkpoint < len(kappas) and kappas[checkpoint] <= current:
            components = 0
            largest = 0
            for vertex in range(length):
                if parent[vertex] == vertex:
                    components += 1
                    largest = max(largest, size[vertex])
            output[checkpoint, 0] = open_count
            output[checkpoint, 1] = components
            output[checkpoint, 2] = largest
            checkpoint += 1

    while checkpoint < len(kappas):
        components = 0
        largest = 0
        for vertex in range(length):
            if parent[vertex] == vertex:
                components += 1
                largest = max(largest, size[vertex])
        output[checkpoint, 0] = open_count
        output[checkpoint, 1] = components
        output[checkpoint, 2] = largest
        checkpoint += 1
    return output, event_count, duplicate_count


def test_scripted_event_semantics_cover_duplicates_antipodes_and_crossings():
    length = 6
    kappas = np.asarray((0.0, 0.1, 0.12, 0.2, 0.4), dtype=np.float64)
    interarrival = np.asarray((0.05, 0.07, 0.0, 0.19), dtype=np.float64)
    classes = np.asarray((2, 2, 0, 1), dtype=np.int64)
    offsets = np.asarray((1, 1, 0, 4), dtype=np.int64)
    multiplicity = np.asarray((6, 6, 3), dtype=np.uint64)
    starts = np.asarray((0, 6, 12, 15), dtype=np.uint64)

    actual, events, duplicates = _run_scripted_events(
        length, kappas, interarrival, classes, offsets, multiplicity, starts
    )
    expected = np.asarray(
        (
            (0, 6, 1),
            (1, 5, 2),
            (1, 5, 2),
            (2, 4, 3),
            (3, 4, 3),
        ),
        dtype=np.int64,
    )
    np.testing.assert_array_equal(actual, expected)
    assert (events, duplicates) == (4, 1)
    if not numba.config.DISABLE_JIT:
        assert _run_scripted_events.nopython_signatures


def test_numba_matches_reference_event_for_event_when_there_is_one_class():
    request, kernel, table = _case(
        length=2, kappas=(0.0, 0.1, 0.5, 2.0), seed=991
    )
    actual = run_poisson_numba(request, kernel, table)
    expected = run_poisson_reference(request, kernel)
    _assert_result_equal(actual, expected, include_hash=False)
    assert actual.hash_diagnostics[1] == 1


def test_independent_audit_matches_every_production_checkpoint_and_counter():
    request, kernel, table = _case(
        length=6,
        sigma=1.0,
        kappas=(0.0, 0.1, 0.3, 1.0, 3.0),
        seed=0x194,
        replica=23,
    )
    audit = _run_independent_audit(request, table)
    actual = run_poisson_numba(request, kernel, table)

    np.testing.assert_array_equal(actual.observables, audit.observables)
    np.testing.assert_array_equal(
        actual.terminal_counters, audit.terminal_counters
    )
    np.testing.assert_array_equal(actual.draw_counts, audit.draw_counts)
    np.testing.assert_array_equal(
        actual.hash_diagnostics, audit.hash_diagnostics
    )
    assert actual.event_count == len(audit.event_ids)
    assert actual.duplicate_count == sum(audit.duplicate_flags)
    assert int(actual.observables[-1, 0]) == len(audit.edge_sets[-1])
    encoded = np.asarray(sorted(audit.edge_sets[-1]), dtype="<u8").tobytes()
    assert hashlib.sha256(encoded).hexdigest() == audit.edge_set_sha256
    antipodal_start = int(np.sum(table.multiplicity[:-1]))
    assert any(edge_id >= antipodal_start for edge_id in audit.event_ids)
    assert any(audit.duplicate_flags)
    assert int(actual.hash_diagnostics[4]) > 0
    assert len(audit.edge_sets) == request.kappas.size
    assert actual.draw_counts[STREAM_EXPONENTIAL, 0] == len(audit.event_ids) + 1


def test_exact_terminal_event_is_included_with_prefix_and_neighbor_semantics():
    unit_kernel = np.asarray((1.0,), dtype=np.float64)
    base_request, _, table = _case(
        length=2,
        kappas=(1.0,),
        seed=0x194,
        replica=31,
        kernel=unit_kernel,
    )
    exponential = _AuditWordStream(
        StreamIdentity(
            base_request.master_seed,
            base_request.phase,
            base_request.length,
            base_request.sigma_grid_id,
            base_request.replica,
            STREAM_EXPONENTIAL,
        )
    )
    first_hazard = -math.log(exponential.uniform())
    assert first_hazard * table.total_rate == first_hazard

    exact = replace(
        base_request, kappas=np.asarray((first_hazard,), dtype=np.float64)
    )
    exact_result = run_poisson_numba(exact, unit_kernel, table)
    exact_audit = _run_independent_audit(exact, table)
    np.testing.assert_array_equal(exact_result.observables, exact_audit.observables)
    assert exact_result.event_count == 1
    np.testing.assert_array_equal(
        exact_result.draw_counts[:, 0], np.asarray((1, 1, 1, 2))
    )

    extended = replace(
        base_request,
        kappas=np.asarray((first_hazard, first_hazard + 1.0), dtype=np.float64),
    )
    extended_result = run_poisson_numba(extended, unit_kernel, table)
    np.testing.assert_array_equal(
        exact_result.observables[0], extended_result.observables[0]
    )

    below = replace(
        base_request,
        kappas=np.asarray(
            (np.nextafter(first_hazard, -math.inf),), dtype=np.float64
        ),
    )
    above = replace(
        base_request,
        kappas=np.asarray(
            (np.nextafter(first_hazard, math.inf),), dtype=np.float64
        ),
    )
    below_result = run_poisson_numba(below, unit_kernel, table)
    above_result = run_poisson_numba(above, unit_kernel, table)
    assert below_result.event_count == 0
    assert above_result.event_count == 1
    np.testing.assert_array_equal(
        above_result.observables[0], exact_result.observables[0]
    )
    assert below_result.draw_counts[STREAM_EXPONENTIAL, 0] == 1
    assert above_result.draw_counts[STREAM_EXPONENTIAL, 0] == 2


def test_initial_counter_perturbations_are_stream_local(monkeypatch):
    unit_kernel = np.asarray((1.0,), dtype=np.float64)
    provisional, _, table = _case(
        length=2,
        kappas=(1.0,),
        seed=774,
        replica=19,
        kernel=unit_kernel,
    )

    cumulative = []
    for delta in (0, 1):
        stream = _AuditWordStream(
            StreamIdentity(
                provisional.master_seed,
                provisional.phase,
                provisional.length,
                provisional.sigma_grid_id,
                provisional.replica,
                STREAM_EXPONENTIAL,
            ),
            delta,
        )
        first = -math.log(stream.uniform())
        second = first - math.log(stream.uniform())
        cumulative.append((first, second))
    lower = max(item[0] for item in cumulative)
    upper = min(item[1] for item in cumulative)
    assert lower < upper
    request = replace(
        provisional,
        kappas=np.asarray(((lower + upper) / 2.0,), dtype=np.float64),
    )
    original_builder = poisson_sweep_module._build_stream_state
    baseline = run_poisson_numba(request, unit_kernel, table)
    baseline_audit = _run_independent_audit(request, table)
    assert baseline.event_count == 1

    outcomes = []
    for changed_stream in range(4):
        def perturbed_builder(request_value, stream_id=changed_stream):
            state = original_builder(request_value)
            counters = state[0]
            carry = 1
            for word in range(4):
                total = int(counters[stream_id, word]) + carry
                counters[stream_id, word] = np.uint32(total & 0xFFFFFFFF)
                carry = total >> 32
            return state

        with monkeypatch.context() as context:
            context.setattr(
                poisson_sweep_module, "_build_stream_state", perturbed_builder
            )
            changed = run_poisson_numba(request, unit_kernel, table)
        audit_deltas = [0, 0, 0, 0]
        audit_deltas[changed_stream] = 1
        changed_audit = _run_independent_audit(
            request, table, counter_deltas=tuple(audit_deltas)
        )
        assert changed.event_count == baseline.event_count == 1
        unrelated = [index for index in range(4) if index != changed_stream]
        np.testing.assert_array_equal(
            changed.draw_counts[unrelated], baseline.draw_counts[unrelated]
        )
        np.testing.assert_array_equal(
            changed.terminal_counters[unrelated],
            baseline.terminal_counters[unrelated],
        )
        np.testing.assert_array_equal(
            changed.terminal_counters, changed_audit.terminal_counters
        )
        outcomes.append(
            (
                changed_stream,
                changed_audit.event_times,
                changed_audit.edge_set_sha256,
            )
        )

    assert outcomes[STREAM_EXPONENTIAL][1] != baseline_audit.event_times
    assert all(
        outcome[2] == baseline_audit.edge_set_sha256 for outcome in outcomes
    )


def test_draw_families_are_isolated_and_accounted():
    request, kernel, table = _case(length=10, kappas=(0.0, 0.3), seed=112)
    result = run_poisson_numba(request, kernel, table)
    assert result.draw_counts[STREAM_EXPONENTIAL, 0] == (
        result.event_count + int(request.kappas[-1] > 0.0)
    )
    assert result.draw_counts[STREAM_ALIAS_COLUMN, 0] >= result.event_count
    assert result.draw_counts[STREAM_ALIAS_THRESHOLD, 0] == result.event_count
    assert result.draw_counts[STREAM_EDGE_OFFSET, 0] >= result.event_count
    assert result.draw_counts[STREAM_EDGE_OFFSET, 2] == (
        result.draw_counts[STREAM_EDGE_OFFSET, 0] - result.event_count
    )
    assert result.draw_counts[STREAM_ALIAS_COLUMN, 2] == (
        result.draw_counts[STREAM_ALIAS_COLUMN, 0] - result.event_count
    )


def test_schedule_retry_and_process_order_are_byte_invariant():
    cases = [_case(replica=index) for index in (2, 9, 17)]
    forward = [run_poisson_numba(*case) for case in cases]
    reverse = {
        case[0].replica: run_poisson_numba(*case) for case in reversed(cases)
    }
    retry = run_poisson_numba(*cases[0])
    with multiprocessing.get_context("spawn").Pool(2) as pool:
        spawned = pool.map(_run_replica_in_spawned_process, (2, 9, 17))
    for case, result in zip(cases, forward, strict=True):
        _assert_result_equal(result, reverse[case[0].replica])
    for result, process_result in zip(forward, spawned, strict=True):
        _assert_result_equal(result, process_result)
    _assert_result_equal(forward[0], retry)


def test_zero_grid_and_extreme_model_parameters_are_finite():
    for length, sigma in (
        (2, 1.0),
        (8, math.ulp(1.0)),
        (8, 128.0),
    ):
        request, kernel, table = _case(
            length=length, sigma=sigma, kappas=(0.0,), replica=length
        )
        result = run_poisson_numba(request, kernel, table)
        assert result.event_count == 0
        assert not np.any(result.draw_counts)
        assert np.all(np.isfinite(result.observables))
        np.testing.assert_array_equal(
            result.observables[0, :4], (0.0, length, 1.0, 1.0 if length > 1 else 0.0)
        )


def test_terminal_equality_includes_event_and_overshoot_only_draws_exponential():
    request, kernel, table = _case(length=2, kappas=(0.5,), seed=4)
    result = run_poisson_numba(request, kernel, table)
    assert result.draw_counts[STREAM_EXPONENTIAL, 0] == result.event_count + 1
    assert result.draw_counts[STREAM_ALIAS_THRESHOLD, 0] == result.event_count


def test_duplicate_saturation_antipodes_and_hash_growth():
    request, kernel, table = _case(
        length=4,
        kappas=(25.0,),
        seed=12,
        kernel=np.asarray((1e-12, 1.0), dtype=np.float64),
    )
    result = run_poisson_numba(request, kernel, table)
    assert result.duplicate_count > 0
    assert result.observables[0, 0] == 2.0
    assert result.hash_diagnostics[1] == 2
    assert result.hash_diagnostics[4] > 0


def test_host_preflight_rejects_bad_alias_before_compiled_state_allocation(monkeypatch):
    request, kernel, table = _case()
    bad = replace(table, total_rate=math.inf)

    def forbidden(*args, **kwargs):
        raise AssertionError("allocation happened before immutable preflight")

    monkeypatch.setattr(
        "long_range_percolation.poisson_sweep.allocate_edge_set", forbidden
    )
    with pytest.raises(ValueError, match="alias"):
        run_poisson_numba(request, kernel, bad)


def test_alias_semantic_preflight_rejects_identity_bias_before_rng_state(monkeypatch):
    request, kernel, table = _case(length=10, sigma=0.8)
    malformed = replace(
        table,
        probability=np.ones_like(table.probability),
        alias=np.arange(table.alias.size, dtype=np.int64),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("RNG state was derived before alias rejection")

    monkeypatch.setattr(
        "long_range_percolation.poisson_sweep._build_stream_state", forbidden
    )
    with pytest.raises(ValueError, match="represented"):
        run_poisson_numba(request, kernel, malformed)


def test_alias_semantic_preflight_rejects_subtle_in_range_bias_before_rng_state(
    monkeypatch,
):
    request, kernel, table = _case(length=16, sigma=0.7)
    probability = table.probability.copy()
    index = int(np.argmin(probability))
    assert 0.0 < probability[index] < 1.0
    probability[index] = np.nextafter(
        probability[index] + 1e-10, 1.0
    )
    malformed = replace(table, probability=probability)

    def forbidden(*args, **kwargs):
        raise AssertionError("RNG state was derived before alias rejection")

    monkeypatch.setattr(
        "long_range_percolation.poisson_sweep._build_stream_state", forbidden
    )
    with pytest.raises(ValueError, match="represented"):
        run_poisson_numba(request, kernel, malformed)


def test_alias_semantic_preflight_accepts_production_size_roundoff():
    request, kernel, table = _case(
        length=2**18,
        sigma=1.0,
        kappas=(0.0,),
    )
    poisson_sweep_module._validate_alias(request, kernel, table)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda table: replace(table, probability=table.probability.astype(np.float32)),
        lambda table: replace(table, alias=table.alias[::-1]),
        lambda table: replace(table, multiplicity=table.multiplicity.copy() * 2),
        lambda table: replace(table, kernel_sha256="0" * 64),
        lambda table: replace(table, normalized_residual=math.nan),
    ),
)
def test_host_preflight_rejects_every_alias_contract_violation(mutation):
    request, kernel, table = _case()
    with pytest.raises(ValueError):
        run_poisson_numba(request, kernel, mutation(table))


def test_tiny_and_huge_rates_have_stable_preflight():
    tiny = np.asarray((np.nextafter(0.0, 1.0),), dtype=np.float64)
    request, _, table = _case(
        length=2,
        kappas=(np.finfo(np.float64).max,),
        kernel=tiny,
    )
    result = run_poisson_numba(request, tiny, table)
    assert result.event_count == 0
    assert np.all(np.isfinite(result.observables))

    huge = np.asarray((np.finfo(np.float64).max / 2.0,), dtype=np.float64)
    request, _, table = _case(length=2, kappas=(1e-100,), kernel=huge)
    with pytest.raises(ValueError, match="event count"):
        run_poisson_numba(request, huge, table)


def test_compensated_hazard_clock_retains_sub_ulp_increment():
    add = getattr(poisson_sweep_module, "_compensated_hazard_add", None)
    assert add is not None
    high = float(2**21)
    minimum_hazard = -math.log(
        (float(np.iinfo(np.uint32).max) + 0.5) * (2.0**-32)
    )
    next_high, next_low = add(high, 0.0, minimum_hazard)
    assert next_high == high
    assert 0.0 < next_low < math.ulp(high)


def test_open_edge_means_pass_registered_simultaneous_analytic_bounds():
    length = 6
    sigma = 0.8
    kappas = (0.05, 0.2, 0.5)
    replicas = 4096
    family_alpha = 0.001
    kernel = periodic_kernel(length, sigma)
    multiplicity = np.asarray((length, length, length // 2), dtype=np.float64)
    samples = np.empty((replicas, len(kappas)), dtype=np.float64)
    for replica in range(replicas):
        request, _, table = _case(
            length=length,
            sigma=sigma,
            kappas=kappas,
            seed=0x194,
            replica=replica,
            kernel=kernel,
        )
        samples[replica] = run_poisson_numba(
            request, kernel, table
        ).observables[:, 0]

    probabilities = -np.expm1(-np.outer(np.asarray(kappas), kernel))
    expected = probabilities @ multiplicity
    variances = (probabilities * (1.0 - probabilities)) @ multiplicity
    observed = np.mean(samples, axis=0)
    alpha_each = family_alpha / len(kappas)
    critical = float(norm.isf(alpha_each / 2.0))
    thresholds = critical * np.sqrt(variances / replicas)
    margins = thresholds - np.abs(observed - expected)
    raw_sums = np.sum(samples, axis=0, dtype=np.float64).astype(np.int64)
    print(
        "poisson_sweep_analytic_family "
        f"replicas={replicas} family_alpha={family_alpha:.17g} "
        f"alpha_each={alpha_each:.17g} raw_open_edge_sums="
        f"{raw_sums.tolist()} minimum_margin={float(np.min(margins)):.17g}"
    )
    assert family_alpha <= 0.001
    assert np.all(margins >= 0.0), {
        "observed": observed.tolist(),
        "expected": expected.tolist(),
        "variance": variances.tolist(),
        "threshold": thresholds.tolist(),
        "margin": margins.tolist(),
        "raw_open_edge_sums": raw_sums.tolist(),
    }


def test_result_is_immutable_and_exported_from_package():
    request, kernel, table = _case()
    result = run_poisson_numba(request, kernel, table)
    for value in (
        result.observables,
        result.terminal_counters,
        result.draw_counts,
        result.hash_diagnostics,
    ):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.flat[0] = 0
    from long_range_percolation import run_poisson_numba as exported

    assert exported is run_poisson_numba


def test_python_numba_and_disabled_jit_parity():
    unit_kernel = np.asarray((1.0,), dtype=np.float64)
    request, kernel, table = _case(
        length=2,
        kappas=(0.0, 0.7),
        seed=71,
        kernel=unit_kernel,
    )
    compiled = run_poisson_numba(request, kernel, table)
    code = """
import hashlib
import numpy as np
from long_range_percolation.alias import build_distance_alias
from long_range_percolation.poisson_reference import TrajectoryRequest
from long_range_percolation.poisson_sweep import run_poisson_numba
kernel=np.asarray([1.0], dtype=np.float64)
digest=hashlib.sha256(kernel.tobytes()).hexdigest()
request=TrajectoryRequest(2,1.0,"task-7-sigma-1.0",np.asarray([0.0,0.7]),71,"validation",7,digest)
table=build_distance_alias(2,1.0,kernel,digest)
result=run_poisson_numba(request,kernel,table)
print(result.observables.tobytes().hex())
print(result.terminal_counters.tobytes().hex())
print(result.draw_counts.tobytes().hex())
print(result.event_count, result.duplicate_count)
"""
    environment = dict(os.environ)
    environment["NUMBA_DISABLE_JIT"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    lines = completed.stdout.splitlines()
    assert lines == [
        compiled.observables.tobytes().hex(),
        compiled.terminal_counters.tobytes().hex(),
        compiled.draw_counts.tobytes().hex(),
        f"{compiled.event_count} {compiled.duplicate_count}",
    ]


def test_production_kernel_has_fixed_real_nopython_signature():
    request, kernel, table = _case()
    run_poisson_numba(request, kernel, table)
    if not numba.config.DISABLE_JIT:
        assert _run_poisson_kernel.nopython_signatures
        assert len(_run_poisson_kernel.signatures) == 1
        assert_nopython_signatures()
