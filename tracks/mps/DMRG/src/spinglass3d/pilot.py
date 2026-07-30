"""Checkpointed Stage 6 temperature-ladder calibration cells."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import tempfile
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from vmcrg_ref.artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    verified_promote_directory,
)

from .backend import BackendCase, checkpoint_nbytes
from .model import EABonds

if TYPE_CHECKING:
    from .jax_backend import JaxParallelTemperingBackend


CALIBRATION_COMPLETE = "CALIBRATION_COMPLETE"
CALIBRATION_EXTENSION_COMPLETE = "CALIBRATION_EXTENSION_COMPLETE"


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and not any(
        character not in "0123456789abcdef" for character in value
    )


@dataclass(frozen=True)
class CalibrationSpec:
    cell_id: str
    length: int
    temperatures: tuple[float, ...]
    chain_pairs: int
    calibration_sweeps: int
    j_seed: int
    swap_bottleneck: float
    swap_target_minimum: float
    swap_target_maximum: float
    source_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.cell_id, str)
            or not self.cell_id
            or "/" in self.cell_id
            or ".." in self.cell_id
        ):
            raise ValueError("cell_id must be one safe path component")
        for name, value, minimum in (
            ("length", self.length, 2),
            ("chain_pairs", self.chain_pairs, 1),
            ("calibration_sweeps", self.calibration_sweeps, 1),
            ("j_seed", self.j_seed, 1),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise ValueError(f"{name} must be an integer")
            if int(value) < minimum:
                raise ValueError(f"{name} is below its minimum")
        values = np.asarray(self.temperatures, dtype=np.float64)
        if (
            values.ndim != 1
            or values.size < 2
            or not np.all(np.isfinite(values))
            or np.any(values <= 0.0)
            or np.any(np.diff(1.0 / values) <= 0.0)
        ):
            raise ValueError(
                "temperatures must be finite, positive, and strictly decreasing"
            )
        thresholds = (
            self.swap_bottleneck,
            self.swap_target_minimum,
            self.swap_target_maximum,
        )
        if not all(math.isfinite(float(value)) for value in thresholds) or not (
            0.0
            <= self.swap_bottleneck
            <= self.swap_target_minimum
            <= self.swap_target_maximum
            <= 1.0
        ):
            raise ValueError("swap thresholds are inconsistent")
        hashes = {str(name): str(value) for name, value in self.source_hashes.items()}
        if not hashes or any(not _valid_sha256(value) for value in hashes.values()):
            raise ValueError("source_hashes must contain valid SHA-256 values")
        object.__setattr__(self, "temperatures", tuple(float(value) for value in values))
        object.__setattr__(self, "source_hashes", hashes)

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json_bytes(asdict(self)))


def _safe_component(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
    ):
        raise ValueError(f"{name} must be one safe path component")
    return value


@dataclass(frozen=True)
class CalibrationCheckpointParent:
    cell_id: str
    manifest_kind: str
    manifest_sha256: str
    checkpoint_spec_sha256: str
    checkpoint_metadata_sha256: str
    checkpoint_state_sha256: str
    completed_sweeps: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_id", _safe_component(self.cell_id, "parent cell_id"))
        if self.manifest_kind not in {"calibration", "calibration_extension"}:
            raise ValueError("parent manifest_kind is invalid")
        for name in (
            "manifest_sha256",
            "checkpoint_spec_sha256",
            "checkpoint_metadata_sha256",
            "checkpoint_state_sha256",
        ):
            if not _valid_sha256(getattr(self, name)):
                raise ValueError(f"parent {name} is invalid")
        if (
            isinstance(self.completed_sweeps, bool)
            or not isinstance(self.completed_sweeps, (int, np.integer))
            or int(self.completed_sweeps) < 1
        ):
            raise ValueError("parent completed_sweeps must be a positive integer")
        object.__setattr__(self, "completed_sweeps", int(self.completed_sweeps))

    @classmethod
    def from_payload(cls, value: object) -> "CalibrationCheckpointParent":
        expected = {
            "cell_id",
            "manifest_kind",
            "manifest_sha256",
            "checkpoint_spec_sha256",
            "checkpoint_metadata_sha256",
            "checkpoint_state_sha256",
            "completed_sweeps",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("parent checkpoint fields are incomplete or unknown")
        return cls(**{name: value[name] for name in expected})


@dataclass(frozen=True)
class CalibrationExtensionSpec:
    schema_version: int
    kind: str
    cell_id: str
    base_cell_id: str
    base_run_id: str
    base_run_spec_sha256: str
    base_package_manifest_sha256: str
    base_calibration_spec_sha256: str
    length: int
    temperatures: tuple[float, ...]
    chain_pairs: int
    j_seed: int
    swap_bottleneck: float
    swap_target_minimum: float
    swap_target_maximum: float
    parent: CalibrationCheckpointParent
    target_completed_sweeps: int
    source_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("extension schema_version must be 1")
        if self.kind != "calibration_extension":
            raise ValueError("extension kind is invalid")
        for name in ("cell_id", "base_cell_id", "base_run_id"):
            object.__setattr__(self, name, _safe_component(getattr(self, name), name))
        for name in (
            "base_run_spec_sha256",
            "base_package_manifest_sha256",
            "base_calibration_spec_sha256",
        ):
            if not _valid_sha256(getattr(self, name)):
                raise ValueError(f"{name} is invalid")
        for name, value, minimum in (
            ("length", self.length, 2),
            ("chain_pairs", self.chain_pairs, 1),
            ("j_seed", self.j_seed, 1),
            ("target_completed_sweeps", self.target_completed_sweeps, 1),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise ValueError(f"{name} must be an integer")
            if int(value) < minimum:
                raise ValueError(f"{name} is below its minimum")
            object.__setattr__(self, name, int(value))
        values = np.asarray(self.temperatures, dtype=np.float64)
        if (
            values.ndim != 1
            or values.size < 2
            or not np.all(np.isfinite(values))
            or np.any(values <= 0.0)
            or np.any(np.diff(1.0 / values) <= 0.0)
        ):
            raise ValueError(
                "temperatures must be finite, positive, and strictly decreasing"
            )
        thresholds = (
            self.swap_bottleneck,
            self.swap_target_minimum,
            self.swap_target_maximum,
        )
        if not all(math.isfinite(float(value)) for value in thresholds) or not (
            0.0
            <= self.swap_bottleneck
            <= self.swap_target_minimum
            <= self.swap_target_maximum
            <= 1.0
        ):
            raise ValueError("swap thresholds are inconsistent")
        parent = (
            self.parent
            if isinstance(self.parent, CalibrationCheckpointParent)
            else CalibrationCheckpointParent.from_payload(self.parent)
        )
        if self.target_completed_sweeps <= parent.completed_sweeps:
            raise ValueError("target_completed_sweeps must be greater than parent")
        hashes = {str(name): str(value) for name, value in self.source_hashes.items()}
        if not hashes or any(not _valid_sha256(value) for value in hashes.values()):
            raise ValueError("source_hashes must contain valid SHA-256 values")
        object.__setattr__(self, "temperatures", tuple(float(value) for value in values))
        object.__setattr__(self, "parent", parent)
        object.__setattr__(self, "source_hashes", hashes)

    @classmethod
    def from_payload(cls, value: object) -> "CalibrationExtensionSpec":
        expected = {
            "schema_version",
            "kind",
            "cell_id",
            "base_cell_id",
            "base_run_id",
            "base_run_spec_sha256",
            "base_package_manifest_sha256",
            "base_calibration_spec_sha256",
            "length",
            "temperatures",
            "chain_pairs",
            "j_seed",
            "swap_bottleneck",
            "swap_target_minimum",
            "swap_target_maximum",
            "parent",
            "target_completed_sweeps",
            "source_hashes",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("extension spec fields are incomplete or unknown")
        payload = {name: value[name] for name in expected}
        payload["temperatures"] = tuple(payload["temperatures"])
        payload["parent"] = CalibrationCheckpointParent.from_payload(payload["parent"])
        return cls(**payload)

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json_bytes(asdict(self)))


def _checkpoint_arrays(state: Mapping[str, object]) -> dict[str, np.ndarray]:
    sampler = state.get("sampler")
    if not isinstance(sampler, Mapping):
        raise ValueError("PT checkpoint sampler state is missing")
    return {
        "spins": np.asarray(sampler["spins"]),
        "local_jax_key": np.asarray(sampler["jax_key"]),
        "local_accepted_changes": np.asarray(
            int(sampler["accepted_changes"]), dtype=np.int64
        ),
        "local_proposed_changes": np.asarray(
            int(sampler["proposed_changes"]), dtype=np.int64
        ),
        "swap_key": np.asarray(state["swap_key"]),
        "replica_ids": np.asarray(state["replica_ids"]),
        "swap_attempts": np.asarray(state["swap_attempts"]),
        "swap_accepts": np.asarray(state["swap_accepts"]),
        "sweep_count": np.asarray(int(state["sweep_count"]), dtype=np.int64),
        "round_trip_phase": np.asarray(state["round_trip_phase"]),
        "round_trips": np.asarray(state["round_trips"]),
        "time_since_endpoint": np.asarray(state["time_since_endpoint"]),
    }


def save_pt_checkpoint(
    backend: JaxParallelTemperingBackend,
    path: str | Path,
    *,
    completed_sweeps: int,
    spec_sha256: str,
) -> None:
    from .jax_backend import JaxParallelTemperingBackend

    if not isinstance(backend, JaxParallelTemperingBackend):
        raise TypeError("backend must be JaxParallelTemperingBackend")
    if isinstance(completed_sweeps, bool) or not isinstance(
        completed_sweeps, (int, np.integer)
    ):
        raise ValueError("completed_sweeps must be an integer")
    if int(completed_sweeps) < 0 or int(completed_sweeps) != backend.sweep_count:
        raise ValueError("completed_sweeps must match backend sweep_count")
    if not _valid_sha256(spec_sha256):
        raise ValueError("spec_sha256 is invalid")
    destination = Path(path)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite PT checkpoint: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            dir=destination.parent,
        )
    )
    try:
        state_path = staging / "state.npz"
        atomic_write_npz(state_path, _checkpoint_arrays(backend.checkpoint_state()))
        metadata = {
            "schema_version": 1,
            "completed_sweeps": int(completed_sweeps),
            "spec_sha256": spec_sha256,
            "state_sha256": sha256_file(state_path),
        }
        metadata_path = staging / "metadata.json"
        atomic_write_json(metadata_path, metadata)
        verified_promote_directory(
            staging,
            destination,
            {
                "state.npz": metadata["state_sha256"],
                "metadata.json": sha256_file(metadata_path),
            },
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def load_pt_checkpoint(
    backend: JaxParallelTemperingBackend,
    path: str | Path,
    *,
    expected_spec_sha256: str,
) -> int:
    from .jax_backend import JaxParallelTemperingBackend

    if not isinstance(backend, JaxParallelTemperingBackend):
        raise TypeError("backend must be JaxParallelTemperingBackend")
    if not _valid_sha256(expected_spec_sha256):
        raise ValueError("expected_spec_sha256 is invalid")
    source = Path(path)
    metadata_path = source / "metadata.json"
    state_path = source / "state.npz"
    if not metadata_path.is_file() or not state_path.is_file():
        raise FileNotFoundError("PT checkpoint is incomplete")
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    if metadata.get("schema_version") != 1:
        raise ValueError("PT checkpoint schema is unsupported")
    if metadata.get("spec_sha256") != expected_spec_sha256:
        raise ValueError("PT checkpoint spec hash mismatch")
    if metadata.get("state_sha256") != sha256_file(state_path):
        raise ValueError("PT checkpoint state hash mismatch")
    with np.load(state_path, allow_pickle=False) as archive:
        required = {
            "spins",
            "local_jax_key",
            "local_accepted_changes",
            "local_proposed_changes",
            "swap_key",
            "replica_ids",
            "swap_attempts",
            "swap_accepts",
            "sweep_count",
            "round_trip_phase",
            "round_trips",
            "time_since_endpoint",
        }
        if set(archive.files) != required:
            raise ValueError("PT checkpoint array inventory is incomplete")
        scalar_names = (
            "local_accepted_changes",
            "local_proposed_changes",
            "sweep_count",
        )
        if any(
            archive[name].dtype != np.dtype(np.int64)
            or archive[name].shape != ()
            for name in scalar_names
        ):
            raise ValueError("PT checkpoint scalar counters must be int64 scalars")
        state = {
            "sampler": {
                "spins": archive["spins"].copy(),
                "jax_key": archive["local_jax_key"].copy(),
                "accepted_changes": int(archive["local_accepted_changes"].item()),
                "proposed_changes": int(archive["local_proposed_changes"].item()),
            },
            "swap_key": archive["swap_key"].copy(),
            "replica_ids": archive["replica_ids"].copy(),
            "swap_attempts": archive["swap_attempts"].copy(),
            "swap_accepts": archive["swap_accepts"].copy(),
            "sweep_count": int(archive["sweep_count"].item()),
            "round_trip_phase": archive["round_trip_phase"].copy(),
            "round_trips": archive["round_trips"].copy(),
            "time_since_endpoint": archive["time_since_endpoint"].copy(),
        }
    raw_completed = metadata.get("completed_sweeps")
    if type(raw_completed) is not int:
        raise ValueError("PT checkpoint completed-sweep count must be an integer")
    completed = raw_completed
    if completed < 0 or completed != int(state["sweep_count"]):
        raise ValueError("PT checkpoint completed-sweep count is inconsistent")
    backend.validate_checkpoint_state(state)
    backend.restore_checkpoint_state(state)
    return completed


def _build_case(spec: CalibrationSpec | CalibrationExtensionSpec) -> BackendCase:
    seeds = np.random.SeedSequence(spec.j_seed).spawn(2)
    bonds = EABonds.sample(spec.length, np.random.default_rng(seeds[0]))
    spins = np.random.default_rng(seeds[1]).choice(
        np.array([-1, 1], dtype=np.int8),
        size=(
            1,
            len(spec.temperatures),
            2 * spec.chain_pairs,
            spec.length,
            spec.length,
            spec.length,
        ),
    )
    backend_seed = int(spec.j_seed % (2**31 - 1)) or 1
    return BackendCase(
        spins=spins,
        bonds=bonds.values[None, ...],
        betas=1.0 / np.asarray(spec.temperatures, dtype=np.float64),
        seed=backend_seed,
    )


def _latest_checkpoint(checkpoint_root: Path) -> Path | None:
    candidates = sorted(
        path
        for path in checkpoint_root.glob("sweep-*")
        if path.is_dir() and (path / "metadata.json").is_file()
    )
    return candidates[-1] if candidates else None


def _latest_extension_checkpoint(checkpoint_root: Path) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    for path in checkpoint_root.glob("sweep-*"):
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"child checkpoint path is not a directory: {path.name}")
        suffix = path.name.removeprefix("sweep-")
        if not suffix.isdigit():
            raise ValueError(f"invalid child checkpoint name: {path.name}")
        candidates.append((int(suffix), path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _validate_extension_work_tree(work: Path, *, resume: bool) -> None:
    if work.is_symlink():
        raise ValueError("calibration extension work path must not be a symlink")
    if not work.exists():
        return
    if not work.is_dir():
        raise ValueError("calibration extension work path is not a directory")
    if not resume:
        raise FileExistsError(
            f"calibration extension work directory exists; explicit resume required: {work}"
        )
    checkpoint_root = work / "checkpoints"
    terminal_checkpoint = work / "checkpoint"
    for path, name in (
        (checkpoint_root, "child checkpoint root"),
        (terminal_checkpoint, "terminal child checkpoint"),
    ):
        if path.is_symlink():
            raise ValueError(f"{name} path must not be a symlink")
        if path.exists() and not path.is_dir():
            raise ValueError(f"{name} path is not a directory")
    if checkpoint_root.exists():
        for path in checkpoint_root.glob("sweep-*"):
            if path.is_symlink() or not path.is_dir():
                raise ValueError(
                    f"child checkpoint path is not a real directory: {path.name}"
                )


def _copy_final_checkpoint_once(source: Path, destination: Path) -> None:
    if source.is_symlink() or destination.is_symlink():
        raise ValueError("terminal child checkpoint paths must not be symlinks")
    expected = {
        path.name: sha256_file(path)
        for path in source.iterdir()
        if path.is_file()
    }
    if set(expected) != {"metadata.json", "state.npz"}:
        raise ValueError("final child checkpoint is incomplete")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("terminal child checkpoint path is not a directory")
        observed = {
            path.name: sha256_file(path)
            for path in destination.iterdir()
            if path.is_file()
        }
        if observed != expected or any(not path.is_file() for path in destination.iterdir()):
            raise ValueError("existing terminal child checkpoint is inconsistent")
        return
    shutil.copytree(source, destination)


def load_bound_parent_checkpoint(
    backend: JaxParallelTemperingBackend,
    checkpoint_path: str | Path,
    parent_ref: CalibrationCheckpointParent,
) -> int:
    """Hash-validate and restore the exact parent checkpoint binding."""

    from .jax_backend import JaxParallelTemperingBackend

    if not isinstance(backend, JaxParallelTemperingBackend):
        raise TypeError("backend must be JaxParallelTemperingBackend")
    if not isinstance(parent_ref, CalibrationCheckpointParent):
        raise TypeError("parent_ref must be CalibrationCheckpointParent")
    checkpoint = Path(checkpoint_path).resolve()
    manifest_path = checkpoint.parent / "manifest.json"
    metadata_path = checkpoint / "metadata.json"
    state_path = checkpoint / "state.npz"
    if not manifest_path.is_file() or not metadata_path.is_file() or not state_path.is_file():
        raise FileNotFoundError("bound parent manifest or checkpoint is incomplete")
    if sha256_file(manifest_path) != parent_ref.manifest_sha256:
        raise ValueError("parent manifest hash mismatch")
    if sha256_file(metadata_path) != parent_ref.checkpoint_metadata_sha256:
        raise ValueError("parent checkpoint metadata hash mismatch")
    if sha256_file(state_path) != parent_ref.checkpoint_state_sha256:
        raise ValueError("parent checkpoint state hash mismatch")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("parent checkpoint metadata is not readable JSON") from error
    if (
        not isinstance(metadata, dict)
        or set(metadata)
        != {"schema_version", "completed_sweeps", "spec_sha256", "state_sha256"}
        or metadata.get("schema_version") != 1
        or metadata.get("completed_sweeps") != parent_ref.completed_sweeps
        or metadata.get("spec_sha256") != parent_ref.checkpoint_spec_sha256
        or metadata.get("state_sha256") != parent_ref.checkpoint_state_sha256
    ):
        raise ValueError("parent checkpoint metadata binding or completed-sweep count mismatch")
    completed = load_pt_checkpoint(
        backend,
        checkpoint,
        expected_spec_sha256=parent_ref.checkpoint_spec_sha256,
    )
    if completed != parent_ref.completed_sweeps:
        raise ValueError("parent checkpoint completed-sweep count mismatch")
    return completed


def _travel_snapshot(backend: JaxParallelTemperingBackend) -> dict[str, object]:
    state = backend.checkpoint_state()
    phase = np.asarray(state["round_trip_phase"], dtype=np.int8)
    trips = np.asarray(state["round_trips"], dtype=np.int64)
    timers = np.asarray(state["time_since_endpoint"], dtype=np.int64)
    return {
        "phase_counts": {
            str(value): int(np.count_nonzero(phase == value)) for value in range(3)
        },
        "completed_tracker_count": int(np.count_nonzero(trips > 0)),
        "endpoint_timer": {
            "minimum": int(np.min(timers)),
            "maximum": int(np.max(timers)),
            "mean": float(np.mean(timers, dtype=np.float64)),
        },
    }


def run_ladder_calibration_extension(
    spec: CalibrationExtensionSpec,
    parent_checkpoint: str | Path,
    output: str | Path,
    *,
    required_platform: str,
    checkpoint_every: int,
    resume: bool = False,
) -> dict[str, object]:
    """Continue one complete parent PT state into an immutable child output."""

    import jax
    from .jax_backend import JaxParallelTemperingBackend

    if not isinstance(spec, CalibrationExtensionSpec):
        raise TypeError("spec must be CalibrationExtensionSpec")
    if required_platform not in {"cpu", "gpu"}:
        raise ValueError("required_platform must be cpu or gpu")
    if (
        isinstance(checkpoint_every, bool)
        or not isinstance(checkpoint_every, (int, np.integer))
        or int(checkpoint_every) < 1
    ):
        raise ValueError("checkpoint_every must be a positive integer")
    destination = Path(output)
    if destination.is_symlink() or destination.exists():
        raise FileExistsError(f"refusing to overwrite calibration extension output: {destination}")
    work = destination.parent / f".{destination.name}.work"
    _validate_extension_work_tree(work, resume=resume)
    devices = jax.devices()
    if jax.default_backend() != required_platform or not devices or any(
        device.platform != required_platform for device in devices
    ):
        raise RuntimeError(
            f"required JAX platform {required_platform!r}, got "
            f"backend={jax.default_backend()!r} devices={devices!r}"
        )
    if not bool(jax.config.jax_enable_x64):
        raise RuntimeError("JAX float64 mode is required")

    backend = JaxParallelTemperingBackend(_build_case(spec))
    start = load_bound_parent_checkpoint(backend, parent_checkpoint, spec.parent)
    if start != spec.parent.completed_sweeps:
        raise ValueError("restored parent sweep count is inconsistent")
    parent_attempts = backend.swap_attempts.copy()
    parent_accepts = backend.swap_accepts.copy()
    parent_travel = _travel_snapshot(backend)
    parent_proposals = backend.proposed_changes

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not work.exists():
        work.mkdir()
    checkpoint_root = work / "checkpoints"
    checkpoint_root.mkdir(exist_ok=True)
    completed = start
    if resume:
        latest = _latest_extension_checkpoint(checkpoint_root)
        if latest is not None:
            completed = load_pt_checkpoint(
                backend,
                latest,
                expected_spec_sha256=spec.sha256,
            )
            declared_sweep = int(latest.name.removeprefix("sweep-"))
            if completed != declared_sweep:
                raise ValueError(
                    "child checkpoint name does not match its completed sweep count"
                )
    if completed < start or completed > spec.target_completed_sweeps:
        raise ValueError("child checkpoint is outside the declared extension interval")

    started = time.perf_counter()
    invocation_proposals_before = backend.proposed_changes
    print(
        f"calibration-extension cell={spec.cell_id} phase=start "
        f"completed={completed}/{spec.target_completed_sweeps}",
        flush=True,
    )
    while completed < spec.target_completed_sweeps:
        count = min(int(checkpoint_every), spec.target_completed_sweeps - completed)
        backend.run_sweeps(count, progress_every=count)
        completed += count
        checkpoint = checkpoint_root / f"sweep-{completed:09d}"
        save_pt_checkpoint(
            backend,
            checkpoint,
            completed_sweeps=completed,
            spec_sha256=spec.sha256,
        )
        print(
            f"calibration-extension cell={spec.cell_id} phase=checkpoint "
            f"completed={completed}/{spec.target_completed_sweeps}",
            flush=True,
        )
    elapsed = time.perf_counter() - started
    attempts = backend.swap_attempts.copy()
    accepts = backend.swap_accepts.copy()
    window_attempts = attempts - parent_attempts
    window_accepts = accepts - parent_accepts
    all_edges_attempted = bool(np.all(attempts > 0))
    window_all_edges_attempted = bool(np.all(window_attempts > 0))
    if not all_edges_attempted or not window_all_edges_attempted:
        raise RuntimeError("extension did not attempt every swap edge cumulatively and in-window")
    acceptance = accepts / attempts
    window_acceptance = window_accepts / window_attempts
    bottleneck_passed = bool(np.min(acceptance) >= spec.swap_bottleneck)
    cumulative_band_passed = bool(
        np.all(acceptance >= spec.swap_target_minimum)
        and np.all(acceptance <= spec.swap_target_maximum)
    )
    window_band_passed = bool(
        np.all(window_acceptance >= spec.swap_target_minimum)
        and np.all(window_acceptance <= spec.swap_target_maximum)
    )
    ladder_decision = (
        "PASS"
        if bottleneck_passed and cumulative_band_passed and window_band_passed
        else "RECALIBRATE"
    )
    resources = backend.resource_snapshot()
    final_checkpoint = checkpoint_root / f"sweep-{completed:09d}"
    _copy_final_checkpoint_once(final_checkpoint, work / "checkpoint")
    lineage_names = (
        "base_cell_id",
        "base_run_id",
        "base_run_spec_sha256",
        "base_package_manifest_sha256",
        "base_calibration_spec_sha256",
    )
    manifest = {
        "schema_version": 1,
        "stage": "stage6",
        "phase": "calibration_extension",
        "classification": CALIBRATION_EXTENSION_COMPLETE,
        "scope": "stage6-ladder-calibration-extension-only",
        "status": "complete",
        "scientific_evidence": False,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "cell_id": spec.cell_id,
        "extension_spec": asdict(spec),
        "extension_spec_sha256": spec.sha256,
        "lineage": {
            **{name: getattr(spec, name) for name in lineage_names},
            "parent_cell_id": spec.parent.cell_id,
            "parent_manifest_kind": spec.parent.manifest_kind,
            "parent_manifest_sha256": spec.parent.manifest_sha256,
            "parent_checkpoint_spec_sha256": spec.parent.checkpoint_spec_sha256,
            "parent_checkpoint_metadata_sha256": (
                spec.parent.checkpoint_metadata_sha256
            ),
            "parent_checkpoint_state_sha256": spec.parent.checkpoint_state_sha256,
        },
        "start_completed_sweeps": start,
        "completed_sweeps": completed,
        "parallel_tempering": {
            "all_edges_attempted": all_edges_attempted,
            "edge_attempts": [int(value) for value in attempts],
            "edge_accepts": [int(value) for value in accepts],
            "edge_acceptance": [float(value) for value in acceptance],
            "bottleneck_passed": bottleneck_passed,
            "target_band_passed": cumulative_band_passed,
            "ladder_decision": ladder_decision,
            "round_trips_min": int(np.min(backend.round_trips)),
            "round_trips_max": int(np.max(backend.round_trips)),
            "extension_window": {
                "start_completed_sweeps": start,
                "completed_sweeps": completed,
                "all_edges_attempted": window_all_edges_attempted,
                "edge_attempts": [int(value) for value in window_attempts],
                "edge_accepts": [int(value) for value in window_accepts],
                "edge_acceptance": [float(value) for value in window_acceptance],
                "target_band_passed": window_band_passed,
            },
        },
        "travel": {
            "parent": parent_travel,
            "child": _travel_snapshot(backend),
        },
        "runtime": {
            "host": platform.node(),
            "python": platform.python_version(),
            "jax": importlib.metadata.version("jax"),
            "jaxlib": importlib.metadata.version("jaxlib"),
            "default_backend": jax.default_backend(),
            "devices": [str(device) for device in devices],
            "x64_enabled": bool(jax.config.jax_enable_x64),
            "elapsed_seconds": elapsed,
            "spin_proposals": backend.proposed_changes - parent_proposals,
            "spin_proposals_per_second": (
                (backend.proposed_changes - invocation_proposals_before)
                / max(elapsed, 1e-12)
            ),
            "invocation_spin_proposals": (
                backend.proposed_changes - invocation_proposals_before
            ),
            "peak_host_memory_bytes": int(resources["host_rss_bytes"]),
            "peak_device_memory_bytes": int(resources["device_memory_bytes"]),
            "backend_compile_seconds": float(resources["compile_seconds"]),
            "checkpoint_bytes": checkpoint_nbytes(backend.checkpoint_state()),
        },
    }
    artifact_hashes = {
        str(path.relative_to(work)): sha256_file(path)
        for path in sorted(work.rglob("*"))
        if path.is_file() and path != work / "manifest.json"
    }
    manifest["artifact_hashes"] = artifact_hashes
    manifest_path = work / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    verified_promote_directory(
        work,
        destination,
        {**artifact_hashes, "manifest.json": sha256_file(manifest_path)},
    )
    print(
        f"calibration-extension cell={spec.cell_id} phase=complete "
        f"ladder_decision={ladder_decision} output={destination}",
        flush=True,
    )
    return manifest


def load_calibration_cell(
    run_spec: str | Path,
    selector: str,
    *,
    track_root: str | Path,
    repo_root: str | Path,
) -> tuple[CalibrationSpec, Path]:
    """Resolve one opaque Stage 6 cell after rebuilding the fixed run spec."""

    from .workflow import build_pilot_run_spec, load_stage6_config

    run_spec_path = Path(run_spec).resolve()
    track = Path(track_root).resolve()
    repository = Path(repo_root).resolve()
    payload = json.loads(run_spec_path.read_text(encoding="ascii"))
    if payload.get("schema_version") != 1 or not isinstance(
        payload.get("run_id"), str
    ):
        raise ValueError("Stage 6 run spec schema is invalid")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Stage 6 run spec provenance is missing")
    if provenance.get("config_path") != "config/hard_goal/stage6_pilot_v1.toml":
        raise ValueError("Stage 6 config path is not fixed")
    if provenance.get("design_path") != "config/hard_goal/design_v1.toml":
        raise ValueError("Hard Goal design path is not fixed")
    config_path = track / str(provenance["config_path"])
    design_path = track / str(provenance["design_path"])
    if provenance.get("config_sha256") != sha256_file(config_path):
        raise ValueError("Stage 6 config hash mismatch")
    if provenance.get("design_sha256") != sha256_file(design_path):
        raise ValueError("Hard Goal design hash mismatch")
    config = load_stage6_config(config_path)
    expected = build_pilot_run_spec(config, str(payload["run_id"]))
    if payload != expected:
        raise ValueError("Stage 6 run spec differs from the fixed generated matrix")

    cells = payload["cells"]
    matches = [cell for cell in cells if str(cell.get("cell_id")) == str(selector)]
    if not matches and str(selector).isdigit():
        index = int(str(selector)) - 1
        if 0 <= index < len(cells):
            matches = [cells[index]]
    if len(matches) != 1:
        raise ValueError(f"Stage 6 cell selector is not unique: {selector}")
    cell = matches[0]
    params = cell["params"]
    output_value = Path(str(params["output"]))
    output = (
        output_value.resolve()
        if output_value.is_absolute()
        else (repository / output_value).resolve()
    )
    allowed_output = (repository / "results" / "hard_goal").resolve()
    if not output.is_relative_to(allowed_output):
        raise ValueError("Stage 6 cell output escapes results/hard_goal")
    source_hashes = {
        "config/hard_goal/stage6_pilot_v1.toml": sha256_file(config_path),
        "config/hard_goal/design_v1.toml": sha256_file(design_path),
        "run_spec.json": sha256_file(run_spec_path),
        **{
            str(name): str(digest)
            for name, digest in sorted(
                payload["provenance"]["source_sha256"].items()
            )
        },
    }
    thresholds = payload["settings"]["thresholds"]
    spec = CalibrationSpec(
        cell_id=str(cell["cell_id"]),
        length=int(params["length"]),
        temperatures=tuple(float(value) for value in params["temperatures"]),
        chain_pairs=int(params["chain_pairs"]),
        calibration_sweeps=int(
            payload["settings"]["sampling"]["calibration_sweeps"]
        ),
        j_seed=int(params["j_seed"]),
        swap_bottleneck=float(thresholds["swap_bottleneck"]),
        swap_target_minimum=float(thresholds["swap_target_minimum"]),
        swap_target_maximum=float(thresholds["swap_target_maximum"]),
        source_hashes=source_hashes,
    )
    return spec, output


def run_ladder_calibration(
    spec: CalibrationSpec,
    output: str | Path,
    *,
    required_platform: str,
    checkpoint_every: int,
    resume: bool = False,
) -> dict[str, object]:
    import jax
    from .jax_backend import JaxParallelTemperingBackend

    if not isinstance(spec, CalibrationSpec):
        raise TypeError("spec must be CalibrationSpec")
    if required_platform not in {"cpu", "gpu"}:
        raise ValueError("required_platform must be cpu or gpu")
    if isinstance(checkpoint_every, bool) or not isinstance(
        checkpoint_every, (int, np.integer)
    ):
        raise ValueError("checkpoint_every must be an integer")
    if int(checkpoint_every) < 1:
        raise ValueError("checkpoint_every must be positive")
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite calibration output: {destination}")
    devices = jax.devices()
    if jax.default_backend() != required_platform or not devices or any(
        device.platform != required_platform for device in devices
    ):
        raise RuntimeError(
            f"required JAX platform {required_platform!r}, got "
            f"backend={jax.default_backend()!r} devices={devices!r}"
        )
    if not bool(jax.config.jax_enable_x64):
        raise RuntimeError("JAX float64 mode is required")

    destination.parent.mkdir(parents=True, exist_ok=True)
    work = destination.parent / f".{destination.name}.work"
    if work.exists() and not resume:
        raise FileExistsError(
            f"calibration work directory exists; explicit resume required: {work}"
        )
    if not work.exists():
        work.mkdir()
    checkpoint_root = work / "checkpoints"
    checkpoint_root.mkdir(exist_ok=True)
    backend = JaxParallelTemperingBackend(_build_case(spec))
    completed = 0
    if resume:
        latest = _latest_checkpoint(checkpoint_root)
        if latest is None:
            raise FileNotFoundError("no complete PT checkpoint is available to resume")
        completed = load_pt_checkpoint(
            backend,
            latest,
            expected_spec_sha256=spec.sha256,
        )
    if completed > spec.calibration_sweeps:
        raise ValueError("checkpoint is beyond the declared calibration budget")

    started = time.perf_counter()
    proposals_before = backend.proposed_changes
    print(
        f"calibration cell={spec.cell_id} phase=start "
        f"completed={completed}/{spec.calibration_sweeps}",
        flush=True,
    )
    while completed < spec.calibration_sweeps:
        count = min(int(checkpoint_every), spec.calibration_sweeps - completed)
        backend.run_sweeps(
            count,
            progress_every=count,
        )
        completed += count
        checkpoint = checkpoint_root / f"sweep-{completed:09d}"
        save_pt_checkpoint(
            backend,
            checkpoint,
            completed_sweeps=completed,
            spec_sha256=spec.sha256,
        )
        print(
            f"calibration cell={spec.cell_id} phase=checkpoint "
            f"completed={completed}/{spec.calibration_sweeps}",
            flush=True,
        )
    elapsed = time.perf_counter() - started
    attempts = backend.swap_attempts
    accepts = backend.swap_accepts
    all_edges_attempted = bool(np.all(attempts > 0))
    if not all_edges_attempted:
        raise RuntimeError("calibration did not attempt every swap edge")
    edge_acceptance = accepts / attempts
    bottleneck_passed = bool(np.min(edge_acceptance) >= spec.swap_bottleneck)
    target_band_passed = bool(
        np.all(edge_acceptance >= spec.swap_target_minimum)
        and np.all(edge_acceptance <= spec.swap_target_maximum)
    )
    ladder_decision = "PASS" if bottleneck_passed and target_band_passed else "RECALIBRATE"
    energies = backend.measure()["energy"].astype(np.float64)
    fields = backend.overlap_fields().astype(np.float64)
    q = np.mean(fields, axis=(-3, -2, -1), dtype=np.float64)
    resources = backend.resource_snapshot()

    final_checkpoint = checkpoint_root / f"sweep-{completed:09d}"
    shutil.copytree(final_checkpoint, work / "checkpoint")
    manifest = {
        "schema_version": 1,
        "stage": "stage6",
        "classification": CALIBRATION_COMPLETE,
        "status": "complete",
        "scope": "stage6-ladder-calibration-only",
        "tc_evidence": False,
        "second_rg_enabled": False,
        "cell_id": spec.cell_id,
        "spec": asdict(spec),
        "spec_sha256": spec.sha256,
        "completed_sweeps": completed,
        "parallel_tempering": {
            "all_edges_attempted": all_edges_attempted,
            "edge_attempts": [int(value) for value in attempts],
            "edge_accepts": [int(value) for value in accepts],
            "edge_acceptance": [float(value) for value in edge_acceptance],
            "bottleneck_passed": bottleneck_passed,
            "target_band_passed": target_band_passed,
            "ladder_decision": ladder_decision,
            "round_trips_min": int(np.min(backend.round_trips)),
            "round_trips_max": int(np.max(backend.round_trips)),
        },
        "terminal_observables": {
            "energy_per_site_mean": [
                float(value)
                for value in np.mean(energies, axis=(0, 2), dtype=np.float64)
                / spec.length**3
            ],
            "q2_mean": [
                float(value)
                for value in np.mean(q * q, axis=(0, 2), dtype=np.float64)
            ],
        },
        "runtime": {
            "host": platform.node(),
            "python": platform.python_version(),
            "jax": importlib.metadata.version("jax"),
            "jaxlib": importlib.metadata.version("jaxlib"),
            "default_backend": jax.default_backend(),
            "devices": [str(device) for device in devices],
            "x64_enabled": bool(jax.config.jax_enable_x64),
            "elapsed_seconds": elapsed,
            "spin_proposals": backend.proposed_changes - proposals_before,
            "spin_proposals_per_second": (
                (backend.proposed_changes - proposals_before) / elapsed
            ),
            "peak_host_memory_bytes": int(resources["host_rss_bytes"]),
            "peak_device_memory_bytes": int(resources["device_memory_bytes"]),
            "backend_compile_seconds": float(resources["compile_seconds"]),
            "checkpoint_bytes": checkpoint_nbytes(backend.checkpoint_state()),
        },
    }
    artifact_hashes = {
        str(path.relative_to(work)): sha256_file(path)
        for path in sorted(work.rglob("*"))
        if path.is_file()
    }
    manifest["artifact_hashes"] = artifact_hashes
    manifest_path = work / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    promotion_hashes = {
        **artifact_hashes,
        "manifest.json": sha256_file(manifest_path),
    }
    verified_promote_directory(work, destination, promotion_hashes)
    print(
        f"calibration cell={spec.cell_id} phase=complete "
        f"ladder_decision={ladder_decision} output={destination}",
        flush=True,
    )
    return manifest
