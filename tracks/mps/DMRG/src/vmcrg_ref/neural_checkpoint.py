"""Atomic, hash-linked checkpoints for pure-neural Issue #28 runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

import numpy as np

from .artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    verified_promote_directory,
)
from .neural_energy import D4EvenLocalMLP


_ARTIFACTS = ("model.npz", "optimizer.npz", "state.json")


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"checkpoint value is not JSON serializable: {type(value).__name__}")


def _validate_hash(value: str | None, name: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA-256")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be hexadecimal") from error


def _array_record(value: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(np.asarray(value))
    if array.dtype.hasobject:
        raise ValueError("checkpoint arrays cannot have object dtype")
    return {
        "shape": list(array.shape),
        "dtype": array.dtype.str,
        "sha256": sha256_bytes(array.tobytes(order="C")),
    }


@dataclass(frozen=True)
class NeuralCheckpoint:
    model: D4EvenLocalMLP
    fixed_linear_bias: np.ndarray
    update: int
    schedule_state: Mapping[str, Any]
    polyak_state: Mapping[str, np.ndarray]
    rng_states: Mapping[str, Any]
    bundle_id: str
    round_index: int
    predecessor_manifest_sha256: str | None
    protocol_sha256: str
    code_sha256: str
    operator_basis_sha256: str
    gauge_reference_sha256: str
    seed_bundle_sha256: str
    stop_state: Mapping[str, Any]
    metadata: Mapping[str, Any]
    gauge_energies: np.ndarray


@dataclass(frozen=True)
class CheckpointExpectations:
    bundle_id: str
    round_index: int
    predecessor_manifest_sha256: str | None
    protocol_sha256: str
    code_sha256: str
    operator_basis_sha256: str
    gauge_reference_sha256: str
    seed_bundle_sha256: str
    gauge_spins: np.ndarray
    energy_atol: float = 1e-10


def _validate_checkpoint(checkpoint: NeuralCheckpoint) -> tuple[np.ndarray, np.ndarray]:
    bias = np.asarray(checkpoint.fixed_linear_bias, dtype=np.float64)
    if bias.shape != (13,) or not np.array_equal(
        bias, np.zeros(13, dtype=np.float64)
    ):
        raise ValueError("pure-neural checkpoint requires an exact zero 13-operator branch")
    if checkpoint.update < 0:
        raise ValueError("checkpoint update cannot be negative")
    if not checkpoint.bundle_id:
        raise ValueError("checkpoint bundle id is required")
    if checkpoint.round_index < 1:
        raise ValueError("checkpoint round must be positive")
    for name in (
        "protocol_sha256",
        "code_sha256",
        "operator_basis_sha256",
        "gauge_reference_sha256",
        "seed_bundle_sha256",
    ):
        _validate_hash(getattr(checkpoint, name), name.replace("_", " "))
    _validate_hash(
        checkpoint.predecessor_manifest_sha256,
        "predecessor manifest hash",
        optional=checkpoint.round_index == 1,
    )
    if checkpoint.round_index > 1 and checkpoint.predecessor_manifest_sha256 is None:
        raise ValueError("later rounds require a predecessor manifest hash")
    model_arrays = (
        checkpoint.model.weight_in,
        checkpoint.model.bias_hidden,
        checkpoint.model.weight_out,
    )
    if not all(np.all(np.isfinite(value)) for value in model_arrays):
        raise ValueError("checkpoint model parameters must be finite")
    gauge_energies = np.asarray(checkpoint.gauge_energies, dtype=np.float64)
    if gauge_energies.ndim != 1 or gauge_energies.size < 2 or not np.all(
        np.isfinite(gauge_energies)
    ):
        raise ValueError("checkpoint gauge energies must be a finite vector")
    required_polyak = {
        "weight_in_sum": checkpoint.model.weight_in.shape,
        "bias_hidden_sum": checkpoint.model.bias_hidden.shape,
        "weight_out_sum": checkpoint.model.weight_out.shape,
        "sample_count": (),
    }
    if set(checkpoint.polyak_state) != set(required_polyak):
        raise ValueError("checkpoint Polyak state fields are incomplete")
    for name, shape in required_polyak.items():
        value = np.asarray(checkpoint.polyak_state[name])
        if value.shape != shape or not np.all(np.isfinite(value)):
            raise ValueError(f"checkpoint Polyak field {name} is invalid")
    if int(np.asarray(checkpoint.polyak_state["sample_count"])) < 0:
        raise ValueError("checkpoint Polyak sample count cannot be negative")
    _json_ready(checkpoint.schedule_state)
    _json_ready(checkpoint.rng_states)
    _json_ready(checkpoint.stop_state)
    _json_ready(checkpoint.metadata)
    return bias.copy(), gauge_energies.copy()


def _logical_payload(
    checkpoint: NeuralCheckpoint,
    bias: np.ndarray,
    gauge_energies: np.ndarray,
) -> dict[str, Any]:
    arrays = {
        "weight_in": _array_record(checkpoint.model.weight_in),
        "bias_hidden": _array_record(checkpoint.model.bias_hidden),
        "weight_out": _array_record(checkpoint.model.weight_out),
        "fixed_linear_bias": _array_record(bias),
        "gauge_energies": _array_record(gauge_energies),
        **{
            f"polyak/{name}": _array_record(np.asarray(value))
            for name, value in checkpoint.polyak_state.items()
        },
    }
    return {
        "schema_version": 1,
        "architecture": {
            "radius": checkpoint.model.radius,
            "hidden": checkpoint.model.hidden,
            "feature_mode": checkpoint.model.feature_mode,
        },
        "arrays": arrays,
        "update": checkpoint.update,
        "schedule_state": _json_ready(checkpoint.schedule_state),
        "rng_states": _json_ready(checkpoint.rng_states),
        "bundle_id": checkpoint.bundle_id,
        "round_index": checkpoint.round_index,
        "predecessor_manifest_sha256": checkpoint.predecessor_manifest_sha256,
        "protocol_sha256": checkpoint.protocol_sha256,
        "code_sha256": checkpoint.code_sha256,
        "operator_basis_sha256": checkpoint.operator_basis_sha256,
        "gauge_reference_sha256": checkpoint.gauge_reference_sha256,
        "seed_bundle_sha256": checkpoint.seed_bundle_sha256,
        "stop_state": _json_ready(checkpoint.stop_state),
        "metadata": _json_ready(checkpoint.metadata),
    }


def save_neural_checkpoint(
    directory: str | Path,
    checkpoint: NeuralCheckpoint,
) -> dict[str, Any]:
    root = Path(directory)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty checkpoint: {root}")
    bias, gauge_energies = _validate_checkpoint(checkpoint)
    logical = _logical_payload(checkpoint, bias, gauge_energies)
    checkpoint_sha256 = sha256_bytes(canonical_json_bytes(logical))
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{root.name}.staging-", dir=root.parent)
    )
    try:
        atomic_write_npz(
            staging / "model.npz",
            {
                "schema_version": np.asarray(1, dtype=np.int64),
                "radius": np.asarray(checkpoint.model.radius, dtype=np.int64),
                "hidden": np.asarray(checkpoint.model.hidden, dtype=np.int64),
                "feature_mode": np.asarray(checkpoint.model.feature_mode),
                "weight_in": checkpoint.model.weight_in,
                "bias_hidden": checkpoint.model.bias_hidden,
                "weight_out": checkpoint.model.weight_out,
                "fixed_linear_bias": bias,
                "gauge_energies": gauge_energies,
            },
        )
        atomic_write_npz(
            staging / "optimizer.npz",
            {name: np.asarray(value) for name, value in checkpoint.polyak_state.items()},
        )
        state = {**logical, "checkpoint_sha256": checkpoint_sha256}
        atomic_write_json(staging / "state.json", state)
        artifact_hashes = {
            name: sha256_file(staging / name) for name in _ARTIFACTS
        }
        manifest = {
            "schema_version": 1,
            "checkpoint_sha256": checkpoint_sha256,
            "artifacts": artifact_hashes,
        }
        atomic_write_json(staging / "manifest.json", manifest)
        expected = {
            **artifact_hashes,
            "manifest.json": sha256_file(staging / "manifest.json"),
        }
        if set(path.name for path in staging.iterdir()) != set(expected):
            raise ValueError("checkpoint staging directory contains unexpected files")
        verified_promote_directory(staging, root, expected)
        return manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _read_manifest(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise FileNotFoundError(f"complete neural checkpoint does not exist: {root}")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"checkpoint manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported neural checkpoint manifest schema")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACTS):
        raise ValueError("checkpoint manifest artifact list is invalid")
    for name, expected_hash in artifacts.items():
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"checkpoint artifact is missing: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"checkpoint hash mismatch for {name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
    return manifest


def _expect_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"checkpoint {label} mismatch: expected {expected}, got {actual}")


def load_neural_checkpoint(
    directory: str | Path,
    expected: CheckpointExpectations,
) -> NeuralCheckpoint:
    root = Path(directory)
    manifest = _read_manifest(root)
    state = json.loads((root / "state.json").read_text(encoding="ascii"))
    if state.get("schema_version") != 1:
        raise ValueError("unsupported neural checkpoint state schema")
    _expect_equal(state.get("protocol_sha256"), expected.protocol_sha256, "protocol hash")
    _expect_equal(state.get("code_sha256"), expected.code_sha256, "code hash")
    _expect_equal(
        state.get("operator_basis_sha256"),
        expected.operator_basis_sha256,
        "operator basis hash",
    )
    _expect_equal(
        state.get("gauge_reference_sha256"),
        expected.gauge_reference_sha256,
        "gauge reference hash",
    )
    _expect_equal(
        state.get("seed_bundle_sha256"),
        expected.seed_bundle_sha256,
        "seed bundle hash",
    )
    _expect_equal(state.get("bundle_id"), expected.bundle_id, "bundle id")
    _expect_equal(state.get("round_index"), expected.round_index, "round")
    _expect_equal(
        state.get("predecessor_manifest_sha256"),
        expected.predecessor_manifest_sha256,
        "predecessor manifest hash",
    )
    _expect_equal(
        state.get("checkpoint_sha256"),
        manifest.get("checkpoint_sha256"),
        "content hash",
    )

    with np.load(root / "model.npz", allow_pickle=False) as archive:
        required = {
            "schema_version",
            "radius",
            "hidden",
            "feature_mode",
            "weight_in",
            "bias_hidden",
            "weight_out",
            "fixed_linear_bias",
            "gauge_energies",
        }
        if set(archive.files) != required:
            raise ValueError("neural checkpoint model fields are invalid")
        if int(archive["schema_version"]) != 1:
            raise ValueError("unsupported neural checkpoint model schema")
        model = D4EvenLocalMLP(
            int(archive["radius"]),
            int(archive["hidden"]),
            archive["weight_in"],
            archive["bias_hidden"],
            archive["weight_out"],
            feature_mode=str(archive["feature_mode"]),
        )
        bias = np.asarray(archive["fixed_linear_bias"], dtype=np.float64).copy()
        gauge_energies = np.asarray(archive["gauge_energies"], dtype=np.float64).copy()
    with np.load(root / "optimizer.npz", allow_pickle=False) as archive:
        polyak_state = {name: archive[name].copy() for name in archive.files}

    checkpoint = NeuralCheckpoint(
        model=model,
        fixed_linear_bias=bias,
        update=int(state["update"]),
        schedule_state=dict(state["schedule_state"]),
        polyak_state=polyak_state,
        rng_states=dict(state["rng_states"]),
        bundle_id=str(state["bundle_id"]),
        round_index=int(state["round_index"]),
        predecessor_manifest_sha256=state["predecessor_manifest_sha256"],
        protocol_sha256=str(state["protocol_sha256"]),
        code_sha256=str(state["code_sha256"]),
        operator_basis_sha256=str(state["operator_basis_sha256"]),
        gauge_reference_sha256=str(state["gauge_reference_sha256"]),
        seed_bundle_sha256=str(state["seed_bundle_sha256"]),
        stop_state=dict(state["stop_state"]),
        metadata=dict(state["metadata"]),
        gauge_energies=gauge_energies,
    )
    validated_bias, validated_gauge = _validate_checkpoint(checkpoint)
    logical = _logical_payload(checkpoint, validated_bias, validated_gauge)
    actual_content_hash = sha256_bytes(canonical_json_bytes(logical))
    _expect_equal(
        actual_content_hash,
        manifest.get("checkpoint_sha256"),
        "content hash",
    )

    gauge_spins = np.asarray(expected.gauge_spins, dtype=np.int8)
    if gauge_spins.ndim != 3 or gauge_spins.shape[0] != gauge_energies.size:
        raise ValueError("expected gauge reference configurations have the wrong shape")
    if not np.all((gauge_spins == -1) | (gauge_spins == 1)):
        raise ValueError("expected gauge reference contains invalid spins")
    if sha256_bytes(np.ascontiguousarray(gauge_spins).tobytes(order="C")) != expected.gauge_reference_sha256:
        raise ValueError("expected gauge reference hash does not match its configurations")
    if expected.energy_atol <= 0.0 or not np.isfinite(expected.energy_atol):
        raise ValueError("checkpoint energy tolerance must be positive and finite")
    observed = np.asarray([model.energy(spins) for spins in gauge_spins])
    difference = observed - gauge_energies
    difference -= difference.mean()
    residual = float(np.max(np.abs(difference)))
    if residual > expected.energy_atol:
        raise ValueError(
            "checkpoint gauge energy mismatch after removing one additive constant: "
            f"{residual} > {expected.energy_atol}"
        )
    bias.setflags(write=False)
    gauge_energies.setflags(write=False)
    return checkpoint
