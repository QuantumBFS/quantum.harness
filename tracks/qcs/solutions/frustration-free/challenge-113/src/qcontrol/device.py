from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import math
from numbers import Integral, Real
from threading import Lock
from typing import Protocol, runtime_checkable

import numpy as np

from qcontrol.config import DeviceConfig
from qcontrol.objectives import normalized_infidelity
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


_CERTIFICATION_SHOTS = 100_000
_CERTIFICATION_TARGET = 0.999
_ONE_SIDED_95_Z = 1.6448536269514722


def _nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a nonnegative integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return result


def _positive_integer(name: str, value: object) -> int:
    result = _nonnegative_integer(name, value)
    if result == 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


@dataclass(frozen=True)
class Observation:
    estimate: float
    shots: int
    optimizer_query_index: int
    validation: bool
    observation_seed: int

    def __post_init__(self) -> None:
        if isinstance(self.estimate, (bool, np.bool_)) or not isinstance(
            self.estimate, Real
        ):
            raise ValueError("estimate must be a finite probability")
        estimate = float(self.estimate)
        if not math.isfinite(estimate) or not 0.0 <= estimate <= 1.0:
            raise ValueError("estimate must be a finite probability")
        shots = _nonnegative_integer("shots", self.shots)
        optimizer_query_index = _nonnegative_integer(
            "optimizer_query_index",
            self.optimizer_query_index,
        )
        observation_seed = _nonnegative_integer(
            "observation_seed",
            self.observation_seed,
        )
        if not isinstance(self.validation, (bool, np.bool_)):
            raise ValueError("validation must be a boolean")
        if self.validation and shots == 0:
            raise ValueError("validation observations must use positive shots")

        object.__setattr__(self, "estimate", estimate)
        object.__setattr__(self, "shots", shots)
        object.__setattr__(self, "optimizer_query_index", optimizer_query_index)
        object.__setattr__(self, "validation", bool(self.validation))
        object.__setattr__(self, "observation_seed", observation_seed)

    def certifies(self, threshold: float = _CERTIFICATION_TARGET) -> bool:
        if isinstance(threshold, (bool, np.bool_)) or not isinstance(threshold, Real):
            raise ValueError("threshold must be a finite probability")
        threshold = float(threshold)
        if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be a finite probability")
        if (
            not self.validation
            or self.shots != _CERTIFICATION_SHOTS
            or threshold < _CERTIFICATION_TARGET
        ):
            return False

        z_squared = _ONE_SIDED_95_Z**2
        denominator = 1.0 + z_squared / self.shots
        center = self.estimate + z_squared / (2.0 * self.shots)
        radius = _ONE_SIDED_95_Z * math.sqrt(
            self.estimate * (1.0 - self.estimate) / self.shots
            + z_squared / (4.0 * self.shots**2)
        )
        lower_bound = (center - radius) / denominator
        return lower_bound >= threshold


@dataclass(frozen=True)
class QueryLedger:
    observations: tuple[Observation, ...] = ()

    def __post_init__(self) -> None:
        observations = tuple(self.observations)
        if not all(isinstance(item, Observation) for item in observations):
            raise ValueError("ledger entries must be observations")
        object.__setattr__(self, "observations", observations)

    @property
    def optimizer_queries(self) -> int:
        return sum(not observation.validation for observation in self.observations)

    @property
    def optimizer_shots(self) -> int:
        return sum(
            observation.shots
            for observation in self.observations
            if not observation.validation
        )

    @property
    def validation_queries(self) -> int:
        return sum(observation.validation for observation in self.observations)

    @property
    def validation_shots(self) -> int:
        return sum(
            observation.shots
            for observation in self.observations
            if observation.validation
        )

    @property
    def total_queries(self) -> int:
        return len(self.observations)

    @property
    def total_shots(self) -> int:
        return sum(observation.shots for observation in self.observations)


@runtime_checkable
class QueryDevice(Protocol):
    @property
    def ledger(self) -> QueryLedger: ...

    def query(self, normalized_pulse: object) -> Observation: ...

    def validate(
        self,
        normalized_pulse: object,
        shots: int = _CERTIFICATION_SHOTS,
    ) -> Observation: ...


def _make_exact_fidelity_evaluator(
    truth: ControlSystem,
    space: PulseSpace,
) -> Callable[[object], float]:
    if not isinstance(truth, ControlSystem):
        raise ValueError("truth must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if len(truth.controls) != space.control_count:
        raise ValueError("pulse space control count does not match the truth system")
    if tuple(truth.amplitude_scales) != tuple(space.amplitude_scales):
        raise ValueError("pulse space amplitude scales do not match the truth system")

    def evaluate(normalized_pulse: object) -> float:
        loss = float(normalized_infidelity(normalized_pulse, truth, space))
        fidelity = float(np.clip(1.0 - loss, 0.0, 1.0))
        if not math.isfinite(fidelity):
            raise ValueError("truth evaluation did not produce a finite fidelity")
        return fidelity

    return evaluate


def make_offline_evaluator(
    truth: ControlSystem,
    space: PulseSpace,
) -> Callable[[object], float]:
    """Build a separate exact evaluator intended only for offline analysis."""
    return _make_exact_fidelity_evaluator(truth, space)


def _observation_seed(device_seed: int, query_index: int, validation: bool) -> int:
    payload = f"{device_seed}:{query_index}:{int(validation)}".encode("ascii")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="little", signed=False)


def make_query_device(
    truth: ControlSystem,
    space: PulseSpace,
    config: DeviceConfig,
    *,
    seed: int,
) -> QueryDevice:
    if not isinstance(config, DeviceConfig):
        raise ValueError("config must be a DeviceConfig")
    device_seed = _nonnegative_integer("seed", seed)
    evaluate = _make_exact_fidelity_evaluator(truth, space)
    configured_shots = config.shots
    observations: tuple[Observation, ...] = ()
    lock = Lock()

    def observe(
        normalized_pulse: object,
        *,
        validation: bool,
        shots: int,
    ) -> Observation:
        nonlocal observations
        with lock:
            optimizer_queries = sum(
                not observation.validation for observation in observations
            )
            optimizer_query_index = (
                optimizer_queries if validation else optimizer_queries + 1
            )
            sequence_index = len(observations) + 1
            observation_seed = _observation_seed(
                device_seed,
                sequence_index,
                validation,
            )
            exact_fidelity = evaluate(normalized_pulse)
            if shots == 0:
                estimate = exact_fidelity
            else:
                rng = np.random.default_rng(observation_seed)
                successes = int(rng.binomial(shots, exact_fidelity))
                estimate = successes / shots
            observation = Observation(
                estimate=estimate,
                shots=shots,
                optimizer_query_index=optimizer_query_index,
                validation=validation,
                observation_seed=observation_seed,
            )
            observations = (*observations, observation)
            return observation

    class _OpaqueQueryDevice:
        __slots__ = ()

        @property
        def ledger(self) -> QueryLedger:
            with lock:
                return QueryLedger(observations)

        def query(self, normalized_pulse: object) -> Observation:
            shots = 0 if configured_shots is None else configured_shots
            return observe(normalized_pulse, validation=False, shots=shots)

        def validate(
            self,
            normalized_pulse: object,
            shots: int = _CERTIFICATION_SHOTS,
        ) -> Observation:
            validation_shots = _positive_integer("shots", shots)
            return observe(
                normalized_pulse,
                validation=True,
                shots=validation_shots,
            )

    return _OpaqueQueryDevice()
