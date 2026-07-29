from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import math

import numpy as np
import pytest
from scipy.stats import norm

import long_range_percolation.poisson_reference as poisson_reference
from long_range_percolation.counter_rng import (
    STREAM_ALIAS_COLUMN,
    STREAM_ALIAS_THRESHOLD,
    STREAM_COUNT,
    STREAM_EDGE_OFFSET,
    STREAM_EXPONENTIAL,
)
from long_range_percolation.kernel import periodic_kernel
from long_range_percolation.model import ModelSpec, distance_classes
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
    variance_open_edges,
)
from long_range_percolation.poisson_reference import (
    TrajectoryRequest,
    TrajectoryResult,
    _build_reference_streams,
    _run_poisson_with_streams,
    run_poisson_reference,
    validate_trajectory_request,
)


UINT64_MAX = (1 << 64) - 1


def digest(kernel: np.ndarray) -> str:
    return hashlib.sha256(kernel.tobytes(order="C")).hexdigest()


def make_request(
    *,
    length: int = 6,
    sigma: float = 1.0,
    kappas: object = (0.0, 0.2),
    master_seed: int = 123,
    phase: str = "validation",
    replica: int = 4,
    sigma_grid_id: str = "sigma-1-test",
    kernel: np.ndarray | None = None,
    kernel_sha256: str | None = None,
) -> TrajectoryRequest:
    values = periodic_kernel(length, sigma) if kernel is None else kernel
    return TrajectoryRequest(
        length=length,
        sigma=sigma,
        sigma_grid_id=sigma_grid_id,
        kappas=np.asarray(kappas, dtype=np.float64),
        master_seed=master_seed,
        phase=phase,
        replica=replica,
        kernel_sha256=digest(values) if kernel_sha256 is None else kernel_sha256,
    )


class ScriptedStreams:
    def __init__(
        self,
        *,
        exponential: list[float],
        columns: list[float] | None = None,
        thresholds: list[float] | None = None,
        offsets: list[int] | None = None,
    ):
        self._uniforms = {
            STREAM_ALIAS_COLUMN: list(columns or []),
            STREAM_ALIAS_THRESHOLD: list(thresholds or []),
            STREAM_EXPONENTIAL: list(exponential),
        }
        self._offsets = list(offsets or [])
        self._positions = {stream: 0 for stream in self._uniforms}
        self._offset_position = 0
        self.terminal_counters = np.zeros((STREAM_COUNT, 4), dtype=np.uint32)
        self.draw_counts = np.zeros((STREAM_COUNT, 3), dtype=np.uint64)

    def uniform(self, stream_id: int) -> float:
        position = self._positions[stream_id]
        values = self._uniforms[stream_id]
        if position >= len(values):
            raise AssertionError(f"unexpected uniform draw from stream {stream_id}")
        self._positions[stream_id] = position + 1
        self.draw_counts[stream_id, 0] += np.uint64(1)
        return values[position]

    def bounded(self, stream_id: int, bound: int) -> int:
        assert stream_id == STREAM_EDGE_OFFSET
        if self._offset_position >= len(self._offsets):
            raise AssertionError("unexpected offset draw")
        value = self._offsets[self._offset_position]
        self._offset_position += 1
        self.draw_counts[stream_id, 0] += np.uint64(1)
        if not 0 <= value < bound:
            raise AssertionError("scripted offset is outside its requested bound")
        return value


def test_request_rejects_nonfinite_unsorted_or_duplicate_couplings():
    for values in ([0.2, 0.1], [0.1, 0.1], [math.nan], [math.inf], [-1.0]):
        with pytest.raises(ValueError):
            validate_trajectory_request(make_request(kappas=values))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("length", True),
        ("length", 3),
        ("length", 0),
        ("sigma", True),
        ("sigma", 0.0),
        ("sigma", math.inf),
        ("sigma", np.nextafter(0.0, 1.0)),
        ("master_seed", True),
        ("master_seed", -1),
        ("master_seed", 1 << 64),
        ("replica", True),
        ("replica", -1),
        ("replica", 1 << 64),
        ("phase", "unknown"),
        ("sigma_grid_id", ""),
        ("sigma_grid_id", " padded "),
        ("kernel_sha256", "not-a-digest"),
    ],
)
def test_request_rejects_every_invalid_scalar(field: str, value: object):
    request = make_request()
    with pytest.raises(ValueError):
        validate_trajectory_request(replace(request, **{field: value}))


