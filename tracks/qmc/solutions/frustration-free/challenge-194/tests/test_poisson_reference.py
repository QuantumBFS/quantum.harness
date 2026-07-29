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
from long_range_percolation.enumeration import enumerate_graphs
from long_range_percolation.model import (
    ModelSpec,
    distance_classes,
    iter_unordered_edges,
)
from long_range_percolation.oracle import (
    expected_open_edges,
    no_edge_probability,
    variance_open_edges,
)
from long_range_percolation.poisson_reference import (
    TrajectoryRequest,
    TrajectoryResult,
    _PREFIX_REL_TOL,
    _build_reference_streams,
    _class_data,
    _compensated_prefix,
    _run_poisson_with_streams,
    run_poisson_reference,
    validate_trajectory_request,
)


UINT64_MAX = (1 << 64) - 1
FAMILYWISE_ALPHA = 0.001
EDGE_CASE_IDS = tuple(f"edge_marginal.{index}" for index in range(15))
COMPONENT_CASE_IDS = (
    "component_count.mean",
    "largest_component.mean",
    "second_component.mean",
    "s1_fraction.mean",
    "s2_fraction.mean",
    "sum_size_sq.mean",
    "sum_size_fourth.mean",
    "q_g.mean",
    "four_sector_crossing.mean",
)
STATISTICAL_CASE_IDS = (
    "interarrival.mean",
    "interarrival.variance",
    "interarrival.cdf_at_1",
    "event_count.mean",
    "event_count.variance",
    "event_count.p0",
    *EDGE_CASE_IDS,
    "no_edge.probability",
    "open_edges.mean",
    "open_edges.variance",
    *COMPONENT_CASE_IDS,
)


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
        offset_words: list[int] | None = None,
    ):
        self._uniforms = {
            STREAM_ALIAS_COLUMN: list(columns or []),
            STREAM_ALIAS_THRESHOLD: list(thresholds or []),
            STREAM_EXPONENTIAL: list(exponential),
        }
        self._offsets = list(offsets or [])
        self._offset_words = list(offset_words or [])
        self._positions = {stream: 0 for stream in self._uniforms}
        self._offset_position = 0
        self._offset_word_position = 0
        self.terminal_counters = np.zeros((STREAM_COUNT, 4), dtype=np.uint32)
        self.draw_counts = np.zeros((STREAM_COUNT, 3), dtype=np.uint64)

    @property
    def minimum_exponential_hazard(self) -> float:
        values = self._uniforms[STREAM_EXPONENTIAL]
        if not values:
            return -math.log(math.nextafter(1.0, 0.0))
        return min(-math.log(value) for value in values)

    def _record_word(self, stream_id: int) -> None:
        words = int(self.draw_counts[stream_id, 0])
        if words % 4 == 0:
            self.draw_counts[stream_id, 1] += np.uint64(1)
            self.terminal_counters[stream_id, 0] += np.uint32(1)
        self.draw_counts[stream_id, 0] += np.uint64(1)

    def uniform(self, stream_id: int) -> float:
        position = self._positions[stream_id]
        values = self._uniforms[stream_id]
        if position >= len(values):
            raise AssertionError(f"unexpected uniform draw from stream {stream_id}")
        self._positions[stream_id] = position + 1
        self._record_word(stream_id)
        return values[position]

    def bounded(self, stream_id: int, bound: int) -> int:
        assert stream_id == STREAM_EDGE_OFFSET
        if self._offset_words:
            threshold = ((1 << 32) - bound) % bound
            while True:
                if self._offset_word_position >= len(self._offset_words):
                    raise AssertionError("unexpected offset word draw")
                word = self._offset_words[self._offset_word_position]
                self._offset_word_position += 1
                self._record_word(stream_id)
                if word < threshold:
                    self.draw_counts[stream_id, 2] += np.uint64(1)
                    continue
                return word % bound
        if self._offset_position >= len(self._offsets):
            raise AssertionError("unexpected offset draw")
        value = self._offsets[self._offset_position]
        self._offset_position += 1
        self._record_word(stream_id)
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


