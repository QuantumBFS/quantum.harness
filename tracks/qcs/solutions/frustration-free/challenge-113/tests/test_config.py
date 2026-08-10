import math
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace

import pytest

from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig


def valid_config() -> ExperimentConfig:
    return ExperimentConfig(
        run_kind="development",
        system=SystemConfig(name="two_qubit", segments=20, amplitude_bound=4.0),
        device=DeviceConfig(gap=0.05, shots=1000, perturbation_seed=7),
        search=SearchConfig(method="model_hessian", dimension=15, budget=200),
        trial_seed=11,
    )


def test_config_id_is_stable_and_semantic() -> None:
    config = valid_config()
    assert config.content_id() == config.content_id()
    assert replace(config, trial_seed=12).content_id() != config.content_id()
    assert replace(config, model_seed=6).content_id() != config.content_id()
    assert replace(config, system=replace(config.system, duration=9.0)).content_id() != (
        config.content_id()
    )
    assert len(config.content_id()) == 20
    assert int(config.content_id(), 16) >= 0


def test_model_seed_is_explicit_canonical_and_defaults_to_five() -> None:
    config = valid_config()

    assert config.model_seed == 5
    assert config.canonical_dict()["model_seed"] == 5


def test_system_duration_defaults_are_canonical_and_serialized() -> None:
    one_qubit = SystemConfig("one_qubit", 12, 4.0)
    two_qubit = SystemConfig("two_qubit", 20, 4.0)

    assert one_qubit.duration is None
    assert two_qubit.duration is None
    assert one_qubit.effective_duration == 1.0
    assert two_qubit.effective_duration == 8.0
    assert valid_config().canonical_dict()["system"]["duration"] == 8.0  # type: ignore[index]


def test_replacing_an_omitted_duration_rederives_it_from_system_name() -> None:
    one_qubit = SystemConfig("one_qubit", 12, 4.0)
    two_qubit = replace(one_qubit, name="two_qubit")

    assert two_qubit.duration is None
    assert two_qubit.effective_duration == 8.0


def test_system_duration_accepts_a_positive_finite_override() -> None:
    config = SystemConfig("two_qubit", 20, 4.0, duration=6.5)
    assert config.duration == 6.5
    assert config.effective_duration == 6.5
    assert replace(config, name="one_qubit").effective_duration == 6.5


def test_omitted_and_explicit_default_durations_have_the_same_content_id() -> None:
    omitted = valid_config()
    explicit = replace(
        omitted,
        system=replace(omitted.system, duration=omitted.system.effective_duration),
    )
    assert omitted.content_id() == explicit.content_id()


@pytest.mark.parametrize("duration", [0.0, -1.0, float("nan"), float("inf"), True])
def test_system_duration_rejects_invalid_values(duration: object) -> None:
    with pytest.raises(ValueError, match="duration"):
        SystemConfig("one_qubit", 12, 4.0, duration=duration)  # type: ignore[arg-type]


def test_negative_zero_gap_is_normalized_for_semantic_ids() -> None:
    config = valid_config()
    negative_zero_device = DeviceConfig(
        gap=-0.0,
        shots=config.device.shots,
        perturbation_seed=config.device.perturbation_seed,
    )
    positive_zero_device = replace(negative_zero_device, gap=0.0)
    normalized = replace(config, device=negative_zero_device)
    positive_zero = replace(config, device=positive_zero_device)

    assert math.copysign(1.0, normalized.device.gap) == 1.0
    assert normalized.canonical_dict() == positive_zero.canonical_dict()
    assert normalized.content_id() == positive_zero.content_id()


