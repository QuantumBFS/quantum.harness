from __future__ import annotations

from dataclasses import dataclass, replace
import inspect
import json
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.optimize import minimize

import qcontrol.closed_loop as closed_loop_module
from qcontrol.closed_loop import (
    ClosedLoopResult,
    SearchSpace,
    ValidationAttempt,
    make_full_space,
    make_model_hessian_space,
    make_oracle_space,
    make_random_space,
    make_search_space,
    run_closed_loop,
)
from qcontrol.config import DeviceConfig, SearchConfig, SystemConfig
from qcontrol.device import DeviceQueryError, Observation, make_query_device
from qcontrol.landscape import analyze_landscape, dense_hessian
from qcontrol.objectives import normalized_infidelity
from qcontrol.open_loop import optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system, perturb_system


@dataclass
class _SyntheticDevice:
    target: np.ndarray
    failures: frozenset[int] = frozenset()
    allow_certification: bool = True

    def __post_init__(self) -> None:
        self.optimizer_queries = 0
        self.optimizer_shots = 0
        self.validation_queries = 0
        self.validation_shots = 0
        self._issued_validations: dict[int, Observation] = {}

    @property
    def ledger(self) -> SimpleNamespace:
        return SimpleNamespace(
            optimizer_queries=self.optimizer_queries,
            optimizer_shots=self.optimizer_shots,
            validation_queries=self.validation_queries,
            validation_shots=self.validation_shots,
        )

    def _fidelity(self, pulse: object) -> float:
        candidate = np.asarray(pulse, dtype=np.float64)
        error = candidate - self.target
        curvature = np.linspace(1.0, 0.2, candidate.size)
        return float(np.clip(1.0 - np.vdot(error, curvature * error), 0.0, 1.0))

    def query(self, normalized_pulse: object) -> Observation:
        self.optimizer_queries += 1
        self.optimizer_shots += 1_000
        query_index = self.optimizer_queries
        if query_index in self.failures:
            raise DeviceQueryError(query_index, "propagation_failure")
        return Observation(
            self._fidelity(normalized_pulse),
            1_000,
            query_index,
            False,
            query_index,
            attempt_index=query_index,
        )

    def validate(
        self,
        normalized_pulse: object,
        shots: int = 100_000,
    ) -> Observation:
        self.validation_queries += 1
        self.validation_shots += shots
        attempt_index = self.optimizer_queries + self.validation_queries
        observation = Observation(
            self._fidelity(normalized_pulse),
            shots,
            self.optimizer_queries,
            True,
            attempt_index,
            attempt_index=attempt_index,
        )
        self._issued_validations[id(observation)] = observation
        return observation

    def certifies(self, observation: Observation, threshold: float = 0.999) -> bool:
        return bool(
            self.allow_certification
            and self._issued_validations.get(id(observation)) is observation
            and observation.estimate >= threshold
        )


@dataclass
class _ScriptedValidationDevice:
    optimizer_estimates: tuple[float, ...]

    def __post_init__(self) -> None:
        self.optimizer_queries = 0
        self.optimizer_shots = 0
        self.validation_queries = 0
        self.validation_shots = 0
        self._issued_validations: dict[int, Observation] = {}

    @property
    def ledger(self) -> SimpleNamespace:
        return SimpleNamespace(
            optimizer_queries=self.optimizer_queries,
            optimizer_shots=self.optimizer_shots,
            validation_queries=self.validation_queries,
            validation_shots=self.validation_shots,
        )

    def query(self, normalized_pulse: object) -> Observation:
        del normalized_pulse
        self.optimizer_queries += 1
        self.optimizer_shots += 1_000
        query_index = self.optimizer_queries
        estimate = self.optimizer_estimates[
            min(query_index - 1, len(self.optimizer_estimates) - 1)
        ]
        return Observation(
            estimate,
            1_000,
            query_index,
            False,
            query_index,
            attempt_index=query_index + self.validation_queries,
        )

    def validate(
        self,
        normalized_pulse: object,
        shots: int = 100_000,
    ) -> Observation:
        del normalized_pulse
        self.validation_queries += 1
        self.validation_shots += shots
        attempt_index = self.optimizer_queries + self.validation_queries
        if self.validation_queries == 1:
            raise DeviceQueryError(attempt_index, "sampling_failure")
        observation = Observation(
            1.0,
            shots,
            self.optimizer_queries,
            True,
            attempt_index,
            attempt_index=attempt_index,
        )
        self._issued_validations[id(observation)] = observation
        return observation

    def certifies(self, observation: Observation, threshold: float = 0.999) -> bool:
        return bool(
            self._issued_validations.get(id(observation)) is observation
            and observation.estimate >= threshold
        )


