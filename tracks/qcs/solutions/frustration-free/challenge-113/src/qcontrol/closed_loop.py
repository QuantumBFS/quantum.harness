from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from numbers import Integral, Real

import cma
import numpy as np
from numpy.typing import NDArray

from qcontrol.config import SearchConfig
from qcontrol.device import DeviceQueryError, Observation, QueryDevice


_TARGET_FIDELITY = 0.999
_VALIDATION_SHOTS = 100_000
_INITIAL_SCALE = 0.2
_DEFAULT_BOUND = 1.0


def _positive_integer(name: str, value: object) -> int:
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, Integral)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _nonnegative_integer(name: str, value: object) -> int:
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, Integral)
        or value < 0
    ):
        raise ValueError(f"{name} must be a nonnegative integer")
    return int(value)


def _finite_vector(name: str, value: object) -> NDArray[np.float64]:
    array = np.asarray(value)
    if np.iscomplexobj(array):
        raise ValueError(f"{name} must be real")
    try:
        vector = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite real vector") from error
    if vector.ndim != 1 or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite real vector")
    return np.array(vector, dtype=np.float64, copy=True)


def _finite_matrix(name: str, value: object) -> NDArray[np.float64]:
    array = np.asarray(value)
    if np.iscomplexobj(array):
        raise ValueError(f"{name} must be real")
    try:
        matrix = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite real matrix") from error
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must be a finite real matrix")
    return np.array(matrix, dtype=np.float64, copy=True)


def _coordinate_bound(value: object, dimension: int) -> NDArray[np.float64]:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("bound must contain finite positive values")
    try:
        bound = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("bound must contain finite positive values") from error
    if bound.ndim == 0:
        bound = np.full(dimension, float(bound), dtype=np.float64)
    elif bound.shape == (dimension,):
        bound = np.array(bound, dtype=np.float64, copy=True)
    else:
        raise ValueError(f"bound must be scalar or have shape ({dimension},)")
    if not np.all(np.isfinite(bound)) or np.any(bound <= 0.0):
        raise ValueError("bound must contain finite positive values")
    return bound


def _readonly(array: NDArray[np.float64]) -> NDArray[np.float64]:
    result = np.ascontiguousarray(array, dtype=np.float64)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, init=False, eq=False)
class SearchSpace:
    origin: NDArray[np.float64]
    basis: NDArray[np.float64]
    lower_bounds: NDArray[np.float64]
    upper_bounds: NDArray[np.float64]

    def __init__(
        self,
        origin: object,
        basis: object,
        lower_bounds: object | None = None,
        upper_bounds: object | None = None,
        *,
        bound: object = _DEFAULT_BOUND,
    ) -> None:
        origin_array = _finite_vector("origin", origin)
        if np.any(np.abs(origin_array) > 1.0):
            raise ValueError("origin must lie within normalized pulse bounds [-1, 1]")
        basis_array = _finite_matrix("basis", basis)
        if basis_array.shape[0] != origin_array.size or basis_array.shape[1] == 0:
            raise ValueError(
                "basis must have shape (origin.size, positive dimension)"
            )
        dimension = basis_array.shape[1]
        if dimension > origin_array.size:
            raise ValueError("basis dimension cannot exceed pulse dimension")
        gram = basis_array.T @ basis_array
        if not np.allclose(gram, np.eye(dimension), rtol=0.0, atol=1e-10):
            raise ValueError("basis columns must be orthonormal (whitened coordinates)")

        if (lower_bounds is None) != (upper_bounds is None):
            raise ValueError("lower_bounds and upper_bounds must be supplied together")
        if lower_bounds is None:
            bound_array = _coordinate_bound(bound, dimension)
            lower_array = -bound_array
            upper_array = bound_array
        else:
            lower_array = _finite_vector("lower_bounds", lower_bounds)
            upper_array = _finite_vector("upper_bounds", upper_bounds)
            if lower_array.shape != (dimension,) or upper_array.shape != (dimension,):
                raise ValueError(
                    f"coordinate bounds must both have shape ({dimension},)"
                )
            if np.any(lower_array >= upper_array):
                raise ValueError("each lower bound must be below its upper bound")
            if np.any(lower_array > 0.0) or np.any(upper_array < 0.0):
                raise ValueError("coordinate bounds must contain the zero origin")

        object.__setattr__(self, "origin", _readonly(origin_array))
        object.__setattr__(self, "basis", _readonly(basis_array))
        object.__setattr__(self, "lower_bounds", _readonly(lower_array))
        object.__setattr__(self, "upper_bounds", _readonly(upper_array))

    @property
    def dimension(self) -> int:
        return int(self.basis.shape[1])

    @property
    def pulse_dimension(self) -> int:
        return int(self.origin.size)

    def to_pulse(self, coordinates: object) -> NDArray[np.float64]:
        coordinate_array = _finite_vector("coordinates", coordinates)
        if coordinate_array.shape != (self.dimension,):
            raise ValueError(f"coordinates must have shape ({self.dimension},)")
        pulse = self.origin + self.basis @ coordinate_array
        return np.clip(pulse, -1.0, 1.0)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SearchSpace):
            return NotImplemented
        return bool(
            np.array_equal(self.origin, other.origin)
            and np.array_equal(self.basis, other.basis)
            and np.array_equal(self.lower_bounds, other.lower_bounds)
            and np.array_equal(self.upper_bounds, other.upper_bounds)
        )

    def __hash__(self) -> int:
        return hash(
            (
                tuple(float(value) for value in self.origin),
                tuple(
                    tuple(float(value) for value in row)
                    for row in self.basis
                ),
                tuple(float(value) for value in self.lower_bounds),
                tuple(float(value) for value in self.upper_bounds),
            )
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "basis": [
                [float(value) for value in row]
                for row in self.basis
            ],
            "lower_bounds": [float(value) for value in self.lower_bounds],
            "origin": [float(value) for value in self.origin],
            "upper_bounds": [float(value) for value in self.upper_bounds],
        }

    @classmethod
    def from_canonical_dict(cls, payload: object) -> SearchSpace:
        if not isinstance(payload, Mapping):
            raise ValueError("search-space payload must be a mapping")
        try:
            return cls(
                payload["origin"],
                payload["basis"],
                payload["lower_bounds"],
                payload["upper_bounds"],
            )
        except KeyError as error:
            raise ValueError(
                f"search-space payload is missing {error.args[0]!r}"
            ) from None


