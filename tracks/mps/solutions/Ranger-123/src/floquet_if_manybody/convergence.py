"""Content-addressed caching and numerical convergence metrics."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import trapezoid


@dataclass(frozen=True)
class ConvergencePoint:
    """Complete numerical controls for one backend evaluation."""

    model: Mapping[str, Any]
    bath: Mapping[str, Any]
    sector: str
    steps_per_period: int
    periods: int
    delay_periods: int
    memory_steps: int
    epsrel: float


@dataclass(frozen=True)
class ConvergenceThresholds:
    state: float = 5e-2
    correlation: float = 5e-2
    heat: float = 5e-2
    phase: float = 1e-3
    trace: float = 5e-3


def fingerprint(point: Mapping[str, Any] | ConvergencePoint, commit: str) -> str:
    """Return a stable SHA-256 key for a point and source revision."""
    payload: Any = asdict(point) if isinstance(point, ConvergencePoint) else point
    encoded = json.dumps(
        {"commit": commit, "point": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_result(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace a JSON cache entry in its destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def state_residual(
    candidate: NDArray[np.complex128], reference: NDArray[np.complex128]
) -> float:
    if candidate.shape != reference.shape:
        raise ValueError("state shapes do not match")
    return float(np.linalg.norm(candidate - reference))


def curve_residual(
    candidate_grid: NDArray[np.float64],
    candidate: NDArray[np.complex128] | NDArray[np.float64],
    reference_grid: NDArray[np.float64],
    reference: NDArray[np.complex128] | NDArray[np.float64],
) -> float:
    """Normalized L1 residual on an identical one-dimensional grid."""
    if (
        candidate_grid.shape != reference_grid.shape
        or candidate.shape != reference.shape
        or candidate.shape != candidate_grid.shape
        or not np.allclose(candidate_grid, reference_grid, atol=1e-12, rtol=1e-12)
    ):
        raise ValueError("curve grids or values do not match")
    numerator = float(trapezoid(abs(candidate - reference), reference_grid))
    denominator = float(trapezoid(abs(reference), reference_grid)) + 1e-15
    return numerator / denominator


class ConvergenceCache:
    """Small JSON cache whose entries are complete only after atomic rename."""

    def __init__(self, directory: Path):
        self.directory = directory

    def path_for(self, key: str) -> Path:
        if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
            raise ValueError("cache key must be a lowercase SHA-256 digest")
        return self.directory / f"{key}.json"

    def contains(self, key: str) -> bool:
        return self.path_for(key).is_file()

    def load(self, key: str) -> dict[str, Any]:
        path = self.path_for(key)
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("fingerprint") != key or value.get("complete") is not True:
            raise ValueError(f"invalid or incomplete cache entry {path}")
        return cast(dict[str, Any], value)

    def store(self, key: str, payload: Mapping[str, Any]) -> Path:
        path = self.path_for(key)
        atomic_write_result(
            path,
            {"fingerprint": key, "complete": True, **dict(payload)},
        )
        return path