@pytest.fixture
def origin() -> np.ndarray:
    return np.asarray([0.1, -0.2, 0.0, 0.3, -0.1, 0.2], dtype=np.float64)


def test_subspace_coordinates_map_to_identical_origin(origin: np.ndarray) -> None:
    basis = np.eye(origin.size, dtype=np.float64)[:, :3]
    space = SearchSpace(origin, basis, bound=1.0)

    np.testing.assert_allclose(space.to_pulse(np.zeros(3)), origin)


def test_search_space_has_array_aware_equality_and_canonical_round_trip(
    origin: np.ndarray,
) -> None:
    source_origin = origin.copy()
    source_basis = np.eye(origin.size)[:, :3]
    first = SearchSpace(source_origin, source_basis, bound=0.7)
    second = SearchSpace(origin.copy(), source_basis.copy(), bound=0.7)

    source_origin[:] = 0.0
    source_basis[:] = 0.0
    payload = json.loads(json.dumps(first.canonical_dict(), allow_nan=False))
    replayed = SearchSpace.from_canonical_dict(payload)

    assert first == second
    assert first == replayed
    assert hash(first) == hash(replayed)
    assert replayed.canonical_dict() == payload
    assert not first.origin.flags.writeable
    assert not first.basis.flags.writeable
    assert not first.lower_bounds.flags.writeable
    assert not first.upper_bounds.flags.writeable


def test_search_space_bytes_backing_prevents_mutation_and_stabilizes_hash(
    origin: np.ndarray,
) -> None:
    space = SearchSpace(origin, np.eye(origin.size)[:, :3], bound=0.7)
    equal_space = SearchSpace(origin.copy(), np.eye(origin.size)[:, :3], bound=0.7)
    original_hash = hash(space)
    mapping = {space: "stable"}
    members = {space}

    for array in (
        space.origin,
        space.basis,
        space.lower_bounds,
        space.upper_bounds,
    ):
        with pytest.raises(ValueError):
            array.setflags(write=True)

    assert space == equal_space
    assert hash(space) == original_hash == hash(equal_space)
    assert mapping[equal_space] == "stable"
    assert equal_space in members


def test_all_candidate_spaces_share_origin_bounds_and_coordinate_scaling(
    origin: np.ndarray,
) -> None:
    model_basis = np.eye(origin.size, dtype=np.float64)
    oracle_basis = np.roll(model_basis, 1, axis=0)
    spaces = (
        make_full_space(origin, bound=0.6),
        make_model_hessian_space(origin, model_basis, dimension=3, bound=0.6),
        make_random_space(origin, dimension=3, seed=9, bound=0.6),
        make_oracle_space(origin, oracle_basis, dimension=3, bound=0.6),
    )

    for space in spaces:
        np.testing.assert_allclose(
            space.to_pulse(np.zeros(space.dimension)),
            origin,
        )
        np.testing.assert_allclose(space.lower_bounds, -0.6)
        np.testing.assert_allclose(space.upper_bounds, 0.6)
        np.testing.assert_allclose(
            space.basis.T @ space.basis,
            np.eye(space.dimension),
            atol=1e-12,
        )
    np.testing.assert_array_equal(spaces[0].basis, np.eye(origin.size))