def _leading_space(
    origin: object,
    basis: object,
    *,
    dimension: object,
    bound: object,
) -> SearchSpace:
    origin_array = _finite_vector("origin", origin)
    basis_array = _finite_matrix("basis", basis)
    resolved_dimension = _positive_integer("dimension", dimension)
    if basis_array.shape[0] != origin_array.size:
        raise ValueError("basis row count must match origin size")
    if basis_array.shape[1] < resolved_dimension:
        raise ValueError("basis has fewer columns than the requested dimension")
    return SearchSpace(
        origin_array,
        basis_array[:, :resolved_dimension],
        bound=bound,
    )


def make_full_space(
    origin: object,
    *,
    bound: object = _DEFAULT_BOUND,
) -> SearchSpace:
    origin_array = _finite_vector("origin", origin)
    return SearchSpace(
        origin_array,
        np.eye(origin_array.size, dtype=np.float64),
        bound=bound,
    )


def make_model_hessian_space(
    origin: object,
    model_basis: object,
    *,
    dimension: object,
    bound: object = _DEFAULT_BOUND,
) -> SearchSpace:
    return _leading_space(
        origin,
        model_basis,
        dimension=dimension,
        bound=bound,
    )


def make_oracle_space(
    origin: object,
    oracle_basis: object,
    *,
    dimension: object,
    bound: object = _DEFAULT_BOUND,
) -> SearchSpace:
    return _leading_space(
        origin,
        oracle_basis,
        dimension=dimension,
        bound=bound,
    )


def make_random_space(
    origin: object,
    *,
    dimension: object,
    seed: object,
    bound: object = _DEFAULT_BOUND,
) -> SearchSpace:
    origin_array = _finite_vector("origin", origin)
    resolved_dimension = _positive_integer("dimension", dimension)
    resolved_seed = _nonnegative_integer("seed", seed)
    if resolved_dimension > origin_array.size:
        raise ValueError("dimension cannot exceed pulse dimension")
    gaussian = np.random.default_rng(resolved_seed).normal(
        size=(origin_array.size, resolved_dimension)
    )
    basis, triangular = np.linalg.qr(gaussian, mode="reduced")
    diagonal = np.diag(triangular)
    signs = np.where(diagonal < 0.0, -1.0, 1.0)
    basis = np.asarray(basis * signs, dtype=np.float64)
    return SearchSpace(origin_array, basis, bound=bound)


