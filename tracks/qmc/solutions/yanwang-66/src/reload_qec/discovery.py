"""Audit, aggregate, and extend paired discovery experiment phases."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analyze import verify_checksums
from .artifacts import INPUT_KEYS, LABEL_KEYS, MANIFEST_SCHEMA
from .candidate import run as run_candidate
from .config import SimulationRequest
from .geometry import Geometry
from .matrix import MATRIX_SCHEMA, load_matrix
from .stats import benjamini_hochberg, paired_comparison


ANALYSIS_SCHEMA = "q66-discovery-analysis-v1"
CONTINUATION_SCHEMA = "q66-discovery-continuation-v1"
CONTINUATION_GROUP_SCHEMA = "q66-discovery-continuation-group-v1"
INITIAL_GROUP_SCHEMA = "q66-discovery-group-v1"
MIN_LOGICAL_FAILURES = 400
MAX_DISCOVERY_SHOTS = 2_000_000
FDR_Q = 0.05
DISTANCES = (3, 5)
ROUND_FACTORS = (1, 2)
BASES = ("X", "Z")
NOISE_PAIRS = (
    (0.0001, 0.0001),
    (0.001, 0.001),
    (0.003, 0.003),
    (0.001, 0.003),
    (0.003, 0.001),
)
LOSS_PROBABILITIES = (0.0, 0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03)
WORST_VALIDATED_SECONDS_PER_SHOT = {
    (3, 3): 0.0020223480752292744,
    (3, 6): 0.004059506441308258,
    (5, 5): 0.007070904446436543,
    (5, 10): 0.01471902721641527,
}
CONTINUATION_RUNTIME_FACTOR = 1.2
CONTINUATION_BUNDLE_BUDGET_SECONDS = 6 * 60 * 60
PARALLEL_POLICY_WORKERS = 8


class DiscoveryError(ValueError):
    """Raised when discovery evidence is incomplete or inconsistent."""


@dataclass(frozen=True)
class PhaseGroup:
    phase_group_index: int
    source_group_index: int
    physical_key: dict[str, Any]
    requests: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Phase:
    phase_index: int
    spec_path: Path
    spec_sha256: str
    results_root: Path
    kind: str
    groups: dict[int, PhaseGroup]


@dataclass(frozen=True)
class LoadedRun:
    manifest: dict[str, Any]
    shot_id: np.ndarray
    logical_failure: np.ndarray
    aggregate: dict[str, Any]


@dataclass(frozen=True)
class PreviousAnalysis:
    root: Path
    summary: dict[str, Any]
    phases: tuple[Phase, ...]
    cell_rows: tuple[dict[str, Any], ...]
    packed_failures: np.ndarray
    shot_counts: np.ndarray


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def _policy_key(policy: dict[str, Any]) -> str:
    return json.dumps(policy, sort_keys=True, separators=(",", ":"))


def _paired_request_view(request: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in request.items()
        if key not in {"run_id", "shots", "shot_start", "shard_size"}
    }


def _wilson_interval(failures: int, shots: int) -> tuple[float, float]:
    z = 1.959963984540054
    rate = failures / shots
    denominator = 1.0 + z * z / shots
    center = (rate + z * z / (2.0 * shots)) / denominator
    half_width = (
        z
        * ((rate * (1.0 - rate) / shots + z * z / (4.0 * shots * shots)) ** 0.5)
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _zero_failure_upper(shots: int) -> float:
    return 1.0 - 0.05 ** (1.0 / shots)


def _bootstrap_seed(matrix_sha256: str, group_index: int, policy: str) -> int:
    payload = (
        b"q66-discovery-bootstrap-v1\0"
        + bytes.fromhex(matrix_sha256)
        + group_index.to_bytes(4, "little")
        + policy.encode("ascii")
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def _expected_policies(distance: int) -> tuple[dict[str, Any], ...]:
    return (
        {"name": "none"},
        {"name": "immediate"},
        {"name": "periodic", "interval": 1},
        {"name": "periodic", "interval": distance},
        {"name": "periodic", "interval": 2 * distance},
        {"name": "threshold", "fraction": 0.02},
        {"name": "threshold", "fraction": 0.05},
        {"name": "threshold", "fraction": 0.10},
    )


def _expected_seed(physical_key: dict[str, Any]) -> int:
    canonical = json.dumps(
        physical_key, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    digest = hashlib.sha256(b"q66-discovery-seed-v1\0" + canonical).digest()
    return int.from_bytes(digest[:8], "little")


def _expected_physical_keys() -> list[dict[str, Any]]:
    return [
        {
            "distance": distance,
            "rounds": factor * distance,
            "basis": basis,
            "p": p,
            "p_m": p_m,
            "p_loss": p_loss,
        }
        for distance in DISTANCES
        for factor in ROUND_FACTORS
        for basis in BASES
        for p, p_m in NOISE_PAIRS
        for p_loss in LOSS_PROBABILITIES
    ]


def _validate_initial_matrix(matrix: dict[str, Any]) -> None:
    if matrix.get("schema_version") != MATRIX_SCHEMA:
        raise DiscoveryError("initial matrix schema mismatch")
    if matrix.get("group_count") != 280 or matrix.get("cell_count") != 2_240:
        raise DiscoveryError("initial matrix is not the frozen 280/2240 expansion")
    if matrix.get("shots_per_cell") != 20_000:
        raise DiscoveryError("initial matrix does not start at 20,000 shots per cell")
    groups = matrix.get("groups")
    if not isinstance(groups, list) or len(groups) != 280:
        raise DiscoveryError("initial matrix group list is incomplete")
    expected_physical_keys = _expected_physical_keys()
    run_ids: set[str] = set()
    instance_files: set[str] = set()
    for group_index, (group, expected_physical) in enumerate(
        zip(groups, expected_physical_keys, strict=True)
    ):
        if group.get("group_index") != group_index:
            raise DiscoveryError("initial matrix group order is not contiguous")
        if group.get("physical_key") != expected_physical:
            raise DiscoveryError(
                "initial matrix physical grid/order differs from frozen"
            )
        requests = group.get("requests")
        if not isinstance(requests, list) or len(requests) != 8:
            raise DiscoveryError(
                f"initial group {group_index} does not have 8 policies"
            )
        expected_policies = _expected_policies(int(expected_physical["distance"]))
        if tuple(request["policy"] for request in requests) != expected_policies:
            raise DiscoveryError("initial matrix policy set/order differs from frozen")
        for request_value, expected_policy in zip(
            requests, expected_policies, strict=True
        ):
            request = SimulationRequest.from_dict(request_value)
            if request.shots != 20_000 or request.shot_start != 0:
                raise DiscoveryError("initial request shot range is not frozen")
            if request.shard_size != matrix.get("shard_size"):
                raise DiscoveryError("initial request shard size differs from matrix")
            if request.distance != expected_physical["distance"]:
                raise DiscoveryError("request distance differs from physical group")
            if request.rounds != expected_physical["rounds"]:
                raise DiscoveryError("request rounds differ from physical group")
            if request.basis != expected_physical["basis"]:
                raise DiscoveryError("request basis differs from physical group")
            if (request.p, request.p_m, request.p_loss) != (
                expected_physical["p"],
                expected_physical["p_m"],
                expected_physical["p_loss"],
            ):
                raise DiscoveryError("request noise differs from physical group")
            if request.policy.as_dict() != expected_policy:
                raise DiscoveryError("request policy differs from frozen policy")
            if request.master_seed != _expected_seed(expected_physical):
                raise DiscoveryError(
                    "request master seed differs from frozen derivation"
                )
            if (
                request.reload.delay_rounds != 0
                or request.reload.reset_error_probability != 0.0
                or request.reload.failure_probability != 0.0
            ):
                raise DiscoveryError("initial discovery matrix is not ideal reload")
            if request.source_commit != matrix.get("source_commit"):
                raise DiscoveryError("request source commit differs from matrix")
            if request.environment_lock_sha256 != matrix.get(
                "environment_lock_sha256"
            ):
                raise DiscoveryError("request environment lock differs from matrix")
            instance_files.add(str(request.instance_file))
            if request.run_id in run_ids:
                raise DiscoveryError(f"duplicate initial run ID {request.run_id}")
            run_ids.add(request.run_id)
    if len(instance_files) != 1:
        raise DiscoveryError("initial matrix uses multiple instance databases")


def _load_phase(
    spec_path: Path,
    results_root: Path,
    *,
    phase_index: int,
    initial_matrix_sha256: str,
) -> Phase:
    spec_sha256 = _sha256(spec_path)
    value = json.loads(spec_path.read_text(encoding="ascii"))
    groups: dict[int, PhaseGroup] = {}
    if value.get("schema_version") == MATRIX_SCHEMA:
        if phase_index != 1 or spec_sha256 != initial_matrix_sha256:
            raise DiscoveryError("only phase 1 may use the frozen initial matrix")
        kind = "initial"
        raw_groups = value["groups"]
        for group in raw_groups:
            source_index = int(group["group_index"])
            groups[source_index] = PhaseGroup(
                phase_group_index=source_index,
                source_group_index=source_index,
                physical_key=dict(group["physical_key"]),
                requests=tuple(dict(request) for request in group["requests"]),
            )
    elif value.get("schema_version") == CONTINUATION_SCHEMA:
        kind = "continuation"
        if value.get("phase_index") != phase_index:
            raise DiscoveryError("continuation phases must be supplied in order")
        if value.get("initial_matrix_sha256") != initial_matrix_sha256:
            raise DiscoveryError("continuation plan names a different initial matrix")
        raw_groups = _validate_executable_plan(value)
        for local_index, group in enumerate(raw_groups):
            if group.get("phase_group_index") != local_index:
                raise DiscoveryError("continuation phase group order is not contiguous")
            source_index = int(group["source_group_index"])
            if source_index in groups:
                raise DiscoveryError("duplicate source group in continuation plan")
            groups[source_index] = PhaseGroup(
                phase_group_index=local_index,
                source_group_index=source_index,
                physical_key=dict(group["physical_key"]),
                requests=tuple(dict(request) for request in group["requests"]),
            )
    else:
        raise DiscoveryError(f"unsupported phase spec {spec_path}")
    return Phase(
        phase_index=phase_index,
        spec_path=spec_path,
        spec_sha256=spec_sha256,
        results_root=results_root,
        kind=kind,
        groups=groups,
    )


def _validate_phase_sequence(phases: list[Phase], source_group_count: int) -> None:
    if not phases or set(phases[0].groups) != set(range(source_group_count)):
        raise DiscoveryError("phase 1 must contain every frozen physical group")
    retired: set[int] = set()
    previous = set(phases[0].groups)
    for phase in phases[1:]:
        current = set(phase.groups)
        if not current <= previous:
            raise DiscoveryError("a retired physical group reappears in a later phase")
        retired.update(previous - current)
        if current & retired:
            raise DiscoveryError("continuation phases are not a monotone subset")
        previous = current


def _expected_checksum_names(manifest: dict[str, Any]) -> set[str]:
    names = {"manifest.json", "aggregates.parquet", "run.log"}
    for shard in manifest["shards"]:
        names.update({shard["inputs"], shard["labels"]})
    return names


def _actual_checksum_names(run_dir: Path) -> set[str]:
    names: list[str] = []
    checksum_path = run_dir / "checksums.sha256"
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        _, separator, name = line.partition("  ")
        if separator != "  " or not name or "/" in name or "\\" in name:
            raise DiscoveryError(f"invalid checksum entry in {run_dir}: {line!r}")
        names.append(name)
    if len(names) != len(set(names)):
        raise DiscoveryError(f"duplicate checksum names in {run_dir}")
    return set(names)


def _validate_shard_contract(
    run_dir: Path, manifest: dict[str, Any], request: SimulationRequest
) -> None:
    expected_count = math.ceil(request.shots / request.shard_size)
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != expected_count:
        raise DiscoveryError(f"shard count mismatch in {run_dir}")
    for shard_index, shard in enumerate(shards):
        start = request.shot_start + shard_index * request.shard_size
        stop = min(request.shot_start + request.shots, start + request.shard_size)
        expected = {
            "index": shard_index,
            "shot_start": start,
            "shot_stop": stop,
            "inputs": f"shots-{shard_index:05d}.npz",
            "labels": f"labels-{shard_index:05d}.npz",
        }
        if shard != expected:
            raise DiscoveryError(f"shard metadata mismatch in {run_dir}")
    if _actual_checksum_names(run_dir) != _expected_checksum_names(manifest):
        raise DiscoveryError(f"checksum coverage mismatch in {run_dir}")
    expected_files = _expected_checksum_names(manifest) | {"checksums.sha256"}
    actual_entries = {path.name for path in run_dir.iterdir()}
    if actual_entries != expected_files:
        raise DiscoveryError(f"run directory contains missing/extra files: {run_dir}")


def _audit_payloads(
    run_dir: Path,
    manifest: dict[str, Any],
    request: SimulationRequest,
    geometry: Geometry,
) -> dict[str, int]:
    counts = {
        "loss_events": 0,
        "reload_requests": 0,
        "reload_successes": 0,
        "reload_failures": 0,
        "missing_site_boundaries": 0,
    }
    n_checks = len(geometry.relevant_checks)
    n_sites = geometry.n_sites
    schema_shapes = {
        "shot_id": (),
        "detection_events": (request.rounds + 1, n_checks),
        "syndrome_valid_mask": (request.rounds, n_checks),
        "missing_mask": (request.rounds + 1, n_sites),
        "erasure_mask": (request.rounds, n_sites),
        "loss_mask": (request.rounds, n_sites),
        "reload_request_mask": (request.rounds, n_sites),
        "reload_mask": (request.rounds + 1, n_sites),
        "reload_failure_mask": (request.rounds + 1, n_sites),
        "logical_observable": (1,),
        "decoder_prediction": (1,),
        "logical_failure": (),
        "catastrophic_loss": (),
        "reload_reset_fault_mask": (request.rounds + 1, n_sites),
    }
    expected_schema = {
        key: {
            "dtype": str(np.dtype(np.uint64 if key == "shot_id" else np.uint8)),
            "shape_per_shot": list(shape),
        }
        for key, shape in sorted(schema_shapes.items())
    }
    if manifest.get("array_schema") != expected_schema:
        raise DiscoveryError(f"manifest array schema mismatch: {run_dir}")
    for shard in manifest["shards"]:
        shard_shots = int(shard["shot_stop"]) - int(shard["shot_start"])
        input_shapes = {
            "shot_id": (shard_shots,),
            "detection_events": (shard_shots, request.rounds + 1, n_checks),
            "syndrome_valid_mask": (shard_shots, request.rounds, n_checks),
            "missing_mask": (shard_shots, request.rounds + 1, n_sites),
            "erasure_mask": (shard_shots, request.rounds, n_sites),
            "loss_mask": (shard_shots, request.rounds, n_sites),
            "reload_request_mask": (shard_shots, request.rounds, n_sites),
            "reload_mask": (shard_shots, request.rounds + 1, n_sites),
            "reload_failure_mask": (shard_shots, request.rounds + 1, n_sites),
        }
        label_shapes = {
            "shot_id": (shard_shots,),
            "logical_observable": (shard_shots, 1),
            "decoder_prediction": (shard_shots, 1),
            "logical_failure": (shard_shots,),
            "catastrophic_loss": (shard_shots,),
            "reload_reset_fault_mask": (
                shard_shots,
                request.rounds + 1,
                n_sites,
            ),
        }
        expected_ids = np.arange(
            shard["shot_start"], shard["shot_stop"], dtype=np.uint64
        )
        with np.load(run_dir / shard["inputs"], allow_pickle=False) as payload:
            if set(payload.files) != set(INPUT_KEYS):
                raise DiscoveryError(f"input shard schema mismatch: {run_dir}")
            for key, shape in input_shapes.items():
                array = np.asarray(payload[key])
                expected_dtype = np.dtype(np.uint64 if key == "shot_id" else np.uint8)
                if array.shape != shape or array.dtype != expected_dtype:
                    raise DiscoveryError(f"input {key} shape/dtype mismatch: {run_dir}")
                if key == "shot_id":
                    if not np.array_equal(array, expected_ids):
                        raise DiscoveryError(
                            f"input shard shot IDs mismatch: {run_dir}"
                        )
                elif np.any(array > 1):
                    raise DiscoveryError(f"input {key} is not binary: {run_dir}")
            counts["loss_events"] += int(np.count_nonzero(payload["loss_mask"]))
            counts["reload_requests"] += int(
                np.count_nonzero(payload["reload_request_mask"])
            )
            counts["reload_successes"] += int(
                np.count_nonzero(payload["reload_mask"])
            )
            counts["reload_failures"] += int(
                np.count_nonzero(payload["reload_failure_mask"])
            )
            counts["missing_site_boundaries"] += int(
                np.count_nonzero(payload["missing_mask"])
            )
        with np.load(run_dir / shard["labels"], allow_pickle=False) as payload:
            if set(payload.files) != set(LABEL_KEYS):
                raise DiscoveryError(f"label shard schema mismatch: {run_dir}")
            for key, shape in label_shapes.items():
                array = np.asarray(payload[key])
                expected_dtype = np.dtype(np.uint64 if key == "shot_id" else np.uint8)
                if array.shape != shape or array.dtype != expected_dtype:
                    raise DiscoveryError(f"label {key} shape/dtype mismatch: {run_dir}")
                if key == "shot_id":
                    if not np.array_equal(array, expected_ids):
                        raise DiscoveryError(
                            f"label shard shot IDs mismatch: {run_dir}"
                        )
                elif np.any(array > 1):
                    raise DiscoveryError(f"label {key} is not binary: {run_dir}")
    return counts


def _validate_run_aggregate(
    run_dir: Path,
    manifest: dict[str, Any],
    request: SimulationRequest,
    labels: dict[str, np.ndarray],
    payload_counts: dict[str, int],
) -> dict[str, Any]:
    aggregate = manifest.get("aggregate")
    if not isinstance(aggregate, dict):
        raise DiscoveryError(f"run aggregate is missing: {run_dir}")
    frame = pd.read_parquet(run_dir / "aggregates.parquet")
    if len(frame) != 1 or set(frame.columns) != set(aggregate):
        raise DiscoveryError(f"aggregate parquet schema mismatch: {run_dir}")
    parquet = frame.iloc[0].to_dict()
    for key, value in aggregate.items():
        observed = parquet[key]
        if isinstance(value, float):
            if not math.isclose(float(observed), value, rel_tol=1e-15, abs_tol=0.0):
                raise DiscoveryError(f"manifest/parquet mismatch for {key}: {run_dir}")
        elif observed != value:
            raise DiscoveryError(f"manifest/parquet mismatch for {key}: {run_dir}")

    failures = int(np.count_nonzero(labels["logical_failure"]))
    catastrophic = int(np.count_nonzero(labels["catastrophic_loss"]))
    lower, upper = _wilson_interval(failures, request.shots)
    expected: dict[str, int | float | str] = {
        "run_id": request.run_id,
        "shots": request.shots,
        "logical_failures": failures,
        "logical_error_rate": failures / request.shots,
        "wilson_95_lower": lower,
        "wilson_95_upper": upper,
        "catastrophic_shots": catastrophic,
        **payload_counts,
    }
    compressed_bytes = sum(
        (run_dir / shard[key]).stat().st_size
        for shard in manifest["shards"]
        for key in ("inputs", "labels")
    )
    expected["compressed_npz_bytes"] = compressed_bytes
    expected["bytes_per_shot"] = compressed_bytes / request.shots
    required_extra = {"wall_seconds", "shots_per_second", "distinct_graphs_accumulated"}
    if set(aggregate) != set(expected) | required_extra:
        raise DiscoveryError(f"aggregate fields differ from frozen contract: {run_dir}")
    for key, value in expected.items():
        observed = aggregate[key]
        if isinstance(value, float):
            if not math.isclose(float(observed), value, rel_tol=1e-12, abs_tol=0.0):
                raise DiscoveryError(f"aggregate value mismatch for {key}: {run_dir}")
        elif observed != value:
            raise DiscoveryError(f"aggregate value mismatch for {key}: {run_dir}")
    wall_seconds = float(aggregate["wall_seconds"])
    shots_per_second = float(aggregate["shots_per_second"])
    if not math.isfinite(wall_seconds) or wall_seconds <= 0.0:
        raise DiscoveryError(f"aggregate wall time is invalid: {run_dir}")
    if not math.isclose(
        shots_per_second,
        request.shots / wall_seconds,
        rel_tol=1e-12,
        abs_tol=0.0,
    ):
        raise DiscoveryError(f"aggregate throughput mismatch: {run_dir}")
    if int(aggregate["distinct_graphs_accumulated"]) < 1:
        raise DiscoveryError(f"aggregate graph count is invalid: {run_dir}")
    return aggregate


def _load_label_view(
    run_dir: Path, manifest: dict[str, Any]
) -> dict[str, np.ndarray]:
    keys = (
        "shot_id",
        "logical_observable",
        "decoder_prediction",
        "logical_failure",
        "catastrophic_loss",
    )
    parts: dict[str, list[np.ndarray]] = {key: [] for key in keys}
    for shard in manifest["shards"]:
        with np.load(run_dir / shard["labels"], allow_pickle=False) as payload:
            for key in keys:
                parts[key].append(np.asarray(payload[key]))
    labels = {key: np.concatenate(values, axis=0) for key, values in parts.items()}
    expected_failure = np.bitwise_xor(
        labels["logical_observable"].reshape(-1),
        labels["decoder_prediction"].reshape(-1),
    )
    if not np.array_equal(expected_failure, labels["logical_failure"].reshape(-1)):
        raise DiscoveryError(f"logical failure is not observable XOR decode: {run_dir}")
    return labels


def _load_expected_run(
    run_dir: Path, expected_request: dict[str, Any], geometry: Geometry
) -> LoadedRun:
    expected = SimulationRequest.from_dict(expected_request)
    verify_checksums(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="ascii"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise DiscoveryError(f"run manifest schema mismatch: {run_dir}")
    if manifest.get("status") != "completed":
        raise DiscoveryError(f"run is not completed: {run_dir}")
    if manifest.get("request") != expected.as_dict():
        raise DiscoveryError(f"run request differs from phase spec: {run_dir}")
    if manifest.get("run_id") != expected.run_id:
        raise DiscoveryError(f"run ID differs from phase spec: {run_dir}")
    if manifest.get("source_commit") != expected.source_commit:
        raise DiscoveryError(f"run source commit mismatch: {run_dir}")
    if manifest.get("shot_range") != [
        expected.shot_start,
        expected.shot_start + expected.shots,
    ]:
        raise DiscoveryError(f"run shot range mismatch: {run_dir}")
    if manifest.get("input_keys") != list(INPUT_KEYS):
        raise DiscoveryError(f"input schema mismatch: {run_dir}")
    if manifest.get("label_keys") != list(LABEL_KEYS):
        raise DiscoveryError(f"label schema mismatch: {run_dir}")
    expected_instance = {
        "instance_id": geometry.instance_id,
        "provenance": geometry.provenance,
        "site_order": [site.site_id for site in geometry.sites],
        "check_order": [check.check_id for check in geometry.relevant_checks],
    }
    if manifest.get("instance") != expected_instance:
        raise DiscoveryError(f"run instance identity/order mismatch: {run_dir}")
    decoder = manifest.get("decoder")
    if not isinstance(decoder, dict):
        raise DiscoveryError(f"run decoder provenance is missing: {run_dir}")
    if decoder.get("name") != "mask-conditioned-pymatching":
        raise DiscoveryError(f"run decoder name mismatch: {run_dir}")
    expected_decoder = {
        "data_probability": 2.0 * expected.p / 3.0,
        "measurement_probability": expected.p_m,
        "erasure_weight": 0.0,
    }
    for key, value in expected_decoder.items():
        if not math.isclose(float(decoder.get(key)), value, rel_tol=1e-15):
            raise DiscoveryError(f"run decoder {key} mismatch: {run_dir}")
    environment = manifest.get("environment")
    if not isinstance(environment, dict):
        raise DiscoveryError(f"run environment provenance is missing: {run_dir}")
    if environment.get("mode") != "locked-venv-slurm":
        raise DiscoveryError(f"run environment mode mismatch: {run_dir}")
    if environment.get("environment_lock_sha256") != expected.environment_lock_sha256:
        raise DiscoveryError(f"run environment lock mismatch: {run_dir}")
    slurm_job_id = environment.get("slurm_job_id")
    if slurm_job_id in {None, "not-under-slurm"}:
        raise DiscoveryError(f"run lacks Slurm provenance: {run_dir}")
    _validate_shard_contract(run_dir, manifest, expected)
    labels = _load_label_view(run_dir, manifest)
    payload_counts = _audit_payloads(run_dir, manifest, expected, geometry)

    shot_id = np.asarray(labels["shot_id"])
    logical_failure = np.asarray(labels["logical_failure"]).reshape(-1)
    expected_ids = np.arange(
        expected.shot_start,
        expected.shot_start + expected.shots,
        dtype=np.uint64,
    )
    if shot_id.dtype != np.uint64 or not np.array_equal(shot_id, expected_ids):
        raise DiscoveryError(f"shot IDs are not the exact requested range: {run_dir}")
    if logical_failure.dtype != np.uint8 or np.any(logical_failure > 1):
        raise DiscoveryError(f"logical failures are not binary uint8: {run_dir}")

    aggregate = _validate_run_aggregate(
        run_dir, manifest, expected, labels, payload_counts
    )
    return LoadedRun(manifest, shot_id, logical_failure, aggregate)


def _validate_group_manifest(phase: Phase, group: PhaseGroup) -> Path:
    group_root = phase.results_root / f"group-{group.source_group_index:03d}"
    path = group_root / "group-manifest.json"
    value = json.loads(path.read_text(encoding="ascii"))
    expected_runs = [request["run_id"] for request in group.requests]
    if phase.kind == "initial":
        expected_keys = {
            "schema_version",
            "matrix_sha256",
            "group_index",
            "slurm_array_job_id",
            "slurm_array_task_id",
            "runs",
        }
        if set(value) != expected_keys:
            raise DiscoveryError(f"initial group manifest schema mismatch: {path}")
        if value.get("schema_version") != INITIAL_GROUP_SCHEMA:
            raise DiscoveryError(f"initial group manifest version mismatch: {path}")
        if value.get("matrix_sha256") != phase.spec_sha256:
            raise DiscoveryError(f"initial group matrix checksum mismatch: {path}")
        if value.get("group_index") != group.source_group_index:
            raise DiscoveryError(f"initial group index mismatch: {path}")
    else:
        expected_keys = {
            "schema_version",
            "plan_sha256",
            "phase_index",
            "phase_group_index",
            "source_group_index",
            "slurm_array_job_id",
            "slurm_array_task_id",
            "runs",
        }
        if set(value) != expected_keys:
            raise DiscoveryError(f"continuation group manifest schema mismatch: {path}")
        if value.get("schema_version") != CONTINUATION_GROUP_SCHEMA:
            raise DiscoveryError(
                f"continuation group manifest version mismatch: {path}"
            )
        if value.get("plan_sha256") != phase.spec_sha256:
            raise DiscoveryError(f"continuation plan checksum mismatch: {path}")
        if value.get("phase_index") != phase.phase_index:
            raise DiscoveryError(f"continuation phase index mismatch: {path}")
        if value.get("phase_group_index") != group.phase_group_index:
            raise DiscoveryError(f"continuation local group index mismatch: {path}")
        if value.get("source_group_index") != group.source_group_index:
            raise DiscoveryError(f"continuation source group index mismatch: {path}")
    if value.get("slurm_array_job_id") != phase.results_root.name:
        raise DiscoveryError(f"group came from a different Slurm array: {path}")
    if phase.kind == "initial":
        expected_task_id = _initial_bundle_task_index(group.source_group_index)
    else:
        plan = json.loads(phase.spec_path.read_text(encoding="ascii"))
        expected_task_id = _continuation_bundle_task_index(
            plan, group.phase_group_index
        )
    if value.get("slurm_array_task_id") != str(expected_task_id):
        raise DiscoveryError(f"group came from a different Slurm task: {path}")
    if value.get("runs") != expected_runs:
        raise DiscoveryError(f"group run list mismatch: {path}")
    expected_entries = set(expected_runs) | {"group-manifest.json"}
    if {entry.name for entry in group_root.iterdir()} != expected_entries:
        raise DiscoveryError(f"group directory contains missing/extra entries: {path}")
    return group_root


def _initial_bundle_task_index(group_index: int) -> int:
    if not 0 <= group_index < 280:
        raise DiscoveryError("initial group index is outside the frozen matrix")
    if group_index < 70:
        return group_index // 4
    if group_index < 140:
        return 18 + (group_index - 70) // 3
    if group_index < 210:
        return 42 + (group_index - 140)
    return 112 + (group_index - 210)


def _load_group_phase(
    phase: Phase, group: PhaseGroup, geometry: Geometry
) -> dict[str, LoadedRun]:
    group_root = _validate_group_manifest(phase, group)
    loaded: dict[str, LoadedRun] = {}
    for request_value in group.requests:
        policy = _policy_key(request_value["policy"])
        if policy in loaded:
            raise DiscoveryError("duplicate policy in phase group")
        loaded[policy] = _load_expected_run(
            group_root / request_value["run_id"], request_value, geometry
        )
    if len(loaded) != 8:
        raise DiscoveryError("phase group does not contain all eight policies")
    return loaded


def _sum_aggregate(runs: list[LoadedRun], key: str) -> int:
    values = [int(run.aggregate[key]) for run in runs]
    if any(value < 0 for value in values):
        raise DiscoveryError(f"aggregate {key} is negative")
    return sum(values)


def _sum_float_aggregate(runs: list[LoadedRun], key: str) -> float:
    values = [float(run.aggregate[key]) for run in runs]
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise DiscoveryError(f"aggregate {key} is negative or non-finite")
    return sum(values)


def _sampling_status(failures: int, shots: int) -> str:
    if failures >= MIN_LOGICAL_FAILURES:
        return "target_met"
    if shots >= MAX_DISCOVERY_SHOTS:
        return "inconclusive_at_budget"
    return "continue"


def _policy_columns(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy": _policy_key(policy),
        "policy_name": policy["name"],
        "policy_interval": policy.get("interval"),
        "policy_fraction": policy.get("fraction"),
    }


def _pack_logical_failure_row(values: np.ndarray) -> np.ndarray:
    logical_failure = np.asarray(values).reshape(-1)
    if (
        logical_failure.dtype != np.uint8
        or not len(logical_failure)
        or np.any(logical_failure > 1)
    ):
        raise DiscoveryError("logical-failure state row is not binary uint8")
    return np.packbits(logical_failure, bitorder="little")


def _unpack_logical_failure_row(packed: np.ndarray, shots: int) -> np.ndarray:
    value = np.asarray(packed)
    if value.dtype != np.uint8 or value.ndim != 1:
        raise DiscoveryError("packed logical-failure state row is invalid")
    if type(shots) is not int or shots <= 0 or shots > value.size * 8:
        raise DiscoveryError("packed logical-failure shot count is invalid")
    required_bytes = (shots + 7) // 8
    if np.any(value[required_bytes:]):
        raise DiscoveryError("packed logical-failure padding is nonzero")
    remaining_bits = shots % 8
    if remaining_bits:
        padding_mask = np.uint8(0xFF ^ ((1 << remaining_bits) - 1))
        if value[required_bytes - 1] & padding_mask:
            raise DiscoveryError("packed logical-failure padding is nonzero")
    unpacked = np.unpackbits(value[:required_bytes], bitorder="little")
    return unpacked[:shots]


def _write_logical_failure_state(
    *,
    out_dir: Path,
    packed_rows: list[np.ndarray],
    shot_counts: list[int],
) -> tuple[Path, Path, dict[str, Any]]:
    if len(packed_rows) != 2_240 or len(shot_counts) != len(packed_rows):
        raise DiscoveryError("logical-failure state is not 2240 rows")
    width = max(row.size for row in packed_rows)
    packed = np.zeros((len(packed_rows), width), dtype=np.uint8)
    for index, (row, shots) in enumerate(
        zip(packed_rows, shot_counts, strict=True)
    ):
        _unpack_logical_failure_row(row, shots)
        packed[index, : row.size] = row
    shots_array = np.asarray(shot_counts, dtype=np.uint64)
    packed_path = out_dir / "logical-failures.packbits.npy"
    shots_path = out_dir / "logical-failure-shots.npy"
    np.save(packed_path, packed, allow_pickle=False)
    np.save(shots_path, shots_array, allow_pickle=False)
    metadata = {
        "encoding": "numpy-packbits-little",
        "row_order": "discovery-cells.parquet",
        "rows": len(packed_rows),
        "max_shots": int(shots_array.max()),
    }
    return packed_path, shots_path, metadata


def _cell_row(
    *,
    group_index: int,
    physical_key: dict[str, Any],
    request: dict[str, Any],
    runs: list[LoadedRun],
    shot_id: np.ndarray,
    logical_failure: np.ndarray,
    n_sites: int,
) -> dict[str, Any]:
    shots = int(shot_id.size)
    failures = int(np.count_nonzero(logical_failure))
    lower, upper = _wilson_interval(failures, shots)
    request_value = SimulationRequest.from_dict(request)
    wall_seconds = _sum_float_aggregate(runs, "wall_seconds")
    if wall_seconds <= 0.0:
        raise DiscoveryError("cumulative wall time must be positive")
    compressed_bytes = _sum_aggregate(runs, "compressed_npz_bytes")
    row: dict[str, Any] = {
        "group_index": group_index,
        **physical_key,
        **_policy_columns(request["policy"]),
        "phase_count": len(runs),
        "run_ids": json.dumps(
            [run.manifest["run_id"] for run in runs], separators=(",", ":")
        ),
        "shots": shots,
        "logical_failures": failures,
        "logical_error_rate": failures / shots,
        "wilson_95_lower": lower,
        "wilson_95_upper": upper,
        "zero_failure_one_sided_95_upper": (
            _zero_failure_upper(shots) if failures == 0 else None
        ),
        "catastrophic_shots": _sum_aggregate(runs, "catastrophic_shots"),
        "loss_events": _sum_aggregate(runs, "loss_events"),
        "reload_requests": _sum_aggregate(runs, "reload_requests"),
        "reload_successes": _sum_aggregate(runs, "reload_successes"),
        "reload_failures": _sum_aggregate(runs, "reload_failures"),
        "missing_site_boundaries": _sum_aggregate(
            runs, "missing_site_boundaries"
        ),
        "wall_seconds": wall_seconds,
        "shots_per_second": shots / wall_seconds,
        "compressed_npz_bytes": compressed_bytes,
        "bytes_per_shot": compressed_bytes / shots,
        "n_sites": n_sites,
        "missing_occupancy": _sum_aggregate(runs, "missing_site_boundaries")
        / (shots * (request_value.rounds + 1) * n_sites),
        "reloads_per_site_round": _sum_aggregate(runs, "reload_successes")
        / (shots * request_value.rounds * n_sites),
        "reload_delay_rounds": request_value.reload.delay_rounds,
        "extra_rounds_per_shot": 0.0,
        "sampling_status": _sampling_status(failures, shots),
    }
    return row


def _extend_cell_row(
    *,
    previous: dict[str, Any],
    run: LoadedRun,
    logical_failure: np.ndarray,
    n_sites: int,
) -> dict[str, Any]:
    request = SimulationRequest.from_dict(run.manifest["request"])
    previous_shots = int(previous["shots"])
    if request.shot_start != previous_shots:
        raise DiscoveryError("incremental run does not start after previous state")
    shots = int(logical_failure.size)
    if shots != previous_shots + request.shots:
        raise DiscoveryError("incremental logical-failure length is inconsistent")
    failures = int(np.count_nonzero(logical_failure))
    expected_failures = int(previous["logical_failures"]) + int(
        run.aggregate["logical_failures"]
    )
    if failures != expected_failures:
        raise DiscoveryError("incremental logical-failure count is inconsistent")
    lower, upper = _wilson_interval(failures, shots)
    row = dict(previous)
    run_ids = json.loads(str(previous["run_ids"]))
    if not isinstance(run_ids, list) or any(
        not isinstance(run_id, str) for run_id in run_ids
    ):
        raise DiscoveryError("previous run ID list is invalid")
    run_ids.append(run.manifest["run_id"])
    row.update(
        {
            "phase_count": int(previous["phase_count"]) + 1,
            "run_ids": json.dumps(run_ids, separators=(",", ":")),
            "shots": shots,
            "logical_failures": failures,
            "logical_error_rate": failures / shots,
            "wilson_95_lower": lower,
            "wilson_95_upper": upper,
            "zero_failure_one_sided_95_upper": (
                _zero_failure_upper(shots) if failures == 0 else None
            ),
        }
    )
    count_keys = (
        "catastrophic_shots",
        "loss_events",
        "reload_requests",
        "reload_successes",
        "reload_failures",
        "missing_site_boundaries",
    )
    for key in count_keys:
        row[key] = int(previous[key]) + int(run.aggregate[key])
    wall_seconds = float(previous["wall_seconds"]) + float(
        run.aggregate["wall_seconds"]
    )
    compressed_bytes = int(previous["compressed_npz_bytes"]) + int(
        run.aggregate["compressed_npz_bytes"]
    )
    row.update(
        {
            "wall_seconds": wall_seconds,
            "shots_per_second": shots / wall_seconds,
            "compressed_npz_bytes": compressed_bytes,
            "bytes_per_shot": compressed_bytes / shots,
            "n_sites": n_sites,
            "missing_occupancy": row["missing_site_boundaries"]
            / (shots * (request.rounds + 1) * n_sites),
            "reloads_per_site_round": row["reload_successes"]
            / (shots * request.rounds * n_sites),
            "reload_delay_rounds": request.reload.delay_rounds,
            "extra_rounds_per_shot": 0.0,
            "sampling_status": _sampling_status(failures, shots),
        }
    )
    return row


def _next_run_id(base_run_id: str, shot_start: int, shots: int) -> str:
    suffix = f"-s{shot_start}-n{shots}"
    if len(base_run_id) + len(suffix) <= 128:
        return base_run_id + suffix
    digest = hashlib.sha256(base_run_id.encode("ascii")).hexdigest()[:12]
    prefix_length = 128 - len(suffix) - len(digest) - 1
    return f"{base_run_id[:prefix_length]}-{digest}{suffix}"


def _continuation_plan(
    *,
    matrix: dict[str, Any],
    matrix_sha256: str,
    phases: list[Phase],
    cell_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    first_request = matrix["groups"][0]["requests"][0]
    rows_by_group: dict[int, list[dict[str, Any]]] = {}
    for row in cell_rows:
        rows_by_group.setdefault(int(row["group_index"]), []).append(row)
    groups = []
    for source_group in matrix["groups"]:
        source_index = int(source_group["group_index"])
        rows = rows_by_group[source_index]
        totals = {int(row["shots"]) for row in rows}
        if len(totals) != 1:
            raise DiscoveryError("policies in a physical group have different totals")
        current_shots = totals.pop()
        needs_more = any(row["sampling_status"] == "continue" for row in rows)
        if not needs_more:
            continue
        if current_shots <= 0 or current_shots >= MAX_DISCOVERY_SHOTS:
            raise DiscoveryError("invalid continuation decision at the shot budget")
        next_shots = min(current_shots, MAX_DISCOVERY_SHOTS - current_shots)
        requests = []
        for base_request in source_group["requests"]:
            request = dict(base_request)
            request["run_id"] = _next_run_id(
                str(base_request["run_id"]), current_shots, next_shots
            )
            request["shot_start"] = current_shots
            request["shots"] = next_shots
            request["shard_size"] = min(int(base_request["shard_size"]), next_shots)
            SimulationRequest.from_dict(request)
            requests.append(request)
        groups.append(
            {
                "phase_group_index": len(groups),
                "source_group_index": source_index,
                "physical_key": dict(source_group["physical_key"]),
                "shot_start": current_shots,
                "shots": next_shots,
                "requests": requests,
            }
        )
    return {
        "schema_version": CONTINUATION_SCHEMA,
        "phase_index": len(phases) + 1,
        "initial_matrix_sha256": matrix_sha256,
        "source_commit": matrix["source_commit"],
        "environment_lock_sha256": matrix["environment_lock_sha256"],
        "instance_file": first_request["instance_file"],
        "parent_phases": [
            {
                "phase_index": phase.phase_index,
                "kind": phase.kind,
                "spec": str(phase.spec_path),
                "spec_sha256": phase.spec_sha256,
                "results_root": str(phase.results_root),
            }
            for phase in phases
        ],
        "stopping_rule": {
            "minimum_logical_failures_per_cell": MIN_LOGICAL_FAILURES,
            "maximum_shots_per_cell": MAX_DISCOVERY_SHOTS,
            "growth": "double cumulative shots while all 8 policies remain paired",
        },
        "group_count": len(groups),
        "cell_count": 8 * len(groups),
        "total_requested_shots": sum(8 * group["shots"] for group in groups),
        "groups": groups,
    }


def _validate_continuation_provenance(phases: list[Phase]) -> None:
    for phase_offset, phase in enumerate(phases[1:], start=1):
        value = json.loads(phase.spec_path.read_text(encoding="ascii"))
        expected_parents = [
            {
                "phase_index": parent.phase_index,
                "kind": parent.kind,
                "spec": str(parent.spec_path),
                "spec_sha256": parent.spec_sha256,
                "results_root": str(parent.results_root),
            }
            for parent in phases[:phase_offset]
        ]
        if value.get("parent_phases") != expected_parents:
            raise DiscoveryError("continuation plan provenance does not match inputs")
        expected_rule = {
            "minimum_logical_failures_per_cell": MIN_LOGICAL_FAILURES,
            "maximum_shots_per_cell": MAX_DISCOVERY_SHOTS,
            "growth": "double cumulative shots while all 8 policies remain paired",
        }
        if value.get("stopping_rule") != expected_rule:
            raise DiscoveryError("continuation plan changes the frozen stopping rule")


def _validate_phase_results_layout(phases: list[Phase]) -> None:
    for phase in phases:
        expected = {
            f"group-{source_index:03d}" for source_index in phase.groups
        }
        actual = {entry.name for entry in phase.results_root.iterdir()}
        if actual != expected:
            raise DiscoveryError(
                f"phase {phase.phase_index} result groups are incomplete or extra"
            )


def _phase_arguments_from_latest(
    matrix_path: Path, latest_spec: Path, latest_results: Path
) -> list[tuple[Path, Path]]:
    value = json.loads(latest_spec.read_text(encoding="ascii"))
    if value.get("schema_version") == MATRIX_SCHEMA:
        if _sha256(latest_spec) != _sha256(matrix_path):
            raise DiscoveryError("latest initial spec differs from --matrix")
        return [(latest_spec, latest_results)]
    if value.get("schema_version") != CONTINUATION_SCHEMA:
        raise DiscoveryError("latest phase spec has an unsupported schema")
    parents = value.get("parent_phases")
    if not isinstance(parents, list):
        raise DiscoveryError("latest continuation plan lacks parent provenance")
    result = []
    for expected_index, parent in enumerate(parents, start=1):
        if parent.get("phase_index") != expected_index:
            raise DiscoveryError("latest plan parent phases are not contiguous")
        result.append((Path(parent["spec"]), Path(parent["results_root"])))
    result.append((latest_spec, latest_results))
    return result


def _verified_analysis_summary(analysis_root: Path) -> dict[str, Any]:
    expected_artifacts = {
        "discovery-cells.parquet",
        "discovery-comparisons.parquet",
        "logical-failures.packbits.npy",
        "logical-failure-shots.npy",
        "continuation-plan.json",
        "analysis-summary.json",
    }
    checksum_path = analysis_root / "analysis-checksums.sha256"
    observed_names: list[str] = []
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if (
            separator != "  "
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not name
            or "/" in name
            or "\\" in name
        ):
            raise DiscoveryError("previous analysis checksum entry is invalid")
        artifact = analysis_root / name
        if not artifact.is_file() or _sha256(artifact) != digest:
            raise DiscoveryError(f"previous analysis checksum mismatch: {artifact}")
        observed_names.append(name)
    if len(observed_names) != len(set(observed_names)):
        raise DiscoveryError("previous analysis checksum names are duplicated")
    if set(observed_names) != expected_artifacts:
        raise DiscoveryError("previous analysis checksum coverage changed")
    summary = json.loads(
        (analysis_root / "analysis-summary.json").read_text(encoding="ascii")
    )
    if summary.get("schema_version") != ANALYSIS_SCHEMA:
        raise DiscoveryError("previous analysis summary schema changed")
    if set(summary.get("artifacts", [])) != expected_artifacts | {
        "analysis-checksums.sha256"
    }:
        raise DiscoveryError("previous analysis artifact list changed")
    return summary


def _previous_cell_rows(
    analysis_root: Path, matrix: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    frame = pd.read_parquet(analysis_root / "discovery-cells.parquet")
    if len(frame) != 2_240:
        raise DiscoveryError("previous analysis is not 2240 cells")
    rows = frame.to_dict(orient="records")
    optional_columns = (
        "policy_interval",
        "policy_fraction",
        "zero_failure_one_sided_95_upper",
    )
    for row in rows:
        for key in optional_columns:
            if pd.isna(row[key]):
                row[key] = None
    expected_order = [
        (int(group["group_index"]), request)
        for group in matrix["groups"]
        for request in group["requests"]
    ]
    for row, (group_index, request) in zip(rows, expected_order, strict=True):
        physical_key = matrix["groups"][group_index]["physical_key"]
        if int(row["group_index"]) != group_index:
            raise DiscoveryError("previous analysis cell group order changed")
        if row["policy"] != _policy_key(request["policy"]):
            raise DiscoveryError("previous analysis cell policy order changed")
        if any(row[key] != value for key, value in physical_key.items()):
            raise DiscoveryError("previous analysis cell physical key changed")
    return tuple(rows)


def _load_previous_analysis(
    *,
    analysis_root: Path,
    matrix_path: Path,
    matrix: dict[str, Any],
    matrix_sha256: str,
) -> PreviousAnalysis:
    summary = _verified_analysis_summary(analysis_root)
    if summary.get("initial_matrix_sha256") != matrix_sha256:
        raise DiscoveryError("previous analysis names a different matrix")
    phase_records = summary.get("phases")
    if not isinstance(phase_records, list) or not phase_records:
        raise DiscoveryError("previous analysis phase list is invalid")
    phases = []
    for phase_index, record in enumerate(phase_records, start=1):
        if not isinstance(record, dict):
            raise DiscoveryError("previous analysis phase record is invalid")
        phase = _load_phase(
            Path(record["spec"]),
            Path(record["results_root"]),
            phase_index=phase_index,
            initial_matrix_sha256=matrix_sha256,
        )
        expected_record = {
            "phase_index": phase.phase_index,
            "kind": phase.kind,
            "spec": str(phase.spec_path),
            "spec_sha256": phase.spec_sha256,
            "results_root": str(phase.results_root),
            "group_count": len(phase.groups),
        }
        if record != expected_record:
            raise DiscoveryError("previous analysis phase provenance changed")
        phases.append(phase)
    _validate_phase_sequence(phases, int(matrix["group_count"]))
    _validate_continuation_provenance(phases)
    rows = _previous_cell_rows(analysis_root, matrix)
    packed = np.load(
        analysis_root / "logical-failures.packbits.npy",
        mmap_mode="r",
        allow_pickle=False,
    )
    shots = np.load(
        analysis_root / "logical-failure-shots.npy",
        mmap_mode="r",
        allow_pickle=False,
    )
    if (
        packed.dtype != np.uint8
        or packed.ndim != 2
        or packed.shape[0] != 2_240
        or shots.dtype != np.uint64
        or shots.shape != (2_240,)
    ):
        raise DiscoveryError("previous logical-failure state shape changed")
    maximum_shots = int(shots.max())
    if packed.shape[1] != (maximum_shots + 7) // 8:
        raise DiscoveryError("previous logical-failure state width changed")
    state_metadata = summary.get("logical_failure_state")
    expected_metadata = {
        "encoding": "numpy-packbits-little",
        "row_order": "discovery-cells.parquet",
        "rows": 2_240,
        "max_shots": maximum_shots,
    }
    if state_metadata != expected_metadata:
        raise DiscoveryError("previous logical-failure state metadata changed")

    expected_cells: list[tuple[int, list[str]]] = []
    for source_group in matrix["groups"]:
        source_index = int(source_group["group_index"])
        base_requests = {
            _policy_key(request["policy"]): request
            for request in source_group["requests"]
        }
        expected_start = 0
        run_ids = {policy: [] for policy in base_requests}
        for phase in phases:
            phase_group = phase.groups.get(source_index)
            if phase_group is None:
                break
            requests, phase_shots = _phase_request_map(
                base_requests, phase_group, expected_start
            )
            for policy, request in requests.items():
                run_ids[policy].append(str(request["run_id"]))
            expected_start += phase_shots
        expected_cells.extend(
            (expected_start, run_ids[_policy_key(request["policy"])])
            for request in source_group["requests"]
        )

    for index, (row, (expected_shots, expected_run_ids)) in enumerate(
        zip(rows, expected_cells, strict=True)
    ):
        shot_count = int(shots[index])
        if int(row["shots"]) != shot_count or shot_count != expected_shots:
            raise DiscoveryError("previous cell/state/spec shot counts differ")
        logical_failure = _unpack_logical_failure_row(packed[index], shot_count)
        failures = int(np.count_nonzero(logical_failure))
        if int(row["logical_failures"]) != failures:
            raise DiscoveryError("previous cell/state failure counts differ")
        if row["sampling_status"] != _sampling_status(failures, shot_count):
            raise DiscoveryError("previous cell stopping status is inconsistent")
        try:
            observed_run_ids = json.loads(str(row["run_ids"]))
        except (TypeError, ValueError) as exc:
            raise DiscoveryError("previous cell run ID list is invalid") from exc
        if observed_run_ids != expected_run_ids:
            raise DiscoveryError("previous cell run IDs differ from phase specs")
        if int(row["phase_count"]) != len(expected_run_ids):
            raise DiscoveryError("previous cell phase count is inconsistent")

    expected_plan = _continuation_plan(
        matrix=matrix,
        matrix_sha256=matrix_sha256,
        phases=phases,
        cell_rows=list(rows),
    )
    observed_plan = json.loads(
        (analysis_root / "continuation-plan.json").read_text(encoding="ascii")
    )
    if observed_plan != expected_plan:
        raise DiscoveryError("previous continuation plan differs from compact state")
    expected_status = (
        "final-discovery" if expected_plan["group_count"] == 0 else "provisional"
    )
    expected_summary = {
        "status": expected_status,
        "cells": len(rows),
        "comparisons": 1_960,
        "total_cell_shots": sum(int(row["shots"]) for row in rows),
        "cell_sampling_status": _count_values(list(rows), "sampling_status"),
        "group_sampling_status": _group_sampling_counts(list(rows)),
        "next_phase_groups": expected_plan["group_count"],
        "next_phase_cells": expected_plan["cell_count"],
    }
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        raise DiscoveryError("previous analysis summary differs from compact state")
    if Path(summary.get("initial_matrix", "")) != matrix_path:
        raise DiscoveryError("previous analysis matrix path changed")
    return PreviousAnalysis(
        root=analysis_root,
        summary=summary,
        phases=tuple(phases),
        cell_rows=rows,
        packed_failures=packed,
        shot_counts=shots,
    )


def _phase_request_map(
    base_requests: dict[str, dict[str, Any]], group: PhaseGroup, expected_start: int
) -> tuple[dict[str, dict[str, Any]], int]:
    if len(group.requests) != 8:
        raise DiscoveryError("phase group does not contain eight requests")
    requests = {_policy_key(value["policy"]): value for value in group.requests}
    if set(requests) != set(base_requests):
        raise DiscoveryError("phase group policy set differs from initial matrix")
    starts = {int(value["shot_start"]) for value in requests.values()}
    shots_values = {int(value["shots"]) for value in requests.values()}
    if starts != {expected_start} or len(shots_values) != 1:
        raise DiscoveryError(
            "phase group does not use one contiguous paired shot range"
        )
    shots = shots_values.pop()
    if shots <= 0 or expected_start + shots > MAX_DISCOVERY_SHOTS:
        raise DiscoveryError("phase group exceeds the discovery shot budget")
    for policy, request in requests.items():
        if _paired_request_view(request) != _paired_request_view(base_requests[policy]):
            raise DiscoveryError(
                "continuation request changes frozen physics/provenance"
            )
    return requests, shots


def _physical_columns(group_index: int, physical_key: dict[str, Any]) -> dict[str, Any]:
    return {"group_index": group_index, **physical_key}


def _finish_discovery_analysis(
    *,
    matrix: dict[str, Any],
    matrix_path: Path,
    matrix_sha256: str,
    phases: list[Phase],
    out_dir: Path,
    bootstrap_resamples: int,
    cell_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    packed_failure_rows: list[np.ndarray],
    failure_shot_counts: list[int],
) -> dict[str, Any]:
    if len(cell_rows) != 2_240 or len(comparison_rows) != 1_960:
        raise DiscoveryError("discovery aggregation is not 2240 cells/1960 comparisons")
    adjusted = benjamini_hochberg(
        np.asarray(
            [row["sign_test_pvalue"] for row in comparison_rows],
            dtype=np.float64,
        )
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_sha256=matrix_sha256,
        phases=phases,
        cell_rows=cell_rows,
    )
    analysis_is_final = plan["group_count"] == 0
    for row, adjusted_value in zip(comparison_rows, adjusted, strict=True):
        row["bh_adjusted_pvalue"] = float(adjusted_value)
        row["fdr_q"] = FDR_Q
        if adjusted_value <= FDR_Q and float(row["bootstrap_95_upper"]) < 0.0:
            statistical_classification = "helpful"
        elif adjusted_value <= FDR_Q and float(row["bootstrap_95_lower"]) > 0.0:
            statistical_classification = "harmful"
        else:
            statistical_classification = "no_significant_difference"
        row["statistical_classification"] = statistical_classification
        if not analysis_is_final:
            row["evidence_classification"] = "provisional"
        elif "inconclusive_at_budget" in {
            row["baseline_sampling_status"],
            row["candidate_sampling_status"],
        }:
            row["evidence_classification"] = "inconclusive_at_budget"
        else:
            row["evidence_classification"] = statistical_classification
    return _write_analysis(
        out_dir=out_dir,
        matrix_path=matrix_path,
        matrix_sha256=matrix_sha256,
        phases=phases,
        cell_rows=cell_rows,
        comparison_rows=comparison_rows,
        packed_failure_rows=packed_failure_rows,
        failure_shot_counts=failure_shot_counts,
        continuation_plan=plan,
        bootstrap_resamples=bootstrap_resamples,
    )


def analyze_discovery(
    *,
    matrix_path: Path,
    phase_arguments: list[tuple[Path, Path]],
    out_dir: Path,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    if not os.environ.get("SLURM_JOB_ID"):
        raise DiscoveryError("discovery analysis must execute inside a Slurm job")
    if bootstrap_resamples < 1:
        raise DiscoveryError("bootstrap resamples must be positive")
    matrix = load_matrix(matrix_path)
    _validate_initial_matrix(matrix)
    matrix_sha256 = _sha256(matrix_path)
    if not phase_arguments or _sha256(phase_arguments[0][0]) != matrix_sha256:
        raise DiscoveryError("the first phase must use the supplied initial matrix")
    phases = [
        _load_phase(
            spec_path,
            results_root,
            phase_index=index,
            initial_matrix_sha256=matrix_sha256,
        )
        for index, (spec_path, results_root) in enumerate(phase_arguments, start=1)
    ]
    _validate_phase_sequence(phases, int(matrix["group_count"]))
    _validate_continuation_provenance(phases)
    _validate_phase_results_layout(phases)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise DiscoveryError(f"analysis output is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    cell_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    packed_failure_rows: list[np.ndarray] = []
    failure_shot_counts: list[int] = []
    none_policy = _policy_key({"name": "none"})
    for source_group in matrix["groups"]:
        source_index = int(source_group["group_index"])
        physical_key = dict(source_group["physical_key"])
        base_requests = {
            _policy_key(request["policy"]): request
            for request in source_group["requests"]
        }
        if len(base_requests) != 8 or none_policy not in base_requests:
            raise DiscoveryError("initial group policy set is incomplete")
        first_request = SimulationRequest.from_dict(next(iter(base_requests.values())))
        geometry = Geometry.load(
            first_request.instance_file,
            distance=first_request.distance,
            rounds=first_request.rounds,
            basis=first_request.basis,
        )
        runs_by_policy: dict[str, list[LoadedRun]] = {
            policy: [] for policy in base_requests
        }
        expected_start = 0
        for phase in phases:
            phase_group = phase.groups.get(source_index)
            if phase_group is None:
                break
            if phase_group.physical_key != physical_key:
                raise DiscoveryError("phase physical key differs from initial matrix")
            requests, phase_shots = _phase_request_map(
                base_requests, phase_group, expected_start
            )
            loaded = _load_group_phase(phase, phase_group, geometry)
            reference_ids: np.ndarray | None = None
            for policy in base_requests:
                run = loaded[policy]
                if run.manifest["request"] != requests[policy]:
                    raise DiscoveryError("loaded request differs from phase request")
                if reference_ids is None:
                    reference_ids = run.shot_id
                elif not np.array_equal(reference_ids, run.shot_id):
                    raise DiscoveryError("policies do not share the phase shot IDs")
                runs_by_policy[policy].append(run)
            expected_start += phase_shots

        cumulative_failures: dict[str, np.ndarray] = {}
        rows_by_policy: dict[str, dict[str, Any]] = {}
        reference_cumulative_ids: np.ndarray | None = None
        for policy, base_request in base_requests.items():
            runs = runs_by_policy[policy]
            ids = np.concatenate([run.shot_id for run in runs])
            failures = np.concatenate([run.logical_failure for run in runs])
            expected_ids = np.arange(ids.size, dtype=np.uint64)
            if not np.array_equal(ids, expected_ids):
                raise DiscoveryError("cumulative shot IDs are not contiguous from zero")
            if reference_cumulative_ids is None:
                reference_cumulative_ids = ids
            elif not np.array_equal(reference_cumulative_ids, ids):
                raise DiscoveryError("cumulative policy shot IDs differ")
            cumulative_failures[policy] = failures
            row = _cell_row(
                group_index=source_index,
                physical_key=physical_key,
                request=base_request,
                runs=runs,
                shot_id=ids,
                logical_failure=failures,
                n_sites=geometry.n_sites,
            )
            rows_by_policy[policy] = row
            cell_rows.append(row)
            packed_failure_rows.append(_pack_logical_failure_row(failures))
            failure_shot_counts.append(int(failures.size))

        baseline_failure = cumulative_failures[none_policy]
        for policy, base_request in base_requests.items():
            if policy == none_policy:
                continue
            seed = _bootstrap_seed(matrix_sha256, source_index, policy)
            comparison = paired_comparison(
                baseline_failure,
                cumulative_failures[policy],
                bootstrap_resamples=bootstrap_resamples,
                bootstrap_seed=seed,
            ).as_dict()
            comparison_rows.append(
                {
                    **_physical_columns(source_index, physical_key),
                    "baseline_policy": none_policy,
                    "candidate_policy": policy,
                    "candidate_policy_name": base_request["policy"]["name"],
                    "candidate_policy_interval": base_request["policy"].get(
                        "interval"
                    ),
                    "candidate_policy_fraction": base_request["policy"].get(
                        "fraction"
                    ),
                    "baseline_sampling_status": rows_by_policy[none_policy][
                        "sampling_status"
                    ],
                    "candidate_sampling_status": rows_by_policy[policy][
                        "sampling_status"
                    ],
                    "bootstrap_resamples": bootstrap_resamples,
                    "bootstrap_seed": seed,
                    **comparison,
                }
            )

    return _finish_discovery_analysis(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=matrix_sha256,
        phases=phases,
        out_dir=out_dir,
        bootstrap_resamples=bootstrap_resamples,
        cell_rows=cell_rows,
        comparison_rows=comparison_rows,
        packed_failure_rows=packed_failure_rows,
        failure_shot_counts=failure_shot_counts,
    )


def analyze_discovery_incremental(
    *,
    matrix_path: Path,
    previous_analysis_root: Path,
    latest_spec: Path,
    latest_results: Path,
    out_dir: Path,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    if not os.environ.get("SLURM_JOB_ID"):
        raise DiscoveryError("incremental analysis must execute inside a Slurm job")
    if bootstrap_resamples < 1:
        raise DiscoveryError("bootstrap resamples must be positive")
    matrix = load_matrix(matrix_path)
    _validate_initial_matrix(matrix)
    matrix_sha256 = _sha256(matrix_path)
    previous = _load_previous_analysis(
        analysis_root=previous_analysis_root,
        matrix_path=matrix_path,
        matrix=matrix,
        matrix_sha256=matrix_sha256,
    )
    expected_spec = (previous.root / "continuation-plan.json").resolve(
        strict=True
    )
    if latest_spec.resolve(strict=True) != expected_spec:
        raise DiscoveryError("latest plan is not the previous continuation plan")
    if previous.summary.get("status") != "provisional":
        raise DiscoveryError("previous analysis has no continuation phase")
    latest_phase = _load_phase(
        latest_spec,
        latest_results,
        phase_index=len(previous.phases) + 1,
        initial_matrix_sha256=matrix_sha256,
    )
    phases = [*previous.phases, latest_phase]
    _validate_phase_sequence(phases, int(matrix["group_count"]))
    _validate_continuation_provenance(phases)
    _validate_phase_results_layout([latest_phase])
    if (
        previous.summary.get("next_phase_groups") != len(latest_phase.groups)
        or previous.summary.get("next_phase_cells")
        != 8 * len(latest_phase.groups)
    ):
        raise DiscoveryError("previous analysis and latest phase counts differ")
    continuing_groups = {
        int(row["group_index"])
        for row in previous.cell_rows
        if row["sampling_status"] == "continue"
    }
    if continuing_groups != set(latest_phase.groups):
        raise DiscoveryError("previous stopping state and latest phase differ")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise DiscoveryError(f"analysis output is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    cell_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    packed_failure_rows: list[np.ndarray] = []
    failure_shot_counts: list[int] = []
    none_policy = _policy_key({"name": "none"})
    cell_index = 0
    for source_group in matrix["groups"]:
        source_index = int(source_group["group_index"])
        physical_key = dict(source_group["physical_key"])
        base_requests = {
            _policy_key(request["policy"]): request
            for request in source_group["requests"]
        }
        previous_rows = {
            _policy_key(request["policy"]): previous.cell_rows[
                cell_index + policy_index
            ]
            for policy_index, request in enumerate(source_group["requests"])
        }
        previous_shots = {int(row["shots"]) for row in previous_rows.values()}
        if len(previous_shots) != 1:
            raise DiscoveryError("previous group policies have different shots")
        group = latest_phase.groups.get(source_index)
        loaded: dict[str, LoadedRun] = {}
        if group is not None:
            if group.physical_key != physical_key:
                raise DiscoveryError("latest phase physical key changed")
            _phase_request_map(base_requests, group, previous_shots.pop())
            first_request = SimulationRequest.from_dict(
                next(iter(base_requests.values()))
            )
            geometry = Geometry.load(
                first_request.instance_file,
                distance=first_request.distance,
                rounds=first_request.rounds,
                basis=first_request.basis,
            )
            loaded = _load_group_phase(latest_phase, group, geometry)
            n_sites = geometry.n_sites
        else:
            n_sites = int(next(iter(previous_rows.values()))["n_sites"])

        failures_by_policy: dict[str, np.ndarray] = {}
        rows_by_policy: dict[str, dict[str, Any]] = {}
        reference_new_ids: np.ndarray | None = None
        for policy_index, (policy, base_request) in enumerate(
            base_requests.items()
        ):
            prior_index = cell_index + policy_index
            prior_shots = int(previous.shot_counts[prior_index])
            failures = _unpack_logical_failure_row(
                previous.packed_failures[prior_index], prior_shots
            )
            row = dict(previous_rows[policy])
            if group is not None:
                run = loaded[policy]
                if reference_new_ids is None:
                    reference_new_ids = run.shot_id
                elif not np.array_equal(reference_new_ids, run.shot_id):
                    raise DiscoveryError("latest phase policy shot IDs differ")
                failures = np.concatenate((failures, run.logical_failure))
                row = _extend_cell_row(
                    previous=row,
                    run=run,
                    logical_failure=failures,
                    n_sites=n_sites,
                )
            if row["policy"] != _policy_key(base_request["policy"]):
                raise DiscoveryError("incremental cell policy changed")
            failures_by_policy[policy] = failures
            rows_by_policy[policy] = row
            cell_rows.append(row)
            packed_failure_rows.append(_pack_logical_failure_row(failures))
            failure_shot_counts.append(int(failures.size))

        baseline_failure = failures_by_policy[none_policy]
        for policy, base_request in base_requests.items():
            if policy == none_policy:
                continue
            seed = _bootstrap_seed(matrix_sha256, source_index, policy)
            comparison = paired_comparison(
                baseline_failure,
                failures_by_policy[policy],
                bootstrap_resamples=bootstrap_resamples,
                bootstrap_seed=seed,
            ).as_dict()
            comparison_rows.append(
                {
                    **_physical_columns(source_index, physical_key),
                    "baseline_policy": none_policy,
                    "candidate_policy": policy,
                    "candidate_policy_name": base_request["policy"]["name"],
                    "candidate_policy_interval": base_request["policy"].get(
                        "interval"
                    ),
                    "candidate_policy_fraction": base_request["policy"].get(
                        "fraction"
                    ),
                    "baseline_sampling_status": rows_by_policy[none_policy][
                        "sampling_status"
                    ],
                    "candidate_sampling_status": rows_by_policy[policy][
                        "sampling_status"
                    ],
                    "bootstrap_resamples": bootstrap_resamples,
                    "bootstrap_seed": seed,
                    **comparison,
                }
            )
        cell_index += len(base_requests)

    if cell_index != 2_240:
        raise DiscoveryError("incremental analysis did not consume every cell")
    return _finish_discovery_analysis(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=matrix_sha256,
        phases=phases,
        out_dir=out_dir,
        bootstrap_resamples=bootstrap_resamples,
        cell_rows=cell_rows,
        comparison_rows=comparison_rows,
        packed_failure_rows=packed_failure_rows,
        failure_shot_counts=failure_shot_counts,
    )


def _count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(row[key])
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _group_sampling_counts(cell_rows: list[dict[str, Any]]) -> dict[str, int]:
    grouped: dict[int, list[str]] = {}
    for row in cell_rows:
        grouped.setdefault(int(row["group_index"]), []).append(
            str(row["sampling_status"])
        )
    counts: dict[str, int] = {}
    for statuses in grouped.values():
        if "continue" in statuses:
            status = "continue"
        elif "inconclusive_at_budget" in statuses:
            status = "complete_with_inconclusive_cells"
        else:
            status = "target_met"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _write_analysis(
    *,
    out_dir: Path,
    matrix_path: Path,
    matrix_sha256: str,
    phases: list[Phase],
    cell_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    packed_failure_rows: list[np.ndarray],
    failure_shot_counts: list[int],
    continuation_plan: dict[str, Any],
    bootstrap_resamples: int,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise DiscoveryError("discovery analysis must execute inside a Slurm job")
    cells_path = out_dir / "discovery-cells.parquet"
    comparisons_path = out_dir / "discovery-comparisons.parquet"
    plan_path = out_dir / "continuation-plan.json"
    summary_path = out_dir / "analysis-summary.json"
    pd.DataFrame(cell_rows).to_parquet(cells_path, index=False)
    pd.DataFrame(comparison_rows).to_parquet(comparisons_path, index=False)
    packed_path, shots_path, state_metadata = _write_logical_failure_state(
        out_dir=out_dir,
        packed_rows=packed_failure_rows,
        shot_counts=failure_shot_counts,
    )
    _canonical_json(plan_path, continuation_plan)
    summary = {
        "schema_version": ANALYSIS_SCHEMA,
        "status": (
            "final-discovery"
            if continuation_plan["group_count"] == 0
            else "provisional"
        ),
        "slurm_job_id": slurm_job_id,
        "initial_matrix": str(matrix_path),
        "initial_matrix_sha256": matrix_sha256,
        "phases": [
            {
                "phase_index": phase.phase_index,
                "kind": phase.kind,
                "spec": str(phase.spec_path),
                "spec_sha256": phase.spec_sha256,
                "results_root": str(phase.results_root),
                "group_count": len(phase.groups),
            }
            for phase in phases
        ],
        "cells": len(cell_rows),
        "comparisons": len(comparison_rows),
        "total_cell_shots": sum(int(row["shots"]) for row in cell_rows),
        "bootstrap_resamples_per_comparison": bootstrap_resamples,
        "fdr": {
            "method": "Benjamini-Hochberg",
            "scope": "all 1960 policy-vs-none discovery comparisons",
            "q": FDR_Q,
        },
        "cell_sampling_status": _count_values(cell_rows, "sampling_status"),
        "group_sampling_status": _group_sampling_counts(cell_rows),
        "statistical_classification": _count_values(
            comparison_rows, "statistical_classification"
        ),
        "evidence_classification": _count_values(
            comparison_rows, "evidence_classification"
        ),
        "logical_failure_state": state_metadata,
        "next_phase_groups": continuation_plan["group_count"],
        "next_phase_cells": continuation_plan["cell_count"],
        "headline_claims_authorized": False,
        "artifacts": [
            cells_path.name,
            comparisons_path.name,
            packed_path.name,
            shots_path.name,
            plan_path.name,
            summary_path.name,
            "analysis-checksums.sha256",
        ],
        "note": (
            "Discovery classifications remain provisional until all stopping rules "
            "finish; headline claims additionally require confirmation and holdout."
        ),
    }
    _canonical_json(summary_path, summary)
    artifact_paths = [
        cells_path,
        comparisons_path,
        packed_path,
        shots_path,
        plan_path,
        summary_path,
    ]
    checksum_text = "".join(
        f"{_sha256(path)}  {path.name}\n" for path in sorted(artifact_paths)
    )
    (out_dir / "analysis-checksums.sha256").write_text(
        checksum_text, encoding="ascii"
    )
    return summary


def _validate_executable_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    if plan.get("schema_version") != CONTINUATION_SCHEMA:
        raise DiscoveryError("unsupported continuation plan schema")
    phase_index = plan.get("phase_index")
    if type(phase_index) is not int or phase_index < 2:
        raise DiscoveryError("continuation phase index is invalid")
    parents = plan.get("parent_phases")
    if not isinstance(parents, list) or len(parents) != phase_index - 1:
        raise DiscoveryError("continuation parent phase count is invalid")
    expected_rule = {
        "minimum_logical_failures_per_cell": MIN_LOGICAL_FAILURES,
        "maximum_shots_per_cell": MAX_DISCOVERY_SHOTS,
        "growth": "double cumulative shots while all 8 policies remain paired",
    }
    if plan.get("stopping_rule") != expected_rule:
        raise DiscoveryError("continuation plan changes the stopping rule")
    groups = plan.get("groups")
    if not isinstance(groups, list) or plan.get("group_count") != len(groups):
        raise DiscoveryError("continuation plan group count mismatch")
    if plan.get("cell_count") != 8 * len(groups):
        raise DiscoveryError("continuation plan cell count mismatch")
    source_indices: set[int] = set()
    run_ids: set[str] = set()
    requested_shots = 0
    frozen_physical_keys = _expected_physical_keys()
    source_commit = plan.get("source_commit")
    environment_hash = plan.get("environment_lock_sha256")
    instance_file = plan.get("instance_file")
    if not isinstance(instance_file, str) or not instance_file:
        raise DiscoveryError("continuation plan instance file is invalid")
    for local_index, group in enumerate(groups):
        if group.get("phase_group_index") != local_index:
            raise DiscoveryError("continuation plan group ordering mismatch")
        source_index = int(group["source_group_index"])
        if source_index in source_indices or not 0 <= source_index < 280:
            raise DiscoveryError("continuation source group index is invalid")
        source_indices.add(source_index)
        physical_key = group.get("physical_key")
        if not isinstance(physical_key, dict):
            raise DiscoveryError("continuation physical key is invalid")
        if physical_key != frozen_physical_keys[source_index]:
            raise DiscoveryError("continuation source group/physical key mismatch")
        distance = int(physical_key["distance"])
        requests = group.get("requests")
        if not isinstance(requests, list) or len(requests) != 8:
            raise DiscoveryError("continuation group must contain eight requests")
        if tuple(request["policy"] for request in requests) != _expected_policies(
            distance
        ):
            raise DiscoveryError("continuation policies differ from the frozen set")
        expected_start = int(group["shot_start"])
        expected_shots = int(group["shots"])
        if (
            expected_start < 20_000
            or expected_shots <= 0
            or expected_start + expected_shots > MAX_DISCOVERY_SHOTS
        ):
            raise DiscoveryError("continuation group shot range is invalid")
        if expected_shots != min(
            expected_start, MAX_DISCOVERY_SHOTS - expected_start
        ):
            raise DiscoveryError("continuation group does not double cumulative shots")
        for request_value in requests:
            request = SimulationRequest.from_dict(request_value)
            if request.shot_start != expected_start or request.shots != expected_shots:
                raise DiscoveryError(
                    "continuation request range differs from its group"
                )
            if (
                request.distance != physical_key["distance"]
                or request.rounds != physical_key["rounds"]
                or request.basis != physical_key["basis"]
                or request.p != physical_key["p"]
                or request.p_m != physical_key["p_m"]
                or request.p_loss != physical_key["p_loss"]
            ):
                raise DiscoveryError("continuation request changes the physical group")
            if request.master_seed != _expected_seed(physical_key):
                raise DiscoveryError("continuation request changes the master seed")
            if (
                request.source_commit != source_commit
                or request.environment_lock_sha256 != environment_hash
                or str(request.instance_file) != instance_file
            ):
                raise DiscoveryError("continuation request provenance mismatch")
            if (
                request.reload.delay_rounds != 0
                or request.reload.reset_error_probability != 0.0
                or request.reload.failure_probability != 0.0
            ):
                raise DiscoveryError("continuation request is not ideal reload")
            if request.run_id in run_ids:
                raise DiscoveryError("continuation plan contains duplicate run IDs")
            run_ids.add(request.run_id)
        requested_shots += 8 * expected_shots
    if plan.get("total_requested_shots") != requested_shots:
        raise DiscoveryError("continuation total requested shots mismatch")
    return groups


def _continuation_bundles(plan: dict[str, Any]) -> list[tuple[int, ...]]:
    groups = _validate_executable_plan(plan)
    bundles: list[tuple[int, ...]] = []
    pending: list[int] = []
    pending_geometry: tuple[int, int] | None = None
    for group in groups:
        physical_key = group["physical_key"]
        geometry = (int(physical_key["distance"]), int(physical_key["rounds"]))
        shots = int(group["shots"])
        projected_group_seconds = (
            WORST_VALIDATED_SECONDS_PER_SHOT[geometry]
            * shots
            * CONTINUATION_RUNTIME_FACTOR
        )
        if projected_group_seconds > CONTINUATION_BUNDLE_BUDGET_SECONDS:
            raise DiscoveryError(
                "parallel continuation group exceeds the six-hour bundle budget"
            )
        capacity = max(
            1,
            int(
                CONTINUATION_BUNDLE_BUDGET_SECONDS // projected_group_seconds
            ),
        )
        if pending and (geometry != pending_geometry or len(pending) >= capacity):
            bundles.append(tuple(pending))
            pending = []
        pending_geometry = geometry
        pending.append(int(group["phase_group_index"]))
    if pending:
        bundles.append(tuple(pending))
    if len(bundles) > 200:
        raise DiscoveryError("continuation bundle count exceeds scheduler limit")
    flattened = [index for bundle in bundles for index in bundle]
    if flattened != list(range(len(groups))):
        raise DiscoveryError("continuation bundles do not cover the plan exactly once")
    return bundles


def _continuation_bundle_task_index(
    plan: dict[str, Any], phase_group_index: int
) -> int:
    matches = [
        bundle_index
        for bundle_index, bundle in enumerate(_continuation_bundles(plan))
        if phase_group_index in bundle
    ]
    if len(matches) != 1:
        raise DiscoveryError("continuation group does not map to one bundle task")
    return matches[0]


def _continuation_group_manifest(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    group: dict[str, Any],
    array_job_id: str,
    array_task_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": CONTINUATION_GROUP_SCHEMA,
        "plan_sha256": _sha256(plan_path),
        "phase_index": plan["phase_index"],
        "phase_group_index": int(group["phase_group_index"]),
        "source_group_index": int(group["source_group_index"]),
        "slurm_array_job_id": array_job_id,
        "slurm_array_task_id": array_task_id,
        "runs": [request["run_id"] for request in group["requests"]],
    }


def _load_completed_continuation_group(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    group: dict[str, Any],
    array_job_id: str,
    array_task_id: str,
    group_root: Path,
) -> dict[str, Any] | None:
    if not group_root.exists():
        return None
    expected = _continuation_group_manifest(
        plan_path=plan_path,
        plan=plan,
        group=group,
        array_job_id=array_job_id,
        array_task_id=array_task_id,
    )
    try:
        observed = json.loads(
            (group_root / "group-manifest.json").read_text(encoding="ascii")
        )
        if observed != expected:
            raise DiscoveryError("completed continuation group manifest mismatch")
        expected_entries = set(expected["runs"]) | {"group-manifest.json"}
        if {entry.name for entry in group_root.iterdir()} != expected_entries:
            raise DiscoveryError("completed continuation group layout mismatch")
        for request_value in group["requests"]:
            request = SimulationRequest.from_dict(request_value)
            run_root = group_root / request.run_id
            verify_checksums(run_root)
            manifest = json.loads(
                (run_root / "manifest.json").read_text(encoding="ascii")
            )
            if (
                manifest.get("schema_version") != MANIFEST_SCHEMA
                or manifest.get("status") != "completed"
                or manifest.get("run_id") != request.run_id
                or manifest.get("request") != request.as_dict()
                or manifest.get("source_commit") != request.source_commit
            ):
                raise DiscoveryError("completed continuation run manifest mismatch")
    except (OSError, TypeError, ValueError) as exc:
        raise DiscoveryError(
            f"invalid completed continuation group: {group_root}"
        ) from exc
    return observed


def _run_continuation_group(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    group: dict[str, Any],
    array_job_id: str,
    array_task_id: str,
    output_root: Path,
) -> dict[str, Any]:
    source_group_index = int(group["source_group_index"])
    requests = group["requests"]
    group_root = output_root / f"group-{source_group_index:03d}"
    completed = _load_completed_continuation_group(
        plan_path=plan_path,
        plan=plan,
        group=group,
        array_job_id=array_job_id,
        array_task_id=array_task_id,
        group_root=group_root,
    )
    if completed is not None:
        return completed
    restart_count = os.environ.get("SLURM_RESTART_COUNT", "0")
    if not restart_count.isdigit():
        raise DiscoveryError("Slurm restart count is invalid")
    group_staging = (
        output_root.parent
        / f".{array_job_id}.staging"
        / f"task-{array_task_id}-restart-{restart_count}"
        / group_root.name
    )
    if group_staging.exists():
        raise FileExistsError(
            f"continuation staging output already exists: {group_staging}"
        )
    group_staging.mkdir(parents=True)
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=PARALLEL_POLICY_WORKERS
    ) as executor:
        manifests = list(
            executor.map(
                _run_candidate_request,
                requests,
                [group_staging] * len(requests),
            )
        )
    group_manifest = _continuation_group_manifest(
        plan_path=plan_path,
        plan=plan,
        group=group,
        array_job_id=array_job_id,
        array_task_id=array_task_id,
    )
    if [manifest["run_id"] for manifest in manifests] != group_manifest["runs"]:
        raise DiscoveryError("continuation worker result ordering mismatch")
    _canonical_json(group_staging / "group-manifest.json", group_manifest)
    group_staging.rename(group_root)
    return group_manifest


def _run_candidate_request(
    request_value: dict[str, Any], group_root: Path
) -> dict[str, Any]:
    request = SimulationRequest.from_dict(request_value)
    return run_candidate(request, group_root / request.run_id, precheck=False)


def run_continuation_bundle(
    plan_path: Path, bundle_index: int, output_root: Path
) -> dict[str, Any]:
    array_job_id = os.environ.get("SLURM_ARRAY_JOB_ID")
    array_task_id = os.environ.get("SLURM_ARRAY_TASK_ID")
    if not array_job_id or array_task_id != str(bundle_index):
        raise DiscoveryError("continuation must run in the matching bundle task")
    if output_root.name != array_job_id:
        raise DiscoveryError("continuation output root differs from the Slurm array ID")
    plan = json.loads(plan_path.read_text(encoding="ascii"))
    groups = _validate_executable_plan(plan)
    bundles = _continuation_bundles(plan)
    if not 0 <= bundle_index < len(bundles):
        raise DiscoveryError("continuation bundle index is outside the plan")
    output_root.mkdir(parents=True, exist_ok=True)
    manifests = [
        _run_continuation_group(
            plan_path=plan_path,
            plan=plan,
            group=groups[phase_group_index],
            array_job_id=array_job_id,
            array_task_id=array_task_id,
            output_root=output_root,
        )
        for phase_group_index in bundles[bundle_index]
    ]
    return {
        "schema_version": "q66-discovery-continuation-bundle-v1",
        "plan_sha256": _sha256(plan_path),
        "phase_index": plan["phase_index"],
        "bundle_index": bundle_index,
        "phase_group_indices": list(bundles[bundle_index]),
        "source_group_indices": [
            manifest["source_group_index"] for manifest in manifests
        ],
        "slurm_array_job_id": array_job_id,
        "slurm_array_task_id": array_task_id,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--matrix", type=Path, required=True)
    analyze.add_argument(
        "--phase",
        type=Path,
        nargs=2,
        action="append",
        metavar=("SPEC", "RESULTS_ROOT"),
    )
    analyze.add_argument("--previous-analysis", type=Path)
    analyze.add_argument("--latest-spec", type=Path)
    analyze.add_argument("--latest-results", type=Path)
    analyze.add_argument("--out", type=Path, required=True)
    analyze.add_argument("--bootstrap-resamples", type=int, default=20_000)
    continuation = commands.add_parser("run-continuation-bundle")
    continuation.add_argument("--plan", type=Path, required=True)
    continuation.add_argument("--bundle-index", type=int, required=True)
    continuation.add_argument("--output-root", type=Path, required=True)
    summary = commands.add_parser("continuation-bundle-summary")
    summary.add_argument("--plan", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "analyze":
        if args.previous_analysis:
            if args.phase or not (args.latest_spec and args.latest_results):
                raise DiscoveryError(
                    "incremental analysis requires previous/latest inputs only"
                )
            summary = analyze_discovery_incremental(
                matrix_path=args.matrix,
                previous_analysis_root=args.previous_analysis,
                latest_spec=args.latest_spec,
                latest_results=args.latest_results,
                out_dir=args.out,
                bootstrap_resamples=args.bootstrap_resamples,
            )
        elif args.phase and (args.latest_spec or args.latest_results):
            raise DiscoveryError("use either --phase or --latest-spec/--latest-results")
        elif args.phase:
            phase_arguments = [tuple(value) for value in args.phase]
            summary = analyze_discovery(
                matrix_path=args.matrix,
                phase_arguments=phase_arguments,
                out_dir=args.out,
                bootstrap_resamples=args.bootstrap_resamples,
            )
        elif args.latest_spec and args.latest_results:
            phase_arguments = _phase_arguments_from_latest(
                args.matrix, args.latest_spec, args.latest_results
            )
            summary = analyze_discovery(
                matrix_path=args.matrix,
                phase_arguments=phase_arguments,
                out_dir=args.out,
                bootstrap_resamples=args.bootstrap_resamples,
            )
        else:
            raise DiscoveryError("analysis phase inputs are required")
        print(json.dumps(summary, sort_keys=True))
    elif args.command == "run-continuation-bundle":
        result = run_continuation_bundle(
            args.plan, args.bundle_index, args.output_root
        )
        print(json.dumps(result, sort_keys=True))
    elif args.command == "continuation-bundle-summary":
        plan = json.loads(args.plan.read_text(encoding="ascii"))
        bundles = _continuation_bundles(plan)
        print(
            json.dumps(
                {
                    "plan": str(args.plan),
                    "plan_sha256": _sha256(args.plan),
                    "phase_index": plan["phase_index"],
                    "group_count": plan["group_count"],
                    "bundle_count": len(bundles),
                    "array_range": (
                        f"0-{len(bundles) - 1}" if bundles else None
                    ),
                    "bundles": [list(bundle) for bundle in bundles],
                },
                sort_keys=True,
            )
        )
    else:
        raise DiscoveryError(f"unsupported command {args.command!r}")


if __name__ == "__main__":
    main()