def test_configuration_instances_are_frozen() -> None:
    instances = [
        valid_config(),
        valid_config().system,
        valid_config().device,
        valid_config().search,
    ]
    for instance in instances:
        with pytest.raises(FrozenInstanceError):
            setattr(instance, next(iter(instance.__dataclass_fields__)), "changed")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SystemConfig("one_qubit", True, 1.0),
        lambda: DeviceConfig(shots=True),
        lambda: DeviceConfig(perturbation_seed=True),
        lambda: SearchConfig("full", True, 200),
        lambda: SearchConfig("full", 1, True),
        lambda: replace(valid_config(), model_seed=True),
        lambda: replace(valid_config(), trial_seed=True),
    ],
)
def test_boolean_integer_fields_are_rejected(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize("name", ["", "three_qubit"])
def test_invalid_system_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        SystemConfig(name, 1, 1.0)


@pytest.mark.parametrize("method", ["", "gradient"])
def test_invalid_search_methods_are_rejected(method: str) -> None:
    with pytest.raises(ValueError):
        SearchConfig(method, 1, 200)


@pytest.mark.parametrize("method", ["full", "model_hessian", "random", "oracle"])
def test_supported_search_methods_are_accepted(method: str) -> None:
    assert SearchConfig(method, 1, 200).method == method


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field", ["amplitude_bound", "gap"])
def test_nonfinite_numeric_values_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        if field == "amplitude_bound":
            SystemConfig("one_qubit", 1, value)
        else:
            DeviceConfig(gap=value)


@pytest.mark.parametrize("field", ["amplitude_bound", "gap"])
def test_huge_integers_raise_value_error(field: str) -> None:
    huge = 10**10_000
    with pytest.raises(ValueError):
        if field == "amplitude_bound":
            SystemConfig("one_qubit", 1, huge)
        else:
            DeviceConfig(gap=huge)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SystemConfig("one_qubit", 0, 1.0),
        lambda: SystemConfig("one_qubit", -1, 1.0),
        lambda: SystemConfig("one_qubit", 1, 0.0),
        lambda: SystemConfig("one_qubit", 1, -1.0),
        lambda: SearchConfig("full", 0, 200),
        lambda: SearchConfig("full", -1, 200),
        lambda: SearchConfig("full", 1, 0),
        lambda: SearchConfig("full", 1, -1),
    ],
)
def test_nonpositive_required_values_are_rejected(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DeviceConfig(shots=0),
        lambda: DeviceConfig(perturbation_seed=-1),
        lambda: replace(valid_config(), model_seed=-1),
        lambda: replace(valid_config(), trial_seed=-1),
    ],
)
def test_invalid_shots_and_seeds_are_rejected(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


def test_dimension_cannot_exceed_system_parameter_count() -> None:
    with pytest.raises(ValueError, match="parameter count"):
        ExperimentConfig(
            run_kind="development",
            system=SystemConfig("one_qubit", 1, 1.0),
            device=DeviceConfig(),
            search=SearchConfig("full", 3, 200),
            trial_seed=0,
        )


@pytest.mark.parametrize(
    ("system", "dimension"),
    [
        (SystemConfig("one_qubit", 1, 1.0), 2),
        (SystemConfig("two_qubit", 1, 1.0), 4),
    ],
)
def test_dimension_can_equal_system_parameter_count(
    system: SystemConfig,
    dimension: int,
) -> None:
    config = ExperimentConfig(
        run_kind="development",
        system=system,
        device=DeviceConfig(),
        search=SearchConfig("full", dimension, 200),
        trial_seed=0,
    )
    assert config.search.dimension == system.parameter_count


def test_exact_development_and_production_budgets_are_accepted() -> None:
    development = valid_config()
    production = replace(
        development,
        run_kind="production",
        search=replace(development.search, budget=2000),
    )

    assert development.search.budget == 200
    assert production.search.budget == 2000


def test_invalid_run_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="run_kind"):
        replace(valid_config(), run_kind="staging")


@pytest.mark.parametrize(
    ("run_kind", "budget", "message"),
    [
        ("development", 2000, "development budget"),
        ("production", 200, "production budget"),
    ],
)
def test_run_kinds_reject_the_other_budget(
    run_kind: str,
    budget: int,
    message: str,
) -> None:
    config = valid_config()
    with pytest.raises(ValueError, match=message):
        replace(
            config,
            run_kind=run_kind,
            search=replace(config.search, budget=budget),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("gap", -0.1), ("shots", -1)],
)
def test_device_config_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        DeviceConfig(**{field: value})


def test_production_cannot_use_development_budget() -> None:
    with pytest.raises(ValueError, match="production budget"):
        replace(valid_config(), run_kind="production").validate()
