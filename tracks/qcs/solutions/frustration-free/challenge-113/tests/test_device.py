from dataclasses import FrozenInstanceError

import numpy as np
import pytest

import qcontrol.device as device_module
from qcontrol.config import DeviceConfig, SystemConfig
from qcontrol.device import Observation, make_query_device
from qcontrol.objectives import normalized_infidelity
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system, perturb_system


@pytest.fixture
def device_inputs() -> tuple[object, PulseSpace, np.ndarray]:
    model = make_system(SystemConfig("one_qubit", 2, 4.0))
    truth = perturb_system(model, gap=0.03, seed=9)
    space = PulseSpace.from_system(model, segments=2)
    pulse = np.zeros(space.parameter_count, dtype=np.float64)
    return truth, space, pulse


def make_device(
    device_inputs: tuple[object, PulseSpace, np.ndarray],
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
    with pytest.raises(FrozenInstanceError):
        after_first.observations = ()  # type: ignore[misc]


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
    assert hasattr(device_module, "make_offline_evaluator")
    offline_evaluator = device_module.make_offline_evaluator(truth, space)

    assert offline_evaluator(pulse) == device.query(pulse).estimate
    assert not hasattr(device, "offline_evaluator")


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


@pytest.mark.parametrize("shots", [0, -1, True, 1.5])
def test_validation_rejects_invalid_shot_counts(device_inputs, shots) -> None:
    _, _, pulse = device_inputs
    device = make_device(device_inputs)

    with pytest.raises(ValueError, match="shots"):
        device.validate(pulse, shots=shots)
