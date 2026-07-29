from __future__ import annotations

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


@dataclass(frozen=True, slots=True, init=False)
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


@dataclass(frozen=True, slots=True)
class ClosedLoopResult:
    space: SearchSpace
    best_pulse: tuple[float, ...]
    best_observation: Observation | None
    observations: tuple[Observation, ...]
    evaluations: int
    budget: int
    budget_exhausted: bool
    provisional_crossings: tuple[int, ...]
    validation_result: Observation | None
    certified: bool
    first_certified_query: int | None
    stop_reason: str


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
    provisional_crossings: list[int] = []
    best_observation: Observation | None = None
    best_pulse = np.array(space.origin, dtype=np.float64, copy=True)
    validation_result: Observation | None = None
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
        nonlocal validation_result
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
                provisional_crossings.append(observation.optimizer_query_index)
                try:
                    validation = device.validate(
                        best_pulse,
                        shots=_VALIDATION_SHOTS,
                    )
                except DeviceQueryError:
                    validation = None
                if validation is not None:
                    validation_result = validation
                    if device.certifies(validation, _TARGET_FIDELITY):
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
        provisional_crossings=tuple(provisional_crossings),
        validation_result=validation_result,
        certified=certified,
        first_certified_query=first_certified_query,
        stop_reason=stop_reason,
    )
