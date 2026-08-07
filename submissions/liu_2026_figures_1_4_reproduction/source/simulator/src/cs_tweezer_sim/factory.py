"""Factories that keep the public runtime and privileged oracle separate."""

from __future__ import annotations

from dataclasses import dataclass

from .config import EnvironmentConfig
from .multilevel_config import MultilevelEnvironmentConfig
from .oracle import TruthOracle
from .observation import ObservationModel
from .qutip_multilevel_backend import QutipMultilevelBackend
from .qutip_backend import QutipReducedBackend
from .runtime import ExperimentRuntime
from .stochastic import ShotNoiseModel
from .stochastic_runtime import StochasticExperimentRuntime


@dataclass(frozen=True)
class PlatformBundle:
    """Platform handles for benchmark setup.

    A benchmark runner gives only ``public`` to a controller and retains
    ``oracle`` for validation and scoring.
    """

    public: ExperimentRuntime | StochasticExperimentRuntime
    oracle: TruthOracle


def create_reduced_platform(
    config: EnvironmentConfig,
    *,
    seed: int = 0,
    observation_model: ObservationModel | None = None,
) -> PlatformBundle:
    """Create the reduced QuTiP platform with separated public/truth handles."""

    backend = QutipReducedBackend(config)
    return PlatformBundle(
        public=ExperimentRuntime(
            backend, seed=seed, observation_model=observation_model
        ),
        oracle=TruthOracle(backend),
    )


def create_multilevel_platform(
    config: MultilevelEnvironmentConfig,
    *,
    seed: int = 0,
    observation_model: ObservationModel | None = None,
) -> PlatformBundle:
    """Create a configured multilevel platform with public/truth separation."""

    backend = QutipMultilevelBackend(config)
    return PlatformBundle(
        public=ExperimentRuntime(
            backend, seed=seed, observation_model=observation_model
        ),
        oracle=TruthOracle(backend),
    )


def create_stochastic_multilevel_platform(
    config: MultilevelEnvironmentConfig,
    noise_model: ShotNoiseModel,
    *,
    seed: int = 0,
    observation_model: ObservationModel | None = None,
) -> PlatformBundle:
    """Create a multilevel platform with hidden per-shot physical contexts."""

    backend = QutipMultilevelBackend(config)
    return PlatformBundle(
        public=StochasticExperimentRuntime(
            backend,
            noise_model,
            seed=seed,
            observation_model=observation_model,
        ),
        oracle=TruthOracle(backend),
    )
