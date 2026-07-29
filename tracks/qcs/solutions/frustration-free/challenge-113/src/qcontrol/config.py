from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def _require_positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _require_finite_number(name: str, value: object, *, positive: bool) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        numeric_value = float(value)
    except OverflowError:
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(numeric_value) or (numeric_value <= 0 if positive else numeric_value < 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{name} must be finite and {qualifier}")


@dataclass(frozen=True)
class SystemConfig:
    name: str
    segments: int
    amplitude_bound: float
    duration: float | None = None

    def __post_init__(self) -> None:
        if self.name not in {"one_qubit", "two_qubit"}:
            raise ValueError("system name must be 'one_qubit' or 'two_qubit'")
        _require_positive_integer("segments", self.segments)
        _require_finite_number("amplitude_bound", self.amplitude_bound, positive=True)
        duration = (
            1.0 if self.name == "one_qubit" else 8.0
        ) if self.duration is None else self.duration
        _require_finite_number("duration", duration, positive=True)
        object.__setattr__(self, "duration", float(duration))

    @property
    def parameter_count(self) -> int:
        control_count = 2 if self.name == "one_qubit" else 4
        return control_count * self.segments


@dataclass(frozen=True)
class DeviceConfig:
    gap: float = 0.0
    shots: int | None = None
    perturbation_seed: int = 0

    def __post_init__(self) -> None:
        _require_finite_number("gap", self.gap, positive=False)
        if self.gap == 0:
            object.__setattr__(self, "gap", 0.0)
        if self.shots is not None:
            _require_positive_integer("shots", self.shots)
        _require_nonnegative_integer("perturbation_seed", self.perturbation_seed)


@dataclass(frozen=True)
class SearchConfig:
    method: str
    dimension: int
    budget: int

    def __post_init__(self) -> None:
        if self.method not in {"full", "model_hessian", "random", "oracle"}:
            raise ValueError("unsupported search method")
        _require_positive_integer("dimension", self.dimension)
        _require_positive_integer("budget", self.budget)


@dataclass(frozen=True)
class ExperimentConfig:
    run_kind: str
    system: SystemConfig
    device: DeviceConfig
    search: SearchConfig
    trial_seed: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.run_kind not in {"development", "production"}:
            raise ValueError("run_kind must be 'development' or 'production'")
        if not isinstance(self.system, SystemConfig):
            raise ValueError("system must be a SystemConfig")
        if not isinstance(self.device, DeviceConfig):
            raise ValueError("device must be a DeviceConfig")
        if not isinstance(self.search, SearchConfig):
            raise ValueError("search must be a SearchConfig")
        _require_nonnegative_integer("trial_seed", self.trial_seed)
        if self.search.dimension > self.system.parameter_count:
            raise ValueError("search dimension exceeds the system parameter count")

        expected_budget = 200 if self.run_kind == "development" else 2000
        if self.search.budget != expected_budget:
            raise ValueError(f"{self.run_kind} budget must be {expected_budget}")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "device": {
                "gap": float(self.device.gap),
                "perturbation_seed": self.device.perturbation_seed,
                "shots": self.device.shots,
            },
            "run_kind": self.run_kind,
            "search": {
                "budget": self.search.budget,
                "dimension": self.search.dimension,
                "method": self.search.method,
            },
            "system": {
                "amplitude_bound": float(self.system.amplitude_bound),
                "duration": self.system.duration,
                "name": self.system.name,
                "segments": self.system.segments,
            },
            "trial_seed": self.trial_seed,
        }

    def content_id(self) -> str:
        payload = json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:20]
