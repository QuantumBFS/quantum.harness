from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import multiprocessing
import os
import subprocess
import sys

import numba
import numpy as np
import pytest

from long_range_percolation.alias import AliasTable, build_distance_alias
from long_range_percolation.counter_rng import (
    STREAM_ALIAS_COLUMN,
    STREAM_ALIAS_THRESHOLD,
    STREAM_EDGE_OFFSET,
    STREAM_EXPONENTIAL,
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
    with pytest.raises(ValueError, match="event ordering"):
        run_poisson_numba(request, huge, table)


def test_independent_reference_and_numba_are_statistically_equivalent():
    production = []
    reference = []
    for replica in range(256):
        case = _case(
            length=6,
            sigma=0.8,
            kappas=(0.2,),
            seed=0x194,
            replica=replica,
        )
        production.append(run_poisson_numba(*case).observables[0, :4])
        reference.append(run_poisson_reference(case[0], case[1]).observables[0, :4])
    production_mean = np.mean(np.asarray(production), axis=0)
    reference_mean = np.mean(np.asarray(reference), axis=0)
    np.testing.assert_allclose(production_mean, reference_mean, rtol=0.08, atol=0.08)


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
