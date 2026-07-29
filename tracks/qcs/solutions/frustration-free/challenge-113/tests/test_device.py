from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import inspect
import pickle
from threading import Event

import numpy as np
import pytest

import qcontrol.device as device_module
from qcontrol.config import DeviceConfig, SystemConfig
from qcontrol.device import DeviceQueryError, Observation, make_query_device
from qcontrol.objectives import normalized_infidelity
from qcontrol.offline import make_offline_evaluator
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem, make_system, perturb_system


@pytest.fixture
def device_inputs() -> tuple[ControlSystem, PulseSpace, np.ndarray]:
    model = make_system(SystemConfig("one_qubit", 2, 4.0))
    truth = perturb_system(model, gap=0.03, seed=9)
    space = PulseSpace.from_system(model, segments=2)
    pulse = np.zeros(space.parameter_count, dtype=np.float64)
    return truth, space, pulse


def make_device(
    device_inputs: tuple[ControlSystem, PulseSpace, np.ndarray],
    *,
    seed: int = 4,
    shots: int | None = 1_000,
):
    truth, space, _ = device_inputs
    return make_query_device(
        truth,
        space,
        DeviceConfig(gap=0.03, shots=shots, perturbation_seed=9),
        seed=seed,
    )


def test_fixed_seed_observations_are_reproducible(device_inputs) -> None:
    _, _, pulse = device_inputs
    first_device = make_device(device_inputs, seed=4)
    second_device = make_device(device_inputs, seed=4)

    first = [first_device.query(pulse), first_device.validate(pulse)]
    second = [second_device.query(pulse), second_device.validate(pulse)]

    assert first == second


def test_observation_seed_depends_on_sequence_and_validation_kind(device_inputs) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs, seed=4)

    first = device.query(pulse)
    validation = device.validate(pulse)
    second = device.query(pulse)

    assert len({first.observation_seed, validation.observation_seed, second.observation_seed}) == 3
    assert first.optimizer_query_index == 1
    assert validation.optimizer_query_index == 1
    assert second.optimizer_query_index == 2
    assert first.attempt_index == 1
    assert validation.attempt_index == 2
    assert second.attempt_index == 3
    assert all(len(item.seed_digest) == 64 for item in (first, validation, second))
    assert all(item.observation_seed.bit_length() <= 128 for item in (first, validation, second))


def test_query_and_validation_accounting_is_exact(device_inputs) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs, seed=4, shots=1_000)

    device.query(pulse)
    device.query(pulse)
    device.validate(pulse, shots=100_000)

    assert device.ledger.optimizer_queries == 2
    assert device.ledger.optimizer_shots == 2_000
    assert device.ledger.validation_queries == 1
    assert device.ledger.validation_shots == 100_000
    assert device.ledger.total_queries == 3
    assert device.ledger.total_shots == 102_000


def test_ledger_is_append_only_from_the_caller_perspective(device_inputs) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)
    empty = device.ledger

    first = device.query(pulse)
    after_first = device.ledger
    device.validate(pulse)

    assert empty.observations == ()
    assert after_first.observations == (first,)
    assert len(device.ledger.observations) == 2
    assert after_first.observations[0] is not first
    assert after_first.observations[0] is not after_first.observations[0]
    with pytest.raises((FrozenInstanceError, AttributeError)):
        after_first.observations = ()  # type: ignore[misc]


def test_public_mutation_cannot_change_private_ledger_accounting(device_inputs) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)
    returned = device.query(pulse)
    snapshot = device.ledger
    public_record = snapshot.records[0]

    object.__setattr__(returned, "shots", 999_999)
    object.__setattr__(public_record, "charged_shots", 999_999)

    assert snapshot.optimizer_shots == 1_000
    assert snapshot.observations[0].shots == 1_000
    assert device.ledger.optimizer_shots == 1_000
    assert device.ledger.observations[0].shots == 1_000


def test_device_and_ledger_capabilities_cannot_be_pickled(device_inputs) -> None:
    device = make_device(device_inputs)

    with pytest.raises(TypeError, match="pickled"):
        pickle.dumps(device)
    with pytest.raises(TypeError, match="pickled"):
        pickle.dumps(device.ledger)