def make_search_space(
    config: SearchConfig,
    origin: object,
    *,
    model_basis: object | None = None,
    oracle_basis: object | None = None,
    seed: object = 0,
    bound: object = _DEFAULT_BOUND,
) -> SearchSpace:
    if not isinstance(config, SearchConfig):
        raise ValueError("config must be a SearchConfig")
    if config.method == "full":
        return make_full_space(origin, bound=bound)
    if config.method == "model_hessian":
        if model_basis is None:
            raise ValueError("model_hessian search requires model_basis")
        return make_model_hessian_space(
            origin,
            model_basis,
            dimension=config.dimension,
            bound=bound,
        )
    if config.method == "random":
        return make_random_space(
            origin,
            dimension=config.dimension,
            seed=seed,
            bound=bound,
        )
    if oracle_basis is None:
        raise ValueError("oracle search requires an externally constructed oracle_basis")
    return make_oracle_space(
        origin,
        oracle_basis,
        dimension=config.dimension,
        bound=bound,
    )


def _observation_dict(observation: Observation) -> dict[str, object]:
    return {
        "attempt_index": int(observation.attempt_index),
        "estimate": float(observation.estimate),
        "observation_seed": int(observation.observation_seed),
        "optimizer_query_index": int(observation.optimizer_query_index),
        "seed_digest": str(observation.seed_digest),
        "shots": int(observation.shots),
        "validation": bool(observation.validation),
    }


def _observation_from_dict(payload: object) -> Observation:
    if not isinstance(payload, Mapping):
        raise ValueError("observation payload must be a mapping")
    try:
        return Observation(
            estimate=payload["estimate"],
            shots=payload["shots"],
            optimizer_query_index=payload["optimizer_query_index"],
            validation=payload["validation"],
            observation_seed=payload["observation_seed"],
            attempt_index=payload["attempt_index"],
            seed_digest=payload["seed_digest"],
        )
    except KeyError as error:
        raise ValueError(
            f"observation payload is missing {error.args[0]!r}"
        ) from None


def _optional_observation_dict(
    observation: Observation | None,
) -> dict[str, object] | None:
    return None if observation is None else _observation_dict(observation)


def _optional_observation_from_dict(payload: object) -> Observation | None:
    return None if payload is None else _observation_from_dict(payload)


def _pulse_tuple(value: object) -> tuple[float, ...]:
    pulse = _finite_vector("pulse", value)
    if pulse.size == 0 or np.any(np.abs(pulse) > 1.0):
        raise ValueError("pulse must be nonempty and within [-1, 1]")
    return tuple(float(item) for item in pulse)


