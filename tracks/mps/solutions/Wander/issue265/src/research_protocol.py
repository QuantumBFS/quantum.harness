"""Frozen research-matrix and decision-rule configuration.

The confirmatory analysis is deliberately driven by versioned JSON files.
Loading performs the high-value checks that prevent post-hoc condition
changes, duplicate jobs, and ambiguous time splits from silently entering a
universality verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConditionSpec:
    """One physical initial condition in the preregistered matrix."""

    condition_id: str
    role: str
    delta: float
    temperature: str
    mu: float
    orientation: int
    profile: str
    width: float
    background_m: float
    j2: float
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ResearchMatrix:
    """Validated conditions, numerical ladder, and blinded time splits."""

    schema_version: int
    conditions: tuple[ConditionSpec, ...]
    convergence_levels: tuple[dict[str, Any], ...]
    convergence_condition_ids: tuple[str, ...]
    train_window: tuple[float, float]
    validation_window: tuple[float, float]
    test_window: tuple[float, float]
    rolling_windows: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class DecisionRules:
    """Immutable lookup wrapper for preregistered scalar thresholds."""

    schema_version: int
    values: dict[str, float]

    def threshold(self, name: str) -> float:
        if name not in self.values:
            raise KeyError(f"{name} is not preregistered")
        return float(self.values[name])


def _window(raw: Any, name: str) -> tuple[float, float]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError(f"{name} must contain exactly two values")
    start, stop = float(raw[0]), float(raw[1])
    if not start < stop:
        raise ValueError(f"{name} must be strictly increasing")
    return start, stop


def load_research_matrix(path: str | Path) -> ResearchMatrix:
    """Load and validate a frozen research condition matrix."""

    raw = json.loads(Path(path).read_text())
    schema_version = int(raw["schema_version"])
    if schema_version != 1:
        raise ValueError(f"Unsupported research matrix schema {schema_version}")

    analysis = raw["analysis_windows"]
    train = _window(analysis["train"], "train window")
    validation = _window(analysis["validation"], "validation window")
    test = _window(analysis["test"], "test window")
    if not (train[1] <= validation[0] and validation[1] <= test[0]):
        raise ValueError("Train, validation, and test windows must not overlap")
    rolling = tuple(
        _window(value, f"rolling window {index}")
        for index, value in enumerate(analysis["rolling"])
    )

    conditions: list[ConditionSpec] = []
    condition_ids: set[str] = set()
    known_roles = {
        "primary_amplitude",
        "primary_width",
        "primary_shape",
        "primary_background",
        "environment_control",
    }
    known_profiles = {"tanh", "erf", "double_wall", "gaussian", "sinusoid"}
    core_keys = {
        "condition_id",
        "role",
        "delta",
        "temperature",
        "mu",
        "orientation",
        "profile",
        "width",
        "background_m",
        "j2",
    }
    for item in raw["conditions"]:
        condition_id = str(item["condition_id"])
        if condition_id in condition_ids:
            raise ValueError(f"Duplicate condition_id: {condition_id}")
        condition_ids.add(condition_id)
        role = str(item["role"])
        if role not in known_roles:
            raise ValueError(f"Unknown role for {condition_id}: {role}")
        profile = str(item["profile"])
        if profile not in known_profiles:
            raise ValueError(f"Unknown profile for {condition_id}: {profile}")
        mu = float(item["mu"])
        if mu <= 0:
            raise ValueError(f"mu must be positive for {condition_id}")
        orientation = int(item["orientation"])
        if orientation not in (-1, 1):
            raise ValueError(f"orientation must be -1 or +1 for {condition_id}")
        width = float(item["width"])
        if width <= 0:
            raise ValueError(f"width must be positive for {condition_id}")
        conditions.append(
            ConditionSpec(
                condition_id=condition_id,
                role=role,
                delta=float(item["delta"]),
                temperature=str(item["temperature"]),
                mu=mu,
                orientation=orientation,
                profile=profile,
                width=width,
                background_m=float(item["background_m"]),
                j2=float(item["j2"]),
                parameters={
                    str(key): value
                    for key, value in item.items()
                    if key not in core_keys
                },
            )
        )

    expected_amplitude_pairs = {
        (mu, orientation)
        for mu in (0.02, 0.05, 0.10, 0.20)
        for orientation in (-1, 1)
    }
    observed_amplitude_pairs = {
        (condition.mu, condition.orientation)
        for condition in conditions
        if condition.role == "primary_amplitude"
    }
    if observed_amplitude_pairs != expected_amplitude_pairs:
        raise ValueError(
            "Primary amplitude matrix must contain all preregistered "
            "mu/orientation pairs"
        )

    levels = tuple(dict(level) for level in raw["convergence_levels"])
    if tuple(level.get("level") for level in levels) != (
        "coarse",
        "medium",
        "fine",
    ):
        raise ValueError("Convergence levels must be coarse, medium, fine")
    convergence_condition_ids = tuple(
        str(value) for value in raw["convergence_condition_ids"]
    )
    unknown = set(convergence_condition_ids) - condition_ids
    if unknown:
        raise ValueError(
            "Unknown convergence condition IDs: " + ", ".join(sorted(unknown))
        )

    return ResearchMatrix(
        schema_version=schema_version,
        conditions=tuple(conditions),
        convergence_levels=levels,
        convergence_condition_ids=convergence_condition_ids,
        train_window=train,
        validation_window=validation,
        test_window=test,
        rolling_windows=rolling,
    )


def load_decision_rules(path: str | Path) -> DecisionRules:
    """Load preregistered numerical thresholds without adding defaults."""

    raw = json.loads(Path(path).read_text())
    schema_version = int(raw["schema_version"])
    if schema_version != 1:
        raise ValueError(f"Unsupported decision-rule schema {schema_version}")
    values = {str(key): float(value) for key, value in raw["thresholds"].items()}
    if not values:
        raise ValueError("Decision rules must contain at least one threshold")
    if any(not (value >= 0.0) for value in values.values()):
        raise ValueError("Decision thresholds must be non-negative")
    return DecisionRules(schema_version=schema_version, values=values)