def test_seeded_random_basis_uses_reproducible_canonical_qr(
    origin: np.ndarray,
) -> None:
    first = make_random_space(origin, dimension=3, seed=9)
    second = make_random_space(origin, dimension=3, seed=9)
    gaussian = np.random.default_rng(9).normal(size=(origin.size, 3))

    np.testing.assert_allclose(first.basis, second.basis)
    np.testing.assert_allclose(first.basis.T @ first.basis, np.eye(3), atol=1e-12)
    assert np.all(np.diag(first.basis.T @ gaussian) >= 0.0)


def test_mapping_clips_normalized_pulses_consistently(origin: np.ndarray) -> None:
    spaces = (
        make_full_space(origin),
        make_model_hessian_space(origin, np.eye(origin.size), dimension=3),
        make_random_space(origin, dimension=3, seed=2),
        make_oracle_space(origin, np.eye(origin.size), dimension=3),
    )

    for space in spaces:
        pulse = space.to_pulse(np.full(space.dimension, 100.0))
        assert np.all(pulse <= 1.0)
        assert np.all(pulse >= -1.0)


def test_search_config_factory_keeps_oracle_basis_external(
    origin: np.ndarray,
) -> None:
    model_basis = np.eye(origin.size)
    full = make_search_space(SearchConfig("full", 3, 20), origin)
    informed = make_search_space(
        SearchConfig("model_hessian", 3, 20),
        origin,
        model_basis=model_basis,
    )
    random = make_search_space(
        SearchConfig("random", 3, 20),
        origin,
        seed=7,
    )

    assert full.dimension == origin.size
    assert informed.dimension == random.dimension == 3
    with pytest.raises(ValueError, match="externally constructed"):
        make_search_space(SearchConfig("oracle", 3, 20), origin)


def test_budget_is_never_exceeded_and_failed_queries_are_charged() -> None:
    origin = np.zeros(5, dtype=np.float64)
    device = _SyntheticDevice(
        target=np.asarray([0.5, -0.4, 0.3, 0.0, 0.0]),
        failures=frozenset({2, 4, 7}),
    )

    result = run_closed_loop(
        device,
        make_full_space(origin),
        budget=11,
        seed=2,
    )

    assert device.ledger.optimizer_queries == 11
    assert result.evaluations == 11
    assert len(result.observations) == 8
    assert result.budget_exhausted


def test_one_dimensional_cma_avoids_broken_bound_range_std_limiter() -> None:
    origin = np.zeros(3, dtype=np.float64)
    space = make_random_space(origin, dimension=1, seed=8, bound=0.1)
    device = _SyntheticDevice(
        target=np.ones(3, dtype=np.float64),
        allow_certification=False,
    )

    result = run_closed_loop(device, space, budget=5, seed=8)

    assert result.evaluations == 5
    assert result.budget_exhausted
    assert device.ledger.optimizer_queries == 5


@pytest.mark.parametrize("method", ("full", "model_hessian", "random", "oracle"))
def test_one_dimensional_search_kinds_are_reproducible_and_bounded(method) -> None:
    origin = np.zeros(1 if method == "full" else 4, dtype=np.float64)
    config = SearchConfig(method, 1, 5)
    kwargs = {
        "model_basis": np.eye(origin.size),
        "oracle_basis": np.eye(origin.size),
        "seed": 8,
    }
    first_space = make_search_space(config, origin, **kwargs)
    second_space = make_search_space(config, origin, **kwargs)
    first_audit = []
    second_audit = []

    first = run_closed_loop(
        _SyntheticDevice(
            target=np.ones(origin.size, dtype=np.float64),
            allow_certification=False,
        ),
        first_space,
        budget=5,
        seed=8,
        audit_sink=lambda pulse, observation: first_audit.append(
            (pulse.copy(), observation)
        ),
    )
    second = run_closed_loop(
        _SyntheticDevice(
            target=np.ones(origin.size, dtype=np.float64),
            allow_certification=False,
        ),
        second_space,
        budget=5,
        seed=8,
        audit_sink=lambda pulse, observation: second_audit.append(
            (pulse.copy(), observation)
        ),
    )
    replayed = ClosedLoopResult.from_canonical_dict(
        json.loads(json.dumps(first.canonical_dict(), allow_nan=False))
    )

    assert first == second == replayed
    assert first.evaluations == 5
    assert first.budget_exhausted
    assert len(first_audit) == len(second_audit) == 5
    assert all(np.all(np.abs(pulse) <= 1.0) for pulse, _ in first_audit)
    for (first_pulse, _), (second_pulse, _) in zip(first_audit, second_audit):
        np.testing.assert_array_equal(first_pulse, second_pulse)