def _sanitized_failure_category(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "device_query_failure"
    if not value.isascii() or any(
        not (character.isalnum() or character == "_")
        for character in value
    ):
        return "device_query_failure"
    return value


@dataclass(frozen=True, slots=True)
class ValidationAttempt:
    optimizer_query_index: int
    pulse: tuple[float, ...]
    best_observation: Observation
    device_attempt_index: int
    validation_observation: Observation | None
    failure_category: str | None
    certified: bool

    def __post_init__(self) -> None:
        optimizer_query_index = _positive_integer(
            "optimizer_query_index",
            self.optimizer_query_index,
        )
        device_attempt_index = _positive_integer(
            "device_attempt_index",
            self.device_attempt_index,
        )
        pulse = _pulse_tuple(self.pulse)
        if (
            not isinstance(self.best_observation, Observation)
            or self.best_observation.validation
            or self.best_observation.optimizer_query_index
            != optimizer_query_index
        ):
            raise ValueError(
                "best_observation must be the matching optimizer observation"
            )
        if not isinstance(self.certified, (bool, np.bool_)):
            raise ValueError("certified must be a boolean")
        validation = self.validation_observation
        if validation is None:
            if (
                not isinstance(self.failure_category, str)
                or _sanitized_failure_category(self.failure_category)
                != self.failure_category
            ):
                raise ValueError(
                    "failed validation attempts require a sanitized failure category"
                )
            if self.certified:
                raise ValueError("failed validation attempts cannot certify")
        else:
            if (
                not isinstance(validation, Observation)
                or not validation.validation
                or validation.optimizer_query_index != optimizer_query_index
                or validation.attempt_index != device_attempt_index
            ):
                raise ValueError(
                    "validation_observation must match the validation attempt"
                )
            if self.failure_category is not None:
                raise ValueError(
                    "successful validation attempts cannot have a failure category"
                )

        object.__setattr__(self, "optimizer_query_index", optimizer_query_index)
        object.__setattr__(self, "pulse", pulse)
        object.__setattr__(self, "device_attempt_index", device_attempt_index)
        object.__setattr__(self, "certified", bool(self.certified))

    @property
    def status(self) -> str:
        if self.certified:
            return "certified"
        if self.validation_observation is None:
            return "failed"
        return "rejected"

    def canonical_dict(self) -> dict[str, object]:
        return {
            "best_observation": _observation_dict(self.best_observation),
            "certified": bool(self.certified),
            "device_attempt_index": int(self.device_attempt_index),
            "failure_category": self.failure_category,
            "optimizer_query_index": int(self.optimizer_query_index),
            "pulse": [float(value) for value in self.pulse],
            "status": self.status,
            "validation_observation": _optional_observation_dict(
                self.validation_observation
            ),
        }

    @classmethod
    def from_canonical_dict(cls, payload: object) -> ValidationAttempt:
        if not isinstance(payload, Mapping):
            raise ValueError("validation-attempt payload must be a mapping")
        try:
            attempt = cls(
                optimizer_query_index=payload["optimizer_query_index"],
                pulse=payload["pulse"],
                best_observation=_observation_from_dict(
                    payload["best_observation"]
                ),
                device_attempt_index=payload["device_attempt_index"],
                validation_observation=_optional_observation_from_dict(
                    payload["validation_observation"]
                ),
                failure_category=payload["failure_category"],
                certified=payload["certified"],
            )
            if payload["status"] != attempt.status:
                raise ValueError(
                    "serialized validation status does not match the attempt"
                )
            return attempt
        except KeyError as error:
            raise ValueError(
                f"validation-attempt payload is missing {error.args[0]!r}"
            ) from None


@dataclass(frozen=True, slots=True)
class ClosedLoopResult:
    space: SearchSpace
    best_pulse: tuple[float, ...]
    best_observation: Observation | None
    observations: tuple[Observation, ...]
    evaluations: int
    budget: int
    budget_exhausted: bool
    validation_attempts: tuple[ValidationAttempt, ...]
    certified: bool
    first_certified_query: int | None
    stop_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.space, SearchSpace):
            raise ValueError("space must be a SearchSpace")
        best_pulse = _pulse_tuple(self.best_pulse)
        observations = tuple(self.observations)
        validation_attempts = tuple(self.validation_attempts)
        evaluations = _nonnegative_integer("evaluations", self.evaluations)
        budget = _positive_integer("budget", self.budget)
        if evaluations > budget:
            raise ValueError("evaluations cannot exceed budget")
        if not isinstance(self.budget_exhausted, (bool, np.bool_)):
            raise ValueError("budget_exhausted must be a boolean")
        if not isinstance(self.certified, (bool, np.bool_)):
            raise ValueError("certified must be a boolean")
        if self.stop_reason not in {"budget", "certified", "optimizer_stopped"}:
            raise ValueError("unsupported stop_reason")
        if any(
            not isinstance(observation, Observation)
            or observation.validation
            for observation in observations
        ):
            raise ValueError("observations must contain optimizer observations")
        if (
            self.best_observation is not None
            and self.best_observation not in observations
        ):
            raise ValueError("best_observation must appear in observations")
        if any(
            not isinstance(attempt, ValidationAttempt)
            for attempt in validation_attempts
        ):
            raise ValueError(
                "validation_attempts must contain ValidationAttempt records"
            )
        if any(
            attempt.best_observation not in observations
            for attempt in validation_attempts
        ):
            raise ValueError(
                "validation-attempt best observations must appear in history"
            )
        if any(
            len(attempt.pulse) != self.space.pulse_dimension
            for attempt in validation_attempts
        ):
            raise ValueError(
                "validation-attempt pulses must match the search pulse dimension"
            )
        crossing_indices = [
            attempt.optimizer_query_index
            for attempt in validation_attempts
        ]
        if any(
            current <= previous
            for previous, current in zip(
                crossing_indices,
                crossing_indices[1:],
            )
        ):
            raise ValueError(
                "validation attempts must follow optimizer query order"
            )
        certified_attempts = [
            attempt for attempt in validation_attempts if attempt.certified
        ]
        if len(certified_attempts) > 1 or (
            certified_attempts
            and validation_attempts[-1] is not certified_attempts[0]
        ):
            raise ValueError(
                "certification must be the final validation attempt"
            )
        expected_first = (
            certified_attempts[0].optimizer_query_index
            if certified_attempts
            else None
        )
        if self.first_certified_query != expected_first:
            raise ValueError(
                "first_certified_query must match validation_attempts"
            )
        if bool(certified_attempts) != bool(self.certified):
            raise ValueError("certified must match validation_attempts")
        if self.certified and self.stop_reason != "certified":
            raise ValueError("certified results must stop immediately")

        object.__setattr__(self, "best_pulse", best_pulse)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "validation_attempts", validation_attempts)
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "budget_exhausted", bool(self.budget_exhausted))
        object.__setattr__(self, "certified", bool(self.certified))

    @property
    def provisional_crossings(self) -> tuple[int, ...]:
        return tuple(
            attempt.optimizer_query_index
            for attempt in self.validation_attempts
        )

    @property
    def validation_result(self) -> Observation | None:
        return next(
            (
                attempt.validation_observation
                for attempt in reversed(self.validation_attempts)
                if attempt.validation_observation is not None
            ),
            None,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "best_observation": _optional_observation_dict(
                self.best_observation
            ),
            "best_pulse": [float(value) for value in self.best_pulse],
            "budget": int(self.budget),
            "budget_exhausted": bool(self.budget_exhausted),
            "certified": bool(self.certified),
            "evaluations": int(self.evaluations),
            "first_certified_query": self.first_certified_query,
            "observations": [
                _observation_dict(observation)
                for observation in self.observations
            ],
            "provisional_crossings": list(self.provisional_crossings),
            "schema_version": 1,
            "space": self.space.canonical_dict(),
            "stop_reason": self.stop_reason,
            "validation_attempts": [
                attempt.canonical_dict()
                for attempt in self.validation_attempts
            ],
            "validation_result": _optional_observation_dict(
                self.validation_result
            ),
        }

    @classmethod
    def from_canonical_dict(cls, payload: object) -> ClosedLoopResult:
        if not isinstance(payload, Mapping):
            raise ValueError("closed-loop result payload must be a mapping")
        try:
            if payload["schema_version"] != 1:
                raise ValueError("unsupported closed-loop result schema version")
            result = cls(
                space=SearchSpace.from_canonical_dict(payload["space"]),
                best_pulse=payload["best_pulse"],
                best_observation=_optional_observation_from_dict(
                    payload["best_observation"]
                ),
                observations=tuple(
                    _observation_from_dict(item)
                    for item in payload["observations"]
                ),
                evaluations=payload["evaluations"],
                budget=payload["budget"],
                budget_exhausted=payload["budget_exhausted"],
                validation_attempts=tuple(
                    ValidationAttempt.from_canonical_dict(item)
                    for item in payload["validation_attempts"]
                ),
                certified=payload["certified"],
                first_certified_query=payload["first_certified_query"],
                stop_reason=payload["stop_reason"],
            )
            if list(result.provisional_crossings) != payload[
                "provisional_crossings"
            ]:
                raise ValueError(
                    "serialized provisional_crossings do not match history"
                )
            if _optional_observation_dict(result.validation_result) != payload[
                "validation_result"
            ]:
                raise ValueError(
                    "serialized validation_result does not match history"
                )
            return result
        except KeyError as error:
            raise ValueError(
                f"closed-loop result payload is missing {error.args[0]!r}"
            ) from None


