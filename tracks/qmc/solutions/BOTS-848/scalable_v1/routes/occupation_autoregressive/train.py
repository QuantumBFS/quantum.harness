"""Deterministic reduced-state VMC for the occupation-autoregressive route."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Mapping

import numpy as np

from .model import AutoregressiveNQS
from .operators import (
    PreparedPairOperator,
    l2_neighbors,
    local_energy,
    local_from_log_neighbors,
)
from .tower import FixedMMetropolisSampler, LadderComponent, LadderTower


_SPIN_TWO_M_VALUES = (-2, -1, 0, 1, 2)
_FULL_TRAINING_SEEDS = (848, 1848, 2848)
_FULL_UPDATES = 2048
_FULL_BATCH_SIZE = 512
_FULL_CHECKPOINT_INTERVAL = 128
_FULL_TOWER_BURN_IN_STEPS = 1024
_FULL_LEARNING_RATE = 1.0e-3
_FULL_BETA1 = 0.9
_FULL_BETA2 = 0.999
_FULL_EPSILON = 1.0e-8
_FULL_GRADIENT_CLIP_NORM = 10.0


class FeatureStateError(RuntimeError):
    """Raised when a later Route A capability is requested before installation."""


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    integer = int(value)
    if integer <= 0:
        raise ValueError(f"{name} must be positive")
    return integer


def _finite_real(name: str, value: object, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _state_integer(state: object) -> int:
    if isinstance(state, bool) or not isinstance(state, Integral):
        raise TypeError("state must be an integer")
    return int(state)


def _finite_vector(name: str, values: object) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 1 or np.iscomplexobj(array):
        raise ValueError(f"{name} must be a one-dimensional real vector")
    try:
        vector = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must contain real numeric values") from error
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def _normalized_weights(weights: object | None, sample_count: int) -> np.ndarray:
    if sample_count <= 0:
        raise ValueError("weighted expectation requires at least one sample")
    if weights is None:
        return np.full(sample_count, 1.0 / sample_count, dtype=np.float64)
    raw = np.asarray(weights)
    if raw.ndim != 1 or raw.shape[0] != sample_count or np.iscomplexobj(raw):
        raise ValueError("weights must contain one real value per sample")
    try:
        values = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise TypeError("weights must contain real numeric values") from error
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("weights must be finite and non-negative")
    total = float(np.sum(values))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("weights must have a positive finite sum")
    return values / total


def _complex_sample_vector(name: str, values: object) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=np.complex128)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must contain numeric values") from error
    if array.ndim != 1 or array.shape[0] == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional vector")
    if not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _complex_score_matrix(name: str, scores: object) -> np.ndarray:
    try:
        array = np.asarray(scores, dtype=np.complex128)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must contain numeric values") from error
    if array.ndim != 2:
        raise ValueError(f"{name} must have shape (samples, parameters)")
    if not np.all(np.isfinite(array.real)) or not np.all(np.isfinite(array.imag)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _hermitian_expectation(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(weights * values).real)


def _score_covariance_from_arrays(
    scores: np.ndarray,
    local_values: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    conjugate_scores = scores.conj()
    centered_scores = conjugate_scores - np.sum(
        weights[:, None] * conjugate_scores,
        axis=0,
    )
    centered_values = local_values - np.sum(weights * local_values)
    covariance = np.sum(
        weights[:, None] * centered_scores * centered_values[:, None],
        axis=0,
    )
    gradient = np.asarray(2.0 * np.real(covariance), dtype=np.float64)
    if not np.all(np.isfinite(gradient)):
        raise FloatingPointError("non-finite VMC score covariance")
    return gradient


def score_covariance(
    scores: object,
    local_values: object,
    *,
    weights: object | None = None,
) -> np.ndarray:
    """Return ``2 Re Cov(conj(d log psi), local)`` for real parameters."""

    score_array = _complex_score_matrix("scores", scores)
    value_array = _complex_sample_vector("local_values", local_values)
    if value_array.ndim != 1 or value_array.shape[0] != score_array.shape[0]:
        raise ValueError("local_values must contain one value per score row")
    sample_count = score_array.shape[0]
    if sample_count == 0:
        raise ValueError("score covariance requires at least one sample")
    normalized_weights = _normalized_weights(weights, sample_count)
    return _score_covariance_from_arrays(
        score_array,
        value_array,
        normalized_weights,
    )


def physical_l2_variance(
    l2_local: object,
    l4_local: object,
    *,
    weights: object | None = None,
) -> float:
    """Return the Hermitian variance ``<L4> - <L2>**2``."""

    l2_array = _complex_sample_vector("l2_local", l2_local)
    l4_array = _complex_sample_vector("l4_local", l4_local)
    if l4_array.shape != l2_array.shape:
        raise ValueError("l2_local and l4_local must have the same shape")
    normalized_weights = _normalized_weights(weights, l2_array.shape[0])
    mean_l2 = _hermitian_expectation(l2_array, normalized_weights)
    mean_l4 = _hermitian_expectation(l4_array, normalized_weights)
    variance = mean_l4 - mean_l2**2
    if not math.isfinite(variance):
        raise FloatingPointError("non-finite physical L2 variance")
    return variance


def _compose_l2_rows(
    source_row: Mapping[int, complex],
    l2_row: Callable[[int], Mapping[int, complex]],
) -> dict[int, complex]:
    final_row: dict[int, complex] = {}
    for intermediate, first_coefficient in source_row.items():
        for final, second_coefficient in l2_row(intermediate).items():
            final_row[final] = (
                final_row.get(final, 0.0j)
                + first_coefficient * second_coefficient
            )
    return {
        target: coefficient
        for target, coefficient in final_row.items()
        if coefficient != 0.0
    }


def local_l4(
    state: int,
    two_q: int,
    target_m: float,
    logpsi: object,
) -> complex:
    """Evaluate L4 by sparse composition of two L2 rows."""

    source = _state_integer(state)
    row_cache: dict[int, dict[int, complex]] = {}

    def row(raw_state: int) -> dict[int, complex]:
        configuration = _state_integer(raw_state)
        cached = row_cache.get(configuration)
        if cached is None:
            cached = l2_neighbors(configuration, two_q, target_m)
            row_cache[configuration] = cached
        return cached

    final_row = _compose_l2_rows(row(source), row)
    return local_from_log_neighbors(source, final_row, logpsi)


def reduced_objective_and_gradient(
    *,
    ground_energy: object,
    ground_l2: object,
    ground_l4: object,
    ground_scores: object,
    excited_energy: object,
    excited_l2: object,
    excited_l4: object,
    excited_scores: object,
    ground_weights: object | None = None,
    excited_weights: object | None = None,
) -> tuple[float, np.ndarray, dict[str, float]]:
    """Evaluate the reduced A03 objective and its real-parameter gradient."""

    ground_energy_array = _complex_sample_vector("ground_energy", ground_energy)
    ground_l2_array = _complex_sample_vector("ground_l2", ground_l2)
    ground_l4_array = (
        None
        if ground_l4 is None
        else _complex_sample_vector("ground_l4", ground_l4)
    )
    excited_energy_array = _complex_sample_vector("excited_energy", excited_energy)
    excited_l2_array = _complex_sample_vector("excited_l2", excited_l2)
    excited_l4_array = _complex_sample_vector("excited_l4", excited_l4)
    ground_score_array = _complex_score_matrix("ground_scores", ground_scores)
    excited_score_array = _complex_score_matrix("excited_scores", excited_scores)
    if ground_energy_array.shape != ground_l2_array.shape or (
        ground_l4_array is not None
        and ground_l4_array.shape != ground_energy_array.shape
    ):
        raise ValueError("ground local estimators must have the same shape")
    if not (
        excited_energy_array.shape
        == excited_l2_array.shape
        == excited_l4_array.shape
    ):
        raise ValueError("excited local estimators must have the same shape")
    if ground_score_array.shape[0] != ground_energy_array.shape[0]:
        raise ValueError("ground_scores must contain one row per ground sample")
    if excited_score_array.shape[0] != excited_energy_array.shape[0]:
        raise ValueError("excited_scores must contain one row per excited sample")
    if ground_score_array.shape[1] != excited_score_array.shape[1]:
        raise ValueError(
            "ground_scores and excited_scores must have the same parameter count"
        )
    ground_normalized_weights = _normalized_weights(
        ground_weights,
        ground_energy_array.shape[0],
    )
    excited_normalized_weights = _normalized_weights(
        excited_weights,
        excited_energy_array.shape[0],
    )

    mean_energy_ground = _hermitian_expectation(
        ground_energy_array,
        ground_normalized_weights,
    )
    mean_energy_excited = _hermitian_expectation(
        excited_energy_array,
        excited_normalized_weights,
    )
    mean_l2_ground = _hermitian_expectation(
        ground_l2_array,
        ground_normalized_weights,
    )
    mean_l2_excited = _hermitian_expectation(
        excited_l2_array,
        excited_normalized_weights,
    )
    mean_l4_excited = _hermitian_expectation(
        excited_l4_array,
        excited_normalized_weights,
    )
    variance_l2_excited = physical_l2_variance(
        excited_l2_array,
        excited_l4_array,
        weights=excited_normalized_weights,
    )
    objective = (
        mean_energy_ground
        + mean_energy_excited
        + 0.25 * mean_l2_ground**2
        + 0.25 * (mean_l2_excited - 6.0) ** 2
        + 0.05 * variance_l2_excited
    )

    ground_l2_gradient = _score_covariance_from_arrays(
        ground_score_array,
        ground_l2_array,
        ground_normalized_weights,
    )
    excited_l2_gradient = _score_covariance_from_arrays(
        excited_score_array,
        excited_l2_array,
        excited_normalized_weights,
    )
    gradient = (
        _score_covariance_from_arrays(
            ground_score_array,
            ground_energy_array,
            ground_normalized_weights,
        )
        + _score_covariance_from_arrays(
            excited_score_array,
            excited_energy_array,
            excited_normalized_weights,
        )
        + 0.5 * mean_l2_ground * ground_l2_gradient
        + 0.5 * (mean_l2_excited - 6.0) * excited_l2_gradient
        + 0.05
        * (
            _score_covariance_from_arrays(
                excited_score_array,
                excited_l4_array,
                excited_normalized_weights,
            )
            - 2.0 * mean_l2_excited * excited_l2_gradient
        )
    )
    if not math.isfinite(objective) or not np.all(np.isfinite(gradient)):
        raise FloatingPointError("non-finite reduced VMC objective or gradient")
    metrics = {
        "energy_ground": mean_energy_ground,
        "energy_excited_m0": mean_energy_excited,
        "mean_l2_ground": mean_l2_ground,
        "mean_l2_excited_m0": mean_l2_excited,
        "mean_l4_excited_m0": mean_l4_excited,
        "variance_l2_excited_m0": variance_l2_excited,
    }
    return objective, np.asarray(gradient, dtype=np.float64), metrics


def _tower_mapping(name: str, values: object) -> Mapping[int, object]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if set(values) != set(_SPIN_TWO_M_VALUES):
        raise ValueError(f"{name} must contain exactly M=-2,-1,0,1,2")
    return values


def full_objective_and_gradient(
    *,
    ground_energy: object,
    ground_l2: object,
    ground_scores: object,
    excited_energy_by_m: object,
    excited_l2_by_m: object,
    excited_l4_by_m: object,
    excited_scores_by_m: object,
) -> tuple[float, np.ndarray, dict[str, float]]:
    """Evaluate the tower-aware objective with equal component weight."""

    ground_energy_array = _complex_sample_vector("ground_energy", ground_energy)
    ground_l2_array = _complex_sample_vector("ground_l2", ground_l2)
    ground_score_array = _complex_score_matrix("ground_scores", ground_scores)
    if ground_energy_array.shape != ground_l2_array.shape:
        raise ValueError("ground local estimators must have the same shape")
    if ground_score_array.shape[0] != ground_energy_array.shape[0]:
        raise ValueError("ground_scores must contain one row per ground sample")
    ground_weights = _normalized_weights(None, ground_energy_array.shape[0])

    energy_mapping = _tower_mapping(
        "excited_energy_by_m",
        excited_energy_by_m,
    )
    l2_mapping = _tower_mapping("excited_l2_by_m", excited_l2_by_m)
    l4_mapping = _tower_mapping("excited_l4_by_m", excited_l4_by_m)
    score_mapping = _tower_mapping(
        "excited_scores_by_m",
        excited_scores_by_m,
    )
    energy_arrays: dict[int, np.ndarray] = {}
    l2_arrays: dict[int, np.ndarray] = {}
    l4_arrays: dict[int, np.ndarray] = {}
    score_arrays: dict[int, np.ndarray] = {}
    component_weights: dict[int, np.ndarray] = {}
    for m in _SPIN_TWO_M_VALUES:
        energy_array = _complex_sample_vector(
            f"excited_energy_by_m[{m}]",
            energy_mapping[m],
        )
        l2_array = _complex_sample_vector(
            f"excited_l2_by_m[{m}]",
            l2_mapping[m],
        )
        l4_array = _complex_sample_vector(
            f"excited_l4_by_m[{m}]",
            l4_mapping[m],
        )
        score_array = _complex_score_matrix(
            f"excited_scores_by_m[{m}]",
            score_mapping[m],
        )
        if not (energy_array.shape == l2_array.shape == l4_array.shape):
            raise ValueError(
                f"excited M={m} local estimators must have the same shape"
            )
        if score_array.shape[0] != energy_array.shape[0]:
            raise ValueError(
                f"excited_scores_by_m[{m}] must contain one row per sample"
            )
        if score_array.shape[1] != ground_score_array.shape[1]:
            raise ValueError("all scores must have the same parameter count")
        energy_arrays[m] = energy_array
        l2_arrays[m] = l2_array
        l4_arrays[m] = l4_array
        score_arrays[m] = score_array
        component_weights[m] = _normalized_weights(None, energy_array.shape[0])

    mean_energy_ground = _hermitian_expectation(
        ground_energy_array,
        ground_weights,
    )
    mean_l2_ground = _hermitian_expectation(
        ground_l2_array,
        ground_weights,
    )
    energy_means = {
        m: _hermitian_expectation(energy_arrays[m], component_weights[m])
        for m in _SPIN_TWO_M_VALUES
    }
    l2_means = {
        m: _hermitian_expectation(l2_arrays[m], component_weights[m])
        for m in _SPIN_TWO_M_VALUES
    }
    l4_means = {
        m: _hermitian_expectation(l4_arrays[m], component_weights[m])
        for m in _SPIN_TWO_M_VALUES
    }
    mean_energy_excited = math.fsum(energy_means.values()) / 5.0
    mean_l2_excited = math.fsum(l2_means.values()) / 5.0
    mean_l4_excited = math.fsum(l4_means.values()) / 5.0
    variance_l2_excited = mean_l4_excited - mean_l2_excited**2
    objective = (
        mean_energy_ground
        + mean_energy_excited
        + 0.25 * mean_l2_ground**2
        + 0.25 * (mean_l2_excited - 6.0) ** 2
        + 0.05 * variance_l2_excited
    )

    def mean_component_covariance(
        local_values: Mapping[int, np.ndarray],
    ) -> np.ndarray:
        component_gradients = [
            _score_covariance_from_arrays(
                score_arrays[m],
                local_values[m],
                component_weights[m],
            )
            for m in _SPIN_TWO_M_VALUES
        ]
        return np.sum(component_gradients, axis=0) / 5.0

    ground_l2_gradient = _score_covariance_from_arrays(
        ground_score_array,
        ground_l2_array,
        ground_weights,
    )
    excited_l2_gradient = mean_component_covariance(l2_arrays)
    gradient = (
        _score_covariance_from_arrays(
            ground_score_array,
            ground_energy_array,
            ground_weights,
        )
        + mean_component_covariance(energy_arrays)
        + 0.5 * mean_l2_ground * ground_l2_gradient
        + 0.5 * (mean_l2_excited - 6.0) * excited_l2_gradient
        + 0.05
        * (
            mean_component_covariance(l4_arrays)
            - 2.0 * mean_l2_excited * excited_l2_gradient
        )
    )
    if not math.isfinite(objective) or not math.isfinite(
        variance_l2_excited
    ) or not np.all(np.isfinite(gradient)):
        raise FloatingPointError("non-finite full VMC objective or gradient")
    metrics = {
        "energy_ground": mean_energy_ground,
        "energy_excited": mean_energy_excited,
        "mean_l2_ground": mean_l2_ground,
        "mean_l2_excited": mean_l2_excited,
        "mean_l4_excited": mean_l4_excited,
        "variance_l2_excited": variance_l2_excited,
        **{
            f"energy_excited_m{m:+d}": energy_means[m]
            for m in _SPIN_TWO_M_VALUES
        },
    }
    return objective, np.asarray(gradient, dtype=np.float64), metrics


def clip_gradient(
    gradient: object,
    *,
    max_norm: float,
) -> tuple[np.ndarray, float, float]:
    """Globally clip a real gradient by its Euclidean norm."""

    vector = _finite_vector("gradient", gradient)
    limit = _finite_real("max_norm", max_norm, positive=True)
    before = float(np.linalg.norm(vector))
    if not math.isfinite(before):
        raise FloatingPointError("non-finite gradient norm")
    if before > limit:
        clipped = vector * (limit / before)
    else:
        clipped = vector.copy()
    after = float(np.linalg.norm(clipped))
    if not math.isfinite(after):
        raise FloatingPointError("non-finite clipped gradient norm")
    return clipped, before, after


@dataclass(frozen=True, slots=True)
class AdamState:
    update: int
    first_moment: np.ndarray
    second_moment: np.ndarray

    @classmethod
    def zeros(cls, parameter_count: int) -> "AdamState":
        size = _positive_integer("parameter_count", parameter_count)
        return cls(
            update=0,
            first_moment=np.zeros(size, dtype=np.float64),
            second_moment=np.zeros(size, dtype=np.float64),
        )


def adam_update(
    parameters: object,
    gradient: object,
    state: AdamState,
    *,
    learning_rate: float,
    beta1: float,
    beta2: float,
    epsilon: float,
    clip_norm: float,
) -> tuple[np.ndarray, AdamState, float, float]:
    """Apply one clipped Adam update with bias correction."""

    parameter_vector = _finite_vector("parameters", parameters)
    gradient_vector = _finite_vector("gradient", gradient)
    if parameter_vector.shape != gradient_vector.shape:
        raise ValueError("parameters and gradient must have the same shape")
    if not isinstance(state, AdamState):
        raise TypeError("state must be an AdamState")
    if (
        state.first_moment.shape != parameter_vector.shape
        or state.second_moment.shape != parameter_vector.shape
    ):
        raise ValueError("Adam state shape does not match parameters")
    if state.update < 0:
        raise ValueError("Adam state update must be non-negative")
    rate = _finite_real("learning_rate", learning_rate, positive=True)
    first_decay = _finite_real("beta1", beta1)
    second_decay = _finite_real("beta2", beta2)
    stabilizer = _finite_real("epsilon", epsilon, positive=True)
    if not 0.0 <= first_decay < 1.0 or not 0.0 <= second_decay < 1.0:
        raise ValueError("Adam beta values must be in [0, 1)")
    clipped, before, after = clip_gradient(gradient_vector, max_norm=clip_norm)
    next_update = state.update + 1
    first_moment = first_decay * state.first_moment + (1.0 - first_decay) * clipped
    second_moment = (
        second_decay * state.second_moment + (1.0 - second_decay) * clipped**2
    )
    first_unbiased = first_moment / (1.0 - first_decay**next_update)
    second_unbiased = second_moment / (1.0 - second_decay**next_update)
    updated = parameter_vector - rate * first_unbiased / (
        np.sqrt(second_unbiased) + stabilizer
    )
    if not np.all(np.isfinite(updated)):
        raise FloatingPointError("non-finite Adam parameter update")
    return (
        updated,
        AdamState(
            update=next_update,
            first_moment=np.asarray(first_moment, dtype=np.float64),
            second_moment=np.asarray(second_moment, dtype=np.float64),
        ),
        before,
        after,
    )


@dataclass(frozen=True, slots=True)
class ReducedTrainingConfig:
    training_seed: int
    updates: int
    batch_size_per_sector: int
    learning_rate: float
    beta1: float
    beta2: float
    epsilon: float
    gradient_clip_norm: float
    checkpoint_interval: int
    protocol_sha256: str
    comparison_sha: str

    def __post_init__(self) -> None:
        if isinstance(self.training_seed, bool) or not isinstance(
            self.training_seed, Integral
        ):
            raise TypeError("training_seed must be an integer")
        if int(self.training_seed) < 0:
            raise ValueError("training_seed must be non-negative")
        _positive_integer("updates", self.updates)
        _positive_integer("batch_size_per_sector", self.batch_size_per_sector)
        _positive_integer("checkpoint_interval", self.checkpoint_interval)
        _finite_real("learning_rate", self.learning_rate, positive=True)
        first_decay = _finite_real("beta1", self.beta1)
        second_decay = _finite_real("beta2", self.beta2)
        if not 0.0 <= first_decay < 1.0 or not 0.0 <= second_decay < 1.0:
            raise ValueError("Adam beta values must be in [0, 1)")
        _finite_real("epsilon", self.epsilon, positive=True)
        _finite_real("gradient_clip_norm", self.gradient_clip_norm, positive=True)
        for name, length, label in (
            ("protocol_sha256", 64, "SHA-256"),
            ("comparison_sha", 40, "Git SHA"),
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != length:
                raise ValueError(f"{name} must be a {length}-character {label}")
            try:
                bytes.fromhex(value)
            except ValueError as error:
                raise ValueError(
                    f"{name} must be a {length}-character {label}"
                ) from error


@dataclass(frozen=True, slots=True)
class FullTrainingConfig:
    """The non-overridable A05.2 production schedule."""

    training_seed: int
    protocol_sha256: str
    comparison_sha: str

    def __post_init__(self) -> None:
        if isinstance(self.training_seed, bool) or not isinstance(
            self.training_seed,
            Integral,
        ):
            raise TypeError("training_seed must be an integer")
        if int(self.training_seed) not in _FULL_TRAINING_SEEDS:
            raise ValueError("training_seed must be one of 848, 1848, or 2848")
        for name, length, label in (
            ("protocol_sha256", 64, "SHA-256"),
            ("comparison_sha", 40, "Git SHA"),
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != length:
                raise ValueError(f"{name} must be a {length}-character {label}")
            try:
                bytes.fromhex(value)
            except ValueError as error:
                raise ValueError(
                    f"{name} must be a {length}-character {label}"
                ) from error

    @property
    def updates(self) -> int:
        return _FULL_UPDATES

    @property
    def batch_size_per_sector(self) -> int:
        return _FULL_BATCH_SIZE

    @property
    def checkpoint_interval(self) -> int:
        return _FULL_CHECKPOINT_INTERVAL

    @property
    def tower_burn_in_steps(self) -> int:
        return _FULL_TOWER_BURN_IN_STEPS

    @property
    def learning_rate(self) -> float:
        return _FULL_LEARNING_RATE

    @property
    def beta1(self) -> float:
        return _FULL_BETA1

    @property
    def beta2(self) -> float:
        return _FULL_BETA2

    @property
    def epsilon(self) -> float:
        return _FULL_EPSILON

    @property
    def gradient_clip_norm(self) -> float:
        return _FULL_GRADIENT_CLIP_NORM


@dataclass(frozen=True, slots=True)
class TrainingArtifacts:
    checkpoint: Path
    optimizer_state: Path
    training_log: Path
    checkpoint_sha256: str
    optimizer_state_sha256: str
    training_log_sha256: str
    selected_update: int


def _deterministic_npz_bytes(arrays: Mapping[str, object]) -> bytes:
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(
        archive_buffer,
        mode="w",
        compression=zipfile.ZIP_STORED,
        strict_timestamps=True,
    ) as archive:
        for name in sorted(arrays):
            if not isinstance(name, str) or not name or "/" in name or "\\" in name:
                raise ValueError("NPZ array names must be simple non-empty strings")
            array = np.asarray(arrays[name])
            if array.dtype.hasobject:
                raise TypeError("checkpoint arrays must not use object dtype")
            array_buffer = io.BytesIO()
            np.lib.format.write_array(array_buffer, array, allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, array_buffer.getvalue())
    return archive_buffer.getvalue()


def atomic_save_npz(path: Path, **arrays: object) -> Path:
    """Write a deterministic NPZ and atomically replace its destination."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _deterministic_npz_bytes(arrays)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        handle = os.fdopen(descriptor, "wb")
        descriptor = -1
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output_path)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
    return output_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sector_estimators(
    model: AutoregressiveNQS,
    operator: PreparedPairOperator,
    states: np.ndarray,
    sector: str,
    *,
    include_l4: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray]:
    if not isinstance(include_l4, bool):
        raise TypeError("include_l4 must be a boolean")
    logpsi_cache: dict[int, complex] = {}
    l2_row_cache: dict[int, dict[int, complex]] = {}

    def logpsi(raw_state: int) -> complex:
        state = _state_integer(raw_state)
        value = logpsi_cache.get(state)
        if value is None:
            value = model.logpsi(state, sector)
            logpsi_cache[state] = value
        return value

    def l2_row(raw_state: int) -> dict[int, complex]:
        state = _state_integer(raw_state)
        row = l2_row_cache.get(state)
        if row is None:
            row = l2_neighbors(state, two_q=model.two_q, target_m=0.0)
            l2_row_cache[state] = row
        return row

    cache: dict[int, tuple[complex, complex, complex | None, np.ndarray]] = {}
    energies: list[complex] = []
    l2_values: list[complex] = []
    l4_values: list[complex] = []
    scores: list[np.ndarray] = []
    for raw_state in states:
        state = _state_integer(raw_state)
        evaluated = cache.get(state)
        if evaluated is None:
            source_row = l2_row(state)
            l4_value = (
                local_from_log_neighbors(
                    state,
                    _compose_l2_rows(source_row, l2_row),
                    logpsi,
                )
                if include_l4
                else None
            )
            evaluated = (
                local_energy(state, operator=operator, logpsi=logpsi),
                local_from_log_neighbors(
                    state,
                    source_row,
                    logpsi,
                ),
                l4_value,
                model.log_derivative(state, sector),
            )
            cache[state] = evaluated
        energy, l2_value, l4_value, score = evaluated
        energies.append(energy)
        l2_values.append(l2_value)
        if l4_value is not None:
            l4_values.append(l4_value)
        scores.append(score)
    energy_array = np.asarray(energies, dtype=np.complex128)
    l2_array = np.asarray(l2_values, dtype=np.complex128)
    l4_array = (
        np.asarray(l4_values, dtype=np.complex128) if include_l4 else None
    )
    score_array = np.asarray(scores, dtype=np.complex128)
    if not (
        np.all(np.isfinite(energy_array.real))
        and np.all(np.isfinite(energy_array.imag))
        and np.all(np.isfinite(l2_array.real))
        and np.all(np.isfinite(l2_array.imag))
        and (
            l4_array is None
            or np.all(np.isfinite(l4_array.real))
            and np.all(np.isfinite(l4_array.imag))
        )
        and np.all(np.isfinite(score_array.real))
        and np.all(np.isfinite(score_array.imag))
    ):
        raise FloatingPointError("non-finite reduced-state estimator")
    return energy_array, l2_array, l4_array, score_array