def test_smallest_positive_rate_uses_hazard_terminal_comparison_without_overflow():
    kernel = np.asarray([np.nextafter(0.0, 1.0)], dtype=np.float64)
    request = make_request(
        length=2,
        kappas=[np.finfo(np.float64).max],
        kernel=kernel,
    )
    streams = ScriptedStreams(exponential=[0.5])
    result = _run_poisson_with_streams(request, kernel, streams).result
    assert result.event_count == result.duplicate_count == 0
    np.testing.assert_array_equal(result.observables[:, 0], [0.0])
    np.testing.assert_array_equal(
        result.draw_counts,
        [[0, 0, 0], [0, 0, 0], [0, 0, 0], [1, 1, 0]],
    )
    np.testing.assert_array_equal(
        result.terminal_counters[:, 0], [0, 0, 0, 1]
    )


def test_terminal_hazard_equality_and_neighbor_have_exact_draw_schedules():
    kernel = np.asarray([1.0], dtype=np.float64)
    uniform = 0.5
    hazard = -math.log(uniform)

    equal_request = make_request(length=2, kappas=[hazard], kernel=kernel)
    equal_streams = ScriptedStreams(exponential=[uniform])
    equal = _run_poisson_with_streams(
        equal_request, kernel, equal_streams
    ).result
    assert equal.event_count == 0
    np.testing.assert_array_equal(
        equal.draw_counts,
        [[0, 0, 0], [0, 0, 0], [0, 0, 0], [1, 1, 0]],
    )
    np.testing.assert_array_equal(
        equal.terminal_counters[:, 0], [0, 0, 0, 1]
    )

    above_request = make_request(
        length=2,
        kappas=[math.nextafter(hazard, math.inf)],
        kernel=kernel,
    )
    above_streams = ScriptedStreams(
        exponential=[uniform, 0.25],
        columns=[0.5],
        thresholds=[0.5],
        offsets=[0],
    )
    above = _run_poisson_with_streams(
        above_request, kernel, above_streams
    ).result
    assert above.event_count == 1
    np.testing.assert_array_equal(
        above.draw_counts,
        [[1, 1, 0], [1, 1, 0], [1, 1, 0], [2, 1, 0]],
    )
    np.testing.assert_array_equal(
        above.terminal_counters[:, 0], [1, 1, 1, 1]
    )


def test_huge_finite_rate_fails_preflight_before_consuming_streams():
    kernel = np.asarray([np.finfo(np.float64).max / 2.0], dtype=np.float64)
    request = make_request(length=2, kappas=[1e-100], kernel=kernel)
    streams = ScriptedStreams(exponential=[])
    with pytest.raises(ValueError, match="event ordering"):
        _run_poisson_with_streams(request, kernel, streams)
    assert not np.any(streams.draw_counts)
    assert not np.any(streams.terminal_counters)


def test_huge_rate_tiny_terminal_hazard_overshoots_without_dividing():
    kernel = np.asarray([np.finfo(np.float64).max / 2.0], dtype=np.float64)
    request = make_request(
        length=2,
        kappas=[np.nextafter(0.0, 1.0)],
        kernel=kernel,
    )
    streams = ScriptedStreams(exponential=[0.9999999999])
    result = _run_poisson_with_streams(request, kernel, streams).result
    assert result.event_count == 0
    np.testing.assert_array_equal(
        result.draw_counts,
        [[0, 0, 0], [0, 0, 0], [0, 0, 0], [1, 1, 0]],
    )


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


def test_non_power_of_two_offset_rejection_is_stream_local_and_exact():
    kernel = np.asarray([1.0, 1e-12, 1e-12], dtype=np.float64)
    total_rate = math.fsum((6.0, 6e-12, 3e-12))
    request = make_request(length=6, kappas=[0.1], kernel=kernel)
    streams = ScriptedStreams(
        exponential=[math.exp(-0.05 * total_rate), math.exp(-1.0)],
        columns=[0.5],
        thresholds=[0.1],
        offset_words=[3, 10],
    )
    result = _run_poisson_with_streams(request, kernel, streams).result
    assert result.event_count == 1
    np.testing.assert_array_equal(
        result.draw_counts,
        [
            [1, 1, 0],
            [1, 1, 0],
            [2, 1, 1],
            [2, 1, 0],
        ],
    )
    np.testing.assert_array_equal(result.terminal_counters[:, 0], [1, 1, 1, 1])
    assert result.draw_counts[STREAM_ALIAS_COLUMN, 0] == result.event_count
    assert result.draw_counts[STREAM_ALIAS_THRESHOLD, 0] == result.event_count
    assert result.draw_counts[STREAM_EXPONENTIAL, 0] == result.event_count + 1


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


