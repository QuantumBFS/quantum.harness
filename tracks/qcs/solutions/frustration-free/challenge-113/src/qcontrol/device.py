from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import math
from numbers import Integral, Real
from threading import RLock
from typing import Protocol, runtime_checkable

import numpy as np

from qcontrol.config import DeviceConfig
from qcontrol.objectives import normalized_infidelity
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


_CERTIFICATION_SHOTS = 100_000
_CERTIFICATION_TARGET = 0.999
_ONE_SIDED_95_Z = 1.6448536269514722
_DIGEST_HEX_LENGTH = 64

RequestedShots = int | float | bool | str | None


class DeviceQueryError(RuntimeError):
    __slots__ = ("attempt_index", "category")

    def __init__(self, attempt_index: int, category: str) -> None:
        self.attempt_index = attempt_index
        self.category = category
        super().__init__(f"device query attempt {attempt_index} failed: {category}")


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


def _sanitized_requested_shots(value: object) -> RequestedShots:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value)
    value_type = type(value)
    return f"<{value_type.__module__}.{value_type.__qualname__}>"


def _default_seed_digest(seed: int) -> str:
    return hashlib.sha256(str(seed).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class Observation:
    estimate: float
    shots: int
    optimizer_query_index: int
    validation: bool
    observation_seed: int
    attempt_index: int | None = None
    seed_digest: str | None = None

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
        attempt_index = (
            optimizer_query_index
            if self.attempt_index is None
            else _positive_integer("attempt_index", self.attempt_index)
        )
        seed_digest = (
            _default_seed_digest(observation_seed)
            if self.seed_digest is None
            else self.seed_digest
        )
        if (
            not isinstance(seed_digest, str)
            or len(seed_digest) != _DIGEST_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in seed_digest)
        ):
            raise ValueError("seed_digest must be a lowercase SHA-256 digest")
        if not isinstance(self.validation, (bool, np.bool_)):
            raise ValueError("validation must be a boolean")
        if self.validation and shots == 0:
            raise ValueError("validation observations must use positive shots")

        object.__setattr__(self, "estimate", estimate)
        object.__setattr__(self, "shots", shots)
        object.__setattr__(self, "optimizer_query_index", optimizer_query_index)
        object.__setattr__(self, "validation", bool(self.validation))
        object.__setattr__(self, "observation_seed", observation_seed)
        object.__setattr__(self, "attempt_index", attempt_index)
        object.__setattr__(self, "seed_digest", seed_digest)

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


@dataclass(frozen=True, slots=True)
class QueryRecord:
    attempt_index: int
    optimizer_query_index: int
    validation: bool
    status: str
    requested_shots: RequestedShots
    charged_shots: int
    estimate: float | None
    observation_seed: int | None
    seed_digest: str | None
    error_category: str | None

    @property
    def success(self) -> bool:
        return self.status == "succeeded"


@dataclass(frozen=True, slots=True)
class _AttemptRecord:
    attempt_index: int
    optimizer_query_index: int
    validation: bool
    status: str
    requested_shots: RequestedShots
    charged_shots: int
    estimate: float | None
    observation_seed: int | None
    seed_digest: str | None
    error_category: str | None

    @property
    def success(self) -> bool:
        return self.status == "succeeded"


def _public_record(record: _AttemptRecord) -> QueryRecord:
    return QueryRecord(
        attempt_index=record.attempt_index,
        optimizer_query_index=record.optimizer_query_index,
        validation=record.validation,
        status=record.status,
        requested_shots=record.requested_shots,
        charged_shots=record.charged_shots,
        estimate=record.estimate,
        observation_seed=record.observation_seed,
        seed_digest=record.seed_digest,
        error_category=record.error_category,
    )


def _public_observation(record: _AttemptRecord) -> Observation:
    if (
        not record.success
        or record.estimate is None
        or record.observation_seed is None
        or record.seed_digest is None
    ):
        raise ValueError("failed attempts do not have observations")
    return Observation(
        estimate=record.estimate,
        shots=record.charged_shots,
        optimizer_query_index=record.optimizer_query_index,
        validation=record.validation,
        observation_seed=record.observation_seed,
        attempt_index=record.attempt_index,
        seed_digest=record.seed_digest,
    )


Certifier = Callable[[Observation, float, frozenset[int]], bool]