@pytest.mark.parametrize("shots", (None, 1_000))
def test_one_dimensional_cma_preserves_exact_and_finite_shot_accounting(
    shots,
) -> None:
    system_config = SystemConfig("one_qubit", 3, 4.0)
    model = make_system(system_config)
    pulse_space = PulseSpace.from_system(model, system_config.segments)
    truth = perturb_system(model, gap=0.2, seed=8)
    device_config = DeviceConfig(gap=0.2, shots=shots, perturbation_seed=8)
    space = make_random_space(
        np.zeros(pulse_space.parameter_count, dtype=np.float64),
        dimension=1,
        seed=8,
    )
    device = make_query_device(truth, pulse_space, device_config, seed=8)

    result = run_closed_loop(device, space, budget=5, seed=8)

    assert result.evaluations == device.ledger.optimizer_queries
    assert result.evaluations <= 5
    assert device.ledger.optimizer_shots == result.evaluations * (shots or 0)
    assert device.ledger.total_queries == (
        device.ledger.optimizer_queries + device.ledger.validation_queries
    )
    assert device.ledger.total_shots == (
        device.ledger.optimizer_shots + device.ledger.validation_shots
    )


def test_one_dimensional_cma_certifies_and_stops_on_flat_fitness() -> None:
    certified = run_closed_loop(
        _SyntheticDevice(target=np.zeros(1, dtype=np.float64)),
        make_full_space(np.zeros(1, dtype=np.float64)),
        budget=20,
        seed=8,
    )
    stopped = run_closed_loop(
        _ScriptedValidationDevice((0.5,)),
        make_full_space(np.zeros(1, dtype=np.float64)),
        budget=100,
        seed=8,
    )

    assert certified.certified
    assert certified.stop_reason == "certified"
    assert certified.evaluations == 1
    assert not stopped.certified
    assert stopped.stop_reason == "optimizer_stopped"
    assert not stopped.budget_exhausted
    assert stopped.evaluations < stopped.budget


def test_cma_options_for_dimension_two_remain_unchanged() -> None:
    options = closed_loop_module._cma_options(
        make_full_space(np.zeros(2, dtype=np.float64)),
        seed=8,
    )

    assert "maxstd_boundrange" not in options
    assert options["popsize"] == 6
    assert options["seed"] == 9


def test_audit_sink_receives_copies_without_influencing_cma() -> None:
    origin = np.zeros(5, dtype=np.float64)
    target = np.asarray([0.5, -0.4, 0.3, 0.0, 0.0])
    audited: list[tuple[np.ndarray, Observation | None]] = []

    def sink(pulse: np.ndarray, observation: Observation | None) -> object:
        audited.append((pulse.copy(), observation))
        pulse[:] = 99.0
        return {"ignored": True}

    with_sink = run_closed_loop(
        _SyntheticDevice(target=target, failures=frozenset({2})),
        make_full_space(origin),
        budget=8,
        seed=2,
        audit_sink=sink,
    )
    replay = run_closed_loop(
        _SyntheticDevice(target=target, failures=frozenset({2})),
        make_full_space(origin),
        budget=8,
        seed=2,
    )

    assert len(audited) == with_sink.evaluations == 8
    assert audited[1][1] is None
    assert all(np.all(np.abs(pulse) <= 1.0) for pulse, _ in audited)
    np.testing.assert_allclose(with_sink.best_pulse, replay.best_pulse, atol=0.0, rtol=0.0)
    assert [item.estimate for item in with_sink.observations] == [
        item.estimate for item in replay.observations
    ]