def test_exact_mode_returns_clipped_fidelity_and_records_zero_shots(
    device_inputs,
) -> None:
    truth, space, pulse = device_inputs
    device = make_device(device_inputs, shots=None)

    observation = device.query(pulse)
    expected = float(np.clip(1.0 - normalized_infidelity(pulse, truth, space), 0.0, 1.0))

    assert observation.estimate == pytest.approx(expected, abs=1e-14)
    assert observation.shots == 0
    assert device.ledger.optimizer_shots == 0


def test_public_device_and_observation_do_not_expose_truth(device_inputs) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)
    observation = device.query(pulse)

    for name in ("exact_fidelity", "hamiltonian", "truth", "_truth", "evaluator", "_evaluator"):
        assert not hasattr(device, name)
    assert "exact_fidelity" not in observation.__dataclass_fields__
    with pytest.raises(AttributeError):
        _ = device.truth


def test_offline_evaluator_is_separate_from_public_device(device_inputs) -> None:
    truth, space, pulse = device_inputs
    device = make_device(device_inputs, shots=None)
    offline_evaluator = make_offline_evaluator(truth, space)

    assert offline_evaluator(pulse) == device.query(pulse).estimate
    assert not hasattr(device, "offline_evaluator")
    assert not hasattr(device_module, "make_offline_evaluator")
    assert "qcontrol.offline" not in inspect.getsource(device_module)


def test_only_independent_100000_shot_validation_can_certify() -> None:
    optimizer = Observation(1.0, 100_000, 1, False, 7)
    too_few_shots = Observation(1.0, 99_999, 1, True, 8)
    validation = Observation(1.0, 100_000, 1, True, 9)
    below_target = Observation(0.999, 100_000, 1, True, 10)

    assert not optimizer.certifies(0.999)
    assert not too_few_shots.certifies(0.999)
    assert validation.certifies(0.999)
    assert not validation.certifies(0.998)
    assert not below_target.certifies(0.999)