def test_request_accepts_uint64_boundaries_and_freezes_a_defensive_kappa_copy():
    kappas = np.asarray([0.0, 0.25], dtype=np.float64)
    request = make_request(
        kappas=kappas, master_seed=UINT64_MAX, replica=UINT64_MAX
    )
    kappas[1] = 9.0
    np.testing.assert_array_equal(request.kappas, [0.0, 0.25])
    assert not request.kappas.flags.writeable
    validate_trajectory_request(request)
    with pytest.raises(ValueError):
        request.kappas[0] = 1.0


def test_kernel_preflight_rejects_shape_dtype_layout_values_and_digest():
    request = make_request(kappas=[0.1])
    valid = periodic_kernel(request.length, request.sigma)
    invalid = (
        valid[:-1],
        valid.astype(np.float32),
        np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64),
        np.asarray([1.0, math.nan, 3.0], dtype=np.float64),
        np.asarray([1.0, 0.0, 3.0], dtype=np.float64),
        np.arange(6.0, dtype=np.float64)[::2],
    )
    for kernel in invalid:
        with pytest.raises(ValueError):
            run_poisson_reference(request, kernel)
    with pytest.raises(ValueError, match="digest"):
        run_poisson_reference(
            replace(request, kernel_sha256="0" * 64),
            valid,
        )


def test_reference_does_not_import_compiled_selection_or_connectivity():
    source = inspect.getsource(poisson_reference)
    forbidden = ("alias", "edge_set", "production_union_find", "poisson_sweep")
    for name in forbidden:
        assert f"import {name}" not in source
        assert f"from .{name}" not in source


def test_scripted_events_have_exact_checkpoint_duplicate_and_overshoot_semantics():
    kernel = np.asarray([1.0, 2.0, 3.0], dtype=np.float64)
    total_rate = 6.0 + 12.0 + 9.0
    request = make_request(
        kappas=[0.0, 0.1, 0.13, 0.18, 0.2, 0.3, 0.4],
        kernel=kernel,
    )
    streams = ScriptedStreams(
        exponential=[
            math.exp(-0.05 * total_rate),
            math.exp(-0.07 * total_rate),
            math.exp(-0.13 * total_rate),
            math.exp(-0.20 * total_rate),
        ],
        columns=[0.2, 0.4, 0.6],
        thresholds=[0.1, 0.1, 0.9],
        offsets=[0, 0, 2],
    )

    run = _run_poisson_with_streams(request, kernel, streams)
    result = run.result

    assert result.event_count == 3
    assert result.duplicate_count == 1
    np.testing.assert_array_equal(
        result.observables[:, 0],
        [0.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0],
    )
    assert run.event_times == pytest.approx((0.05, 0.12, 0.25))
    assert run.edge_ids_by_checkpoint[0] == frozenset()
    assert run.edge_ids_by_checkpoint[1] == frozenset({0})
    assert run.edge_ids_by_checkpoint[2:5] == (frozenset({0}),) * 3
    assert run.edge_ids_by_checkpoint[5:] == (frozenset({0, 14}),) * 2
    np.testing.assert_array_equal(
        result.draw_counts[:, 0],
        [3, 3, 3, 4],
    )
    np.testing.assert_array_equal(result.hash_diagnostics, np.zeros(5))


def test_zero_only_request_records_empty_graph_without_any_draw():
    kernel = periodic_kernel(8, 1.0)
    request = make_request(length=8, kappas=[0.0], kernel=kernel)
    streams = ScriptedStreams(exponential=[])
    result = _run_poisson_with_streams(request, kernel, streams).result
    assert result.event_count == result.duplicate_count == 0
    assert result.observables[0, 0] == 0.0
    assert result.observables[0, 1] == 8.0
    assert result.observables[0, 2] == 1.0
    assert not np.any(result.draw_counts)


def test_positive_terminal_coupling_consumes_only_final_overshoot_exponential():
    kernel = np.asarray([1.0, 1.0], dtype=np.float64)
    request = make_request(length=4, kappas=[0.1], kernel=kernel)
    streams = ScriptedStreams(exponential=[math.exp(-1.0)])
    result = _run_poisson_with_streams(request, kernel, streams).result
    assert result.event_count == 0
    np.testing.assert_array_equal(result.draw_counts[:, 0], [0, 0, 0, 1])