def _population_size(dimension: int) -> int:
    return 4 + int(math.floor(3.0 * math.log(dimension)))


def _cma_options(space: SearchSpace, seed: int) -> dict[str, object]:
    return {
        "bounds": [space.lower_bounds.tolist(), space.upper_bounds.tolist()],
        "popsize": _population_size(space.dimension),
        # pycma reserves zero for a time-derived seed, so offset the public
        # nonnegative seed to keep every accepted value deterministic.
        "seed": seed + 1,
        "verbose": -9,
        "verb_disp": 0,
        "verb_log": 0,
        "verb_time": False,
    }


def run_closed_loop(
    device: QueryDevice,
    space: SearchSpace,
    budget: object,
    seed: object,
) -> ClosedLoopResult:
    if not isinstance(space, SearchSpace):
        raise ValueError("space must be a SearchSpace")
    resolved_budget = _positive_integer("budget", budget)
    resolved_seed = _nonnegative_integer("seed", seed)
    try:
        initial_queries = int(device.ledger.optimizer_queries)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("device must expose QueryDevice ledger accounting") from error

    observations: list[Observation] = []
    validation_attempts: list[ValidationAttempt] = []
    best_observation: Observation | None = None
    best_pulse = np.array(space.origin, dtype=np.float64, copy=True)
    certified = False
    first_certified_query: int | None = None

    def evaluations() -> int:
        count = int(device.ledger.optimizer_queries) - initial_queries
        if count < 0:
            raise RuntimeError("device optimizer ledger count moved backwards")
        return count

    def evaluate(coordinates: NDArray[np.float64]) -> tuple[float, bool]:
        nonlocal best_observation
        nonlocal best_pulse
        nonlocal certified
        nonlocal first_certified_query

        pulse = space.to_pulse(coordinates)
        try:
            observation = device.query(pulse)
        except DeviceQueryError:
            return 1.0, False
        observations.append(observation)
        is_new_best = (
            best_observation is None
            or observation.estimate > best_observation.estimate
        )
        if is_new_best:
            best_observation = observation
            best_pulse = np.array(pulse, dtype=np.float64, copy=True)
            if observation.estimate >= _TARGET_FIDELITY:
                try:
                    validation = device.validate(
                        best_pulse,
                        shots=_VALIDATION_SHOTS,
                    )
                except DeviceQueryError as error:
                    validation_attempts.append(
                        ValidationAttempt(
                            optimizer_query_index=observation.optimizer_query_index,
                            pulse=tuple(float(value) for value in best_pulse),
                            best_observation=observation,
                            device_attempt_index=error.attempt_index,
                            validation_observation=None,
                            failure_category=_sanitized_failure_category(
                                error.category
                            ),
                            certified=False,
                        )
                    )
                else:
                    attempt_certified = bool(
                        device.certifies(validation, _TARGET_FIDELITY)
                    )
                    validation_attempts.append(
                        ValidationAttempt(
                            optimizer_query_index=observation.optimizer_query_index,
                            pulse=tuple(float(value) for value in best_pulse),
                            best_observation=observation,
                            device_attempt_index=int(validation.attempt_index),
                            validation_observation=validation,
                            failure_category=None,
                            certified=attempt_certified,
                        )
                    )
                    if attempt_certified:
                        certified = True
                        first_certified_query = observation.optimizer_query_index
        return 1.0 - observation.estimate, True

    evaluate(np.zeros(space.dimension, dtype=np.float64))

    optimizer: cma.CMAEvolutionStrategy | None = None
    stop_reason = "certified" if certified else "budget"
    while not certified and evaluations() < resolved_budget:
        if optimizer is None:
            optimizer = cma.CMAEvolutionStrategy(
                np.zeros(space.dimension, dtype=np.float64),
                _INITIAL_SCALE,
                _cma_options(space, resolved_seed),
            )
        if optimizer.stop():
            stop_reason = "optimizer_stopped"
            break
        candidates = optimizer.ask()
        scores: list[float] = []
        evaluated_candidates: list[NDArray[np.float64]] = []
        for raw_candidate in candidates:
            if evaluations() >= resolved_budget or certified:
                break
            candidate = np.clip(
                np.asarray(raw_candidate, dtype=np.float64),
                space.lower_bounds,
                space.upper_bounds,
            )
            score, _ = evaluate(candidate)
            evaluated_candidates.append(candidate)
            scores.append(score)
        if certified:
            stop_reason = "certified"
            break
        if len(evaluated_candidates) != len(candidates):
            stop_reason = "budget"
            break
        optimizer.tell(evaluated_candidates, scores)

    used_evaluations = evaluations()
    budget_exhausted = used_evaluations >= resolved_budget and not certified
    if certified:
        stop_reason = "certified"
    elif budget_exhausted:
        stop_reason = "budget"

    return ClosedLoopResult(
        space=space,
        best_pulse=tuple(float(value) for value in best_pulse),
        best_observation=best_observation,
        observations=tuple(observations),
        evaluations=used_evaluations,
        budget=resolved_budget,
        budget_exhausted=budget_exhausted,
        validation_attempts=tuple(validation_attempts),
        certified=certified,
        first_certified_query=first_certified_query,
        stop_reason=stop_reason,
    )