class QueryLedger:
    __slots__ = ("_records", "_certifier", "_authorized_attempts")

    def __init__(
        self,
        records: tuple[_AttemptRecord, ...],
        certifier: Certifier,
    ) -> None:
        self._records = records
        self._certifier = certifier
        self._authorized_attempts = frozenset(
            record.attempt_index for record in records if record.success
        )

    @property
    def records(self) -> tuple[QueryRecord, ...]:
        return tuple(_public_record(record) for record in self._records)

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(
            _public_observation(record) for record in self._records if record.success
        )

    @property
    def optimizer_queries(self) -> int:
        return sum(not record.validation for record in self._records)

    @property
    def optimizer_shots(self) -> int:
        return sum(
            record.charged_shots for record in self._records if not record.validation
        )

    @property
    def validation_queries(self) -> int:
        return sum(record.validation for record in self._records)

    @property
    def validation_shots(self) -> int:
        return sum(
            record.charged_shots for record in self._records if record.validation
        )

    @property
    def total_queries(self) -> int:
        return len(self._records)

    @property
    def total_shots(self) -> int:
        return sum(record.charged_shots for record in self._records)

    def certifies(
        self,
        observation: Observation,
        threshold: float = _CERTIFICATION_TARGET,
    ) -> bool:
        return self._certifier(observation, threshold, self._authorized_attempts)

    def __reduce__(self) -> object:
        raise TypeError("QueryLedger capability cannot be pickled")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("QueryLedger capability cannot be pickled")


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

    def certifies(
        self,
        observation: Observation,
        threshold: float = _CERTIFICATION_TARGET,
    ) -> bool: ...


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


def _seed_identity(
    device_seed: int,
    attempt_index: int,
    validation: bool,
) -> tuple[int, str]:
    payload = f"{device_seed}:{attempt_index}:{int(validation)}".encode("ascii")
    digest = hashlib.sha256(payload).digest()
    observation_seed = int.from_bytes(digest[:16], byteorder="big", signed=False)
    return observation_seed, digest.hex()


def _failure_category(stage: str, error: Exception) -> str:
    if stage == "request":
        return "request_validation"
    if stage == "seed":
        return "seed_derivation_failure"
    if stage == "seed_guard":
        return "seed_collision"
    if stage == "shot_validation":
        return "invalid_shots"
    if stage == "evaluation":
        return "invalid_pulse" if isinstance(error, ValueError) else "propagation_failure"
    if stage == "rng":
        return "rng_failure"
    if stage == "sampling":
        return "sampling_failure"
    if stage == "observation":
        return "observation_failure"
    return "internal_failure"