def test_antipodal_offset_decoding_and_duplicate_suppression():
    kernel = np.asarray([1e-12, 1.0], dtype=np.float64)
    total_rate = 4e-12 + 2.0
    request = make_request(length=4, kappas=[1.0], kernel=kernel)
    streams = ScriptedStreams(
        exponential=[
            math.exp(-0.1 * total_rate),
            math.exp(-0.1 * total_rate),
            math.exp(-2.0 * total_rate),
        ],
        columns=[0.1, 0.2],
        thresholds=[0.9, 0.9],
        offsets=[1, 1],
    )
    run = _run_poisson_with_streams(request, kernel, streams)
    assert run.result.event_count == 2
    assert run.result.duplicate_count == 1
    assert run.edge_ids_by_checkpoint == (frozenset({5}),)
    assert run.result.observables[0, 0] == 1.0
    assert run.result.observables[0, 2] == 2.0


def test_results_are_reproducible_schedule_independent_and_immutable():
    kernel = periodic_kernel(8, 0.75)
    requests = [
        make_request(
            length=8,
            sigma=0.75,
            kappas=[0.0, 0.2, 0.7],
            replica=replica,
            kernel=kernel,
        )
        for replica in (2, 9)
    ]
    forward = [run_poisson_reference(request, kernel) for request in requests]
    reverse = {
        request.replica: run_poisson_reference(request, kernel)
        for request in reversed(requests)
    }
    repeated = run_poisson_reference(requests[0], kernel)

    for request, first in zip(requests, forward, strict=True):
        second = reverse[request.replica]
        assert first.request_sha256 == second.request_sha256
        for name in (
            "observables",
            "terminal_counters",
            "draw_counts",
            "hash_diagnostics",
        ):
            np.testing.assert_array_equal(
                getattr(first, name), getattr(second, name)
            )
    np.testing.assert_array_equal(forward[0].observables, repeated.observables)
    for array in (
        forward[0].observables,
        forward[0].terminal_counters,
        forward[0].draw_counts,
        forward[0].hash_diagnostics,
    ):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.flat[0] = 0


def _assert_statistical_law(
    *,
    name: str,
    observed: float,
    expected: float,
    standard_error: float,
    z_score: float,
) -> None:
    threshold = z_score * standard_error
    signed_margin = threshold - abs(observed - expected)
    assert signed_margin >= 0.0, (
        f"{name}: raw_observed={observed:.17g}, expected={expected:.17g}, "
        f"threshold={threshold:.17g}, signed_margin={signed_margin:.17g}"
    )


def test_fixed_identity_stream_interarrivals_have_exponential_moments():
    request = make_request(kappas=[0.1], master_seed=991)
    streams = _build_reference_streams(request)
    sample = np.asarray(
        [
            -math.log(streams.uniform(STREAM_EXPONENTIAL))
            for _ in range(12_000)
        ]
    )
    alpha_each = 0.001 / 2
    z_score = float(norm.isf(alpha_each / 2.0))
    _assert_statistical_law(
        name="unit exponential mean",
        observed=float(np.mean(sample)),
        expected=1.0,
        standard_error=1.0 / math.sqrt(sample.size),
        z_score=z_score,
    )
    _assert_statistical_law(
        name="unit exponential variance",
        observed=float(np.var(sample, ddof=1)),
        expected=1.0,
        standard_error=math.sqrt(8.0 / (sample.size - 1)),
        z_score=z_score,
    )