def test_seed_zero_replays_the_same_cma_trajectory() -> None:
    origin = np.zeros(5, dtype=np.float64)
    target = np.asarray([0.2, -0.1, 0.15, 0.0, 0.0])
    first = run_closed_loop(
        _SyntheticDevice(target=target),
        make_full_space(origin),
        budget=20,
        seed=0,
    )
    second = run_closed_loop(
        _SyntheticDevice(target=target),
        make_full_space(origin),
        budget=20,
        seed=0,
    )

    np.testing.assert_allclose(first.best_pulse, second.best_pulse, rtol=0.0, atol=0.0)
    assert [item.estimate for item in first.observations] == [
        item.estimate for item in second.observations
    ]


def test_zero_gap_origin_uses_one_optimizer_query_and_one_validation() -> None:
    origin = np.zeros(5, dtype=np.float64)
    device = _SyntheticDevice(target=origin.copy())

    result = run_closed_loop(
        device,
        make_model_hessian_space(origin, np.eye(5), dimension=3),
        budget=20,
        seed=4,
    )

    assert result.certified
    assert result.first_certified_query == 1
    assert result.provisional_crossings == (1,)
    assert len(result.observations) == 1
    assert result.validation_result is not None
    assert device.ledger.optimizer_queries == 1
    assert device.ledger.validation_queries == 1
    assert device.ledger.optimizer_shots == 1_000
    assert device.ledger.validation_shots == 100_000


def test_completion_requires_device_backed_certification() -> None:
    origin = np.zeros(4, dtype=np.float64)
    device = _SyntheticDevice(target=origin.copy(), allow_certification=False)

    result = run_closed_loop(
        device,
        make_full_space(origin),
        budget=5,
        seed=3,
    )

    assert result.validation_result is not None
    assert result.validation_result.certifies()
    assert not result.certified
    assert result.first_certified_query is None
    assert device.ledger.optimizer_queries == 5


def test_validation_attempt_history_preserves_failure_then_certification() -> None:
    device = _ScriptedValidationDevice((0.9991, 0.9992))
    result = run_closed_loop(
        device,
        make_full_space(np.zeros(3)),
        budget=5,
        seed=7,
    )

    assert result.certified
    assert result.first_certified_query == 2
    assert result.evaluations == 2
    assert result.provisional_crossings == (1, 2)
    assert len(result.validation_attempts) == 2
    failed, succeeded = result.validation_attempts
    assert isinstance(failed, ValidationAttempt)
    assert failed.optimizer_query_index == 1
    assert failed.best_observation == result.observations[0]
    assert failed.validation_observation is None
    assert failed.failure_category == "sampling_failure"
    assert failed.status == "failed"
    assert not failed.certified
    assert succeeded.optimizer_query_index == 2
    assert succeeded.best_observation == result.observations[1]
    assert succeeded.validation_observation is result.validation_result
    assert succeeded.failure_category is None
    assert succeeded.status == "certified"
    assert succeeded.certified
    assert device.ledger.optimizer_queries == 2
    assert device.ledger.validation_queries == 2
    assert device.ledger.optimizer_shots == 2_000
    assert device.ledger.validation_shots == 200_000


def test_closed_loop_result_is_comparable_and_json_round_trips_complete_history() -> None:
    result = run_closed_loop(
        _ScriptedValidationDevice((0.9991, 0.9992)),
        make_full_space(np.zeros(3)),
        budget=5,
        seed=7,
    )

    payload = json.loads(json.dumps(result.canonical_dict(), allow_nan=False))
    replayed = ClosedLoopResult.from_canonical_dict(payload)

    assert replayed == result
    assert hash(replayed) == hash(result)
    assert replayed.canonical_dict() == payload
    assert len(replayed.observations) == 2
    assert len(replayed.validation_attempts) == 2
    assert replayed.validation_attempts[0].failure_category == "sampling_failure"
    assert payload["validation_attempts"][0]["status"] == "failed"
    assert payload["validation_attempts"][1]["status"] == "certified"
    assert replayed.validation_attempts[1].validation_observation is not None
    assert (
        replayed.validation_result
        == replayed.validation_attempts[1].validation_observation
    )


