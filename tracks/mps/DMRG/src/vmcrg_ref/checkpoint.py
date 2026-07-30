"""Small atomic checkpoints for the local patch-MPS experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from .mps_patch import PatchMPS


@dataclass(frozen=True)
class MPSCheckpoint:
    model: PatchMPS
    alpha: float
    linear_bias: np.ndarray
    metadata: dict[str, Any]


def _atomic_npz(path: Path, payload: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
        np.savez_compressed(handle, **payload)
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        suffix=".json",
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def save_mps_checkpoint(
    directory: str | Path,
    model: PatchMPS,
    alpha: float,
    linear_bias: np.ndarray,
    metadata: dict[str, Any],
) -> None:
    root = Path(directory)
    if not np.isfinite(alpha):
        raise ValueError("alpha must be finite")
    bias = np.asarray(linear_bias, dtype=np.float64)
    if bias.ndim != 1 or not np.all(np.isfinite(bias)):
        raise ValueError("linear_bias must be a finite vector")
    payload: dict[str, np.ndarray] = {
        "schema_version": np.asarray(1, dtype=np.int64),
        "chi": np.asarray(model.chi, dtype=np.int64),
        "symmetrize": np.asarray(int(model.symmetrize), dtype=np.int8),
        "alpha": np.asarray(alpha, dtype=np.float64),
        "linear_bias": bias,
    }
    for index, core in enumerate(model.cores):
        payload[f"core_{index}"] = core
    _atomic_npz(root / "model.npz", payload)
    _atomic_json(root / "metadata.json", metadata)


def load_mps_checkpoint(directory: str | Path) -> MPSCheckpoint:
    root = Path(directory)
    with np.load(root / "model.npz", allow_pickle=False) as data:
        if int(data["schema_version"]) != 1:
            raise ValueError("unsupported MPS checkpoint schema")
        chi = int(data["chi"])
        symmetrize = bool(int(data["symmetrize"]))
        cores = tuple(data[f"core_{index}"].copy() for index in range(9))
        model = PatchMPS(chi, cores, symmetrize=symmetrize)
        alpha = float(data["alpha"])
        linear_bias = data["linear_bias"].copy()
    with (root / "metadata.json").open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    return MPSCheckpoint(model, alpha, linear_bias, metadata)
