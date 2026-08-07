"""Validated TOML configuration for local MPS VMCRG experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ModelConfig:
    length: int
    coupling: float
    block_size: int
    rg_levels: int
    operator_count: int


@dataclass(frozen=True)
class MPSConfig:
    chi: int
    symmetrize: bool = True


@dataclass(frozen=True)
class TrainingConfig:
    walkers: int
    baseline_steps: int
    residual_steps: int
    sweeps_per_step: int
    baseline_learning_rate: float
    alpha_learning_rate: float
    core_learning_rate: float
    linear_learning_rate: float = 0.0
    gradient_clip: float = 10.0
    cache_check_every: int = 25
    canonicalize_every: int = 25
    compiled: bool = True
    parallel_walkers: bool = True


@dataclass(frozen=True)
class MeasurementConfig:
    thermalization_sweeps: int
    measurement_sweeps: int
    thinning: int


@dataclass(frozen=True)
class RunConfig:
    seeds: tuple[int, ...]
    output: Path


@dataclass(frozen=True)
class ExperimentConfig:
    model: ModelConfig
    mps: MPSConfig
    training: TrainingConfig
    measurement: MeasurementConfig
    run: RunConfig
    source: Path

    @property
    def coarse_length(self) -> int:
        return self.model.length // (self.model.block_size**self.model.rg_levels)


def _positive_int(section: dict, key: str) -> int:
    value = int(section[key])
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _positive_float(section: dict, key: str) -> float:
    value = float(section[key])
    if value <= 0.0:
        raise ValueError(f"{key} must be positive")
    return value


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    source = Path(path).resolve()
    with source.open("rb") as handle:
        raw = tomllib.load(handle)
    for section in ("model", "mps", "training", "measurement", "run"):
        if section not in raw:
            raise ValueError(f"missing [{section}] section")
    model_raw = raw["model"]
    mps_raw = raw["mps"]
    training_raw = raw["training"]
    measurement_raw = raw["measurement"]
    run_raw = raw["run"]

    model = ModelConfig(
        length=_positive_int(model_raw, "length"),
        coupling=float(model_raw["coupling"]),
        block_size=_positive_int(model_raw, "block_size"),
        rg_levels=_positive_int(model_raw, "rg_levels"),
        operator_count=_positive_int(model_raw, "operator_count"),
    )
    if model.block_size % 2 == 0:
        raise ValueError("block_size must be odd")
    divisor = model.block_size**model.rg_levels
    if model.length % divisor != 0:
        raise ValueError("length must be divisible by block_size**rg_levels")
    coarse_length = model.length // divisor
    if coarse_length < 3:
        raise ValueError("final coarse lattice must be at least 3x3")
    if not 1 <= model.operator_count <= 13:
        raise ValueError("operator_count must lie in [1, 13]")
    if model.operator_count == 13 and coarse_length < 5:
        raise ValueError("the published 13-operator basis requires coarse length >= 5")

    mps = MPSConfig(
        chi=_positive_int(mps_raw, "chi"),
        symmetrize=bool(mps_raw.get("symmetrize", True)),
    )
    training = TrainingConfig(
        walkers=_positive_int(training_raw, "walkers"),
        baseline_steps=_positive_int(training_raw, "baseline_steps"),
        residual_steps=_positive_int(training_raw, "residual_steps"),
        sweeps_per_step=_positive_int(training_raw, "sweeps_per_step"),
        baseline_learning_rate=float(
            training_raw.get("baseline_learning_rate", 5e-5)
        ),
        alpha_learning_rate=_positive_float(training_raw, "alpha_learning_rate"),
        core_learning_rate=_positive_float(training_raw, "core_learning_rate"),
        linear_learning_rate=float(training_raw.get("linear_learning_rate", 0.0)),
        gradient_clip=float(training_raw.get("gradient_clip", 10.0)),
        cache_check_every=int(training_raw.get("cache_check_every", 25)),
        canonicalize_every=int(training_raw.get("canonicalize_every", 25)),
        compiled=bool(training_raw.get("compiled", True)),
        parallel_walkers=bool(training_raw.get("parallel_walkers", True)),
    )
    if training.walkers < 2:
        raise ValueError("walkers must be at least two")
    if training.baseline_learning_rate <= 0.0:
        raise ValueError("baseline_learning_rate must be positive")
    if training.linear_learning_rate < 0.0:
        raise ValueError("linear_learning_rate cannot be negative")
    if training.gradient_clip <= 0.0:
        raise ValueError("gradient_clip must be positive")
    if training.cache_check_every < 0 or training.canonicalize_every < 0:
        raise ValueError("check/canonicalize intervals cannot be negative")

    measurement = MeasurementConfig(
        thermalization_sweeps=_positive_int(
            measurement_raw, "thermalization_sweeps"
        ),
        measurement_sweeps=_positive_int(measurement_raw, "measurement_sweeps"),
        thinning=_positive_int(measurement_raw, "thinning"),
    )
    seeds = tuple(int(seed) for seed in run_raw["seeds"])
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("run seeds must be nonempty and unique")
    output_raw = Path(str(run_raw["output"]))
    output = output_raw if output_raw.is_absolute() else source.parent.parent / output_raw
    run = RunConfig(seeds=seeds, output=output.resolve())
    return ExperimentConfig(model, mps, training, measurement, run, source)