def test_backed_certification_rejects_forgery_and_mutation(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    monkeypatch.setattr(device_module, "normalized_infidelity", lambda *args: 0.0)
    device = make_device(device_inputs)
    validation = device.validate(pulse)
    ledger = device.ledger
    forged = replace(validation)

    assert validation.certifies(0.999)
    assert forged.certifies(0.999)
    assert device.certifies(validation, 0.999)
    assert ledger.certifies(validation, 0.999)
    assert not device.certifies(forged, 0.999)
    assert not ledger.certifies(forged, 0.999)

    object.__setattr__(validation, "seed_digest", "0" * 64)

    assert validation.certifies(0.999)
    assert not device.certifies(validation, 0.999)
    assert not ledger.certifies(validation, 0.999)
    assert ledger.validation_shots == 100_000
    assert ledger.observations[0].seed_digest != "0" * 64


@pytest.mark.parametrize("shots", [0, -1, True, 1.5])
def test_validation_rejects_invalid_shot_counts(device_inputs, shots) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    with pytest.raises(DeviceQueryError) as captured:
        device.validate(pulse, shots=shots)

    record = device.ledger.records[0]
    assert captured.value.attempt_index == 1
    assert captured.value.category == "invalid_shots"
    assert captured.value.__context__ is None
    assert record.attempt_index == 1
    assert record.validation
    assert not record.success
    assert record.status == "failed"
    assert record.requested_shots == shots
    assert record.charged_shots == 0
    assert record.error_category == "invalid_shots"
    assert device.ledger.optimizer_queries == 0
    assert device.ledger.validation_queries == 1


def test_invalid_pulse_is_a_failed_chargeless_optimizer_attempt(device_inputs) -> None:
    _, space, pulse = device_inputs
    device = make_device(device_inputs)
    invalid = np.full(space.parameter_count, np.nan)

    with pytest.raises(DeviceQueryError) as captured:
        device.query(invalid)
    successful = device.query(pulse)

    failed, passed = device.ledger.records
    assert (failed.attempt_index, passed.attempt_index) == (1, 2)
    assert failed.optimizer_query_index == 1
    assert passed.optimizer_query_index == 2
    assert captured.value.category == "invalid_pulse"
    assert not failed.success
    assert failed.error_category == "invalid_pulse"
    assert failed.requested_shots == 1_000
    assert failed.charged_shots == 0
    assert device.ledger.optimizer_queries == 2
    assert device.ledger.optimizer_shots == 1_000
    assert successful.attempt_index == 2


def test_propagation_failure_is_sanitized_and_ledgered(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    def fail_propagation(*args):
        raise RuntimeError("private propagation detail")

    monkeypatch.setattr(device_module, "normalized_infidelity", fail_propagation)

    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    record = device.ledger.records[0]
    assert captured.value.attempt_index == 1
    assert captured.value.category == "propagation_failure"
    assert captured.value.__context__ is None
    assert "private propagation detail" not in str(captured.value)
    assert "private propagation detail" not in repr(captured.value)
    assert record.error_category == "propagation_failure"
    assert not hasattr(record, "error_message")
    assert record.charged_shots == 0


def test_sampling_failure_charges_requested_shots(device_inputs, monkeypatch) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    class FailingSampler:
        def binomial(self, shots, probability):
            raise RuntimeError("sensitive backend detail")

    monkeypatch.setattr(device_module.np.random, "default_rng", lambda seed: FailingSampler())

    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    record = device.ledger.records[0]
    assert captured.value.category == "sampling_failure"
    assert captured.value.__context__ is None
    assert "sensitive backend detail" not in str(captured.value)
    assert "sensitive backend detail" not in repr(captured.value)
    assert not record.success
    assert record.error_category == "sampling_failure"
    assert record.requested_shots == 1_000
    assert record.charged_shots == 1_000
    assert device.ledger.optimizer_shots == 1_000


def test_rng_setup_failure_is_not_charged(device_inputs, monkeypatch) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    def fail_rng(seed):
        raise RuntimeError("rng setup failed")

    monkeypatch.setattr(device_module.np.random, "default_rng", fail_rng)

    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    record = device.ledger.records[0]
    assert captured.value.category == "rng_failure"
    assert "rng setup failed" not in str(captured.value)
    assert record.error_category == "rng_failure"
    assert record.charged_shots == 0


def test_observation_construction_failure_is_ledgered(device_inputs, monkeypatch) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    def fail_observation(record):
        raise RuntimeError("public conversion failed")

    monkeypatch.setattr(device_module, "_public_observation", fail_observation)

    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    record = device.ledger.records[0]
    assert captured.value.category == "observation_failure"
    assert "public conversion failed" not in str(captured.value)
    assert record.error_category == "observation_failure"
    assert record.charged_shots == 1_000


def test_concurrent_attempts_have_unique_ordered_indices_and_seeds(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    monkeypatch.setattr(device_module, "normalized_infidelity", lambda *args: 0.25)
    device = make_device(device_inputs)

    with ThreadPoolExecutor(max_workers=8) as executor:
        observations = list(executor.map(device.query, [pulse.copy() for _ in range(64)]))

    records = device.ledger.records
    assert [record.attempt_index for record in records] == list(range(1, 65))
    assert [record.optimizer_query_index for record in records] == list(range(1, 65))
    assert len({record.observation_seed for record in records}) == 64
    assert len({record.seed_digest for record in records}) == 64
    assert {item.attempt_index for item in observations} == set(range(1, 65))


def test_pending_attempt_remains_visible_before_later_completion(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    first_started = Event()
    release_first = Event()

    def blocking_evaluator(*args):
        if not first_started.is_set():
            first_started.set()
            assert release_first.wait(timeout=10)
        return 0.25

    monkeypatch.setattr(device_module, "normalized_infidelity", blocking_evaluator)
    device = make_device(device_inputs)

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_future = executor.submit(device.query, pulse)
        assert first_started.wait(timeout=10)
        pending_snapshot = device.ledger
        second = device.query(pulse)
        overlap_snapshot = device.ledger
        release_first.set()
        first = first_future.result(timeout=10)

    assert first.attempt_index == 1
    assert second.attempt_index == 2
    assert [(item.attempt_index, item.status) for item in pending_snapshot.records] == [
        (1, "reserved")
    ]
    assert pending_snapshot.optimizer_queries == 1
    assert [(item.attempt_index, item.status) for item in overlap_snapshot.records] == [
        (1, "reserved"),
        (2, "succeeded"),
    ]
    assert overlap_snapshot.optimizer_queries == 2
    assert [(item.attempt_index, item.status) for item in device.ledger.records] == [
        (1, "succeeded"),
        (2, "succeeded"),
    ]
    assert [(item.attempt_index, item.status) for item in overlap_snapshot.records] == [
        (1, "reserved"),
        (2, "succeeded"),
    ]


def test_reentrant_query_does_not_deadlock_or_reorder_attempts(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)
    nested = []
    during_reentry = []
    entered = False

    def reentrant_evaluator(*args):
        nonlocal entered
        if not entered:
            entered = True
            nested.append(device.query(pulse))
            during_reentry.extend(device.ledger.records)
        return 0.25

    monkeypatch.setattr(device_module, "normalized_infidelity", reentrant_evaluator)
    outer = device.query(pulse)

    assert outer.attempt_index == 1
    assert nested[0].attempt_index == 2
    assert [(item.attempt_index, item.status) for item in during_reentry] == [
        (1, "reserved"),
        (2, "succeeded"),
    ]
    assert [record.attempt_index for record in device.ledger.records] == [1, 2]


def test_seed_identity_is_unique_and_replayable_over_bounded_run(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    monkeypatch.setattr(device_module, "normalized_infidelity", lambda *args: 0.25)

    def run():
        device = make_device(device_inputs, seed=41)
        for index in range(256):
            if index % 7:
                device.query(pulse)
            else:
                device.validate(pulse)
        return [
            (record.observation_seed, record.seed_digest)
            for record in device.ledger.records
        ]

    first = run()
    second = run()

    assert first == second
    assert len(set(first)) == 256
    assert all(seed.bit_length() <= 128 for seed, _ in first)
    assert all(len(digest) == 64 for _, digest in first)


def test_truncated_seed_collision_guard_fails_closed(device_inputs, monkeypatch) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)
    identities = iter(
        [
            (7, "1" * 64),
            (7, "2" * 64),
        ]
    )
    monkeypatch.setattr(device_module, "_seed_identity", lambda *args: next(identities))

    device.query(pulse)
    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    first, collision = device.ledger.records
    assert first.success
    assert not collision.success
    assert captured.value.category == "seed_collision"
    assert collision.error_category == "seed_collision"
    assert collision.seed_digest == "2" * 64
    assert collision.charged_shots == 0


def test_request_sanitization_failure_is_reserved_and_publicly_sanitized(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    def fail_request(value):
        raise RuntimeError("sensitive request detail")

    monkeypatch.setattr(device_module, "_sanitized_requested_shots", fail_request)

    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    record = device.ledger.records[0]
    assert captured.value.attempt_index == 1
    assert captured.value.category == "request_validation"
    assert captured.value.__context__ is None
    assert "sensitive request detail" not in str(captured.value)
    assert record.status == "failed"
    assert record.error_category == "request_validation"


def test_seed_derivation_failure_is_reserved(device_inputs, monkeypatch) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    def fail_seed(*args):
        raise RuntimeError("sensitive seed detail")

    monkeypatch.setattr(device_module, "_seed_identity", fail_seed)

    with pytest.raises(DeviceQueryError) as captured:
        device.query(pulse)

    record = device.ledger.records[0]
    assert captured.value.category == "seed_derivation_failure"
    assert "sensitive seed detail" not in repr(captured.value)
    assert record.attempt_index == 1
    assert record.status == "failed"
    assert record.error_category == "seed_derivation_failure"


def test_keyboard_interrupt_finalizes_aborted_attempt_without_swallowing(
    device_inputs,
    monkeypatch,
) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    def interrupt(*args):
        raise KeyboardInterrupt("process control detail")

    monkeypatch.setattr(device_module, "normalized_infidelity", interrupt)

    with pytest.raises(KeyboardInterrupt, match="process control detail"):
        device.query(pulse)

    record = device.ledger.records[0]
    assert record.attempt_index == 1
    assert record.status == "aborted"
    assert not record.success
    assert record.error_category == "keyboard_interrupt"
    assert record.charged_shots == 0
    assert device.ledger.optimizer_queries == 1
