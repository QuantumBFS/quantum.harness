"""Versioned request objects and strict public-input validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUEST_SCHEMA = "q66-simulation-request-v1"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RequestError(ValueError):
    """Raised when a simulation request violates the frozen contract."""


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestError(f"{field} must be an integer")
    return value


def _probability(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestError(f"{field} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise RequestError(f"{field} must be in [0,1], got {result}")
    return result


@dataclass(frozen=True)
class ReloadConfig:
    delay_rounds: int
    reset_error_probability: float
    failure_probability: float

    @classmethod
    def from_dict(cls, value: Any) -> ReloadConfig:
        if not isinstance(value, dict):
            raise RequestError("reload must be an object")
        delay = _integer(value.get("delay_rounds"), "reload.delay_rounds")
        if delay < 0:
            raise RequestError("reload.delay_rounds must be non-negative")
        return cls(
            delay_rounds=delay,
            reset_error_probability=_probability(
                value.get("reset_error_probability"),
                "reload.reset_error_probability",
            ),
            failure_probability=_probability(
                value.get("failure_probability"),
                "reload.failure_probability",
            ),
        )


@dataclass(frozen=True)
class PolicyConfig:
    name: str
    interval: int | None = None
    fraction: float | None = None

    @classmethod
    def from_dict(cls, value: Any) -> PolicyConfig:
        if not isinstance(value, dict):
            raise RequestError("policy must be an object")
        name = value.get("name")
        if not isinstance(name, str):
            raise RequestError("policy.name must be a string")
        if name in {"none", "immediate"}:
            if set(value) != {"name"}:
                raise RequestError(f"policy {name} accepts no extra fields")
            return cls(name=name)
        if name == "periodic":
            interval = _integer(value.get("interval"), "policy.interval")
            if interval <= 0:
                raise RequestError("policy.interval must be positive")
            if set(value) != {"name", "interval"}:
                raise RequestError("periodic policy requires only name and interval")
            return cls(name=name, interval=interval)
        if name == "threshold":
            fraction = _probability(value.get("fraction"), "policy.fraction")
            if fraction == 0:
                raise RequestError("policy.fraction must be in (0,1]")
            if set(value) != {"name", "fraction"}:
                raise RequestError("threshold policy requires only name and fraction")
            return cls(name=name, fraction=fraction)
        raise RequestError(f"unknown policy name {name!r}")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.interval is not None:
            result["interval"] = self.interval
        if self.fraction is not None:
            result["fraction"] = self.fraction
        return result


@dataclass(frozen=True)
class SimulationRequest:
    run_id: str
    instance_file: Path
    distance: int
    rounds: int
    basis: str
    shots: int
    shot_start: int
    shard_size: int
    master_seed: int
    p: float
    p_m: float
    p_loss: float
    reload: ReloadConfig
    policy: PolicyConfig
    source_commit: str
    environment_lock_sha256: str

    @classmethod
    def from_dict(cls, value: Any) -> SimulationRequest:
        if not isinstance(value, dict):
            raise RequestError("request root must be an object")
        allowed_fields = {
            "schema_version",
            "run_id",
            "instance_file",
            "distance",
            "rounds",
            "basis",
            "shots",
            "shot_start",
            "shard_size",
            "master_seed",
            "noise",
            "reload",
            "policy",
            "provenance",
        }
        unknown_fields = set(value) - allowed_fields
        if unknown_fields:
            raise RequestError(f"unknown request fields: {sorted(unknown_fields)}")
        if value.get("schema_version") != REQUEST_SCHEMA:
            raise RequestError(
                f"schema_version must be {REQUEST_SCHEMA!r}, "
                f"got {value.get('schema_version')!r}"
            )
        run_id = value.get("run_id")
        if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
            raise RequestError("run_id contains unsafe or unsupported characters")
        instance_file = value.get("instance_file")
        if not isinstance(instance_file, str) or not instance_file:
            raise RequestError("instance_file must be a non-empty path string")
        distance = _integer(value.get("distance"), "distance")
        if distance not in {3, 5}:
            raise RequestError("distance must be 3 or 5")
        rounds = _integer(value.get("rounds"), "rounds")
        if rounds not in {distance, 2 * distance}:
            raise RequestError("rounds must equal d or 2d")
        basis = value.get("basis")
        if basis not in {"X", "Z"}:
            raise RequestError("basis must be X or Z")
        shots = _integer(value.get("shots"), "shots")
        shot_start = _integer(value.get("shot_start", 0), "shot_start")
        shard_size = _integer(value.get("shard_size", shots), "shard_size")
        master_seed = _integer(value.get("master_seed"), "master_seed")
        if shots <= 0 or shot_start < 0 or shard_size <= 0:
            raise RequestError("shots/shard_size must be positive and shot_start non-negative")
        if not 0 <= master_seed < 1 << 64:
            raise RequestError("master_seed must be a uint64")
        noise = value.get("noise")
        if not isinstance(noise, dict):
            raise RequestError("noise must be an object")
        if set(noise) != {"p", "p_m", "p_loss"}:
            raise RequestError("noise must contain exactly p, p_m, and p_loss")
        provenance = value.get("provenance")
        if not isinstance(provenance, dict):
            raise RequestError("provenance must be an object")
        source_commit = provenance.get("source_commit")
        environment_hash = provenance.get("environment_lock_sha256")
        if not isinstance(source_commit, str) or not re.fullmatch(
            r"[0-9a-f]{40}", source_commit
        ):
            raise RequestError("provenance.source_commit must be a full Git hash")
        if not isinstance(environment_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", environment_hash
        ):
            raise RequestError("provenance.environment_lock_sha256 must be SHA-256")
        result = cls(
            run_id=run_id,
            instance_file=Path(instance_file),
            distance=distance,
            rounds=rounds,
            basis=basis,
            shots=shots,
            shot_start=shot_start,
            shard_size=shard_size,
            master_seed=master_seed,
            p=_probability(noise["p"], "noise.p"),
            p_m=_probability(noise["p_m"], "noise.p_m"),
            p_loss=_probability(noise["p_loss"], "noise.p_loss"),
            reload=ReloadConfig.from_dict(value.get("reload")),
            policy=PolicyConfig.from_dict(value.get("policy")),
            source_commit=source_commit,
            environment_lock_sha256=environment_hash,
        )
        if result.p >= 0.75:
            raise RequestError("noise.p must keep the relevant component below 1/2")
        if result.p_m >= 0.5:
            raise RequestError("noise.p_m must be below 1/2 for MWPM weights")
        if result.reload.reset_error_probability >= 0.5:
            raise RequestError("reload.reset_error_probability must be below 1/2")
        return result

    @classmethod
    def load(cls, path: Path) -> SimulationRequest:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REQUEST_SCHEMA,
            "run_id": self.run_id,
            "instance_file": str(self.instance_file),
            "distance": self.distance,
            "rounds": self.rounds,
            "basis": self.basis,
            "shots": self.shots,
            "shot_start": self.shot_start,
            "shard_size": self.shard_size,
            "master_seed": self.master_seed,
            "noise": {"p": self.p, "p_m": self.p_m, "p_loss": self.p_loss},
            "reload": {
                "delay_rounds": self.reload.delay_rounds,
                "reset_error_probability": self.reload.reset_error_probability,
                "failure_probability": self.reload.failure_probability,
            },
            "policy": self.policy.as_dict(),
            "provenance": {
                "source_commit": self.source_commit,
                "environment_lock_sha256": self.environment_lock_sha256,
            },
        }
