from dataclasses import replace

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