def _abort_category(error: BaseException) -> str:
    if isinstance(error, KeyboardInterrupt):
        return "keyboard_interrupt"
    if isinstance(error, SystemExit):
        return "system_exit"
    return "process_abort"


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
    configured_shots = 0 if config.shots is None else config.shots
    lock = RLock()
    next_attempt_index = 0
    optimizer_attempts = 0
    records: dict[int, _AttemptRecord] = {}
    issued: dict[int, tuple[Observation, int]] = {}
    digest_by_seed: dict[int, str] = {}
    seed_digests: set[str] = set()

    def allocate_attempt(validation: bool) -> _AttemptRecord:
        nonlocal next_attempt_index, optimizer_attempts
        with lock:
            next_attempt_index += 1
            if not validation:
                optimizer_attempts += 1
            reserved = _AttemptRecord(
                attempt_index=next_attempt_index,
                optimizer_query_index=optimizer_attempts,
                validation=validation,
                status="reserved",
                requested_shots=None,
                charged_shots=0,
                estimate=None,
                observation_seed=None,
                seed_digest=None,
                error_category=None,
            )
            records[reserved.attempt_index] = reserved
            return reserved

    def register_seed(observation_seed: int, seed_digest: str) -> bool:
        with lock:
            prior_digest = digest_by_seed.get(observation_seed)
            seed_collision = (
                prior_digest is not None and prior_digest != seed_digest
            ) or seed_digest in seed_digests
            if prior_digest is None:
                digest_by_seed[observation_seed] = seed_digest
            seed_digests.add(seed_digest)
            return seed_collision

    def finalize(record: _AttemptRecord, observation: Observation | None = None) -> None:
        with lock:
            records[record.attempt_index] = record
            if observation is not None:
                issued[id(observation)] = (observation, record.attempt_index)

    def terminal_record(
        allocated: _AttemptRecord,
        *,
        status: str,
        requested_shots: RequestedShots,
        charged_shots: int,
        observation_seed: int | None,
        seed_digest: str | None,
        estimate: float | None = None,
        error_category: str | None = None,
    ) -> _AttemptRecord:
        return _AttemptRecord(
            attempt_index=allocated.attempt_index,
            optimizer_query_index=allocated.optimizer_query_index,
            validation=allocated.validation,
            status=status,
            requested_shots=requested_shots,
            charged_shots=charged_shots,
            estimate=estimate,
            observation_seed=observation_seed,
            seed_digest=seed_digest,
            error_category=error_category,
        )

    def invoke(
        normalized_pulse: object,
        *,
        validation: bool,
        raw_shots: object,
    ) -> Observation:
        allocated = allocate_attempt(validation)
        requested_shots: RequestedShots = None
        charged_shots = 0
        observation_seed: int | None = None
        seed_digest: str | None = None
        stage = "request"
        public_error: DeviceQueryError | None = None
        try:
            requested_shots = _sanitized_requested_shots(raw_shots)
            stage = "seed"
            observation_seed, seed_digest = _seed_identity(
                device_seed,
                allocated.attempt_index,
                validation,
            )
            stage = "seed_guard"
            if register_seed(observation_seed, seed_digest):
                raise RuntimeError("deterministic observation seed collision")
            stage = "shot_validation"
            shots = (
                _positive_integer("shots", raw_shots)
                if validation
                else configured_shots
            )
            stage = "evaluation"
            exact_fidelity = evaluate(normalized_pulse)
            if shots == 0:
                estimate = exact_fidelity
            else:
                stage = "rng"
                rng = np.random.default_rng(observation_seed)
                stage = "sampling"
                charged_shots = shots
                successes = int(rng.binomial(shots, exact_fidelity))
                estimate = successes / shots
            record = terminal_record(
                allocated,
                status="succeeded",
                requested_shots=requested_shots,
                charged_shots=charged_shots,
                estimate=estimate,
                observation_seed=observation_seed,
                seed_digest=seed_digest,
            )
            stage = "observation"
            observation = _public_observation(record)
            finalize(record, observation)
            return observation
        except Exception as error:
            category = _failure_category(stage, error)
            finalize(
                terminal_record(
                    allocated,
                    status="failed",
                    requested_shots=requested_shots,
                    charged_shots=charged_shots,
                    observation_seed=observation_seed,
                    seed_digest=seed_digest,
                    error_category=category,
                )
            )
            public_error = DeviceQueryError(allocated.attempt_index, category)
        except BaseException as error:
            finalize(
                terminal_record(
                    allocated,
                    status="aborted",
                    requested_shots=requested_shots,
                    charged_shots=charged_shots,
                    observation_seed=observation_seed,
                    seed_digest=seed_digest,
                    error_category=_abort_category(error),
                )
            )
            raise
        if public_error is not None:
            raise public_error from None
        raise AssertionError("unreachable device query state")

    def certify(
        observation: Observation,
        threshold: float,
        authorized_attempts: frozenset[int],
    ) -> bool:
        if not isinstance(observation, Observation):
            return False
        with lock:
            authorization = issued.get(id(observation))
            if authorization is None or authorization[0] is not observation:
                return False
            attempt_index = authorization[1]
            record = records.get(attempt_index)
        if (
            attempt_index not in authorized_attempts
            or record is None
            or not record.success
        ):
            return False
        canonical = _public_observation(record)
        if observation != canonical:
            return False
        return canonical.certifies(threshold)

    class _OpaqueQueryDevice:
        __slots__ = ()

        @property
        def ledger(self) -> QueryLedger:
            with lock:
                snapshot = tuple(records[index] for index in sorted(records))
            return QueryLedger(snapshot, certify)

        def query(self, normalized_pulse: object) -> Observation:
            return invoke(
                normalized_pulse,
                validation=False,
                raw_shots=configured_shots,
            )

        def validate(
            self,
            normalized_pulse: object,
            shots: int = _CERTIFICATION_SHOTS,
        ) -> Observation:
            return invoke(
                normalized_pulse,
                validation=True,
                raw_shots=shots,
            )

        def certifies(
            self,
            observation: Observation,
            threshold: float = _CERTIFICATION_TARGET,
        ) -> bool:
            with lock:
                authorized = frozenset(
                    record.attempt_index for record in records.values() if record.success
                )
            return certify(observation, threshold, authorized)

        def __reduce__(self) -> object:
            raise TypeError("QueryDevice capability cannot be pickled")

        def __reduce_ex__(self, protocol: int) -> object:
            raise TypeError("QueryDevice capability cannot be pickled")

    return _OpaqueQueryDevice()