def _integrity_result(kind: str) -> ClosedLoopResult:
    if kind == "certified":
        return run_closed_loop(
            _ScriptedValidationDevice((0.9991, 0.9992)),
            make_full_space(np.zeros(3)),
            budget=5,
            seed=7,
        )
    budget_result = run_closed_loop(
        _SyntheticDevice(target=np.zeros(3), allow_certification=False),
        make_full_space(np.zeros(3)),
        budget=5,
        seed=7,
    )
    if kind == "budget":
        return budget_result
    assert kind == "optimizer_stopped"
    return replace(
        budget_result,
        observations=budget_result.observations[:4],
        evaluations=4,
        budget_exhausted=False,
        stop_reason="optimizer_stopped",
    )


@pytest.mark.parametrize(
    ("kind", "changes"),
    [
        ("certified", {"certified": False}),
        ("certified", {"stop_reason": "budget"}),
        ("certified", {"budget_exhausted": True}),
        ("certified", {"evaluations": 6}),
        ("budget", {"budget_exhausted": False}),
        ("budget", {"stop_reason": "optimizer_stopped"}),
        ("optimizer_stopped", {"certified": True}),
        ("optimizer_stopped", {"budget_exhausted": True}),
        ("optimizer_stopped", {"stop_reason": "budget"}),
        ("optimizer_stopped", {"stop_reason": "certified"}),
    ],
)
def test_closed_loop_result_rejects_contradictory_direct_states(
    kind: str,
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(_integrity_result(kind), **changes)


@pytest.mark.parametrize(
    ("kind", "changes"),
    [
        ("certified", {"certified": False}),
        ("certified", {"stop_reason": "budget"}),
        ("certified", {"budget_exhausted": True}),
        ("certified", {"evaluations": 6}),
        ("budget", {"budget_exhausted": False}),
        ("budget", {"stop_reason": "optimizer_stopped"}),
        ("optimizer_stopped", {"certified": True}),
        ("optimizer_stopped", {"budget_exhausted": True}),
        ("optimizer_stopped", {"stop_reason": "budget"}),
        ("optimizer_stopped", {"stop_reason": "certified"}),
    ],
)
def test_closed_loop_result_rejects_json_state_tampering(
    kind: str,
    changes: dict[str, object],
) -> None:
    payload = json.loads(
        json.dumps(_integrity_result(kind).canonical_dict(), allow_nan=False)
    )
    payload.update(changes)

    with pytest.raises(ValueError):
        ClosedLoopResult.from_canonical_dict(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provisional_crossings", [999]),
        ("validation_result", None),
    ],
)
def test_closed_loop_result_rejects_tampered_derived_validation_fields(
    field: str,
    value: object,
) -> None:
    payload = json.loads(
        json.dumps(
            _integrity_result("certified").canonical_dict(),
            allow_nan=False,
        )
    )
    payload[field] = value

    with pytest.raises(ValueError):
        ClosedLoopResult.from_canonical_dict(payload)


def test_closed_loop_imports_only_query_boundary() -> None:
    source = inspect.getsource(closed_loop_module)
    assert "qcontrol.offline" not in source
    assert "qcontrol.landscape" not in source
    assert "qcontrol.objectives" not in source
    assert "qcontrol.systems" not in source