def test_poisson_counts_bernoulli_marginals_and_open_edge_laws():
    length = 6
    sigma = 1.0
    kappa = 0.18
    replicas = 6_000
    kernel = periodic_kernel(length, sigma)
    classes = distance_classes(length)
    class_starts = np.cumsum(
        [0, *(item.multiplicity for item in classes)], dtype=np.int64
    )
    edge_rates = np.concatenate(
        [
            np.full(item.multiplicity, kernel[index], dtype=np.float64)
            for index, item in enumerate(classes)
        ]
    )
    total_rate = math.fsum(edge_rates.tolist())

    event_counts = np.empty(replicas, dtype=np.float64)
    open_counts = np.empty(replicas, dtype=np.float64)
    edge_hits = np.zeros(edge_rates.size, dtype=np.float64)
    no_edge = 0
    for replica in range(replicas):
        request = make_request(
            length=length,
            sigma=sigma,
            kappas=[kappa],
            master_seed=0x194,
            replica=replica,
            kernel=kernel,
        )
        run = _run_poisson_with_streams(
            request, kernel, _build_reference_streams(request)
        )
        event_counts[replica] = run.result.event_count
        open_counts[replica] = run.result.observables[0, 0]
        ids = run.edge_ids_by_checkpoint[0]
        if not ids:
            no_edge += 1
        for edge_id in ids:
            edge_hits[edge_id] += 1.0

    poisson_mean = kappa * total_rate
    edge_probability = -np.expm1(-kappa * edge_rates)
    spec = ModelSpec(length, sigma, kappa)
    expected_mean = expected_open_edges(spec)
    expected_variance = variance_open_edges(spec)

    law_count = 2 + edge_rates.size + 3
    alpha_each = 0.001 / law_count
    z_score = float(norm.isf(alpha_each / 2.0))

    _assert_statistical_law(
        name="Poisson event-count mean",
        observed=float(np.mean(event_counts)),
        expected=poisson_mean,
        standard_error=math.sqrt(poisson_mean / replicas),
        z_score=z_score,
    )
    poisson_variance_se = math.sqrt(
        (
            poisson_mean
            + 3.0 * poisson_mean**2
            - ((replicas - 3) / (replicas - 1)) * poisson_mean**2
        )
        / replicas
    )
    _assert_statistical_law(
        name="Poisson event-count variance",
        observed=float(np.var(event_counts, ddof=1)),
        expected=poisson_mean,
        standard_error=poisson_variance_se,
        z_score=z_score,
    )
    for edge_id, probability in enumerate(edge_probability):
        _assert_statistical_law(
            name=f"Bernoulli edge marginal {edge_id}",
            observed=float(edge_hits[edge_id] / replicas),
            expected=float(probability),
            standard_error=math.sqrt(
                float(probability * (1.0 - probability)) / replicas
            ),
            z_score=z_score,
        )
    _assert_statistical_law(
        name="no-edge law",
        observed=no_edge / replicas,
        expected=no_edge_probability(spec),
        standard_error=math.sqrt(
            no_edge_probability(spec)
            * (1.0 - no_edge_probability(spec))
            / replicas
        ),
        z_score=z_score,
    )
    _assert_statistical_law(
        name="open-edge mean",
        observed=float(np.mean(open_counts)),
        expected=expected_mean,
        standard_error=math.sqrt(expected_variance / replicas),
        z_score=z_score,
    )
    fourth_central = (
        3.0 * expected_variance**2
        + math.fsum(
            (
                float(probability)
                * (1.0 - float(probability))
                * (
                    1.0
                    - 6.0
                    * float(probability)
                    * (1.0 - float(probability))
                )
            )
            for probability in edge_probability
        )
    )
    variance_standard_error = math.sqrt(
        (
            fourth_central
            - ((replicas - 3) / (replicas - 1)) * expected_variance**2
        )
        / replicas
    )
    _assert_statistical_law(
        name="open-edge variance",
        observed=float(np.var(open_counts, ddof=1)),
        expected=expected_variance,
        standard_error=variance_standard_error,
        z_score=z_score,
    )


def test_result_constructor_defensively_freezes_exact_array_contract():
    arrays = {
        "observables": np.zeros((1, 10), dtype=np.float64),
        "terminal_counters": np.zeros((STREAM_COUNT, 4), dtype=np.uint32),
        "draw_counts": np.zeros((STREAM_COUNT, 3), dtype=np.uint64),
        "hash_diagnostics": np.zeros(5, dtype=np.uint64),
    }
    result = TrajectoryResult(
        request_sha256="1" * 64,
        event_count=0,
        duplicate_count=0,
        **arrays,
    )
    for array in arrays.values():
        array.flat[0] = 1
    assert not np.any(result.observables)
    assert not np.any(result.terminal_counters)
    assert not np.any(result.draw_counts)
    assert not np.any(result.hash_diagnostics)
    for array in (
        result.observables,
        result.terminal_counters,
        result.draw_counts,
        result.hash_diagnostics,
    ):
        assert not array.flags.writeable