def test_compensated_prefix_is_monotone_accurate_and_linear_at_large_n():
    count = 1 << 17
    weights = tuple(
        1.0 if index % 2 == 0 else np.finfo(np.float64).eps
        for index in range(count)
    )
    cumulative, total, operations = _compensated_prefix(weights)
    exact = math.fsum(weights)
    assert len(cumulative) == count
    assert operations == count
    assert all(
        cumulative[index] <= cumulative[index + 1]
        for index in range(count - 1)
    )
    assert cumulative[-1] == total
    assert abs(total - exact) <= _PREFIX_REL_TOL * exact

    length = count * 2
    kernel = np.ones(count, dtype=np.float64)
    _, _, class_cumulative, class_total = _class_data(length, kernel)
    assert len(class_cumulative) == count
    assert class_cumulative[-1] == class_total


def _statistical_result(
    *,
    case_id: str,
    observed: float,
    expected: float,
    standard_error: float,
    z_score: float,
) -> tuple[str, float, float]:
    threshold = z_score * standard_error
    deviation = abs(observed - expected)
    signed_margin = threshold - deviation
    z_observed = deviation / standard_error
    p_value = float(2.0 * norm.sf(z_observed))
    assert signed_margin >= 0.0, (
        f"{case_id}: raw_observed={observed:.17g}, expected={expected:.17g}, "
        f"threshold={threshold:.17g}, signed_margin={signed_margin:.17g}, "
        f"p_value={p_value:.17g}"
    )
    return case_id, p_value, signed_margin


def test_statistical_case_registry_is_unique_complete_and_familywise_bounded():
    assert len(STATISTICAL_CASE_IDS) == len(set(STATISTICAL_CASE_IDS))
    expected = {
        "interarrival.mean",
        "interarrival.variance",
        "interarrival.cdf_at_1",
        "event_count.mean",
        "event_count.variance",
        "event_count.p0",
        *(f"edge_marginal.{index}" for index in range(15)),
        "no_edge.probability",
        "open_edges.mean",
        "open_edges.variance",
        "component_count.mean",
        "largest_component.mean",
        "second_component.mean",
        "s1_fraction.mean",
        "s2_fraction.mean",
        "sum_size_sq.mean",
        "sum_size_fourth.mean",
        "q_g.mean",
        "four_sector_crossing.mean",
    }
    assert set(STATISTICAL_CASE_IDS) == expected
    allocated_alpha = math.fsum(
        FAMILYWISE_ALPHA / len(STATISTICAL_CASE_IDS)
        for _ in STATISTICAL_CASE_IDS
    )
    assert allocated_alpha <= FAMILYWISE_ALPHA