def _tower_component_estimators(
    component: LadderComponent,
    operator: PreparedPairOperator,
    states: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate one derived component with its own amplitude and score."""

    if not isinstance(component, LadderComponent):
        raise TypeError("component must be a LadderComponent")
    if not isinstance(operator, PreparedPairOperator):
        raise TypeError("operator must be a PreparedPairOperator")
    if operator.two_q != component.two_q:
        raise ValueError("operator and tower component flux do not match")
    logpsi_cache: dict[int, complex] = {}
    l2_row_cache: dict[int, dict[int, complex]] = {}

    def logpsi(raw_state: int) -> complex:
        state = _state_integer(raw_state)
        value = logpsi_cache.get(state)
        if value is None:
            value = component.logpsi(state)
            logpsi_cache[state] = value
        return value

    def l2_row(raw_state: int) -> dict[int, complex]:
        state = _state_integer(raw_state)
        row = l2_row_cache.get(state)
        if row is None:
            row = l2_neighbors(
                state,
                two_q=component.two_q,
                target_m=float(component.m),
            )
            l2_row_cache[state] = row
        return row

    cache: dict[int, tuple[complex, complex, complex, np.ndarray]] = {}
    energies: list[complex] = []
    l2_values: list[complex] = []
    l4_values: list[complex] = []
    scores: list[np.ndarray] = []
    for raw_state in states:
        state = _state_integer(raw_state)
        evaluated = cache.get(state)
        if evaluated is None:
            source_row = l2_row(state)
            evaluated = (
                local_energy(state, operator=operator, logpsi=logpsi),
                local_from_log_neighbors(state, source_row, logpsi),
                local_from_log_neighbors(
                    state,
                    _compose_l2_rows(source_row, l2_row),
                    logpsi,
                ),
                component.log_score(state),
            )
            cache[state] = evaluated
        energy, l2_value, l4_value, score = evaluated
        energies.append(energy)
        l2_values.append(l2_value)
        l4_values.append(l4_value)
        scores.append(score)
    arrays = (
        np.asarray(energies, dtype=np.complex128),
        np.asarray(l2_values, dtype=np.complex128),
        np.asarray(l4_values, dtype=np.complex128),
        np.asarray(scores, dtype=np.complex128),
    )
    if any(
        not np.all(np.isfinite(array.real))
        or not np.all(np.isfinite(array.imag))
        for array in arrays
    ):
        raise FloatingPointError("non-finite tower-component estimator")
    return arrays


def _checkpoint(
    *,
    model: AutoregressiveNQS,
    adam_state: AdamState,
    config: ReducedTrainingConfig | FullTrainingConfig,
    run_dir: Path,
    completed_update: int,
    final: bool,
) -> tuple[Path, Path]:
    selected_update = completed_update if final else -1
    checkpoint_path = atomic_save_npz(
        run_dir / "checkpoint.npz",
        parameters=model.flat_parameters(),
        selected_update=np.asarray(selected_update, dtype=np.int64),
        completed_update=np.asarray(completed_update, dtype=np.int64),
        training_seed=np.asarray(config.training_seed, dtype=np.int64),
        selection_rule=np.asarray("final_update"),
        protocol_sha256=np.asarray(config.protocol_sha256),
        comparison_sha=np.asarray(config.comparison_sha),
        n_electrons=np.asarray(model.n_electrons, dtype=np.int64),
        two_q=np.asarray(model.two_q, dtype=np.int64),
        target_m2=np.asarray(model.target_m2, dtype=np.int64),
        width=np.asarray(model.width, dtype=np.int64),
        layers=np.asarray(2, dtype=np.int64),
        batch_size_per_sector=np.asarray(
            config.batch_size_per_sector,
            dtype=np.int64,
        ),
    )
    optimizer_path = atomic_save_npz(
        run_dir / "optimizer-state.npz",
        update=np.asarray(adam_state.update, dtype=np.int64),
        first_moment=adam_state.first_moment,
        second_moment=adam_state.second_moment,
        training_seed=np.asarray(config.training_seed, dtype=np.int64),
        protocol_sha256=np.asarray(config.protocol_sha256),
    )
    return checkpoint_path, optimizer_path


def run_reduced_training(
    *,
    model: AutoregressiveNQS,
    operator: PreparedPairOperator,
    config: ReducedTrainingConfig,
    run_dir: Path,
) -> TrainingArtifacts:
    """Train only the ground and excited ``M=0`` sectors for A03 smoke."""

    if not isinstance(model, AutoregressiveNQS):
        raise TypeError("model must be an AutoregressiveNQS")
    if model.target_m2 != 0:
        raise ValueError("model.target_m2 must be 0 for reduced training")
    if not isinstance(operator, PreparedPairOperator):
        raise TypeError("operator must be a PreparedPairOperator")
    if operator.two_q != model.two_q:
        raise ValueError("operator and model flux do not match")
    if not isinstance(config, ReducedTrainingConfig):
        raise TypeError("config must be a ReducedTrainingConfig")
    output_dir = Path(run_dir)
    artifact_names = ("checkpoint.npz", "optimizer-state.npz", "training.jsonl")
    if output_dir.exists() and any((output_dir / name).exists() for name in artifact_names):
        raise FileExistsError("run directory already contains training artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    training_log = output_dir / "training.jsonl"
    adam_state = AdamState.zeros(model.parameter_count)
    checkpoint_path = output_dir / "checkpoint.npz"
    optimizer_path = output_dir / "optimizer-state.npz"

    with training_log.open("x", encoding="utf-8", newline="\n") as progress:
        for update in range(1, config.updates + 1):
            ground_seed = config.training_seed * 1_000_003 + 2 * update
            excited_seed = ground_seed + 1
            ground_states = model.sample(
                config.batch_size_per_sector,
                "ground",
                seed=ground_seed,
            )
            excited_states = model.sample(
                config.batch_size_per_sector,
                "excited",
                seed=excited_seed,
            )
            ground_energy, ground_l2, ground_l4, ground_scores = (
                _sector_estimators(
                    model,
                    operator,
                    ground_states,
                    "ground",
                    include_l4=False,
                )
            )
            excited_energy, excited_l2, excited_l4, excited_scores = (
                _sector_estimators(
                    model,
                    operator,
                    excited_states,
                    "excited",
                    include_l4=True,
                )
            )
            objective, gradient, metrics = reduced_objective_and_gradient(
                ground_energy=ground_energy,
                ground_l2=ground_l2,
                ground_l4=ground_l4,
                ground_scores=ground_scores,
                excited_energy=excited_energy,
                excited_l2=excited_l2,
                excited_l4=excited_l4,
                excited_scores=excited_scores,
            )
            parameters, adam_state, gradient_before, gradient_after = adam_update(
                model.flat_parameters(),
                gradient,
                adam_state,
                learning_rate=config.learning_rate,
                beta1=config.beta1,
                beta2=config.beta2,
                epsilon=config.epsilon,
                clip_norm=config.gradient_clip_norm,
            )
            model.set_flat_parameters(parameters)
            final_update = update == config.updates
            record = {
                "update": update,
                "selected": final_update,
                "selection_rule": "final_update",
                "training_seed": config.training_seed,
                "ground_m0_samples": config.batch_size_per_sector,
                "excited_m0_samples": config.batch_size_per_sector,
                "total_samples": 2 * config.batch_size_per_sector,
                "objective": objective,
                **metrics,
                "maximum_local_energy_imaginary_part": float(
                    max(
                        np.max(np.abs(ground_energy.imag), initial=0.0),
                        np.max(np.abs(excited_energy.imag), initial=0.0),
                    )
                ),
                "gradient_norm_before_clip": gradient_before,
                "gradient_norm_after_clip": gradient_after,
            }
            progress.write(
                json.dumps(
                    record,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            )
            progress.flush()
            os.fsync(progress.fileno())
            if update % config.checkpoint_interval == 0 or final_update:
                checkpoint_path, optimizer_path = _checkpoint(
                    model=model,
                    adam_state=adam_state,
                    config=config,
                    run_dir=output_dir,
                    completed_update=update,
                    final=final_update,
                )

    if not checkpoint_path.exists() or not optimizer_path.exists():
        raise RuntimeError("final checkpoint artifacts were not written")
    return TrainingArtifacts(
        checkpoint=checkpoint_path,
        optimizer_state=optimizer_path,
        training_log=training_log,
        checkpoint_sha256=_sha256_file(checkpoint_path),
        optimizer_state_sha256=_sha256_file(optimizer_path),
        training_log_sha256=_sha256_file(training_log),
        selected_update=config.updates,
    )


def run_full_training(
    *,
    model: AutoregressiveNQS,
    operator: PreparedPairOperator,
    config: FullTrainingConfig,
    run_dir: Path,
    progress_callback: Callable[[Mapping[str, object]], None] | None = None,
) -> TrainingArtifacts:
    """Run the frozen ground plus five-component tower training schedule."""

    if not isinstance(model, AutoregressiveNQS):
        raise TypeError("model must be an AutoregressiveNQS")
    if model.target_m2 != 0:
        raise ValueError("model.target_m2 must be 0 for full training")
    if not isinstance(operator, PreparedPairOperator):
        raise TypeError("operator must be a PreparedPairOperator")
    if operator.two_q != model.two_q:
        raise ValueError("operator and model flux do not match")
    if not isinstance(config, FullTrainingConfig):
        raise TypeError("config must be a FullTrainingConfig")
    if progress_callback is not None and not callable(progress_callback):
        raise TypeError("progress_callback must be callable or None")
    output_dir = Path(run_dir)
    artifact_names = (
        "checkpoint.npz",
        "optimizer-state.npz",
        "training.jsonl",
        "training-manifest.json",
    )
    if output_dir.exists() and any(
        (output_dir / name).exists() for name in artifact_names
    ):
        raise FileExistsError("run directory already contains training artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    training_log = output_dir / "training.jsonl"
    tower = LadderTower.from_m0(
        logpsi=lambda state: model.logpsi(state, "excited"),
        log_score=lambda state: model.log_derivative(state, "excited"),
        n_electrons=model.n_electrons,
        two_q=model.two_q,
        l=2,
        cache_token=lambda: model.parameter_revision,
    )
    samplers = {
        m: FixedMMetropolisSampler(tower, target_m=m)
        for m in _SPIN_TWO_M_VALUES
    }
    adam_state = AdamState.zeros(model.parameter_count)
    checkpoint_path = output_dir / "checkpoint.npz"
    optimizer_path = output_dir / "optimizer-state.npz"
    descriptor = os.open(
        training_log,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        progress = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with progress:
            for update in range(1, config.updates + 1):
                tower.clear_evaluation_cache()
                seed_base = config.training_seed * 1_000_003 + 6 * (update - 1)
                ground_seed = seed_base
                tower_seeds = {
                    m: seed_base + index
                    for index, m in enumerate(_SPIN_TWO_M_VALUES, start=1)
                }
                ground_states = model.sample(
                    config.batch_size_per_sector,
                    "ground",
                    seed=ground_seed,
                )
                ground_energy, ground_l2, _ground_l4, ground_scores = (
                    _sector_estimators(
                        model,
                        operator,
                        ground_states,
                        "ground",
                        include_l4=False,
                    )
                )
                energy_by_m: dict[int, np.ndarray] = {}
                l2_by_m: dict[int, np.ndarray] = {}
                l4_by_m: dict[int, np.ndarray] = {}
                scores_by_m: dict[int, np.ndarray] = {}
                sample_batches = {}
                for m in _SPIN_TWO_M_VALUES:
                    batch = samplers[m].sample(
                        n_samples=config.batch_size_per_sector,
                        burn_in_steps=config.tower_burn_in_steps,
                        seed=tower_seeds[m],
                    )
                    sample_batches[m] = batch
                    (
                        energy_by_m[m],
                        l2_by_m[m],
                        l4_by_m[m],
                        scores_by_m[m],
                    ) = _tower_component_estimators(
                        tower[m],
                        operator,
                        batch.configs,
                    )
                objective, gradient, metrics = full_objective_and_gradient(
                    ground_energy=ground_energy,
                    ground_l2=ground_l2,
                    ground_scores=ground_scores,
                    excited_energy_by_m=energy_by_m,
                    excited_l2_by_m=l2_by_m,
                    excited_l4_by_m=l4_by_m,
                    excited_scores_by_m=scores_by_m,
                )
                parameters, adam_state, gradient_before, gradient_after = (
                    adam_update(
                        model.flat_parameters(),
                        gradient,
                        adam_state,
                        learning_rate=config.learning_rate,
                        beta1=config.beta1,
                        beta2=config.beta2,
                        epsilon=config.epsilon,
                        clip_norm=config.gradient_clip_norm,
                    )
                )
                model.set_flat_parameters(parameters)
                final_update = update == config.updates
                record = {
                    "update": update,
                    "selected": final_update,
                    "selection_rule": "final_update",
                    "training_seed": config.training_seed,
                    "ground_samples": config.batch_size_per_sector,
                    "excited_samples_by_m": {
                        str(m): sample_batches[m].n_samples
                        for m in _SPIN_TWO_M_VALUES
                    },
                    "total_samples": 6 * config.batch_size_per_sector,
                    "ground_sample_seed": ground_seed,
                    "excited_sample_seeds_by_m": {
                        str(m): tower_seeds[m] for m in _SPIN_TWO_M_VALUES
                    },
                    "excited_sampling_by_m": {
                        str(m): {
                            "burn_in_steps": sample_batches[m].burn_in_steps,
                            "burn_in_proposals": sample_batches[m].burn_in_proposals,
                            "burn_in_accepted_moves": (
                                sample_batches[m].burn_in_accepted_moves
                            ),
                            "sampling_proposals": sample_batches[m].sampling_proposals,
                            "sampling_accepted_moves": (
                                sample_batches[m].sampling_accepted_moves
                            ),
                        }
                        for m in _SPIN_TWO_M_VALUES
                    },
                    "objective": objective,
                    **metrics,
                    "maximum_local_energy_imaginary_part": float(
                        max(
                            np.max(np.abs(ground_energy.imag), initial=0.0),
                            *(
                                np.max(np.abs(energy_by_m[m].imag), initial=0.0)
                                for m in _SPIN_TWO_M_VALUES
                            ),
                        )
                    ),
                    "gradient_norm_before_clip": gradient_before,
                    "gradient_norm_after_clip": gradient_after,
                }
                progress.write(
                    json.dumps(
                        record,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                )
                progress.flush()
                os.fsync(progress.fileno())
                if update % config.checkpoint_interval == 0 or final_update:
                    checkpoint_path, optimizer_path = _checkpoint(
                        model=model,
                        adam_state=adam_state,
                        config=config,
                        run_dir=output_dir,
                        completed_update=update,
                        final=final_update,
                    )
                    if progress_callback is not None:
                        progress_callback(dict(record))
    finally:
        if descriptor != -1:
            os.close(descriptor)

    if not checkpoint_path.exists() or not optimizer_path.exists():
        raise RuntimeError("final checkpoint artifacts were not written")
    return TrainingArtifacts(
        checkpoint=checkpoint_path,
        optimizer_state=optimizer_path,
        training_log=training_log,
        checkpoint_sha256=_sha256_file(checkpoint_path),
        optimizer_state_sha256=_sha256_file(optimizer_path),
        training_log_sha256=_sha256_file(training_log),
        selected_update=config.updates,
    )
