"""Checkpointed scientific Stage 6 pilot execution over full PT ladders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields, is_dataclass
import json
import math
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any

import numpy as np

from vmcrg_ref.artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    verified_promote_directory,
)

from .equilibration import (
    EquilibrationRecord,
    EquilibrationReport,
    EquilibrationThresholds,
    assess_equilibration,
)
from .jax_backend import JaxParallelTemperingBackend
from .model import EABonds
from .pilot import (
    CalibrationSpec,
    _build_case,
    load_calibration_cell,
    load_pt_checkpoint,
    save_pt_checkpoint,
)
from .rg import block_majority_3d
from .templates import TemplateEncoder


CALIBRATION_COMPLETE = "CALIBRATION_COMPLETE"
PILOT_PASS = "PILOT_PASS"
PILOT_NEEDS_EXTENSION = "PILOT_NEEDS_EXTENSION"
CORRECTNESS_FAILURE = "CORRECTNESS_FAILURE"
REPRESENTATION_NOT_RUN = "NOT_RUN"

_CLASSIFICATIONS = {
    CALIBRATION_COMPLETE,
    PILOT_PASS,
    PILOT_NEEDS_EXTENSION,
    CORRECTNESS_FAILURE,
}
_OBSERVABLES = (
    "energy",
    "q",
    "q2",
    "q4",
    "qk2_x",
    "qk2_y",
    "qk2_z",
)


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and not any(
        character not in "0123456789abcdef" for character in value
    )


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _jsonable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        if math.isnan(float(value)):
            return "NaN"
        return "Infinity" if float(value) > 0.0 else "-Infinity"
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


@dataclass(frozen=True)
class SciencePilotSpec:
    """Hash-bound scientific schedule for one quenched-disorder PT cell."""

    cell_id: str
    length: int
    temperatures: tuple[float, ...]
    chain_pairs: int
    calibration_sweeps: int
    equilibration_initial_sweeps: int
    equilibration_multiplier: int
    equilibration_maximum_sweeps: int
    measurement_sweeps: int
    equilibration_cadence: int
    measurement_cadence: int
    j_seed: int
    thresholds: EquilibrationThresholds
    templates: tuple[str, ...]
    rg_levels: int
    source_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.cell_id, str)
            or not self.cell_id
            or "/" in self.cell_id
            or ".." in self.cell_id
        ):
            raise ValueError("cell_id must be one safe path component")
        integer_fields = (
            ("length", self.length, 3),
            ("chain_pairs", self.chain_pairs, 1),
            ("calibration_sweeps", self.calibration_sweeps, 1),
            (
                "equilibration_initial_sweeps",
                self.equilibration_initial_sweeps,
                1,
            ),
            ("equilibration_multiplier", self.equilibration_multiplier, 2),
            (
                "equilibration_maximum_sweeps",
                self.equilibration_maximum_sweeps,
                1,
            ),
            ("measurement_sweeps", self.measurement_sweeps, 1),
            ("equilibration_cadence", self.equilibration_cadence, 1),
            ("measurement_cadence", self.measurement_cadence, 1),
            ("j_seed", self.j_seed, 1),
        )
        for name, value, minimum in integer_fields:
            if isinstance(value, (bool, np.bool_)) or not isinstance(
                value, (int, np.integer)
            ):
                raise ValueError(f"{name} must be an integer")
            if int(value) < minimum:
                raise ValueError(f"{name} is below its minimum")
        if self.length % 3:
            raise ValueError("length must be divisible by three for one RG")
        if self.rg_levels != 1:
            raise ValueError("science pilot permits exactly one RG")
        if self.equilibration_initial_sweeps > self.equilibration_maximum_sweeps:
            raise ValueError("equilibration schedule is reversed")
        if self.equilibration_cadence > self.equilibration_initial_sweeps:
            raise ValueError("equilibration cadence exceeds its initial phase")
        if self.measurement_cadence > self.measurement_sweeps:
            raise ValueError("measurement cadence exceeds its scientific phase")
        temperatures = np.asarray(self.temperatures, dtype=np.float64)
        if (
            temperatures.ndim != 1
            or temperatures.size < 2
            or not np.all(np.isfinite(temperatures))
            or np.any(temperatures <= 0.0)
            or np.any(np.diff(1.0 / temperatures) <= 0.0)
        ):
            raise ValueError(
                "temperatures must be finite, positive, and strictly decreasing"
            )
        if not isinstance(self.thresholds, EquilibrationThresholds):
            raise TypeError("thresholds must be EquilibrationThresholds")
        if self.chain_pairs < self.thresholds.min_chains:
            raise ValueError("chain pairs are below the independent-chain threshold")
        templates = tuple(str(value) for value in self.templates)
        if not templates or len(set(templates)) != len(templates) or any(
            value not in {"cube", "cross"} for value in templates
        ):
            raise ValueError("science templates must be unique cube/cross entries")
        hashes = {str(name): str(value) for name, value in self.source_hashes.items()}
        if not hashes or any(not _valid_sha256(value) for value in hashes.values()):
            raise ValueError("source_hashes must contain valid SHA-256 values")
        object.__setattr__(
            self,
            "temperatures",
            tuple(float(value) for value in temperatures),
        )
        object.__setattr__(self, "templates", templates)
        object.__setattr__(self, "source_hashes", hashes)

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json_bytes(_jsonable(asdict(self))))

    @property
    def calibration_spec(self) -> CalibrationSpec:
        return CalibrationSpec(
            cell_id=self.cell_id,
            length=self.length,
            temperatures=self.temperatures,
            chain_pairs=self.chain_pairs,
            calibration_sweeps=self.calibration_sweeps,
            j_seed=self.j_seed,
            swap_bottleneck=self.thresholds.swap_bottleneck,
            swap_target_minimum=self.thresholds.swap_target_min,
            swap_target_maximum=self.thresholds.swap_target_max,
            source_hashes=self.source_hashes,
        )


class ObservationHistory:
    """Per-temperature, per-independent-pair diagnostic time series."""

    def __init__(
        self,
        temperature_count: int,
        chain_pairs: int,
        *,
        sweeps: Sequence[int] = (),
        values: Mapping[str, np.ndarray] | None = None,
    ) -> None:
        if temperature_count < 2 or chain_pairs < 1:
            raise ValueError("history dimensions are invalid")
        self.temperature_count = int(temperature_count)
        self.chain_pairs = int(chain_pairs)
        self._sweeps = [int(value) for value in sweeps]
        if any(value < 1 for value in self._sweeps) or any(
            right <= left
            for left, right in zip(self._sweeps, self._sweeps[1:], strict=False)
        ):
            raise ValueError("history sweeps must be positive and increasing")
        self._values: dict[str, list[np.ndarray]] = {
            name: [] for name in _OBSERVABLES
        }
        if values is not None:
            if set(values) != set(_OBSERVABLES):
                raise ValueError("history observable inventory is incomplete")
            expected = (
                len(self._sweeps),
                self.temperature_count,
                self.chain_pairs,
            )
            for name in _OBSERVABLES:
                array = np.asarray(values[name], dtype=np.float64)
                if array.shape != expected or not np.all(np.isfinite(array)):
                    raise ValueError("history array is invalid")
                self._values[name] = [row.copy() for row in array]

    @classmethod
    def empty(
        cls,
        *,
        temperature_count: int,
        chain_pairs: int,
    ) -> "ObservationHistory":
        return cls(temperature_count, chain_pairs)

    @property
    def count(self) -> int:
        return len(self._sweeps)

    @property
    def sweeps(self) -> tuple[int, ...]:
        return tuple(self._sweeps)

    def append(self, sweep: int, snapshot: Mapping[str, np.ndarray]) -> None:
        selected = int(sweep)
        if selected < 1 or (self._sweeps and selected <= self._sweeps[-1]):
            raise ValueError("history sweep must increase")
        if set(snapshot) != set(_OBSERVABLES):
            raise ValueError("snapshot observable inventory is incomplete")
        expected = (self.temperature_count, self.chain_pairs)
        normalized: dict[str, np.ndarray] = {}
        for name in _OBSERVABLES:
            values = np.asarray(snapshot[name], dtype=np.float64)
            if values.shape != expected or not np.all(np.isfinite(values)):
                raise ValueError(f"snapshot {name} has invalid shape or values")
            normalized[name] = values.copy()
        self._sweeps.append(selected)
        for name, values in normalized.items():
            self._values[name].append(values)

    def arrays(self) -> dict[str, np.ndarray]:
        shape = (0, self.temperature_count, self.chain_pairs)
        return {
            name: (
                np.stack(values, axis=0)
                if values
                else np.empty(shape, dtype=np.float64)
            )
            for name, values in self._values.items()
        }

    def checkpoint_arrays(self, prefix: str) -> dict[str, np.ndarray]:
        result = {
            f"{prefix}_sweeps": np.asarray(self._sweeps, dtype=np.int64),
        }
        result.update(
            {f"{prefix}_{name}": value for name, value in self.arrays().items()}
        )
        return result

    @classmethod
    def from_checkpoint(
        cls,
        archive: Mapping[str, np.ndarray],
        prefix: str,
        *,
        temperature_count: int,
        chain_pairs: int,
    ) -> "ObservationHistory":
        return cls(
            temperature_count,
            chain_pairs,
            sweeps=np.asarray(archive[f"{prefix}_sweeps"], dtype=np.int64),
            values={
                name: np.asarray(archive[f"{prefix}_{name}"], dtype=np.float64)
                for name in _OBSERVABLES
            },
        )


@dataclass
class SciencePilotProgress:
    phase: str
    calibration_completed: int
    equilibration_completed: int
    measurement_completed: int
    equilibration_target: int
    extension_count: int
    checkpoint_index: int
    elapsed_seconds: float
    equilibration_history: ObservationHistory
    measurement_history: ObservationHistory

    @classmethod
    def initial(cls, spec: SciencePilotSpec) -> "SciencePilotProgress":
        history_args = {
            "temperature_count": len(spec.temperatures),
            "chain_pairs": spec.chain_pairs,
        }
        return cls(
            phase="calibration",
            calibration_completed=0,
            equilibration_completed=0,
            measurement_completed=0,
            equilibration_target=spec.equilibration_initial_sweeps,
            extension_count=0,
            checkpoint_index=0,
            elapsed_seconds=0.0,
            equilibration_history=ObservationHistory.empty(**history_args),
            measurement_history=ObservationHistory.empty(**history_args),
        )

    def metadata(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "calibration_completed": self.calibration_completed,
            "equilibration_completed": self.equilibration_completed,
            "measurement_completed": self.measurement_completed,
            "equilibration_target": self.equilibration_target,
            "extension_count": self.extension_count,
            "checkpoint_index": self.checkpoint_index,
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass(frozen=True)
class PTDiagnostics:
    edge_attempts: np.ndarray
    edge_accepts: np.ndarray
    round_trips: np.ndarray
    round_trip_phase: np.ndarray
    time_since_endpoint: np.ndarray

    def __post_init__(self) -> None:
        arrays = {
            "edge_attempts": np.asarray(self.edge_attempts, dtype=np.int64),
            "edge_accepts": np.asarray(self.edge_accepts, dtype=np.int64),
            "round_trips": np.asarray(self.round_trips, dtype=np.int64),
            "round_trip_phase": np.asarray(self.round_trip_phase, dtype=np.int8),
            "time_since_endpoint": np.asarray(
                self.time_since_endpoint,
                dtype=np.int64,
            ),
        }
        if arrays["edge_attempts"].ndim != 1 or arrays["edge_accepts"].shape != arrays[
            "edge_attempts"
        ].shape:
            raise ValueError("PT edge diagnostics are invalid")
        tracker_shape = arrays["round_trips"].shape
        if (
            len(tracker_shape) != 2
            or arrays["round_trip_phase"].shape != tracker_shape
            or arrays["time_since_endpoint"].shape != tracker_shape
            or np.any(arrays["edge_attempts"] < 0)
            or np.any(arrays["edge_accepts"] < 0)
            or np.any(arrays["edge_accepts"] > arrays["edge_attempts"])
            or np.any(arrays["round_trips"] < 0)
            or np.any(arrays["time_since_endpoint"] < 0)
        ):
            raise ValueError("PT tracker diagnostics are invalid")
        for name, value in arrays.items():
            owned = value.copy()
            owned.setflags(write=False)
            object.__setattr__(self, name, owned)

    @classmethod
    def from_backend(cls, backend: JaxParallelTemperingBackend) -> "PTDiagnostics":
        state = backend.checkpoint_state()
        return cls(
            edge_attempts=np.asarray(state["swap_attempts"]),
            edge_accepts=np.asarray(state["swap_accepts"]),
            round_trips=np.asarray(state["round_trips"])[0],
            round_trip_phase=np.asarray(state["round_trip_phase"])[0],
            time_since_endpoint=np.asarray(state["time_since_endpoint"])[0],
        )


def measure_pt_snapshot(
    backend: JaxParallelTemperingBackend,
) -> dict[str, np.ndarray]:
    if not isinstance(backend, JaxParallelTemperingBackend):
        raise TypeError("backend must be JaxParallelTemperingBackend")
    energies = np.asarray(backend.measure()["energy"], dtype=np.float64)
    fields = np.asarray(backend.overlap_fields(), dtype=np.int8)
    if energies.shape[0] != 1 or fields.shape[0] != 1:
        raise ValueError("science cells require exactly one quenched J sample")
    temperatures = energies.shape[1]
    chain_pairs = fields.shape[2]
    length = fields.shape[-1]
    pair_energy = np.mean(
        energies[0].reshape(temperatures, chain_pairs, 2),
        axis=2,
        dtype=np.float64,
    ) / float(length**3)
    q = np.mean(fields[0], axis=(-3, -2, -1), dtype=np.float64)
    spectrum = np.fft.fftn(
        fields[0].astype(np.float64),
        axes=(-3, -2, -1),
    ) / float(length**3)
    return {
        "energy": pair_energy,
        "q": q,
        "q2": q**2,
        "q4": q**4,
        "qk2_x": np.abs(spectrum[..., 1, 0, 0]) ** 2,
        "qk2_y": np.abs(spectrum[..., 0, 1, 0]) ** 2,
        "qk2_z": np.abs(spectrum[..., 0, 0, 1]) ** 2,
    }


def run_observation_block(
    backend: JaxParallelTemperingBackend,
    progress: SciencePilotProgress,
    *,
    phase: str,
    sweeps: int,
    cadence: int = 1,
) -> None:
    if phase not in {"equilibration", "measurement"}:
        raise ValueError("observation phase is invalid")
    if progress.phase != phase:
        raise ValueError("progress phase does not match observation block")
    if sweeps < 0 or cadence < 1:
        raise ValueError("observation block controls are invalid")
    history = (
        progress.equilibration_history
        if phase == "equilibration"
        else progress.measurement_history
    )
    for _ in range(int(sweeps)):
        backend.run_sweeps(1)
        if phase == "equilibration":
            progress.equilibration_completed += 1
            completed = progress.equilibration_completed
        else:
            progress.measurement_completed += 1
            completed = progress.measurement_completed
        if completed % int(cadence) == 0:
            history.append(completed, measure_pt_snapshot(backend))


def _thermal_error_fraction(values: Mapping[str, np.ndarray], temperature: int) -> float:
    fractions: list[float] = []
    for name in ("energy", "q2", "q4", "qk2_x", "qk2_y", "qk2_z"):
        series = np.mean(values[name][:, temperature, :], axis=1, dtype=np.float64)
        half = series.size // 2
        first = float(np.mean(series[:half], dtype=np.float64))
        second = float(np.mean(series[-half:], dtype=np.float64))
        scale = abs(float(np.mean(series, dtype=np.float64))) + float(
            np.std(series, dtype=np.float64)
        )
        fractions.append(
            min(1.0, abs(first - second) / max(scale, np.finfo(float).eps))
        )
    return float(max(fractions))


def build_equilibration_records(
    spec: SciencePilotSpec,
    history: ObservationHistory,
    diagnostics: PTDiagnostics,
    *,
    elapsed_seconds: float,
    extension_count: int,
) -> tuple[tuple[EquilibrationRecord, ...], tuple[EquilibrationReport, ...]]:
    if history.count < 8:
        raise ValueError("equilibration history needs at least eight measurements")
    if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0.0:
        raise ValueError("elapsed_seconds must be positive and finite")
    expected_tracker = (2 * spec.chain_pairs, len(spec.temperatures))
    if diagnostics.round_trips.shape != expected_tracker:
        raise ValueError("PT tracker shape does not match science spec")
    if diagnostics.edge_attempts.shape != (len(spec.temperatures) - 1,):
        raise ValueError("PT edge shape does not match science spec")
    if np.any(diagnostics.edge_attempts <= 0):
        raise ValueError("every PT edge must be attempted before assessment")
    edge_acceptance = diagnostics.edge_accepts / diagnostics.edge_attempts
    pair_trips = np.min(
        diagnostics.round_trips.reshape(
            spec.chain_pairs,
            2,
            len(spec.temperatures),
        ),
        axis=(1, 2),
    )
    tmax_forgetting = bool(
        np.all(
            (diagnostics.round_trip_phase >= 2)
            | (diagnostics.round_trips > 0)
        )
    )
    arrays = history.arrays()
    records: list[EquilibrationRecord] = []
    reports: list[EquilibrationReport] = []
    volume = float(spec.length**3)
    for temperature_index, _temperature in enumerate(spec.temperatures):
        q2 = arrays["q2"][:, temperature_index, :].T
        observables = {
            "energy": arrays["energy"][:, temperature_index, :].T,
            "q2": q2,
            "q4": arrays["q4"][:, temperature_index, :].T,
            "chi0": volume * q2,
            "chik_x": volume * arrays["qk2_x"][:, temperature_index, :].T,
            "chik_y": volume * arrays["qk2_y"][:, temperature_index, :].T,
            "chik_z": volume * arrays["qk2_z"][:, temperature_index, :].T,
        }
        record = EquilibrationRecord(
            j_id=f"{spec.cell_id}@T{temperature_index:03d}",
            edge_acceptance=tuple(float(value) for value in edge_acceptance),
            round_trips=tuple(int(value) for value in pair_trips),
            observables=observables,
            elapsed_seconds=float(elapsed_seconds),
            thermal_error_fraction=_thermal_error_fraction(
                arrays,
                temperature_index,
            ),
            extension_count=int(extension_count),
            tmax_forgetting_passed=tmax_forgetting,
        )
        records.append(record)
        reports.append(assess_equilibration(record, spec.thresholds))
    return tuple(records), tuple(reports)


def build_one_rg_evidence(
    spec: SciencePilotSpec,
    backend: JaxParallelTemperingBackend,
) -> dict[str, np.ndarray]:
    if spec.rg_levels != 1:
        raise ValueError("science pilot permits exactly one RG")
    fields = np.asarray(backend.overlap_fields(), dtype=np.int8)
    if fields.shape[0] != 1:
        raise ValueError("science RG evidence requires one J sample")
    q_prime = np.asarray(
        [
            [block_majority_3d(fields[0, temperature, pair]) for pair in range(spec.chain_pairs)]
            for temperature in range(len(spec.temperatures))
        ],
        dtype=np.int8,
    )
    bonds = EABonds(np.asarray(backend.case.bonds[0], dtype=np.int8))
    result: dict[str, np.ndarray] = {"q_prime": q_prime}
    centers = tuple(np.ndindex(q_prime.shape[-3:]))
    for kind in spec.templates:
        encoder = TemplateEncoder(kind, conditioned=True, rg_level=1)
        result[f"tokens_{kind}"] = np.asarray(
            [
                [
                    [
                        encoder.encode(q_prime[temperature, pair], bonds, center)
                        for center in centers
                    ]
                    for pair in range(spec.chain_pairs)
                ]
                for temperature in range(len(spec.temperatures))
            ],
            dtype=np.int8,
        )
    return result


def _history_checkpoint_arrays(progress: SciencePilotProgress) -> dict[str, np.ndarray]:
    return {
        **progress.equilibration_history.checkpoint_arrays("equilibration"),
        **progress.measurement_history.checkpoint_arrays("measurement"),
    }


def save_science_checkpoint(
    backend: JaxParallelTemperingBackend,
    progress: SciencePilotProgress,
    path: str | Path,
    *,
    spec_sha256: str,
) -> None:
    if not _valid_sha256(spec_sha256):
        raise ValueError("spec_sha256 is invalid")
    expected_sweeps = (
        progress.calibration_completed
        + progress.equilibration_completed
        + progress.measurement_completed
    )
    if backend.sweep_count != expected_sweeps:
        raise ValueError("progress counters do not match sampler sweep count")
    destination = Path(path)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite science checkpoint: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    try:
        save_pt_checkpoint(
            backend,
            staging / "sampler",
            completed_sweeps=backend.sweep_count,
            spec_sha256=spec_sha256,
        )
        history_path = staging / "history.npz"
        atomic_write_npz(history_path, _history_checkpoint_arrays(progress))
        sampler_metadata = staging / "sampler" / "metadata.json"
        sampler_state = staging / "sampler" / "state.npz"
        artifact_hashes = {
            "sampler/metadata.json": sha256_file(sampler_metadata),
            "sampler/state.npz": sha256_file(sampler_state),
            "history.npz": sha256_file(history_path),
        }
        metadata = {
            "schema_version": 1,
            "spec_sha256": spec_sha256,
            "progress": progress.metadata(),
            "rng_state_location": "sampler/state.npz",
            "artifact_hashes": artifact_hashes,
        }
        metadata_path = staging / "metadata.json"
        atomic_write_json(metadata_path, metadata)
        verified_promote_directory(
            staging,
            destination,
            {**artifact_hashes, "metadata.json": sha256_file(metadata_path)},
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def load_science_checkpoint(
    backend: JaxParallelTemperingBackend,
    path: str | Path,
    *,
    expected_spec_sha256: str,
) -> SciencePilotProgress:
    if not _valid_sha256(expected_spec_sha256):
        raise ValueError("expected_spec_sha256 is invalid")
    source = Path(path)
    metadata_path = source / "metadata.json"
    history_path = source / "history.npz"
    if not metadata_path.is_file() or not history_path.is_file():
        raise FileNotFoundError("science checkpoint is incomplete")
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    if metadata.get("schema_version") != 1:
        raise ValueError("science checkpoint schema is unsupported")
    if metadata.get("spec_sha256") != expected_spec_sha256:
        raise ValueError("science checkpoint spec hash mismatch")
    hashes = metadata.get("artifact_hashes")
    if not isinstance(hashes, dict):
        raise ValueError("science checkpoint hashes are missing")
    for relative, digest in hashes.items():
        if not _valid_sha256(digest) or sha256_file(source / relative) != digest:
            raise ValueError(f"science checkpoint hash mismatch: {relative}")
    load_pt_checkpoint(
        backend,
        source / "sampler",
        expected_spec_sha256=expected_spec_sha256,
    )
    raw = metadata.get("progress")
    if not isinstance(raw, dict):
        raise ValueError("science checkpoint progress is missing")
    with np.load(history_path, allow_pickle=False) as archive:
        temperature_count = backend.case.betas.size
        chain_pairs = backend.case.spins.shape[2] // 2
        equilibration = ObservationHistory.from_checkpoint(
            archive,
            "equilibration",
            temperature_count=temperature_count,
            chain_pairs=chain_pairs,
        )
        measurement = ObservationHistory.from_checkpoint(
            archive,
            "measurement",
            temperature_count=temperature_count,
            chain_pairs=chain_pairs,
        )
    progress = SciencePilotProgress(
        phase=str(raw["phase"]),
        calibration_completed=int(raw["calibration_completed"]),
        equilibration_completed=int(raw["equilibration_completed"]),
        measurement_completed=int(raw["measurement_completed"]),
        equilibration_target=int(raw["equilibration_target"]),
        extension_count=int(raw["extension_count"]),
        checkpoint_index=int(raw["checkpoint_index"]),
        elapsed_seconds=float(raw["elapsed_seconds"]),
        equilibration_history=equilibration,
        measurement_history=measurement,
    )
    expected_sweeps = (
        progress.calibration_completed
        + progress.equilibration_completed
        + progress.measurement_completed
    )
    if expected_sweeps != backend.sweep_count:
        raise ValueError("restored progress does not match sampler sweep count")
    return progress


def classify_science_pilot(
    phase: str,
    reports: Sequence[EquilibrationReport],
    *,
    correctness_failure: bool = False,
) -> str:
    if correctness_failure:
        return CORRECTNESS_FAILURE
    if phase == "calibration":
        return CALIBRATION_COMPLETE
    if phase == "complete" and reports and all(report.passed for report in reports):
        return PILOT_PASS
    return PILOT_NEEDS_EXTENSION


def build_science_manifest(
    spec: SciencePilotSpec,
    progress: SciencePilotProgress,
    *,
    classification: str,
    reports: Sequence[EquilibrationReport],
    artifact_hashes: Mapping[str, str],
    error: str | None = None,
) -> dict[str, object]:
    if classification not in _CLASSIFICATIONS:
        raise ValueError("science pilot classification is invalid")
    if any(not _valid_sha256(value) for value in artifact_hashes.values()):
        raise ValueError("science pilot artifact hash is invalid")
    return {
        "schema_version": 1,
        "stage": "stage6",
        "scope": "scientific-stage6-pilot-cell",
        "classification": classification,
        "tc_evidence": False,
        "second_rg_enabled": False,
        "representation_comparison": REPRESENTATION_NOT_RUN,
        "production_freeze_allowed": False,
        "cell_id": spec.cell_id,
        "spec": _jsonable(asdict(spec)),
        "spec_sha256": spec.sha256,
        "progress": progress.metadata(),
        "equilibration": {
            "passed": bool(reports) and all(report.passed for report in reports),
            "reports": [_jsonable(report) for report in reports],
        },
        "artifacts": dict(artifact_hashes),
        "error": error,
    }


def _checkpoint_path(root: Path, progress: SciencePilotProgress) -> Path:
    return root / f"checkpoint-{progress.checkpoint_index:09d}"


def _latest_checkpoint(root: Path) -> Path | None:
    candidates = sorted(
        path
        for path in root.glob("checkpoint-*")
        if path.is_dir() and (path / "metadata.json").is_file()
    )
    return candidates[-1] if candidates else None


def _save_progress_checkpoint(
    backend: JaxParallelTemperingBackend,
    progress: SciencePilotProgress,
    root: Path,
    spec: SciencePilotSpec,
) -> None:
    progress.checkpoint_index += 1
    save_science_checkpoint(
        backend,
        progress,
        _checkpoint_path(root, progress),
        spec_sha256=spec.sha256,
    )
    complete = sorted(
        path
        for path in root.glob("checkpoint-*")
        if path.is_dir() and (path / "metadata.json").is_file()
    )
    for stale in complete[:-2]:
        shutil.rmtree(stale)


def _write_status(
    work: Path,
    spec: SciencePilotSpec,
    progress: SciencePilotProgress,
    classification: str,
    reports: Sequence[EquilibrationReport] = (),
    *,
    error: str | None = None,
) -> dict[str, object]:
    manifest = build_science_manifest(
        spec,
        progress,
        classification=classification,
        reports=reports,
        artifact_hashes={},
        error=error,
    )
    atomic_write_json(work / "status.json", manifest)
    return manifest


def _validate_platform(required_platform: str) -> None:
    import jax

    if required_platform not in {"cpu", "gpu"}:
        raise ValueError("required_platform must be cpu or gpu")
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


def _run_plain_phase(
    backend: JaxParallelTemperingBackend,
    progress: SciencePilotProgress,
    *,
    target: int,
    counter: str,
    checkpoint_every: int,
    checkpoint_root: Path,
    spec: SciencePilotSpec,
) -> None:
    total = target - int(getattr(progress, counter))
    progress_stride = max(1, math.ceil(max(total, 1) / 25))
    next_progress = int(getattr(progress, counter)) + progress_stride
    while int(getattr(progress, counter)) < target:
        count = min(
            checkpoint_every,
            target - int(getattr(progress, counter)),
        )
        started = time.perf_counter()
        backend.run_sweeps(count)
        progress.elapsed_seconds += time.perf_counter() - started
        setattr(progress, counter, int(getattr(progress, counter)) + count)
        _save_progress_checkpoint(backend, progress, checkpoint_root, spec)
        completed = int(getattr(progress, counter))
        if completed >= next_progress or completed == target:
            print(
                f"science cell={spec.cell_id} phase={progress.phase} "
                f"completed={completed}/{target}",
                flush=True,
            )
            next_progress += progress_stride


def _run_observed_phase(
    backend: JaxParallelTemperingBackend,
    progress: SciencePilotProgress,
    *,
    phase: str,
    target: int,
    checkpoint_every: int,
    checkpoint_root: Path,
    spec: SciencePilotSpec,
) -> None:
    counter = (
        "equilibration_completed" if phase == "equilibration" else "measurement_completed"
    )
    total = target - int(getattr(progress, counter))
    progress_stride = max(1, math.ceil(max(total, 1) / 25))
    next_progress = int(getattr(progress, counter)) + progress_stride
    while int(getattr(progress, counter)) < target:
        count = min(
            checkpoint_every,
            target - int(getattr(progress, counter)),
        )
        started = time.perf_counter()
        run_observation_block(
            backend,
            progress,
            phase=phase,
            sweeps=count,
            cadence=(
                spec.equilibration_cadence
                if phase == "equilibration"
                else spec.measurement_cadence
            ),
        )
        progress.elapsed_seconds += time.perf_counter() - started
        _save_progress_checkpoint(backend, progress, checkpoint_root, spec)
        completed = int(getattr(progress, counter))
        if completed >= next_progress or completed == target:
            print(
                f"science cell={spec.cell_id} phase={phase} "
                f"completed={completed}/{target}",
                flush=True,
            )
            next_progress += progress_stride


def run_science_pilot(
    spec: SciencePilotSpec,
    output: str | Path,
    *,
    required_platform: str,
    checkpoint_every: int,
    resume: bool = False,
    calibration_only: bool = False,
) -> dict[str, object]:
    """Run or resume one scientific Stage 6 cell without publishing partial data."""

    if not isinstance(spec, SciencePilotSpec):
        raise TypeError("spec must be SciencePilotSpec")
    if isinstance(checkpoint_every, bool) or not isinstance(
        checkpoint_every, (int, np.integer)
    ) or int(checkpoint_every) < 1:
        raise ValueError("checkpoint_every must be a positive integer")
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite science output: {destination}")
    _validate_platform(required_platform)
    destination.parent.mkdir(parents=True, exist_ok=True)
    work = destination.parent / f".{destination.name}.science-work"
    if work.exists() and not resume:
        raise FileExistsError(f"science work exists; explicit resume required: {work}")
    if not work.exists():
        work.mkdir()
    checkpoint_root = work / "checkpoints"
    checkpoint_root.mkdir(exist_ok=True)
    backend = JaxParallelTemperingBackend(_build_case(spec.calibration_spec))
    progress = SciencePilotProgress.initial(spec)
    if resume:
        checkpoint = _latest_checkpoint(checkpoint_root)
        if checkpoint is None:
            raise FileNotFoundError("no complete science checkpoint is available")
        progress = load_science_checkpoint(
            backend,
            checkpoint,
            expected_spec_sha256=spec.sha256,
        )

    try:
        if progress.calibration_completed < spec.calibration_sweeps:
            progress.phase = "calibration"
            _run_plain_phase(
                backend,
                progress,
                target=spec.calibration_sweeps,
                counter="calibration_completed",
                checkpoint_every=int(checkpoint_every),
                checkpoint_root=checkpoint_root,
                spec=spec,
            )
        if calibration_only:
            return _write_status(
                work,
                spec,
                progress,
                CALIBRATION_COMPLETE,
            )

        progress.phase = "equilibration"
        if progress.equilibration_completed >= progress.equilibration_target:
            diagnostics = PTDiagnostics.from_backend(backend)
            _, existing_reports = build_equilibration_records(
                spec,
                progress.equilibration_history,
                diagnostics,
                elapsed_seconds=max(progress.elapsed_seconds, np.finfo(float).eps),
                extension_count=progress.extension_count,
            )
            if not all(report.passed for report in existing_reports):
                if progress.equilibration_target >= spec.equilibration_maximum_sweeps:
                    return _write_status(
                        work,
                        spec,
                        progress,
                        PILOT_NEEDS_EXTENSION,
                        existing_reports,
                    )
                progress.extension_count += 1
                progress.equilibration_target = min(
                    spec.equilibration_maximum_sweeps,
                    progress.equilibration_target * spec.equilibration_multiplier,
                )
        _run_observed_phase(
            backend,
            progress,
            phase="equilibration",
            target=progress.equilibration_target,
            checkpoint_every=int(checkpoint_every),
            checkpoint_root=checkpoint_root,
            spec=spec,
        )
        diagnostics = PTDiagnostics.from_backend(backend)
        records, reports = build_equilibration_records(
            spec,
            progress.equilibration_history,
            diagnostics,
            elapsed_seconds=max(progress.elapsed_seconds, np.finfo(float).eps),
            extension_count=progress.extension_count,
        )
        if not all(report.passed for report in reports):
            return _write_status(
                work,
                spec,
                progress,
                PILOT_NEEDS_EXTENSION,
                reports,
            )

        progress.phase = "measurement"
        _run_observed_phase(
            backend,
            progress,
            phase="measurement",
            target=spec.measurement_sweeps,
            checkpoint_every=int(checkpoint_every),
            checkpoint_root=checkpoint_root,
            spec=spec,
        )
        progress.phase = "complete"
        rg_evidence = build_one_rg_evidence(spec, backend)
        atomic_write_npz(
            work / "equilibration_history.npz",
            progress.equilibration_history.checkpoint_arrays("equilibration"),
        )
        atomic_write_npz(
            work / "measurement_history.npz",
            progress.measurement_history.checkpoint_arrays("measurement"),
        )
        atomic_write_npz(work / "rg_once.npz", rg_evidence)
        classification = classify_science_pilot("complete", reports)
        status = build_science_manifest(
            spec,
            progress,
            classification=classification,
            reports=reports,
            artifact_hashes={},
        )
        atomic_write_json(work / "status.json", status)
        artifact_hashes = {
            str(path.relative_to(work)): sha256_file(path)
            for path in sorted(work.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }
        manifest = build_science_manifest(
            spec,
            progress,
            classification=classification,
            reports=reports,
            artifact_hashes=artifact_hashes,
        )
        manifest_path = work / "manifest.json"
        atomic_write_json(manifest_path, manifest)
        verified_promote_directory(
            work,
            destination,
            {**artifact_hashes, "manifest.json": sha256_file(manifest_path)},
        )
        print(
            f"science cell={spec.cell_id} phase=complete "
            f"classification={classification} output={destination}",
            flush=True,
        )
        return manifest
    except Exception as error:
        _write_status(
            work,
            spec,
            progress,
            CORRECTNESS_FAILURE,
            error=f"{type(error).__name__}: {error}",
        )
        raise


def load_science_pilot_cell(
    run_spec: str | Path,
    selector: str,
    *,
    track_root: str | Path,
    repo_root: str | Path,
    measurement_cadence: int,
) -> tuple[SciencePilotSpec, Path]:
    calibration, calibration_output = load_calibration_cell(
        run_spec,
        selector,
        track_root=track_root,
        repo_root=repo_root,
    )
    from .workflow import load_stage6_config

    track = Path(track_root).resolve()
    config = load_stage6_config(track / "config/hard_goal/stage6_pilot_v1.toml")
    science_sources = (
        "src/spinglass3d/science_pilot.py",
        "scripts/hard_goal_science_pilot_cell.py",
        "jobs/hard_goal_science_pilot.slurm",
    )
    source_hashes = {
        **dict(calibration.source_hashes),
        **{name: sha256_file(track / name) for name in science_sources},
    }
    thresholds = EquilibrationThresholds(
        swap_bottleneck=config.swap_bottleneck,
        swap_target_min=config.swap_target_minimum,
        swap_target_max=config.swap_target_maximum,
        min_round_trips=config.minimum_round_trips,
        max_rhat=config.maximum_rhat,
        min_ess=config.minimum_ess,
        bin_sigma=config.bin_sigma,
        max_thermal_error_fraction=config.maximum_thermal_error_fraction,
        min_chains=config.chain_pairs,
    )
    spec = SciencePilotSpec(
        cell_id=calibration.cell_id,
        length=calibration.length,
        temperatures=calibration.temperatures,
        chain_pairs=calibration.chain_pairs,
        calibration_sweeps=calibration.calibration_sweeps,
        equilibration_initial_sweeps=config.initial_equilibration_sweeps,
        equilibration_multiplier=config.equilibration_multiplier,
        equilibration_maximum_sweeps=config.maximum_equilibration_sweeps,
        measurement_sweeps=config.measurement_sweeps,
        equilibration_cadence=int(measurement_cadence),
        measurement_cadence=int(measurement_cadence),
        j_seed=calibration.j_seed,
        thresholds=thresholds,
        templates=config.templates,
        rg_levels=1,
        source_hashes=source_hashes,
    )
    run_root = calibration_output.parent.parent
    output = run_root / "science-cells" / spec.cell_id
    return spec, output