def test_complete_reference_statistical_family():
    request = make_request(kappas=[0.1], master_seed=991)
    streams = _build_reference_streams(request)
    sample = np.asarray(
        [
            -math.log(streams.uniform(STREAM_EXPONENTIAL))
            for _ in range(12_000)
        ]
    )
    observations: list[tuple[str, float, float, float]] = [
        (
            "interarrival.mean",
            float(np.mean(sample)),
            1.0,
            1.0 / math.sqrt(sample.size),
        ),
        (
            "interarrival.variance",
            float(np.var(sample, ddof=1)),
            1.0,
            math.sqrt(8.0 / (sample.size - 1)),
        ),
        (
            "interarrival.cdf_at_1",
            float(np.mean(sample <= 1.0)),
            1.0 - math.exp(-1.0),
            math.sqrt(
                (1.0 - math.exp(-1.0))
                * math.exp(-1.0)
                / sample.size
            ),
        ),
    ]
    alpha_each = FAMILYWISE_ALPHA / len(STATISTICAL_CASE_IDS)
    z_score = float(norm.isf(alpha_each / 2.0))

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
    component_samples = np.empty((replicas, len(COMPONENT_CASE_IDS)))
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
        component_samples[replica] = run.result.observables[0, 1:10]
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

    observations.append(
        (
            "event_count.mean",
            float(np.mean(event_counts)),
            poisson_mean,
            math.sqrt(poisson_mean / replicas),
        )
    )
    poisson_variance_se = math.sqrt(
        (
            poisson_mean
            + 3.0 * poisson_mean**2
            - ((replicas - 3) / (replicas - 1)) * poisson_mean**2
        )
        / replicas
    )
    observations.append(
        (
            "event_count.variance",
            float(np.var(event_counts, ddof=1)),
            poisson_mean,
            poisson_variance_se,
        )
    )
    poisson_zero = math.exp(-poisson_mean)
    observations.append(
        (
            "event_count.p0",
            float(np.mean(event_counts == 0.0)),
            poisson_zero,
            math.sqrt(poisson_zero * (1.0 - poisson_zero) / replicas),
        )
    )
    for edge_id, probability in enumerate(edge_probability):
        observations.append(
            (
                f"edge_marginal.{edge_id}",
                float(edge_hits[edge_id] / replicas),
                float(probability),
                math.sqrt(
                    float(probability * (1.0 - probability)) / replicas
                ),
            )
        )
    no_edge_expected = no_edge_probability(spec)
    observations.append(
        (
            "no_edge.probability",
            no_edge / replicas,
            no_edge_expected,
            math.sqrt(
                no_edge_expected * (1.0 - no_edge_expected) / replicas
            ),
        )
    )
    observations.append(
        (
            "open_edges.mean",
            float(np.mean(open_counts)),
            expected_mean,
            math.sqrt(expected_variance / replicas),
        )
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
    observations.append(
        (
            "open_edges.variance",
            float(np.var(open_counts, ddof=1)),
            expected_variance,
            variance_standard_error,
        )
    )

    edges = list(iter_unordered_edges(length))
    component_values = []
    component_probabilities = []
    for outcome in enumerate_graphs(spec):
        sizes = outcome.component_sizes
        sum_sq = math.fsum(float(size) ** 2 for size in sizes)
        sum_fourth = math.fsum(float(size) ** 4 for size in sizes)
        connectivity = poisson_reference.UnionFind(length)
        for edge_index, (left, right) in enumerate(edges):
            if outcome.mask & (1 << edge_index):
                connectivity.union(left, right)
        labels = connectivity.labels().tolist()
        sectors: dict[int, int] = {}
        for vertex, label in enumerate(labels):
            sectors[label] = sectors.get(label, 0) | (
                1 << min(3, (4 * vertex) // length)
            )
        component_values.append(
            (
                float(len(sizes)),
                float(sizes[0]),
                float(sizes[1] if len(sizes) > 1 else 0),
                float(sizes[0]) / length,
                float(sizes[1] if len(sizes) > 1 else 0) / length,
                sum_sq,
                sum_fourth,
                sum_fourth / (sum_sq * sum_sq),
                float(any(mask == 0b1111 for mask in sectors.values())),
            )
        )
        component_probabilities.append(outcome.probability)
    values = np.asarray(component_values, dtype=np.float64)
    probabilities = np.asarray(component_probabilities, dtype=np.float64)
    for index, case_id in enumerate(COMPONENT_CASE_IDS):
        expected = float(probabilities @ values[:, index])
        variance = float(
            probabilities @ ((values[:, index] - expected) ** 2)
        )
        observations.append(
            (
                case_id,
                float(np.mean(component_samples[:, index])),
                expected,
                math.sqrt(variance / replicas),
            )
        )

    assert {item[0] for item in observations} == set(STATISTICAL_CASE_IDS)
    results = [
        _statistical_result(
            case_id=case_id,
            observed=observed,
            expected=expected,
            standard_error=standard_error,
            z_score=z_score,
        )
        for case_id, observed, expected, standard_error in observations
    ]
    minimum_p = min(item[1] for item in results)
    minimum_margin = min(item[2] for item in results)
    print(
        "statistical_family "
        f"laws={len(results)} alpha_each={alpha_each:.17g} "
        f"minimum_p_value={minimum_p:.17g} "
        f"minimum_signed_margin={minimum_margin:.17g}"
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
