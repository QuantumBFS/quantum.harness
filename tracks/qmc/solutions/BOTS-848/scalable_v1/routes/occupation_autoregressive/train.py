"""Deterministic reduced-state VMC for the occupation-autoregressive route."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
import zipfile
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Mapping

import numpy as np

from .model import AutoregressiveNQS
from .operators import PreparedPairOperator, local_energy, local_l2


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


def score_covariance(scores: object, local_values: object) -> np.ndarray:
    """Return ``2 Re Cov(conj(d log psi), local)`` for real parameters."""

    try:
        score_array = np.asarray(scores, dtype=np.complex128)
        value_array = np.asarray(local_values, dtype=np.complex128)
    except (TypeError, ValueError) as error:
        raise TypeError("scores and local_values must be numeric") from error
    if score_array.ndim != 2:
        raise ValueError("scores must have shape (samples, parameters)")
    if value_array.ndim != 1 or value_array.shape[0] != score_array.shape[0]:
        raise ValueError("local_values must contain one value per score row")
    if score_array.shape[0] == 0:
        raise ValueError("score covariance requires at least one sample")
    if not (
        np.all(np.isfinite(score_array.real))
        and np.all(np.isfinite(score_array.imag))
        and np.all(np.isfinite(value_array.real))
        and np.all(np.isfinite(value_array.imag))
    ):
        raise ValueError("score covariance inputs must be finite")
    conjugate_scores = score_array.conj()
    covariance = np.mean(
        conjugate_scores * value_array[:, None],
        axis=0,
    ) - np.mean(conjugate_scores, axis=0) * np.mean(value_array)
    gradient = np.asarray(2.0 * np.real(covariance), dtype=np.float64)
    if not np.all(np.isfinite(gradient)):
        raise FloatingPointError("non-finite VMC score covariance")
    return gradient


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    logpsi_cache: dict[int, complex] = {}

    def logpsi(raw_state: int) -> complex:
        state = int(raw_state)
        value = logpsi_cache.get(state)
        if value is None:
            value = model.logpsi(state, sector)
            logpsi_cache[state] = value
        return value

    cache: dict[int, tuple[complex, complex, np.ndarray]] = {}
    energies: list[complex] = []
    l2_values: list[complex] = []
    scores: list[np.ndarray] = []
    for raw_state in states:
        state = int(raw_state)
        evaluated = cache.get(state)
        if evaluated is None:
            evaluated = (
                local_energy(state, operator=operator, logpsi=logpsi),
                local_l2(
                    state,
                    two_q=model.two_q,
                    target_m=0.0,
                    logpsi=logpsi,
                ),
                model.log_derivative(state, sector),
            )
            cache[state] = evaluated
        energy, l2_value, score = evaluated
        energies.append(energy)
        l2_values.append(l2_value)
        scores.append(score)
    energy_array = np.asarray(energies, dtype=np.complex128)
    l2_array = np.asarray(l2_values, dtype=np.complex128)
    score_array = np.asarray(scores, dtype=np.complex128)
    if not (
        np.all(np.isfinite(energy_array.real))
        and np.all(np.isfinite(energy_array.imag))
        and np.all(np.isfinite(l2_array.real))
        and np.all(np.isfinite(l2_array.imag))
        and np.all(np.isfinite(score_array.real))
        and np.all(np.isfinite(score_array.imag))
    ):
        raise FloatingPointError("non-finite reduced-state estimator")
    return energy_array, l2_array, score_array


def _checkpoint(
    *,
    model: AutoregressiveNQS,
    adam_state: AdamState,
    config: ReducedTrainingConfig,
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
            ground_energy, ground_l2, ground_scores = _sector_estimators(
                model,
                operator,
                ground_states,
                "ground",
            )
            excited_energy, excited_l2, excited_scores = _sector_estimators(
                model,
                operator,
                excited_states,
                "excited",
            )
            mean_energy_ground = float(np.mean(ground_energy).real)
            mean_energy_excited = float(np.mean(excited_energy).real)
            ground_l2_real = ground_l2.real
            excited_l2_real = excited_l2.real
            mean_l2_ground = float(np.mean(ground_l2_real))
            mean_l2_excited = float(np.mean(excited_l2_real))
            variance_l2_excited = float(
                np.mean((excited_l2_real - mean_l2_excited) ** 2)
            )
            objective = (
                mean_energy_ground
                + mean_energy_excited
                + 0.25 * mean_l2_ground**2
                + 0.25 * (mean_l2_excited - 6.0) ** 2
                + 0.05 * variance_l2_excited
            )

            ground_l2_gradient = score_covariance(ground_scores, ground_l2_real)
            excited_l2_gradient = score_covariance(excited_scores, excited_l2_real)
            gradient = (
                score_covariance(ground_scores, ground_energy)
                + score_covariance(excited_scores, excited_energy)
                + 0.5 * mean_l2_ground * ground_l2_gradient
                + 0.5 * (mean_l2_excited - 6.0) * excited_l2_gradient
                + 0.05
                * (
                    score_covariance(excited_scores, excited_l2_real**2)
                    - 2.0 * mean_l2_excited * excited_l2_gradient
                )
            )
            if not math.isfinite(objective) or not np.all(np.isfinite(gradient)):
                raise FloatingPointError("non-finite reduced VMC objective or gradient")
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
                "energy_ground": mean_energy_ground,
                "energy_excited_m0": mean_energy_excited,
                "mean_l2_ground": mean_l2_ground,
                "mean_l2_excited_m0": mean_l2_excited,
                "variance_l2_excited_m0": variance_l2_excited,
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
