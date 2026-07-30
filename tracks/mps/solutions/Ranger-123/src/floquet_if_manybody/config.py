"""Validated scientific and numerical configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

Normalization = Literal["bounded", "kac", "collective"]
DriveNormalization = Literal["coupling", "per_spin"]


@dataclass(frozen=True)
class ModelConfig:
    n: int = 2
    j: float = 0.5
    omega: float = 1.0
    drive_amplitude: float = 0.3
    drive_frequency: float = 1.0
    normalization: Normalization = "bounded"
    drive_normalization: DriveNormalization = "coupling"
    counterterm: bool = False
    counterterm_strength: float = 0.0

    def __post_init__(self) -> None:
        if self.n not in (1, 2, 3):
            raise ValueError("n must be one of 1, 2, 3")
        if self.j < 0:
            raise ValueError("j must be nonnegative")
        if self.omega <= 0:
            raise ValueError("omega must be positive")
        if self.drive_amplitude < 0:
            raise ValueError("drive_amplitude must be nonnegative")
        if self.drive_frequency <= 0:
            raise ValueError("drive_frequency must be positive")
        if isinstance(self.counterterm_strength, bool) or self.counterterm_strength < 0:
            raise ValueError("counterterm_strength must be a nonnegative coefficient")
        if self.counterterm and self.counterterm_strength <= 0:
            raise ValueError(
                "counterterm=True requires a positive counterterm_strength"
            )
        if self.normalization not in ("bounded", "kac", "collective"):
            raise ValueError("unknown normalization")
        if self.drive_normalization not in ("coupling", "per_spin"):
            raise ValueError("unknown drive normalization")

    @property
    def eta(self) -> float:
        if self.normalization == "bounded":
            return 1.0 / self.n
        if self.normalization == "kac":
            return float(1.0 / self.n**0.5)
        return 1.0

    @property
    def drive_eta(self) -> float:
        if self.drive_normalization == "coupling":
            return self.eta
        return 1.0

    @property
    def period(self) -> float:
        import math

        return 2 * math.pi / self.drive_frequency


@dataclass(frozen=True)
class BathConfig:
    alpha: float = 0.05
    cutoff: float = 2.5
    temperature: float = 0.0

    def __post_init__(self) -> None:
        if self.alpha < 0:
            raise ValueError("alpha must be nonnegative")
        if self.cutoff <= 0:
            raise ValueError("cutoff must be positive")
        if self.temperature < 0:
            raise ValueError("temperature must be nonnegative")


@dataclass(frozen=True)
class NumericsConfig:
    drive_steps: int = 240
    memory_steps: int = 4
    periods: int = 80
    correlation_periods: int = 20
    harmonic_cutoff: int = 6
    convergence_tolerance: float = 1e-3

    def __post_init__(self) -> None:
        if self.drive_steps < 8:
            raise ValueError("drive_steps must be at least 8")
        if self.memory_steps < 1:
            raise ValueError("memory_steps must be positive")
        if self.periods < 1 or self.correlation_periods < 1:
            raise ValueError("period counts must be positive")
        if self.harmonic_cutoff < 0:
            raise ValueError("harmonic_cutoff must be nonnegative")
        if self.convergence_tolerance <= 0:
            raise ValueError("convergence_tolerance must be positive")


@dataclass(frozen=True)
class RunConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    bath: BathConfig = field(default_factory=BathConfig)
    numerics: NumericsConfig = field(default_factory=NumericsConfig)
    sector: Literal["full", "triplet", "singlet", "even", "odd"] = "full"
    method: Literal["closed", "floquet_markov", "finite_memory_if"] = "closed"


def _section(cls: type[Any], data: dict[str, Any], key: str) -> Any:
    return cls(**data.get(key, {}))


def load_config(path: Path) -> RunConfig:
    """Load a validated run configuration from YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("configuration root must be a mapping")
    return RunConfig(
        model=_section(ModelConfig, data, "model"),
        bath=_section(BathConfig, data, "bath"),
        numerics=_section(NumericsConfig, data, "numerics"),
        sector=data.get("sector", "full"),
        method=data.get("method", "closed"),
    )
