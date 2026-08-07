"""Literal stochastic-training protocol for pure-neural VMCRG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .neural_energy import D4EvenLocalMLP, MLPGradient


@dataclass(frozen=True)
class RobbinsMonroSchedule:
    eta_0: float
    t_0: float
    p: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.eta_0) or self.eta_0 <= 0.0:
            raise ValueError("Robbins-Monro eta_0 must be positive and finite")
        if not np.isfinite(self.t_0) or self.t_0 <= 0.0:
            raise ValueError("Robbins-Monro t_0 must be positive and finite")
        if not np.isfinite(self.p) or not 0.5 < self.p <= 1.0:
            raise ValueError("Robbins-Monro p must lie in (0.5, 1]")

    def rate(self, update: int) -> float:
        if update < 0:
            raise ValueError("Robbins-Monro update index cannot be negative")
        return float(self.eta_0 * (float(update) + self.t_0) ** (-self.p))


@dataclass(frozen=True)
class TrainingStopConfig:
    minimum_updates: int
    maximum_updates: int
    monitor_every: int
    patience_windows: int
    held_out_objective_change_upper: float
    gradient_norm_upper: float
    operator_equivalence_upper: float
    patch_tv_upper: float
    parameter_drift_upper: float
    minimum_polyak_fraction: float

    def __post_init__(self) -> None:
        if self.minimum_updates <= 0 or self.maximum_updates < self.minimum_updates:
            raise ValueError("training update bounds are invalid")
        if self.monitor_every <= 0 or self.patience_windows <= 0:
            raise ValueError("training monitor cadence and patience must be positive")
        thresholds = (
            self.held_out_objective_change_upper,
            self.gradient_norm_upper,
            self.operator_equivalence_upper,
            self.patch_tv_upper,
            self.parameter_drift_upper,
        )
        if any(not np.isfinite(value) or value < 0.0 for value in thresholds):
            raise ValueError("training stop thresholds must be finite and nonnegative")
        if not 0.0 <= self.minimum_polyak_fraction <= 1.0:
            raise ValueError("minimum Polyak fraction must lie in [0, 1]")


@dataclass(frozen=True)
class TrainingWindow:
    update: int
    held_out_objective: float
    held_out_objective_change: float
    gradient_norm: float
    operator_equivalence: float
    patch_tv: float
    parameter_drift: float
    polyak_fraction: float
    parameters_finite: bool
    gradient_finite: bool


class TrainingStopState:
    def __init__(self, config: TrainingStopConfig) -> None:
        self.config = config
        self.consecutive_passing_windows = 0
        self.last_update = 0
        self.terminal_reason: str | None = None
        self.windows: list[TrainingWindow] = []

    def observe(self, window: TrainingWindow) -> str | None:
        if self.terminal_reason is not None:
            return self.terminal_reason
        if window.update <= self.last_update:
            raise ValueError("training monitor updates must be strictly increasing")
        if (
            window.update % self.config.monitor_every != 0
            and window.update != self.config.maximum_updates
        ):
            raise ValueError("training window does not match monitor cadence")
        if window.update > self.config.maximum_updates:
            raise ValueError("training window exceeds the hard update cap")
        self.last_update = window.update
        self.windows.append(window)
        numeric = (
            window.held_out_objective,
            window.held_out_objective_change,
            window.gradient_norm,
            window.operator_equivalence,
            window.patch_tv,
            window.parameter_drift,
            window.polyak_fraction,
        )
        if (
            not window.parameters_finite
            or not window.gradient_finite
            or not all(np.isfinite(value) for value in numeric)
        ):
            self.terminal_reason = "CORRECTNESS_FAILURE"
            return self.terminal_reason
        passing = bool(
            window.update >= self.config.minimum_updates
            and abs(window.held_out_objective_change)
            <= self.config.held_out_objective_change_upper
            and window.gradient_norm <= self.config.gradient_norm_upper
            and window.operator_equivalence
            <= self.config.operator_equivalence_upper
            and window.patch_tv <= self.config.patch_tv_upper
            and window.parameter_drift <= self.config.parameter_drift_upper
            and window.polyak_fraction >= self.config.minimum_polyak_fraction
        )
        self.consecutive_passing_windows = (
            self.consecutive_passing_windows + 1 if passing else 0
        )
        if self.consecutive_passing_windows >= self.config.patience_windows:
            self.terminal_reason = "CONVERGED"
        elif window.update >= self.config.maximum_updates:
            self.terminal_reason = "NOT_CONVERGED"
        return self.terminal_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_update": self.last_update,
            "consecutive_passing_windows": self.consecutive_passing_windows,
            "terminal_reason": self.terminal_reason,
            "windows": [
                {
                    key: getattr(window, key)
                    for key in window.__dataclass_fields__
                }
                for window in self.windows
            ],
        }


def clip_mlp_gradient(
    gradient: MLPGradient,
    max_norm: float,
) -> tuple[MLPGradient, float, float]:
    if not np.isfinite(max_norm) or max_norm <= 0.0:
        raise ValueError("gradient clip norm must be positive and finite")
    arrays = (
        np.asarray(gradient.weight_in, dtype=np.float64),
        np.asarray(gradient.bias_hidden, dtype=np.float64),
        np.asarray(gradient.weight_out, dtype=np.float64),
    )
    if not all(np.all(np.isfinite(value)) for value in arrays):
        raise FloatingPointError("non-finite neural gradient")
    original_norm = float(
        np.sqrt(sum(float(np.sum(value * value)) for value in arrays))
    )
    scale = 1.0 if original_norm <= max_norm or original_norm == 0.0 else max_norm / original_norm
    clipped = MLPGradient(
        arrays[0].copy() * scale,
        arrays[1].copy() * scale,
        arrays[2].copy() * scale,
    )
    clipped_norm = float(original_norm * scale)
    return clipped, original_norm, clipped_norm


def model_parameters_finite(model: D4EvenLocalMLP) -> bool:
    return all(
        np.all(np.isfinite(value))
        for value in (model.weight_in, model.bias_hidden, model.weight_out)
    )


class PolyakAverager:
    def __init__(self, start_update: int) -> None:
        if start_update <= 0:
            raise ValueError("Polyak averaging must start after a positive update")
        self.start_update = int(start_update)
        self._last_update = 0
        self._weight_in: np.ndarray | None = None
        self._bias_hidden: np.ndarray | None = None
        self._weight_out: np.ndarray | None = None
        self.sample_count = 0

    def observe(self, update: int, model: D4EvenLocalMLP) -> None:
        if update <= self._last_update:
            raise ValueError("Polyak observations must have increasing update indices")
        self._last_update = int(update)
        if update < self.start_update:
            return
        if not model_parameters_finite(model):
            raise FloatingPointError("non-finite neural parameters during Polyak averaging")
        if self._weight_in is None:
            self._weight_in = np.zeros_like(model.weight_in)
            self._bias_hidden = np.zeros_like(model.bias_hidden)
            self._weight_out = np.zeros_like(model.weight_out)
        self._weight_in += model.weight_in
        self._bias_hidden += model.bias_hidden
        self._weight_out += model.weight_out
        self.sample_count += 1

    def fraction(self, completed_updates: int) -> float:
        if completed_updates <= 0:
            return 0.0
        return float(self.sample_count / completed_updates)

    def assign_to(self, model: D4EvenLocalMLP) -> None:
        if self.sample_count == 0 or self._weight_in is None:
            raise ValueError("Polyak averaging collected no parameter samples")
        model.weight_in[:] = self._weight_in / self.sample_count
        model.bias_hidden[:] = self._bias_hidden / self.sample_count
        model.weight_out[:] = self._weight_out / self.sample_count


@dataclass(frozen=True)
class TrainingProtocol:
    schedule: RobbinsMonroSchedule
    stop: TrainingStopConfig
    sweeps_per_gradient_batch: int
    gradient_accumulation_batches: int
    target_samples_per_batch: int
    polyak_start_update: int
    polyak_start_fraction: float
    gradient_clip_l2: float
    checkpoint_every: int
    progress_every: int
    independent_sampling_before_update: bool
    monitoring_stream_role: str

    @property
    def minimum_updates(self) -> int:
        return self.stop.minimum_updates

    @property
    def maximum_updates(self) -> int:
        return self.stop.maximum_updates


def load_training_protocol(value: dict[str, Any]) -> TrainingProtocol:
    required = {
        "eta_0",
        "t_0",
        "p",
        "minimum_updates",
        "maximum_updates",
        "sweeps_per_gradient_batch",
        "gradient_accumulation_batches",
        "target_samples_per_batch",
        "polyak_start_update",
        "polyak_start_fraction",
        "gradient_clip_l2",
        "monitor_every",
        "patience_windows",
        "checkpoint_every",
        "progress_every",
        "held_out_objective_change_upper",
        "gradient_norm_upper",
        "operator_equivalence_upper",
        "patch_tv_upper",
        "parameter_drift_upper",
        "minimum_polyak_fraction",
        "independent_sampling_before_update",
        "monitoring_stream_role",
        "nonfinite_action",
        "hard_cap_action",
    }
    missing = required - set(value)
    if missing:
        raise ValueError(f"training protocol fields are missing: {sorted(missing)}")
    if value["independent_sampling_before_update"] is not True:
        raise ValueError("each update requires an independent sampling segment")
    if value["monitoring_stream_role"] != "held_out_stopping_only":
        raise ValueError("training monitoring must use a held-out stopping stream")
    if value["nonfinite_action"] != "CORRECTNESS_FAILURE":
        raise ValueError("non-finite training state must be a correctness failure")
    if value["hard_cap_action"] != "NOT_CONVERGED":
        raise ValueError("training hard cap must classify as NOT_CONVERGED")
    stop = TrainingStopConfig(
        minimum_updates=int(value["minimum_updates"]),
        maximum_updates=int(value["maximum_updates"]),
        monitor_every=int(value["monitor_every"]),
        patience_windows=int(value["patience_windows"]),
        held_out_objective_change_upper=float(
            value["held_out_objective_change_upper"]
        ),
        gradient_norm_upper=float(value["gradient_norm_upper"]),
        operator_equivalence_upper=float(value["operator_equivalence_upper"]),
        patch_tv_upper=float(value["patch_tv_upper"]),
        parameter_drift_upper=float(value["parameter_drift_upper"]),
        minimum_polyak_fraction=float(value["minimum_polyak_fraction"]),
    )
    positive_integer_fields = (
        "sweeps_per_gradient_batch",
        "gradient_accumulation_batches",
        "target_samples_per_batch",
        "polyak_start_update",
        "checkpoint_every",
        "progress_every",
    )
    if any(int(value[key]) <= 0 for key in positive_integer_fields):
        raise ValueError("training sampling, averaging, and output cadences must be positive")
    polyak_start_update = int(value["polyak_start_update"])
    polyak_start_fraction = float(value["polyak_start_fraction"])
    if not np.isclose(
        polyak_start_update / stop.maximum_updates,
        polyak_start_fraction,
        atol=0.0,
        rtol=1e-15,
    ):
        raise ValueError("Polyak start update and fraction disagree")
    gradient_clip = float(value["gradient_clip_l2"])
    if not np.isfinite(gradient_clip) or gradient_clip <= 0.0:
        raise ValueError("training gradient clip must be positive and finite")
    return TrainingProtocol(
        schedule=RobbinsMonroSchedule(
            eta_0=float(value["eta_0"]),
            t_0=float(value["t_0"]),
            p=float(value["p"]),
        ),
        stop=stop,
        sweeps_per_gradient_batch=int(value["sweeps_per_gradient_batch"]),
        gradient_accumulation_batches=int(value["gradient_accumulation_batches"]),
        target_samples_per_batch=int(value["target_samples_per_batch"]),
        polyak_start_update=polyak_start_update,
        polyak_start_fraction=polyak_start_fraction,
        gradient_clip_l2=gradient_clip,
        checkpoint_every=int(value["checkpoint_every"]),
        progress_every=int(value["progress_every"]),
        independent_sampling_before_update=True,
        monitoring_stream_role="held_out_stopping_only",
    )
