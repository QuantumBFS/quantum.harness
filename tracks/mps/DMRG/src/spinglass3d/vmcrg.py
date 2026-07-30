"""Variational overlap-field VMCRG training and frozen evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import copy
import hashlib
import math
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, runtime_checkable

import numpy as np

from .bias import BiasRoute, OverlapBias, ResidualProjection
from .checkpoint import TrainingCheckpoint
from .linear_bias import LinearFeatureBasis
from .templates import TemplateEncoder
from .tensor_train import LocalTensorTrain, SymmetricLocalTT, TTGradient


def _ordered_j_ids(
    values: object,
    *,
    expected_count: int | None = None,
    label: str = "J IDs",
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{label} must be a sequence, not str or bytes")
    try:
        identifiers = tuple(values)
    except TypeError as error:
        raise TypeError(f"{label} must be a sequence of strings") from error
    if (
        (not identifiers and not allow_empty)
        or (expected_count is not None and len(identifiers) != expected_count)
        or any(not isinstance(value, str) or not value for value in identifiers)
        or len(identifiers) != len(set(identifiers))
    ):
        raise ValueError(f"{label} must contain unique nonempty strings")
    return identifiers


def _positive_schema_count(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"backend {name} must be an integer")
    result = int(value)
    if result < 1:
        raise ValueError(f"backend {name} must be positive")
    return result


def _owned_mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a Mapping")
    return copy.deepcopy(dict(value))


def _state_equal(left: object, right: object) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _state_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return bool(np.array_equal(np.asarray(left), np.asarray(right)))
    if (
        isinstance(left, Sequence)
        and not isinstance(left, (str, bytes))
        and isinstance(right, Sequence)
        and not isinstance(right, (str, bytes))
    ):
        return len(left) == len(right) and all(
            _state_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def _normalized_j_split(
    j_split: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(j_split, Mapping) or set(j_split) != {
        "train",
        "validation",
        "test",
    }:
        raise ValueError("checkpoint split must contain train/validation/test")
    split = {
        name: _ordered_j_ids(
            j_split[name],
            label=f"checkpoint {name} J IDs",
            allow_empty=True,
        )
        for name in ("train", "validation", "test")
    }
    flat = [value for values in split.values() for value in values]
    if len(flat) != len(set(flat)):
        raise ValueError("checkpoint J splits must be disjoint")
    return split


@dataclass(frozen=True)
class VMCRGGradient:
    target: np.ndarray
    biased: np.ndarray
    difference: np.ndarray

    def __post_init__(self) -> None:
        arrays = tuple(
            np.asarray(value, dtype=np.float64)
            for value in (self.target, self.biased, self.difference)
        )
        if arrays[0].shape != arrays[1].shape or arrays[1].shape != arrays[2].shape:
            raise ValueError("VMCRG gradient components must have matching shapes")
        if not all(np.all(np.isfinite(value)) for value in arrays):
            raise ValueError("VMCRG gradient components must be finite")
        if not np.array_equal(arrays[2], arrays[0] - arrays[1]):
            raise ValueError("VMCRG difference must equal target minus biased")
        for name, value in zip(
            ("target", "biased", "difference"), arrays, strict=True
        ):
            owned = value.copy()
            owned.setflags(write=False)
            object.__setattr__(self, name, owned)


@dataclass(frozen=True)
class VMCRGBatch:
    """Immutable training draws with an explicit quenched-disorder axis."""

    target_tokens: np.ndarray
    biased_tokens: np.ndarray
    j_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        target = np.asarray(self.target_tokens)
        biased = np.asarray(self.biased_tokens)
        if target.ndim != 3 or biased.shape != target.shape:
            raise ValueError(
                "VMCRG batches must have matching shape (J,draw,tokens)"
            )
        if any(size < 1 for size in target.shape):
            raise ValueError("VMCRG batch dimensions must be positive")
        if not np.all((target == -1) | (target == 1)) or not np.all(
            (biased == -1) | (biased == 1)
        ):
            raise ValueError("VMCRG token batches must be binary")
        identifiers = _ordered_j_ids(
            self.j_ids,
            expected_count=target.shape[0],
            label="VMCRG batch J IDs",
        )
        for name, value in (
            ("target_tokens", target),
            ("biased_tokens", biased),
        ):
            owned = value.astype(np.int8, copy=True)
            owned.setflags(write=False)
            object.__setattr__(self, name, owned)
        object.__setattr__(self, "j_ids", identifiers)


def vmcrg_gradient(target: np.ndarray, biased: np.ndarray) -> np.ndarray:
    left = np.asarray(target, dtype=np.float64)
    right = np.asarray(biased, dtype=np.float64)
    if (
        left.shape != right.shape
        or not np.all(np.isfinite(left))
        or not np.all(np.isfinite(right))
    ):
        raise ValueError("target and biased feature means must be finite and compatible")
    return left - right


def estimate_gradient(
    model: object | None,
    target_batch: np.ndarray,
    biased_batch: np.ndarray,
) -> VMCRGGradient:
    target = np.asarray(target_batch, dtype=np.float64)
    biased = np.asarray(biased_batch, dtype=np.float64)
    if target.ndim == 2:
        target = target[:, None, :]
    if biased.ndim == 2:
        biased = biased[:, None, :]
    if (
        target.ndim != 3
        or biased.shape != target.shape
        or any(size < 1 for size in target.shape)
        or not np.all(np.isfinite(target))
        or not np.all(np.isfinite(biased))
    ):
        raise ValueError(
            "gradient batches must be finite matching (J,draw,features) arrays"
        )
    if model is not None:
        if not hasattr(model, "feature_values"):
            raise TypeError("gradient model must expose feature_values")
        n_j, n_draw = target.shape[:2]

        def feature_values(tokens: np.ndarray) -> np.ndarray:
            flat = tokens.reshape(-1, tokens.shape[-1])
            values = np.asarray(model.feature_values(flat), dtype=np.float64)
            if (
                values.ndim != 2
                or values.shape[0] != flat.shape[0]
                or not np.all(np.isfinite(values))
            ):
                raise ValueError("gradient model returned incompatible features")
            return values.reshape(n_j, n_draw, values.shape[-1])

        target = feature_values(target)
        biased = feature_values(biased)
    target_mean = np.mean(
        np.mean(target, axis=1, dtype=np.float64),
        axis=0,
        dtype=np.float64,
    )
    biased_mean = np.mean(
        np.mean(biased, axis=1, dtype=np.float64),
        axis=0,
        dtype=np.float64,
    )
    return VMCRGGradient(
        target=target_mean,
        biased=biased_mean,
        difference=vmcrg_gradient(target_mean, biased_mean),
    )


@dataclass(frozen=True)
class ExactTwoStateVMCRG:
    effective_hamiltonian_centered: np.ndarray
    optimal_bias_centered: np.ndarray
    recovered_hamiltonian: np.ndarray


def exact_two_state_vmcrg(
    hamiltonian: np.ndarray | None = None,
) -> ExactTwoStateVMCRG:
    values = np.asarray(
        (-0.7, 0.2) if hamiltonian is None else hamiltonian,
        dtype=np.float64,
    )
    if values.shape != (2,) or not np.all(np.isfinite(values)):
        raise ValueError("two-state Hamiltonian must contain two finite values")
    centered = values - float(np.mean(values))
    bias = -centered
    return ExactTwoStateVMCRG(
        effective_hamiltonian_centered=centered,
        optimal_bias_centered=bias,
        recovered_hamiltonian=-bias,
    )


@dataclass(frozen=True)
class VMCRGProtocol:
    c1_steps: int
    c2_steps: int
    c3_steps: int
    linear_learning_rate: float
    tt_learning_rate: float
    gradient_clip: float
    canonicalize_every: int
    momentum: float = 0.9

    def __post_init__(self) -> None:
        if (
            min(self.c1_steps, self.c2_steps, self.c3_steps) < 0
            or self.c1_steps + self.c2_steps < 1
        ):
            raise ValueError("VMCRG stage lengths are invalid")
        if min(
            self.linear_learning_rate,
            self.tt_learning_rate,
            self.gradient_clip,
        ) <= 0.0:
            raise ValueError("VMCRG learning rates and clip must be positive")
        if not all(
            math.isfinite(value)
            for value in (
                self.linear_learning_rate,
                self.tt_learning_rate,
                self.gradient_clip,
                self.momentum,
            )
        ):
            raise ValueError("VMCRG numerical controls must be finite")
        if self.canonicalize_every < 1:
            raise ValueError("canonicalization interval must be positive")
        if not 0.0 <= self.momentum < 1.0:
            raise ValueError("momentum must lie in [0,1)")


@dataclass(frozen=True)
class CheckpointContext:
    beta: float
    hashes: Mapping[str, str]
    j_split: Mapping[str, Sequence[str]]
    rg_level: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.beta) or self.beta <= 0.0:
            raise ValueError("checkpoint beta must be positive and finite")
        if self.rg_level not in (1, 2):
            raise ValueError("checkpoint RG level must be one or two")
        hashes = {str(key): str(value) for key, value in self.hashes.items()}
        if not hashes or any(not key or not value for key, value in hashes.items()):
            raise ValueError("checkpoint hashes must be nonempty")
        split = _normalized_j_split(self.j_split)
        object.__setattr__(self, "hashes", MappingProxyType(hashes))
        object.__setattr__(self, "j_split", MappingProxyType(split))


@runtime_checkable
class VMCRGSamplingBackend(Protocol):
    """Stable whole-J schema and complete, detached sampler state."""

    @property
    def j_ids(self) -> tuple[str, ...]: ...

    @property
    def draw_count(self) -> int: ...

    @property
    def token_count(self) -> int: ...

    def next_batch(self) -> VMCRGBatch: ...

    # This state owns every training RNG and includes an identical rng_state.
    def checkpoint_state(self) -> Mapping[str, object]: ...

    def restore_state(self, state: Mapping[str, object]) -> None: ...

    def training_rng_state(self) -> Mapping[str, object]: ...


class InMemoryVMCRGBackend:
    """Deterministic whole-J batches used by the correctness path."""

    def __init__(
        self,
        *,
        target_batches: Sequence[np.ndarray],
        biased_batches: Sequence[np.ndarray],
        j_ids: Sequence[str],
        seed: int,
    ) -> None:
        if len(target_batches) != len(biased_batches) or not target_batches:
            raise ValueError("target and biased batch schedules must match")
        self._j_ids = _ordered_j_ids(j_ids, label="backend J IDs")
        batches: list[VMCRGBatch] = []
        for target, biased in zip(target_batches, biased_batches, strict=True):
            target_array = np.asarray(target)
            biased_array = np.asarray(biased)
            if target_array.ndim == 2:
                target_array = target_array[:, None, :]
            if biased_array.ndim == 2:
                biased_array = biased_array[:, None, :]
            batches.append(
                VMCRGBatch(
                    target_tokens=target_array,
                    biased_tokens=biased_array,
                    j_ids=self._j_ids,
                )
            )
        shape = batches[0].target_tokens.shape
        if any(batch.target_tokens.shape != shape for batch in batches):
            raise ValueError("scheduled VMCRG batch shapes must match")
        self._draw_count = shape[1]
        self._token_count = shape[2]
        self._batches = tuple(batches)
        self.target_batches = tuple(batch.target_tokens for batch in batches)
        self.biased_batches = tuple(batch.biased_tokens for batch in batches)
        self.rng = np.random.default_rng(seed)
        self.index = 0
        self.decision_count = 0

    @property
    def j_ids(self) -> tuple[str, ...]:
        return self._j_ids

    @property
    def draw_count(self) -> int:
        return self._draw_count

    @property
    def token_count(self) -> int:
        return self._token_count

    def next_batch(self) -> VMCRGBatch:
        index = self.index % len(self._batches)
        self.index += 1
        return self._batches[index]

    def draw_decisions(self, count: int) -> tuple[np.ndarray, np.ndarray]:
        if count < 0:
            raise ValueError("decision count must be nonnegative")
        uniforms = self.rng.random(count)
        decisions = uniforms < 0.5
        self.decision_count += count
        return uniforms, decisions

    def checkpoint_state(self) -> dict[str, object]:
        """Return a detached, complete state including every training RNG."""

        return {
            "j_ids": self.j_ids,
            "draw_count": self.draw_count,
            "token_count": self.token_count,
            "batch_index": self.index,
            "decision_count": self.decision_count,
            "rng_state": copy.deepcopy(self.rng.bit_generator.state),
        }

    def training_rng_state(self) -> dict[str, object]:
        return copy.deepcopy(self.rng.bit_generator.state)

    def restore_state(self, state: Mapping[str, object]) -> None:
        if not isinstance(state, Mapping):
            raise TypeError("backend checkpoint state must be a Mapping")
        restored = copy.deepcopy(dict(state))
        required = {
            "j_ids",
            "draw_count",
            "token_count",
            "batch_index",
            "decision_count",
            "rng_state",
        }
        if set(restored) != required:
            raise ValueError("backend checkpoint state is incomplete")
        identifiers = _ordered_j_ids(
            restored["j_ids"],
            expected_count=len(self.j_ids),
            label="backend checkpoint ordered J IDs",
        )
        if identifiers != self.j_ids:
            raise ValueError("backend checkpoint ordered J IDs do not match")
        draw_count = _positive_schema_count(
            restored["draw_count"], name="draw_count"
        )
        token_count = _positive_schema_count(
            restored["token_count"], name="token_count"
        )
        if (draw_count, token_count) != (self.draw_count, self.token_count):
            raise ValueError("backend checkpoint batch schema does not match")
        index_value = restored["batch_index"]
        decision_value = restored["decision_count"]
        if (
            isinstance(index_value, bool)
            or not isinstance(index_value, (int, np.integer))
            or isinstance(decision_value, bool)
            or not isinstance(decision_value, (int, np.integer))
        ):
            raise TypeError("backend checkpoint counters must be integers")
        index = int(index_value)
        decision_count = int(decision_value)
        if index < 0 or decision_count < 0:
            raise ValueError("backend checkpoint counters are invalid")
        rng_state = _owned_mapping(
            restored["rng_state"], label="backend checkpoint rng_state"
        )
        rng = np.random.default_rng()
        rng.bit_generator.state = rng_state
        self.index = index
        self.decision_count = decision_count
        self.rng = rng


@dataclass(frozen=True)
class TrainingStep:
    step: int
    stage: str
    route: str
    objective_estimate: float
    unclipped_gradient_norm: float
    clipped_gradient_norm: float
    parameter_norm: float
    core_norms: tuple[float, ...]
    output_min: float
    output_max: float
    finite: bool
    optimizer_moments_reset: bool


@dataclass(frozen=True)
class FrozenRouteBatch:
    target: np.ndarray
    biased: np.ndarray
    j_ids: tuple[str, ...]
    split: str
    budget_kind: str
    proposal_count: int
    wall_seconds: float
    acceptance: float
    iat: float
    ess: float

    def __post_init__(self) -> None:
        target = np.asarray(self.target, dtype=np.int8)
        biased = np.asarray(self.biased, dtype=np.int8)
        if target.ndim != 3 or biased.shape != target.shape:
            raise ValueError("frozen batches must have shape (J,measurements,tokens)")
        if not np.all((target == -1) | (target == 1)) or not np.all(
            (biased == -1) | (biased == 1)
        ):
            raise ValueError("frozen token batches must be binary")
        j_ids = tuple(self.j_ids)
        if len(j_ids) != target.shape[0] or len(j_ids) != len(set(j_ids)):
            raise ValueError("frozen batches require one unique J ID per row")
        if self.split not in {"validation", "test"}:
            raise ValueError("frozen evaluation must use validation or test data")
        if self.budget_kind not in {"proposal", "wall"}:
            raise ValueError("budget kind must be proposal or wall")
        scalars = (self.wall_seconds, self.acceptance, self.iat, self.ess)
        if self.proposal_count < 1 or not all(math.isfinite(value) for value in scalars):
            raise ValueError("frozen budget and diagnostics must be finite")
        if self.wall_seconds <= 0.0 or self.iat <= 0.0 or self.ess <= 0.0:
            raise ValueError("frozen time, IAT, and ESS must be positive")
        if not 0.0 <= self.acceptance <= 1.0:
            raise ValueError("frozen acceptance must lie in [0,1]")
        for name, value in (("target", target), ("biased", biased)):
            owned = value.copy()
            owned.setflags(write=False)
            object.__setattr__(self, name, owned)
        object.__setattr__(self, "j_ids", j_ids)


@dataclass(frozen=True)
class FrozenEvaluation:
    objective_estimate: float
    total_variation: float
    jensen_shannon: float
    standardized_moments: tuple[float, ...]
    mmd: float
    acceptance: float
    iat: float
    ess: float
    projection: ResidualProjection | None
    route_name: str
    split: str
    budget_kind: str
    proposal_count: int
    wall_seconds: float
    j_ids: tuple[str, ...]
    primary_metric_by_j: np.ndarray
    other_metric_by_j: np.ndarray
    initialization_hash: str | None
    finite: bool
    mmd_kernel: str = "linear"

    def __post_init__(self) -> None:
        primary = np.asarray(self.primary_metric_by_j, dtype=np.float64)
        other = np.asarray(self.other_metric_by_j, dtype=np.float64)
        if (
            primary.shape != (len(self.j_ids),)
            or other.shape != primary.shape
            or len(self.j_ids) != len(set(self.j_ids))
        ):
            raise ValueError("frozen per-J metrics have the wrong shape")
        if self.route_name not in {"linear", "C", "B", "A"}:
            raise ValueError("frozen route name is invalid")
        scalars = (
            self.objective_estimate,
            self.total_variation,
            self.jensen_shannon,
            self.mmd,
            self.acceptance,
            self.iat,
            self.ess,
            self.wall_seconds,
        )
        if not all(math.isfinite(value) for value in scalars) or not all(
            np.all(np.isfinite(value)) for value in (primary, other)
        ):
            raise ValueError("frozen evaluation must be finite")
        if self.mmd_kernel != "linear":
            raise ValueError("only explicitly labeled linear-kernel MMD is supported")
        for name, value in (("primary_metric_by_j", primary), ("other_metric_by_j", other)):
            owned = value.copy()
            owned.setflags(write=False)
            object.__setattr__(self, name, owned)


def _small_marginal(tokens: np.ndarray) -> np.ndarray:
    selected = np.asarray(tokens)
    width = selected.shape[1]
    codes = np.sum((selected == 1) * (1 << np.arange(width)), axis=1)
    counts = np.bincount(codes, minlength=1 << width).astype(np.float64)
    return counts / counts.sum()


def _evaluate_frozen(
    batch: FrozenRouteBatch,
    *,
    route_name: str,
    encoder: TemplateEncoder,
    local_value,
    projection: ResidualProjection | None,
    initialization_hash: str | None,
) -> FrozenEvaluation:
    if batch.target.shape[-1] != encoder.token_count:
        raise ValueError("frozen token count does not match model encoder")
    target = batch.target.reshape(-1, batch.target.shape[-1])
    biased = batch.biased.reshape(-1, batch.biased.shape[-1])
    target_outputs = np.asarray([local_value(row) for row in target], dtype=np.float64)
    biased_outputs = np.asarray([local_value(row) for row in biased], dtype=np.float64)
    measurements = batch.target.shape[1]
    objective_by_j = (
        target_outputs.reshape(len(batch.j_ids), measurements).mean(axis=1)
        - biased_outputs.reshape(len(batch.j_ids), measurements).mean(axis=1)
    )
    q_positions = np.asarray(encoder.q_token_indices, dtype=np.int64)
    marginal_positions = q_positions[: min(4, q_positions.size)]
    target_q = target[:, q_positions].astype(np.float64)
    biased_q = biased[:, q_positions].astype(np.float64)
    target_probability = _small_marginal(target[:, marginal_positions])
    biased_probability = _small_marginal(biased[:, marginal_positions])
    total_variation = 0.5 * float(np.sum(np.abs(target_probability - biased_probability)))
    midpoint = 0.5 * (target_probability + biased_probability)
    target_mask = target_probability > 0.0
    biased_mask = biased_probability > 0.0
    jensen_shannon = 0.5 * float(
        np.sum(
            target_probability[target_mask]
            * np.log(target_probability[target_mask] / midpoint[target_mask])
        )
        + np.sum(
            biased_probability[biased_mask]
            * np.log(biased_probability[biased_mask] / midpoint[biased_mask])
        )
    )
    pooled = np.std(np.concatenate((target_q, biased_q), axis=0), axis=0, ddof=1)
    mean_difference = target_q.mean(axis=0) - biased_q.mean(axis=0)
    standardized = mean_difference / np.where(pooled > 0.0, pooled, 1.0)
    target_by_j = batch.target[..., q_positions].mean(axis=1, dtype=np.float64)
    biased_by_j = batch.biased[..., q_positions].mean(axis=1, dtype=np.float64)
    difference_by_j = target_by_j - biased_by_j
    primary = np.mean(difference_by_j**2, axis=1, dtype=np.float64)
    other = np.mean(np.abs(difference_by_j), axis=1, dtype=np.float64)
    return FrozenEvaluation(
        objective_estimate=float(np.mean(objective_by_j, dtype=np.float64)),
        total_variation=total_variation,
        jensen_shannon=jensen_shannon,
        standardized_moments=tuple(float(value) for value in standardized),
        mmd=float(np.mean(primary, dtype=np.float64)),
        acceptance=batch.acceptance,
        iat=batch.iat,
        ess=batch.ess,
        projection=projection,
        route_name=route_name,
        split=batch.split,
        budget_kind=batch.budget_kind,
        proposal_count=batch.proposal_count,
        wall_seconds=batch.wall_seconds,
        j_ids=batch.j_ids,
        primary_metric_by_j=primary,
        other_metric_by_j=other,
        initialization_hash=initialization_hash,
        finite=True,
    )


def evaluate_frozen_linear(
    basis: LinearFeatureBasis,
    coefficients: np.ndarray,
    encoder: TemplateEncoder,
    batch: FrozenRouteBatch,
) -> FrozenEvaluation:
    values = np.asarray(coefficients, dtype=np.float64)
    if not isinstance(basis, LinearFeatureBasis) or values.shape != (len(basis.features),):
        raise ValueError("linear frozen model has incompatible coefficients")
    if not np.all(np.isfinite(values)):
        raise ValueError("linear frozen coefficients must be finite")

    def local_value(tokens: np.ndarray) -> float:
        return float(values @ basis.local_features(tokens, encoder))

    return _evaluate_frozen(
        batch,
        route_name="linear",
        encoder=encoder,
        local_value=local_value,
        projection=None,
        initialization_hash=None,
    )


def evaluate_frozen_bias(
    bias: OverlapBias,
    batch: FrozenRouteBatch,
    *,
    initialization_hash: str,
) -> FrozenEvaluation:
    if not isinstance(bias, OverlapBias) or not initialization_hash:
        raise ValueError("frozen bias and initialization hash are required")
    projection = (
        bias.residual_projection(batch.target.reshape(-1, batch.target.shape[-1]))
        if bias.route is BiasRoute.C_LINEAR_PLUS_TT
        else None
    )
    return _evaluate_frozen(
        batch,
        route_name=bias.route.value,
        encoder=bias.tt.encoder,
        local_value=bias.local_value,
        projection=projection,
        initialization_hash=initialization_hash,
    )


@dataclass(frozen=True)
class ImprovementAssessment:
    classification: str
    mean_improvement: float
    confidence_interval: tuple[float, float]
    maximum_other_regression: float

    def __post_init__(self) -> None:
        if self.classification not in {"PASS", "SCIENTIFIC_NEGATIVE"}:
            raise ValueError("improvement classification is invalid")
        values = (
            self.mean_improvement,
            *self.confidence_interval,
            self.maximum_other_regression,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("improvement assessment must be finite")
        if self.confidence_interval[0] > self.confidence_interval[1]:
            raise ValueError("improvement interval is reversed")


def classify_tt_improvement(
    improvements_by_j: np.ndarray,
    *,
    other_metric_regression: np.ndarray,
    seed: int,
    bootstrap_replicates: int,
    material_regression: float = 0.0,
) -> ImprovementAssessment:
    improvements = np.asarray(improvements_by_j, dtype=np.float64)
    regressions = np.asarray(other_metric_regression, dtype=np.float64)
    if (
        improvements.ndim != 1
        or regressions.shape != improvements.shape
        or improvements.size < 2
    ):
        raise ValueError("improvement evidence must contain whole-J paired rows")
    if not np.all(np.isfinite(improvements)) or not np.all(np.isfinite(regressions)):
        raise ValueError("improvement evidence must be finite")
    if bootstrap_replicates < 1 or not math.isfinite(material_regression):
        raise ValueError("bootstrap controls must be finite and positive")
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0,
        improvements.size,
        size=(bootstrap_replicates, improvements.size),
    )
    bootstrap = np.mean(improvements[indices], axis=1)
    interval = tuple(float(value) for value in np.quantile(bootstrap, (0.025, 0.975)))
    maximum_regression = float(np.max(regressions))
    passed = interval[0] > 0.0 and maximum_regression <= material_regression
    return ImprovementAssessment(
        classification="PASS" if passed else "SCIENTIFIC_NEGATIVE",
        mean_improvement=float(np.mean(improvements)),
        confidence_interval=interval,
        maximum_other_regression=maximum_regression,
    )


@dataclass(frozen=True)
class FrozenComparison:
    route_names: tuple[str, ...]
    budget_kinds: tuple[str, ...]
    evaluations: tuple[FrozenEvaluation, ...]
    assessments: Mapping[str, tuple[ImprovementAssessment, ...]]


def compare_frozen_routes(
    evaluations: Sequence[FrozenEvaluation],
    *,
    seed: int,
    bootstrap_replicates: int,
    material_regression: float = 0.0,
) -> FrozenComparison:
    items = tuple(evaluations)
    route_names = ("linear", "C", "B", "A")
    budget_kinds = ("proposal", "wall")
    grouped: dict[str, dict[str, FrozenEvaluation]] = {}
    for item in items:
        group = grouped.setdefault(item.budget_kind, {})
        if item.route_name in group:
            raise ValueError("duplicate frozen route/budget evaluation")
        group[item.route_name] = item
    if set(grouped) != set(budget_kinds) or any(
        set(group) != set(route_names) for group in grouped.values()
    ):
        raise ValueError("both fair budget groups require linear/C/B/A evaluations")
    assessments: dict[str, list[ImprovementAssessment]] = {
        name: [] for name in route_names[1:]
    }
    for budget_index, budget in enumerate(budget_kinds):
        group = grouped[budget]
        identifiers = {item.j_ids for item in group.values()}
        if len(identifiers) != 1:
            raise ValueError("fair route comparisons require identical held-out J IDs")
        if len({item.split for item in group.values()}) != 1:
            raise ValueError("fair route comparisons require one held-out split")
        if budget == "proposal" and len(
            {item.proposal_count for item in group.values()}
        ) != 1:
            raise ValueError("proposal-budget route counts must match")
        if budget == "wall" and not np.allclose(
            [item.wall_seconds for item in group.values()],
            group["linear"].wall_seconds,
            atol=1e-12,
            rtol=0.0,
        ):
            raise ValueError("wall-budget route times must match")
        if (
            not group["C"].initialization_hash
            or group["C"].initialization_hash != group["B"].initialization_hash
        ):
            raise ValueError("Routes C and B must share the same TT initialization")
        baseline = group["linear"]
        for route in route_names[1:]:
            candidate = group[route]
            assessments[route].append(
                classify_tt_improvement(
                    baseline.primary_metric_by_j - candidate.primary_metric_by_j,
                    other_metric_regression=(
                        candidate.other_metric_by_j - baseline.other_metric_by_j
                    ),
                    seed=seed + budget_index * 17 + route_names.index(route),
                    bootstrap_replicates=bootstrap_replicates,
                    material_regression=material_regression,
                )
            )
    return FrozenComparison(
        route_names=route_names,
        budget_kinds=budget_kinds,
        evaluations=items,
        assessments=MappingProxyType(
            {name: tuple(values) for name, values in assessments.items()}
        ),
    )


@dataclass(frozen=True)
class NumericalFailureRecord:
    classification: str
    failure_kind: str
    step: int
    message: str
    checkpoint_path: Path


def _tt_hash(model: LocalTensorTrain) -> str:
    digest = hashlib.sha256()
    for core in model.cores:
        digest.update(str(core.shape).encode("ascii"))
        digest.update(core.dtype.str.encode("ascii"))
        digest.update(np.ascontiguousarray(core).tobytes())
    return digest.hexdigest()


def _runtime_backend_schema(
    backend: object,
    *,
    encoder_token_count: int,
) -> tuple[tuple[str, ...], int, int]:
    for name in (
        "next_batch",
        "checkpoint_state",
        "restore_state",
        "training_rng_state",
    ):
        if not callable(getattr(backend, name, None)):
            raise TypeError(f"VMCRGSamplingBackend {name} must be callable")
    for name in ("j_ids", "draw_count", "token_count"):
        if not hasattr(backend, name):
            raise TypeError(f"VMCRGSamplingBackend must expose {name}")
    identifiers = _ordered_j_ids(
        getattr(backend, "j_ids"),
        label="backend J IDs",
    )
    draw_count = _positive_schema_count(
        getattr(backend, "draw_count"), name="draw_count"
    )
    token_count = _positive_schema_count(
        getattr(backend, "token_count"), name="token_count"
    )
    if token_count != encoder_token_count:
        raise ValueError("backend token_count must match encoder token_count")
    if not isinstance(backend, VMCRGSamplingBackend):
        raise TypeError("backend must implement VMCRGSamplingBackend")
    return identifiers, draw_count, token_count


class VMCRGTrainer:
    def __init__(
        self,
        protocol: VMCRGProtocol,
        basis: LinearFeatureBasis,
        tt: SymmetricLocalTT,
        backend: VMCRGSamplingBackend,
        *,
        route: BiasRoute | str = BiasRoute.C_LINEAR_PLUS_TT,
        checkpoint_context: CheckpointContext | None = None,
        failure_checkpoint_root: str | Path | None = None,
    ) -> None:
        if not isinstance(protocol, VMCRGProtocol):
            raise TypeError("protocol must be VMCRGProtocol")
        if not isinstance(basis, LinearFeatureBasis) or not basis.is_primary_comparator:
            raise TypeError("basis must be the primary conditioned comparator")
        if not isinstance(tt, SymmetricLocalTT) or not tt.encoder.conditioned:
            raise TypeError("trainer requires a conditioned SymmetricLocalTT")
        backend_j_ids, draw_count, token_count = _runtime_backend_schema(
            backend,
            encoder_token_count=tt.encoder.token_count,
        )
        selected_route = BiasRoute(route)
        if selected_route not in {
            BiasRoute.C_LINEAR_PLUS_TT,
            BiasRoute.B_CONDITIONED_TT,
        }:
            raise ValueError("VMCRGTrainer supports only Routes C and B")
        self.protocol = protocol
        self.basis = basis
        self.tt = tt
        self.backend = backend
        self._backend_j_ids = backend_j_ids
        self._backend_draw_count = draw_count
        self._backend_token_count = token_count
        self.route = selected_route
        self.coefficients = (
            np.zeros(len(basis.features), dtype=np.float64)
            if selected_route is BiasRoute.C_LINEAR_PLUS_TT
            else np.empty(0, dtype=np.float64)
        )
        self._linear_momentum = np.zeros_like(self.coefficients)
        self._tt_momentum = [np.zeros_like(core) for core in tt.model.cores]
        self.step_index = 0
        self.records: list[TrainingStep] = []
        self._c3_allowed = False
        self.initialization_hash = _tt_hash(tt.model)
        self.checkpoint_context = checkpoint_context
        self.failure_checkpoint_root = (
            None if failure_checkpoint_root is None else Path(failure_checkpoint_root)
        )
        self.last_failure: NumericalFailureRecord | None = None
        if (
            checkpoint_context is not None
            and tuple(checkpoint_context.j_split["train"]) != backend_j_ids
        ):
            raise ValueError(
                "checkpoint train split must match ordered backend J IDs"
            )
        if selected_route is BiasRoute.B_CONDITIONED_TT and protocol.c2_steps < 1:
            raise ValueError("Route B requires at least one TT training step")

    @property
    def maximum_steps(self) -> int:
        if self.route is BiasRoute.B_CONDITIONED_TT:
            return self.protocol.c2_steps
        return self.protocol.c1_steps + self.protocol.c2_steps + self.protocol.c3_steps

    def _assert_backend_schema(self) -> None:
        try:
            current = _runtime_backend_schema(
                self.backend,
                encoder_token_count=self.tt.encoder.token_count,
            )
        except Exception as error:
            raise RuntimeError(
                "VMCRGSamplingBackend schema changed during training"
            ) from error
        expected = (
            self._backend_j_ids,
            self._backend_draw_count,
            self._backend_token_count,
        )
        if current != expected:
            raise RuntimeError("VMCRGSamplingBackend schema changed during training")

    def _validate_backend_state_payload(
        self,
        state_value: object,
        rng_value: object,
        *,
        label: str,
    ) -> dict[str, object]:
        state = _owned_mapping(state_value, label=f"{label} checkpoint_state")
        rng_state = _owned_mapping(rng_value, label=f"{label} training_rng_state")
        required = {"j_ids", "draw_count", "token_count", "rng_state"}
        if not required <= set(state):
            raise ValueError(f"{label} checkpoint state is incomplete")
        identifiers = _ordered_j_ids(
            state["j_ids"],
            expected_count=len(self._backend_j_ids),
            label=f"{label} ordered J IDs",
        )
        if identifiers != self._backend_j_ids:
            raise ValueError(f"{label} ordered J IDs do not match the backend")
        draw_count = _positive_schema_count(
            state["draw_count"], name="draw_count"
        )
        token_count = _positive_schema_count(
            state["token_count"], name="token_count"
        )
        if (draw_count, token_count) != (
            self._backend_draw_count,
            self._backend_token_count,
        ):
            raise ValueError(f"{label} batch schema does not match the backend")
        checkpoint_rng = _owned_mapping(
            state["rng_state"], label=f"{label} checkpoint rng_state"
        )
        if not _state_equal(checkpoint_rng, rng_state):
            raise ValueError(f"{label} RNG evidence is inconsistent")
        return state

    def _backend_snapshot(self) -> dict[str, object]:
        self._assert_backend_schema()
        state = self.backend.checkpoint_state()
        rng_state = self.backend.training_rng_state()
        result = self._validate_backend_state_payload(
            state,
            rng_state,
            label="backend",
        )
        self._assert_backend_schema()
        return result

    def _restore_backend_snapshot(self, state: Mapping[str, object]) -> None:
        self.backend.restore_state(copy.deepcopy(dict(state)))
        self._assert_backend_schema()
        observed = self._backend_snapshot()
        if not _state_equal(observed, state):
            raise RuntimeError("VMCRGSamplingBackend rollback state mismatch")

    def _validate_batch(self, batch: object) -> VMCRGBatch:
        if not isinstance(batch, VMCRGBatch):
            raise TypeError("VMCRGSamplingBackend must return VMCRGBatch")
        if batch.j_ids != self._backend_j_ids:
            raise ValueError("VMCRG batch J inventory must match the backend")
        actual = batch.target_tokens.shape
        expected = (
            len(self._backend_j_ids),
            self._backend_draw_count,
            self._backend_token_count,
        )
        if actual[-1] != self._backend_token_count:
            raise ValueError(
                "VMCRG batch token count must match encoder token count"
            )
        if actual != expected:
            raise ValueError(
                f"VMCRG batch shape must remain {expected}, received {actual}"
            )
        return batch

    def _checkpoint_split(
        self,
        j_split: Mapping[str, Sequence[str]],
    ) -> dict[str, tuple[str, ...]]:
        split = _normalized_j_split(j_split)
        if split["train"] != self._backend_j_ids:
            raise ValueError(
                "checkpoint train split must match ordered backend J IDs"
            )
        return split

    def authorize_joint_tuning(
        self,
        *,
        baseline_evaluation: FrozenEvaluation,
        evaluation: FrozenEvaluation,
        seed: int,
        bootstrap_replicates: int,
        material_regression: float = 0.0,
    ) -> ImprovementAssessment:
        if (
            baseline_evaluation.route_name != "linear"
            or evaluation.route_name != "C"
            or baseline_evaluation.split != "validation"
            or evaluation.split != "validation"
            or baseline_evaluation.budget_kind != evaluation.budget_kind
            or baseline_evaluation.j_ids != evaluation.j_ids
            or (
                baseline_evaluation.budget_kind == "proposal"
                and baseline_evaluation.proposal_count
                != evaluation.proposal_count
            )
            or (
                baseline_evaluation.budget_kind == "wall"
                and not math.isclose(
                    baseline_evaluation.wall_seconds,
                    evaluation.wall_seconds,
                    abs_tol=1e-12,
                    rel_tol=0.0,
                )
            )
            or not baseline_evaluation.finite
            or not evaluation.finite
        ):
            raise ValueError(
                "C3 authorization requires matched immutable held-out evaluations"
            )
        if evaluation.initialization_hash != self.initialization_hash:
            raise ValueError("C3 evaluation does not match the trainer initialization")
        assessment = classify_tt_improvement(
            baseline_evaluation.primary_metric_by_j
            - evaluation.primary_metric_by_j,
            other_metric_regression=(
                evaluation.other_metric_by_j
                - baseline_evaluation.other_metric_by_j
            ),
            seed=seed,
            bootstrap_replicates=bootstrap_replicates,
            material_regression=material_regression,
        )
        if (
            assessment.classification != "PASS"
            or assessment.confidence_interval[0] <= 0.0
            or assessment.maximum_other_regression > material_regression
        ):
            raise ValueError("C3 authorization requires passing held-out improvement")
        self._c3_allowed = True
        return assessment

    def _stage(self) -> str:
        if self.step_index >= self.maximum_steps:
            raise RuntimeError("VMCRG protocol is exhausted")
        if self.route is BiasRoute.B_CONDITIONED_TT:
            return "B"
        if self.step_index < self.protocol.c1_steps:
            return "C1"
        if self.step_index < self.protocol.c1_steps + self.protocol.c2_steps:
            return "C2"
        if not self._c3_allowed:
            raise RuntimeError("C3 joint tuning requires passing held-out evidence")
        return "C3"

    def _features(self, batch: np.ndarray) -> np.ndarray:
        return np.asarray(
            [self.basis.local_features(row, self.tt.encoder) for row in batch],
            dtype=np.float64,
        )

    def _active_gradients(
        self,
        stage: str,
        batch: VMCRGBatch,
    ) -> tuple[np.ndarray | None, TTGradient | None]:
        target = batch.target_tokens
        biased = batch.biased_tokens
        n_j, n_draw, n_token = target.shape
        linear_gradient: np.ndarray | None = None
        tt_gradient: TTGradient | None = None
        if stage in {"C1", "C3"}:
            target_features = self._features(target.reshape(-1, n_token)).reshape(
                n_j, n_draw, -1
            )
            biased_features = self._features(biased.reshape(-1, n_token)).reshape(
                n_j, n_draw, -1
            )
            linear_gradient = vmcrg_gradient(
                np.mean(np.mean(target_features, axis=1), axis=0),
                np.mean(np.mean(biased_features, axis=1), axis=0),
            )
        if stage in {"C2", "C3", "B"}:
            target_by_j = [
                self.tt.gradient(row, np.full(n_draw, 1.0 / n_draw))
                for row in target
            ]
            biased_by_j = [
                self.tt.gradient(row, np.full(n_draw, 1.0 / n_draw))
                for row in biased
            ]
            target_mean = target_by_j[0].scale(1.0 / n_j)
            biased_mean = biased_by_j[0].scale(1.0 / n_j)
            for target_gradient, biased_gradient in zip(
                target_by_j[1:], biased_by_j[1:], strict=True
            ):
                target_mean = target_mean.add(target_gradient.scale(1.0 / n_j))
                biased_mean = biased_mean.add(biased_gradient.scale(1.0 / n_j))
            tt_gradient = target_mean.add(biased_mean.scale(-1.0))
        return linear_gradient, tt_gradient

    def _output_values(
        self,
        stage: str,
        tt: SymmetricLocalTT,
        coefficients: np.ndarray,
        tokens: np.ndarray,
    ) -> np.ndarray:
        token_shape = tokens.shape[:-1]
        flat_tokens = tokens.reshape(-1, tokens.shape[-1])
        if stage == "C1":
            values = np.asarray(
                [
                    coefficients @ self.basis.local_features(row, tt.encoder)
                    for row in flat_tokens
                ],
                dtype=np.float64,
            )
        elif self.route is BiasRoute.B_CONDITIONED_TT:
            values = np.asarray([tt.centered_value(row) for row in flat_tokens])
        else:
            bias = OverlapBias(
                BiasRoute.C_LINEAR_PLUS_TT,
                self.basis,
                coefficients,
                tt,
            )
            values = np.asarray([bias.local_value(row) for row in flat_tokens])
        return values.reshape(token_shape)

    def current_bias(self) -> OverlapBias:
        """Return the complete currently trained Route C/B sampling bias."""

        if self.route is BiasRoute.C_LINEAR_PLUS_TT:
            return OverlapBias(
                self.route,
                self.basis,
                self.coefficients,
                self.tt,
            )
        return OverlapBias(
            self.route,
            None,
            np.empty(0, dtype=np.float64),
            self.tt,
        )

    @staticmethod
    def _zero_tt(tt: SymmetricLocalTT) -> SymmetricLocalTT:
        return SymmetricLocalTT(
            LocalTensorTrain([np.zeros_like(core) for core in tt.model.cores]),
            tt.encoder,
        )

    def _candidate_bias(
        self,
        tt: SymmetricLocalTT,
        coefficients: np.ndarray,
        *,
        step_index: int | None = None,
    ) -> OverlapBias:
        if self.route is BiasRoute.C_LINEAR_PLUS_TT:
            index = self.step_index if step_index is None else int(step_index)
            tt_enabled = index >= self.protocol.c1_steps and (
                self.protocol.c2_steps + self.protocol.c3_steps > 0
            )
            return OverlapBias(
                self.route,
                self.basis,
                coefficients,
                tt if tt_enabled else self._zero_tt(tt),
            )
        return OverlapBias(
            self.route,
            None,
            np.empty(0, dtype=np.float64),
            tt,
        )

    def sampling_bias(self) -> OverlapBias:
        """Return the stage-appropriate bias currently used by physical sampling."""

        return self._candidate_bias(
            self.tt,
            self.coefficients,
            step_index=self.step_index,
        )

    def _refresh_sampling_bias(self, bias: OverlapBias) -> None:
        refresh = getattr(self.backend, "refresh_bias", None)
        if refresh is not None:
            if not callable(refresh):
                raise TypeError("VMCRG backend refresh_bias must be callable")
            refresh(bias)

    def _record_failure(self, error: BaseException) -> None:
        if self.failure_checkpoint_root is None or self.checkpoint_context is None:
            raise RuntimeError("failure checkpoint configuration is missing")
        checkpoint_path = self.failure_checkpoint_root / f"step-{self.step_index:08d}"
        self.checkpoint_from_context().save(checkpoint_path)
        self.last_failure = NumericalFailureRecord(
            classification="CORRECTNESS_FAILURE",
            failure_kind="NUMERICAL_FAILURE",
            step=self.step_index,
            message=str(error),
            checkpoint_path=checkpoint_path,
        )

    def step(self) -> TrainingStep:
        if self.failure_checkpoint_root is None or self.checkpoint_context is None:
            raise RuntimeError(
                "VMCRG training requires a failure checkpoint context and root"
            )
        stage = self._stage()
        backend_state_before = self._backend_snapshot()
        try:
            self._assert_backend_schema()
            batch = self.backend.next_batch()
            self._assert_backend_schema()
            batch = self._validate_batch(batch)
            target = batch.target_tokens
            biased = batch.biased_tokens
            linear_gradient, tt_gradient = self._active_gradients(stage, batch)
            squared_norm = 0.0
            if linear_gradient is not None:
                squared_norm += float(np.vdot(linear_gradient, linear_gradient).real)
            if tt_gradient is not None:
                squared_norm += tt_gradient.norm() ** 2
            raw_norm = math.sqrt(squared_norm)
            if not math.isfinite(raw_norm):
                raise FloatingPointError("gradient norm is NaN/Inf")
            scale = min(
                1.0,
                self.protocol.gradient_clip / max(raw_norm, np.finfo(float).tiny),
            )
            candidate_coefficients = self.coefficients.copy()
            candidate_linear_momentum = self._linear_momentum.copy()
            candidate_tt_momentum = [value.copy() for value in self._tt_momentum]
            candidate_model = self.tt.model.copy()
            with np.errstate(over="raise", invalid="raise"):
                if linear_gradient is not None:
                    candidate_linear_momentum = (
                        self.protocol.momentum * candidate_linear_momentum
                        + scale * linear_gradient
                    )
                    candidate_coefficients = (
                        candidate_coefficients
                        - self.protocol.linear_learning_rate
                        * candidate_linear_momentum
                    )
                if tt_gradient is not None:
                    candidate_tt_momentum = [
                        self.protocol.momentum * moment + scale * gradient
                        for moment, gradient in zip(
                            candidate_tt_momentum,
                            tt_gradient.cores,
                            strict=True,
                        )
                    ]
                    candidate_model = LocalTensorTrain(
                        [
                            core - self.protocol.tt_learning_rate * moment
                            for core, moment in zip(
                                self.tt.model.cores,
                                candidate_tt_momentum,
                                strict=True,
                            )
                        ]
                    )
            reset = False
            if (
                tt_gradient is not None
                and (self.step_index + 1) % self.protocol.canonicalize_every == 0
            ):
                candidate_model = candidate_model.left_canonicalize()
                candidate_tt_momentum = [
                    np.zeros_like(core) for core in candidate_model.cores
                ]
                reset = True
            candidate_tt = SymmetricLocalTT(candidate_model, self.tt.encoder)
            target_output = self._output_values(
                stage, candidate_tt, candidate_coefficients, target
            )
            biased_output = self._output_values(
                stage, candidate_tt, candidate_coefficients, biased
            )
            core_norms = tuple(float(np.linalg.norm(core)) for core in candidate_model.cores)
            parameter_norm = math.sqrt(
                float(np.vdot(candidate_coefficients, candidate_coefficients).real)
                + candidate_model.parameter_norm**2
            )
            finite = bool(
                np.all(np.isfinite(candidate_coefficients))
                and np.all(np.isfinite(target_output))
                and np.all(np.isfinite(biased_output))
                and all(math.isfinite(value) for value in core_norms)
                and math.isfinite(parameter_norm)
            )
            if not finite:
                raise FloatingPointError("VMCRG step produced NaN/Inf")
            self._refresh_sampling_bias(
                self._candidate_bias(
                    candidate_tt,
                    candidate_coefficients,
                    step_index=self.step_index + 1,
                )
            )
        except Exception as error:
            try:
                self._restore_backend_snapshot(backend_state_before)
            except Exception as rollback_error:
                raise RuntimeError(
                    "VMCRGSamplingBackend transaction rollback failed"
                ) from rollback_error
            numerical = isinstance(error, (FloatingPointError, OverflowError)) or (
                isinstance(error, ValueError)
                and (
                    "finite" in str(error).lower()
                    or "nan/inf" in str(error).lower()
                )
            )
            if numerical:
                self._record_failure(error)
                raise FloatingPointError(
                    "VMCRG step produced NaN/Inf; last finite checkpoint saved"
                ) from error
            raise

        self.coefficients = candidate_coefficients
        self._linear_momentum = candidate_linear_momentum
        self._tt_momentum = candidate_tt_momentum
        self.tt.model = candidate_model
        record = TrainingStep(
            step=self.step_index,
            stage=stage,
            route=self.route.value,
            objective_estimate=float(
                np.mean(np.mean(target_output, axis=1), axis=0)
                - np.mean(np.mean(biased_output, axis=1), axis=0)
            ),
            unclipped_gradient_norm=raw_norm,
            clipped_gradient_norm=raw_norm * scale,
            parameter_norm=parameter_norm,
            core_norms=core_norms,
            output_min=float(min(np.min(target_output), np.min(biased_output))),
            output_max=float(max(np.max(target_output), np.max(biased_output))),
            finite=True,
            optimizer_moments_reset=reset,
        )
        self.records.append(record)
        self.step_index += 1
        return record

    def run(self, steps: int) -> tuple[TrainingStep, ...]:
        if steps < 0:
            raise ValueError("training step count must be nonnegative")
        return tuple(self.step() for _ in range(steps))

    def freeze(self, batch: FrozenRouteBatch) -> FrozenEvaluation:
        if set(batch.j_ids) & set(self.backend.j_ids):
            raise ValueError("frozen evaluation requires held-out disorder IDs")
        if self.route is BiasRoute.C_LINEAR_PLUS_TT:
            bias = OverlapBias(
                self.route,
                self.basis,
                self.coefficients,
                self.tt,
            )
        else:
            bias = OverlapBias(
                self.route,
                None,
                np.empty(0),
                self.tt,
            )
        return evaluate_frozen_bias(
            bias,
            batch,
            initialization_hash=self.initialization_hash,
        )

    def checkpoint(
        self,
        *,
        beta: float,
        hashes: Mapping[str, str],
        j_split: Mapping[str, Sequence[str]],
        rg_level: int,
    ) -> TrainingCheckpoint:
        split = self._checkpoint_split(j_split)
        sampler_state = self._backend_snapshot()
        rng_state = _owned_mapping(
            sampler_state["rng_state"], label="backend checkpoint rng_state"
        )
        return TrainingCheckpoint(
            cores=self.tt.model.save_arrays(),
            coefficients=self.coefficients,
            optimizer_state={
                "kind": "global-clipped-momentum-sgd",
                "route": self.route.value,
                "c3_allowed": self._c3_allowed,
                "initialization_hash": self.initialization_hash,
                "linear_momentum": self._linear_momentum,
                "tt_momentum": self._tt_momentum,
            },
            rng_state=rng_state,
            pt_state=sampler_state,
            hashes=dict(hashes),
            step=self.step_index,
            beta=beta,
            j_split=split,
            rg_level=rg_level,
        )

    def checkpoint_from_context(self) -> TrainingCheckpoint:
        if self.checkpoint_context is None:
            raise RuntimeError("checkpoint context is not configured")
        return self.checkpoint(
            beta=self.checkpoint_context.beta,
            hashes=self.checkpoint_context.hashes,
            j_split=self.checkpoint_context.j_split,
            rg_level=self.checkpoint_context.rg_level,
        )

    def restore(
        self,
        checkpoint: TrainingCheckpoint,
        *,
        context: CheckpointContext,
    ) -> None:
        if not isinstance(checkpoint, TrainingCheckpoint):
            raise TypeError("checkpoint must be TrainingCheckpoint")
        if not isinstance(context, CheckpointContext):
            raise TypeError("context must be CheckpointContext")
        self._assert_backend_schema()
        if tuple(context.j_split["train"]) != self._backend_j_ids:
            raise ValueError(
                "checkpoint context must match ordered backend J IDs"
            )
        checkpoint_split = self._checkpoint_split(checkpoint.j_split)
        if (
            checkpoint.beta != context.beta
            or checkpoint.rg_level != context.rg_level
            or dict(checkpoint.hashes) != dict(context.hashes)
            or checkpoint_split
            != {name: tuple(values) for name, values in context.j_split.items()}
        ):
            raise ValueError("checkpoint context mismatch")
        state = checkpoint.optimizer_state
        if state.get("kind") != "global-clipped-momentum-sgd":
            raise ValueError("checkpoint optimizer kind is incompatible")
        if state.get("route") != self.route.value:
            raise ValueError("checkpoint route is incompatible")
        if state.get("initialization_hash") != self.initialization_hash:
            raise ValueError("checkpoint TT initialization is incompatible")
        sampler_state = self._validate_backend_state_payload(
            checkpoint.pt_state,
            checkpoint.rng_state,
            label="checkpoint",
        )
        model = LocalTensorTrain.from_arrays(checkpoint.cores)
        if model.token_count != self.tt.model.token_count:
            raise ValueError("checkpoint TT shape is incompatible")
        expected_coefficients = (
            len(self.basis.features)
            if self.route is BiasRoute.C_LINEAR_PLUS_TT
            else 0
        )
        if checkpoint.coefficients.shape != (expected_coefficients,):
            raise ValueError("checkpoint coefficient shape is incompatible")
        linear_momentum = np.asarray(state.get("linear_momentum"), dtype=np.float64)
        tt_momentum = [
            np.asarray(value, dtype=np.float64)
            for value in state.get("tt_momentum", ())
        ]
        if (
            linear_momentum.shape != checkpoint.coefficients.shape
            or len(tt_momentum) != len(model.cores)
        ):
            raise ValueError("checkpoint optimizer moments are incomplete")
        if any(
            left.shape != right.shape
            for left, right in zip(tt_momentum, model.cores, strict=True)
        ):
            raise ValueError("checkpoint TT moments have incompatible shapes")
        if checkpoint.step > self.maximum_steps:
            raise ValueError("checkpoint step exceeds protocol length")
        backend_state_before = self._backend_snapshot()
        previous_bias = self.sampling_bias()
        try:
            candidate_tt = SymmetricLocalTT(model, self.tt.encoder)
            self._refresh_sampling_bias(
                self._candidate_bias(
                    candidate_tt,
                    checkpoint.coefficients,
                    step_index=checkpoint.step,
                )
            )
            self.backend.restore_state(copy.deepcopy(sampler_state))
            self._assert_backend_schema()
            observed = self._backend_snapshot()
            if not _state_equal(observed, sampler_state):
                raise ValueError("restored backend state does not match checkpoint")
        except Exception:
            try:
                self._refresh_sampling_bias(previous_bias)
                self._restore_backend_snapshot(backend_state_before)
            except Exception as rollback_error:
                raise RuntimeError(
                    "VMCRGSamplingBackend restore rollback failed"
                ) from rollback_error
            raise
        self.tt.model = model
        self.coefficients = checkpoint.coefficients.copy()
        self._linear_momentum = linear_momentum.copy()
        self._tt_momentum = [value.copy() for value in tt_momentum]
        self.step_index = checkpoint.step
        self._c3_allowed = bool(state.get("c3_allowed", False))
        self.records.clear()
        self.last_failure = None
        self.checkpoint_context = context
