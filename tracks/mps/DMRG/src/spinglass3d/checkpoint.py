"""Atomic complete VMCRG optimizer/sampler checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import os
from pathlib import Path
import shutil
import tempfile
from collections.abc import Mapping, Sequence

import numpy as np

from vmcrg_ref.artifacts import atomic_write_json, atomic_write_npz, sha256_file


_ARRAY_MARKER = "__npz_array__"


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"checkpoint state contains unsupported type {type(value).__name__}")


def _pack_state(
    value: object,
    arrays: dict[str, np.ndarray],
) -> object:
    if isinstance(value, Mapping):
        return {str(key): _pack_state(item, arrays) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_pack_state(item, arrays) for item in value]
    if isinstance(value, np.ndarray):
        name = f"array_{len(arrays):06d}"
        arrays[name] = np.asarray(value).copy()
        return {_ARRAY_MARKER: name}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"checkpoint state contains unsupported type {type(value).__name__}")


def _unpack_state(value: object, arrays: Mapping[str, np.ndarray]) -> object:
    if isinstance(value, Mapping):
        if set(value) == {_ARRAY_MARKER}:
            name = value[_ARRAY_MARKER]
            if not isinstance(name, str) or name not in arrays:
                raise ValueError("checkpoint state array reference is invalid")
            return np.asarray(arrays[name]).copy()
        return {str(key): _unpack_state(item, arrays) for key, item in value.items()}
    if isinstance(value, list):
        return [_unpack_state(item, arrays) for item in value]
    return value


@dataclass(frozen=True)
class TrainingCheckpoint:
    cores: tuple[np.ndarray, ...]
    coefficients: np.ndarray
    optimizer_state: Mapping[str, object]
    rng_state: Mapping[str, object]
    pt_state: Mapping[str, object]
    hashes: Mapping[str, str]
    step: int
    beta: float
    j_split: Mapping[str, Sequence[str]]
    rg_level: int

    def __post_init__(self) -> None:
        owned_cores: list[np.ndarray] = []
        for core in self.cores:
            value = np.asarray(core, dtype=np.float64)
            if value.ndim != 3 or not np.all(np.isfinite(value)):
                raise ValueError("checkpoint cores must be finite rank-three arrays")
            copy_value = value.copy()
            copy_value.setflags(write=False)
            owned_cores.append(copy_value)
        coefficients = np.asarray(self.coefficients, dtype=np.float64)
        if coefficients.ndim != 1 or not np.all(np.isfinite(coefficients)):
            raise ValueError("checkpoint coefficients must be finite")
        owned_coefficients = coefficients.copy()
        owned_coefficients.setflags(write=False)
        if self.step < 0 or not np.isfinite(self.beta) or self.beta <= 0.0:
            raise ValueError("checkpoint step/beta are invalid")
        if self.rg_level not in (1, 2):
            raise ValueError("checkpoint RG level must be one or two")
        object.__setattr__(self, "cores", tuple(owned_cores))
        object.__setattr__(self, "coefficients", owned_coefficients)
        object.__setattr__(self, "optimizer_state", copy.deepcopy(dict(self.optimizer_state)))
        object.__setattr__(self, "rng_state", copy.deepcopy(dict(self.rng_state)))
        object.__setattr__(self, "pt_state", copy.deepcopy(dict(self.pt_state)))
        object.__setattr__(self, "hashes", dict(self.hashes))
        object.__setattr__(
            self,
            "j_split",
            {name: tuple(values) for name, values in self.j_split.items()},
        )

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        if destination.exists():
            raise FileExistsError(f"refusing to overwrite checkpoint: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                dir=destination.parent,
                prefix=f".{destination.name}.",
            )
        )
        try:
            arrays = {
                **{f"core_{index:03d}": core for index, core in enumerate(self.cores)},
                "coefficients": self.coefficients,
            }
            model_path = staging / "model.npz"
            atomic_write_npz(model_path, arrays)
            state_arrays: dict[str, np.ndarray] = {}
            optimizer_state = _pack_state(self.optimizer_state, state_arrays)
            rng_state = _pack_state(self.rng_state, state_arrays)
            pt_state = _pack_state(self.pt_state, state_arrays)
            state_path = staging / "state.npz"
            atomic_write_npz(state_path, state_arrays)
            metadata = {
                "schema_version": 1,
                "step": self.step,
                "beta": self.beta,
                "rg_level": self.rg_level,
                "optimizer_state": optimizer_state,
                "rng_state": rng_state,
                "pt_state": pt_state,
                "hashes": dict(self.hashes),
                "j_split": _jsonable(self.j_split),
                "model_sha256": sha256_file(model_path),
                "state_sha256": sha256_file(state_path),
            }
            atomic_write_json(staging / "metadata.json", metadata)
            os.replace(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    @classmethod
    def load(cls, path: str | Path) -> "TrainingCheckpoint":
        source = Path(path)
        metadata_path = source / "metadata.json"
        model_path = source / "model.npz"
        if not metadata_path.is_file() or not model_path.is_file():
            raise FileNotFoundError("checkpoint is incomplete")
        import json

        metadata = json.loads(metadata_path.read_text(encoding="ascii"))
        if sha256_file(model_path) != metadata["model_sha256"]:
            raise ValueError("checkpoint model hash mismatch")
        state_arrays: dict[str, np.ndarray] = {}
        state_path = source / "state.npz"
        if "state_sha256" in metadata:
            if not state_path.is_file() or sha256_file(state_path) != metadata["state_sha256"]:
                raise ValueError("checkpoint sampler-state hash mismatch")
            with np.load(state_path, allow_pickle=False) as archive:
                state_arrays = {name: archive[name].copy() for name in archive.files}
        elif state_path.exists():
            raise ValueError("legacy checkpoint contains an unbound state archive")
        with np.load(model_path, allow_pickle=False) as archive:
            core_names = sorted(name for name in archive.files if name.startswith("core_"))
            cores = tuple(archive[name].copy() for name in core_names)
            coefficients = archive["coefficients"].copy()
        return cls(
            cores=cores,
            coefficients=coefficients,
            optimizer_state=_unpack_state(metadata["optimizer_state"], state_arrays),
            rng_state=_unpack_state(metadata["rng_state"], state_arrays),
            pt_state=_unpack_state(metadata["pt_state"], state_arrays),
            hashes=metadata["hashes"],
            step=int(metadata["step"]),
            beta=float(metadata["beta"]),
            j_split=metadata["j_split"],
            rg_level=int(metadata["rg_level"]),
        )