def test_deterministic_small_gap_d2_fixture_orders_candidate_spaces() -> None:
    model = make_system(SystemConfig("one_qubit", 6, 4.0))
    pulse_space = PulseSpace.from_system(model, segments=6)
    accepted = optimize_open_loop(model, pulse_space, seed=5, starts=5)
    landscape = analyze_landscape(
        model,
        pulse_space,
        accepted,
        leading_count=5,
    )
    assert landscape.polishing is not None
    origin = np.asarray(landscape.polishing.normalized_pulse)
    truth = perturb_system(model, gap=0.02, seed=9)
    truth_hessian = dense_hessian(
        lambda pulse: normalized_infidelity(pulse, truth, pulse_space),
        origin,
    )
    truth_values, truth_vectors = np.linalg.eigh(truth_hessian)
    oracle_order = np.argsort(np.abs(truth_values))[::-1]
    oracle_basis = truth_vectors[:, oracle_order]
    budget = 120

    def device():
        return make_query_device(
            truth,
            pulse_space,
            DeviceConfig(gap=0.02, shots=None, perturbation_seed=9),
            seed=100,
        )

    top_space = make_model_hessian_space(
        origin,
        landscape.model_basis,
        dimension=3,
    )
    random_space = make_random_space(origin, dimension=3, seed=12)
    oracle_space = make_oracle_space(origin, oracle_basis, dimension=3)
    top_device = device()
    random_device = device()
    oracle_device = device()
    top = run_closed_loop(
        top_device,
        top_space,
        budget=budget,
        seed=11,
    )
    random = run_closed_loop(
        random_device,
        random_space,
        budget=budget,
        seed=11,
    )
    oracle = run_closed_loop(
        oracle_device,
        oracle_space,
        budget=budget,
        seed=11,
    )

    def restricted_floor(space: SearchSpace) -> float:
        optimization = minimize(
            lambda coordinates: float(
                normalized_infidelity(space.to_pulse(coordinates), truth, pulse_space)
            ),
            np.zeros(space.dimension),
            method="Nelder-Mead",
            bounds=list(zip(space.lower_bounds, space.upper_bounds, strict=True)),
            options={"maxiter": 1_000, "xatol": 1e-11, "fatol": 1e-13},
        )
        assert optimization.success
        return max(0.0, float(optimization.fun))

    random_floor = restricted_floor(random_space)
    oracle_floor = restricted_floor(oracle_space)

    assert top.certified
    assert top.first_certified_query == 4
    assert random.first_certified_query == 76
    assert oracle.first_certified_query == 4
    assert random.first_certified_query >= top.first_certified_query
    assert oracle_floor <= random_floor
    assert oracle_floor <= 1e-12
    for result, query_device in (
        (top, top_device),
        (random, random_device),
        (oracle, oracle_device),
    ):
        assert result.evaluations == result.first_certified_query
        assert query_device.ledger.optimizer_queries == result.evaluations
        assert query_device.ledger.optimizer_shots == 0
        assert query_device.ledger.validation_shots == (
            100_000 * query_device.ledger.validation_queries
        )


@pytest.mark.parametrize("parameter_count", (24, 80))
def test_full_dimension_model_hessian_exactly_matches_bounded_full_space(
    parameter_count: int,
) -> None:
    origin = np.linspace(-0.95, 0.95, parameter_count)
    gaussian = np.random.default_rng(parameter_count).normal(
        size=(parameter_count, parameter_count)
    )
    curvature_basis, _ = np.linalg.qr(gaussian)
    bound = 0.375
    model_hessian = make_search_space(
        SearchConfig("model_hessian", parameter_count, 200),
        origin,
        model_basis=curvature_basis,
        bound=bound,
    )
    full = make_search_space(
        SearchConfig("full", parameter_count, 200),
        origin,
        bound=bound,
    )

    assert np.array_equal(model_hessian.origin, full.origin)
    assert np.array_equal(model_hessian.basis, full.basis)
    assert np.array_equal(model_hessian.lower_bounds, full.lower_bounds)
    assert np.array_equal(model_hessian.upper_bounds, full.upper_bounds)
    samples = (
        full.lower_bounds,
        full.upper_bounds,
        np.where(np.arange(parameter_count) % 2, bound, -bound),
        np.eye(parameter_count)[0] * bound,
        -np.eye(parameter_count)[-1] * bound,
    )
    for coordinates in samples:
        assert np.array_equal(
            model_hessian.to_pulse(coordinates),
            full.to_pulse(coordinates),
        )
