"""Analyze and continue the preregistered headline confirmation in one job."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analyze import verify_checksums
from .confirmation import (
    CONFIRMATION_POLICIES,
    CONFIRMATION_SAMPLING,
    load_confirmation_matrix,
)
from .confirmation_run import (
    FROZEN_CANDIDATE_COMMIT,
    FROZEN_CANDIDATE_TREE_SHA256,
    GROUP_SCHEMA,
    RUN_SCHEMA,
    _run_one,
    _validate_one,
)
from .config import SimulationRequest
from .dev_validator import _candidate_tree_sha256
from .stats import benjamini_hochberg, paired_comparison


ANALYSIS_SCHEMA = "q66-confirmation-analysis-v1"
CONTINUATION_SCHEMA = "q66-confirmation-continuation-v1"
CONTINUATION_GROUP_SCHEMA = "q66-confirmation-continuation-group-v1"
CONTINUATION_RUN_SCHEMA = "q66-confirmation-continuation-run-v1"
FDR_Q = 0.05
MIN_FAILURES = 1_000
MAX_SHOTS = 20_000_000
REQUIRED_PRECISION_FRACTION = 0.8
ANALYSIS_CHECKSUM_NAMES = {
    "analysis-summary.json",
    "confirmation-cells.parquet",
    "confirmation-comparisons.parquet",
    "continuation-plan.json",
}


class ConfirmationCycleError(RuntimeError):
    """Raised when confirmation evidence or continuation provenance is invalid."""


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


def _wilson_interval(failures: int, shots: int) -> tuple[float, float]:
    if shots <= 0 or failures < 0 or failures > shots:
        raise ConfirmationCycleError("invalid binomial counts")
    z = 1.959963984540054
    estimate = failures / shots
    denominator = 1.0 + z * z / shots
    center = (estimate + z * z / (2.0 * shots)) / denominator
    radius = z * np.sqrt(
        estimate * (1.0 - estimate) / shots + z * z / (4.0 * shots * shots)
    ) / denominator
    return float(center - radius), float(center + radius)


def _zero_failure_upper(shots: int) -> float:
    return float(1.0 - 0.05 ** (1.0 / shots))


def _bootstrap_seed(matrix_sha256: str, group_index: int, policy: str) -> int:
    digest = hashlib.sha256(
        b"q66-confirmation-bootstrap-v1\0"
        + matrix_sha256.encode("ascii")
        + group_index.to_bytes(4, "little")
        + policy.encode("ascii")
    ).digest()
    return int.from_bytes(digest[:8], "little")


def _cell_status(failures: int, shots: int) -> str:
    if failures >= MIN_FAILURES:
        return "target_met"
    if shots >= MAX_SHOTS:
        return "inconclusive_at_budget"
    return "continue"


def _precision_status(
    *, baseline_rate: float, lower: float, upper: float, shots: int
) -> tuple[str, float, float]:
    if not 0.0 <= baseline_rate <= 1.0 or lower > upper:
        raise ConfirmationCycleError("invalid paired precision inputs")
    half_width = (upper - lower) / 2.0
    threshold = max(0.2 * baseline_rate, 0.0001)
    if half_width <= threshold:
        status = "precision_met"
    elif shots >= MAX_SHOTS:
        status = "inconclusive_at_budget"
    else:
        status = "continue"
    return status, float(half_width), float(threshold)


def _next_run_id(base_run_id: str, shot_start: int, shots: int) -> str:
    suffix = f"-s{shot_start}-n{shots}"
    if len(base_run_id) + len(suffix) <= 128:
        return base_run_id + suffix
    digest = hashlib.sha256(base_run_id.encode("ascii")).hexdigest()[:12]
    prefix_length = 128 - len(suffix) - len(digest) - 1
    return f"{base_run_id[:prefix_length]}-{digest}{suffix}"


def _paired_request_view(request: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in request.items()
        if key not in {"run_id", "shots", "shot_start", "shard_size", "policy"}
    }


def _phase_record(
    phase_index: int, spec_path: Path, results_root: Path, group_count: int
) -> dict[str, Any]:
    return {
        "phase_index": phase_index,
        "spec": str(spec_path),
        "spec_sha256": _sha256(spec_path),
        "results_root": str(results_root),
        "group_count": group_count,
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ConfirmationCycleError(f"JSON artifact is not an object: {path}")
    return value


def _verify_checksum_manifest(
    root: Path, name: str, expected_names: set[str]
) -> None:
    checksum_path = root / name
    entries: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, relative_name = line.partition("  ")
        relative = Path(relative_name)
        if (
            separator != "  "
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not relative_name
            or "\\" in relative_name
            or relative.is_absolute()
            or ".." in relative.parts
            or relative_name in entries
        ):
            raise ConfirmationCycleError(f"invalid checksum entry in {checksum_path}")
        entries[relative_name] = digest
    if set(entries) != expected_names:
        raise ConfirmationCycleError(f"checksum coverage changed in {checksum_path}")
    for relative_name, digest in entries.items():
        artifact = root / relative_name
        if not artifact.is_file() or _sha256(artifact) != digest:
            raise ConfirmationCycleError(f"checksum mismatch for {artifact}")


def _validate_group_evidence(
    *,
    group_root: Path,
    group_manifest: dict[str, Any],
    requests: list[dict[str, Any]],
) -> None:
    evidence = group_manifest.get("runs")
    validation = group_manifest.get("validation")
    expected_ids = [request["run_id"] for request in requests]
    if (
        not isinstance(evidence, list)
        or not isinstance(validation, list)
        or len(evidence) != 5
        or len(validation) != 5
        or [row.get("run_id") for row in evidence if isinstance(row, dict)]
        != expected_ids
        or [row.get("run_id") for row in validation if isinstance(row, dict)]
        != expected_ids
    ):
        raise ConfirmationCycleError("confirmation group evidence order changed")
    shot_id_hashes = set()
    for request_value, run_evidence, replay in zip(
        requests, evidence, validation, strict=True
    ):
        if not isinstance(run_evidence, dict) or not isinstance(replay, dict):
            raise ConfirmationCycleError("confirmation group evidence is invalid")
        request = SimulationRequest.from_dict(request_value)
        request_name = run_evidence.get("request")
        runner_name = run_evidence.get("runner")
        if (
            not isinstance(request_name, str)
            or not isinstance(runner_name, str)
            or Path(request_name).name != request_name
            or Path(runner_name).name != runner_name
            or not re.fullmatch(r"[0-9a-f]{64}", str(run_evidence.get("request_sha256")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(run_evidence.get("runner_sha256")))
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(run_evidence.get("run_checksums_sha256"))
            )
        ):
            raise ConfirmationCycleError("confirmation runner evidence changed")
        request_path = group_root / request_name
        runner_path = group_root / runner_name
        run_root = group_root / request.run_id
        if (
            not request_path.is_file()
            or _sha256(request_path) != run_evidence["request_sha256"]
            or _load_json_object(request_path) != request.as_dict()
            or not runner_path.is_file()
            or _sha256(runner_path) != run_evidence["runner_sha256"]
            or _sha256(run_root / "checksums.sha256")
            != run_evidence["run_checksums_sha256"]
            or replay.get("shots") != request.shots
            or replay.get("shot_start") != request.shot_start
            or replay.get("validation") != "exact-replay-passed"
        ):
            raise ConfirmationCycleError("confirmation runner evidence mismatch")
        shot_id_hash = replay.get("shot_id_sha256")
        failure_hash = replay.get("logical_failure_sha256")
        if (
            not isinstance(shot_id_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", shot_id_hash)
            or not isinstance(failure_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", failure_hash)
        ):
            raise ConfirmationCycleError("confirmation replay digest changed")
        shot_id_hashes.add(shot_id_hash)
    if len(shot_id_hashes) != 1:
        raise ConfirmationCycleError("confirmation paired replay shot IDs differ")


def _validate_continuation_plan(
    plan: dict[str, Any], matrix: dict[str, Any], matrix_sha256: str
) -> list[dict[str, Any]]:
    expected_keys = {
        "schema_version",
        "phase_index",
        "initial_matrix",
        "initial_matrix_sha256",
        "source_commit",
        "environment_lock_sha256",
        "parent_phases",
        "stopping_rule",
        "group_count",
        "cell_count",
        "total_requested_shots",
        "groups",
    }
    if not isinstance(plan, dict) or set(plan) != expected_keys:
        raise ConfirmationCycleError("confirmation continuation fields changed")
    if plan["schema_version"] != CONTINUATION_SCHEMA:
        raise ConfirmationCycleError("unsupported confirmation continuation schema")
    phase_index = plan["phase_index"]
    parent_phases = plan["parent_phases"]
    initial_matrix = plan["initial_matrix"]
    if (
        type(phase_index) is not int
        or not 2 <= phase_index <= 12
        or not isinstance(initial_matrix, str)
        or not Path(initial_matrix).is_absolute()
        or not isinstance(parent_phases, list)
        or len(parent_phases) != phase_index - 1
    ):
        raise ConfirmationCycleError("confirmation continuation phase provenance changed")
    previous_group_count = 8
    for expected_phase, record in enumerate(parent_phases, start=1):
        if (
            not isinstance(record, dict)
            or set(record)
            != {
                "phase_index",
                "spec",
                "spec_sha256",
                "results_root",
                "group_count",
            }
            or record["phase_index"] != expected_phase
            or not isinstance(record["spec"], str)
            or not Path(record["spec"]).is_absolute()
            or not re.fullmatch(r"[0-9a-f]{64}", str(record["spec_sha256"]))
            or not isinstance(record["results_root"], str)
            or not Path(record["results_root"]).is_absolute()
            or type(record["group_count"]) is not int
            or not 1 <= record["group_count"] <= previous_group_count
        ):
            raise ConfirmationCycleError("confirmation parent phase record changed")
        previous_group_count = record["group_count"]
    if parent_phases[0]["group_count"] != 8:
        raise ConfirmationCycleError("confirmation initial phase is incomplete")
    if (
        plan["initial_matrix_sha256"] != matrix_sha256
        or plan["source_commit"] != matrix["source_commit"]
        or plan["environment_lock_sha256"] != matrix["environment_lock_sha256"]
        or plan["stopping_rule"] != CONFIRMATION_SAMPLING
    ):
        raise ConfirmationCycleError("confirmation continuation provenance changed")
    groups = plan.get("groups")
    if (
        not isinstance(groups, list)
        or plan["group_count"] != len(groups)
        or plan["cell_count"] != 5 * len(groups)
    ):
        raise ConfirmationCycleError("confirmation continuation shape changed")
    base_groups = {int(group["group_index"]): group for group in matrix["groups"]}
    requested_shots = 0
    seen_sources: set[int] = set()
    ordered_sources: list[int] = []
    expected_shot_start = min(20_000 * 2 ** (phase_index - 2), MAX_SHOTS)
    for phase_group_index, group in enumerate(groups):
        if not isinstance(group, dict) or set(group) != {
            "phase_group_index",
            "source_group_index",
            "physical_key",
            "shot_start",
            "shots",
            "requests",
        }:
            raise ConfirmationCycleError("confirmation continuation group changed")
        source_index = group["source_group_index"]
        if (
            group["phase_group_index"] != phase_group_index
            or type(source_index) is not int
            or source_index not in base_groups
            or source_index in seen_sources
        ):
            raise ConfirmationCycleError("confirmation continuation group order changed")
        seen_sources.add(source_index)
        ordered_sources.append(source_index)
        base_group = base_groups[source_index]
        if group["physical_key"] != base_group["physical_key"]:
            raise ConfirmationCycleError("confirmation continuation physics changed")
        shot_start = group["shot_start"]
        shots = group["shots"]
        if (
            type(shot_start) is not int
            or type(shots) is not int
            or shot_start != expected_shot_start
            or shots <= 0
            or shot_start + shots > MAX_SHOTS
            or shots != min(shot_start, MAX_SHOTS - shot_start)
        ):
            raise ConfirmationCycleError("confirmation continuation is not paired doubling")
        requests = group["requests"]
        if not isinstance(requests, list) or len(requests) != 5:
            raise ConfirmationCycleError("confirmation continuation is not five policies")
        if [request["policy"] for request in requests] != CONFIRMATION_POLICIES:
            raise ConfirmationCycleError("confirmation continuation policies changed")
        for request_value, base_value in zip(
            requests, base_group["requests"], strict=True
        ):
            request = SimulationRequest.from_dict(request_value)
            base = SimulationRequest.from_dict(base_value)
            if (
                request.shot_start != shot_start
                or request.shots != shots
                or request.master_seed != base.master_seed
                or request.policy.as_dict() != base.policy.as_dict()
                or _paired_request_view(request.as_dict())
                != _paired_request_view(base.as_dict())
                or request.run_id != _next_run_id(base.run_id, shot_start, shots)
            ):
                raise ConfirmationCycleError("confirmation continuation request changed")
        requested_shots += 5 * shots
    if ordered_sources != sorted(ordered_sources):
        raise ConfirmationCycleError("confirmation continuation source order changed")
    if plan["total_requested_shots"] != requested_shots:
        raise ConfirmationCycleError("confirmation continuation shot count changed")
    return groups


def _load_failure_view(
    run_root: Path, expected_request: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    verify_checksums(run_root)
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="ascii"))
    request = SimulationRequest.from_dict(expected_request)
    if (
        manifest.get("status") != "completed"
        or manifest.get("run_id") != request.run_id
        or manifest.get("request") != request.as_dict()
        or manifest.get("source_commit") != request.source_commit
    ):
        raise ConfirmationCycleError(f"run identity mismatch: {run_root}")
    id_parts = []
    failure_parts = []
    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise ConfirmationCycleError(f"run shards are invalid: {run_root}")
    for shard in shards:
        with np.load(run_root / str(shard["labels"]), allow_pickle=False) as payload:
            if "shot_id" not in payload.files or "logical_failure" not in payload.files:
                raise ConfirmationCycleError(f"run labels are incomplete: {run_root}")
            shot_id = np.asarray(payload["shot_id"])
            failure = np.asarray(payload["logical_failure"])
            if (
                shot_id.dtype != np.uint64
                or failure.dtype != np.uint8
                or shot_id.ndim != 1
                or failure.shape != shot_id.shape
                or np.any(failure > 1)
            ):
                raise ConfirmationCycleError(f"run label arrays are invalid: {run_root}")
            id_parts.append(shot_id)
            failure_parts.append(failure)
    ids = np.concatenate(id_parts)
    failures = np.concatenate(failure_parts)
    expected_ids = np.arange(
        request.shot_start,
        request.shot_start + request.shots,
        dtype=np.uint64,
    )
    if not np.array_equal(ids, expected_ids):
        raise ConfirmationCycleError(f"run shot IDs are not contiguous: {run_root}")
    aggregate = manifest.get("aggregate")
    if (
        not isinstance(aggregate, dict)
        or int(aggregate.get("shots", -1)) != request.shots
        or int(aggregate.get("logical_failures", -1))
        != int(np.count_nonzero(failures))
    ):
        raise ConfirmationCycleError(f"run aggregate differs from labels: {run_root}")
    return ids, failures, aggregate


def _validate_phase_evidence(
    *,
    phase_index: int,
    spec_path: Path,
    results_root: Path,
    matrix: dict[str, Any],
    matrix_sha256: str,
    groups: list[dict[str, Any]],
) -> None:
    summary_path = results_root / "run-summary.json"
    summary = _load_json_object(summary_path)
    slurm_job_id = summary.get("slurm_job_id")
    if not isinstance(slurm_job_id, str) or slurm_job_id != results_root.name:
        raise ConfirmationCycleError("confirmation phase Slurm identity changed")
    summary_groups = summary.get("groups")
    if not isinstance(summary_groups, list) or len(summary_groups) != len(groups):
        raise ConfirmationCycleError("confirmation phase summary groups changed")

    expected_checksum_names = {"run-summary.json"}
    if phase_index == 1:
        if (
            summary.get("schema_version") != RUN_SCHEMA
            or summary.get("status") != "initial-confirmation-complete"
            or summary.get("matrix_sha256") != matrix_sha256
            or summary.get("candidate_commit") != FROZEN_CANDIDATE_COMMIT
            or summary.get("candidate_tree_sha256")
            != FROZEN_CANDIDATE_TREE_SHA256
            or summary.get("group_count") != 8
            or summary.get("cell_count") != 40
            or summary.get("total_shots") != 800_000
            or summary.get("validation")
            != "exact-replay-passed-for-every-run"
        ):
            raise ConfirmationCycleError("initial confirmation summary changed")
        matrix_name = summary.get("matrix")
        if (
            not isinstance(matrix_name, str)
            or Path(matrix_name).name != matrix_name
            or _sha256(results_root / matrix_name) != matrix_sha256
        ):
            raise ConfirmationCycleError("initial confirmation matrix copy changed")
        expected_checksum_names.add(matrix_name)
    else:
        if (
            summary.get("schema_version") != CONTINUATION_RUN_SCHEMA
            or summary.get("status") != "confirmation-continuation-complete"
            or summary.get("phase_index") != phase_index
            or summary.get("plan_sha256") != _sha256(spec_path)
            or summary.get("candidate_commit") != FROZEN_CANDIDATE_COMMIT
            or summary.get("candidate_tree_sha256")
            != FROZEN_CANDIDATE_TREE_SHA256
            or summary.get("group_count") != len(groups)
            or summary.get("cell_count") != 5 * len(groups)
            or summary.get("total_shots")
            != sum(5 * int(group["shots"]) for group in groups)
            or summary.get("validation")
            != "exact-replay-passed-for-every-run"
        ):
            raise ConfirmationCycleError("confirmation continuation summary changed")

    for position, (group, summary_group) in enumerate(
        zip(groups, summary_groups, strict=True)
    ):
        if not isinstance(summary_group, dict):
            raise ConfirmationCycleError("confirmation group summary is invalid")
        source_index = int(group["source_group_index"])
        group_relative = f"group-{source_index:02d}/group-manifest.json"
        summary_index_key = (
            "group_index" if phase_index == 1 else "source_group_index"
        )
        if (
            summary_group.get(summary_index_key) != source_index
            or summary_group.get("group_manifest") != group_relative
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(summary_group.get("group_manifest_sha256"))
            )
        ):
            raise ConfirmationCycleError("confirmation group summary changed")
        group_root = results_root / f"group-{source_index:02d}"
        manifest_path = results_root / group_relative
        if _sha256(manifest_path) != summary_group["group_manifest_sha256"]:
            raise ConfirmationCycleError("confirmation group manifest digest changed")
        manifest = _load_json_object(manifest_path)
        if phase_index == 1:
            if (
                manifest.get("schema_version") != GROUP_SCHEMA
                or manifest.get("slurm_job_id") != slurm_job_id
                or manifest.get("matrix_sha256") != matrix_sha256
                or manifest.get("group_index") != source_index
                or manifest.get("physical_key") != matrix["groups"][position]["physical_key"]
            ):
                raise ConfirmationCycleError("initial confirmation group identity changed")
        elif (
            manifest.get("schema_version") != CONTINUATION_GROUP_SCHEMA
            or manifest.get("slurm_job_id") != slurm_job_id
            or manifest.get("plan_sha256") != _sha256(spec_path)
            or manifest.get("phase_index") != phase_index
            or manifest.get("source_group_index") != source_index
        ):
            raise ConfirmationCycleError("continuation confirmation group identity changed")
        _validate_group_evidence(
            group_root=group_root,
            group_manifest=manifest,
            requests=list(group["requests"]),
        )
        expected_checksum_names.add(group_relative)
    _verify_checksum_manifest(
        results_root, "result-checksums.sha256", expected_checksum_names
    )


def _phase_groups(
    *,
    phase_index: int,
    spec_path: Path,
    results_root: Path,
    matrix: dict[str, Any],
    matrix_sha256: str,
) -> dict[int, list[dict[str, Any]]]:
    value = json.loads(spec_path.read_text(encoding="ascii"))
    if phase_index == 1:
        if _sha256(spec_path) != matrix_sha256:
            raise ConfirmationCycleError("first confirmation phase is not the matrix")
        groups = [
            {
                "source_group_index": group["group_index"],
                "requests": group["requests"],
            }
            for group in matrix["groups"]
        ]
    else:
        groups = _validate_continuation_plan(value, matrix, matrix_sha256)
        if value["phase_index"] != phase_index:
            raise ConfirmationCycleError("confirmation phase index changed")
    result: dict[int, list[dict[str, Any]]] = {}
    for group in groups:
        source_index = int(group["source_group_index"])
        group_root = results_root / f"group-{source_index:02d}"
        if not (group_root / "group-manifest.json").is_file():
            raise ConfirmationCycleError(f"confirmation group is missing: {group_root}")
        result[source_index] = list(group["requests"])
    if {entry.name for entry in results_root.iterdir() if entry.is_dir()} != {
        f"group-{index:02d}" for index in result
    }:
        raise ConfirmationCycleError("confirmation phase group layout is incomplete")
    _validate_phase_evidence(
        phase_index=phase_index,
        spec_path=spec_path,
        results_root=results_root,
        matrix=matrix,
        matrix_sha256=matrix_sha256,
        groups=groups,
    )
    return result


def _continuation_plan(
    *,
    matrix: dict[str, Any],
    matrix_path: Path,
    matrix_sha256: str,
    phase_records: list[dict[str, Any]],
    cell_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    cells_by_group: dict[int, list[dict[str, Any]]] = {}
    comparisons_by_group: dict[int, list[dict[str, Any]]] = {}
    for row in cell_rows:
        cells_by_group.setdefault(int(row["group_index"]), []).append(row)
    for row in comparison_rows:
        comparisons_by_group.setdefault(int(row["group_index"]), []).append(row)
    groups = []
    for source_group in matrix["groups"]:
        source_index = int(source_group["group_index"])
        cells = cells_by_group[source_index]
        comparisons = comparisons_by_group[source_index]
        totals = {int(row["shots"]) for row in cells}
        if len(cells) != 5 or len(comparisons) != 4 or len(totals) != 1:
            raise ConfirmationCycleError("confirmation stopping rows are incomplete")
        current_shots = totals.pop()
        needs_more = any(row["sampling_status"] == "continue" for row in cells) or any(
            row["precision_status"] == "continue" for row in comparisons
        )
        if not needs_more:
            continue
        if current_shots <= 0 or current_shots >= MAX_SHOTS:
            raise ConfirmationCycleError("invalid confirmation continuation at budget")
        next_shots = min(current_shots, MAX_SHOTS - current_shots)
        requests = []
        for base_value in source_group["requests"]:
            request = dict(base_value)
            request["run_id"] = _next_run_id(
                str(base_value["run_id"]), current_shots, next_shots
            )
            request["shot_start"] = current_shots
            request["shots"] = next_shots
            request["shard_size"] = min(int(base_value["shard_size"]), next_shots)
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
    plan = {
        "schema_version": CONTINUATION_SCHEMA,
        "phase_index": len(phase_records) + 1,
        "initial_matrix": str(matrix_path),
        "initial_matrix_sha256": matrix_sha256,
        "source_commit": matrix["source_commit"],
        "environment_lock_sha256": matrix["environment_lock_sha256"],
        "parent_phases": phase_records,
        "stopping_rule": matrix["sampling"],
        "group_count": len(groups),
        "cell_count": 5 * len(groups),
        "total_requested_shots": sum(5 * group["shots"] for group in groups),
        "groups": groups,
    }
    _validate_continuation_plan(plan, matrix, matrix_sha256)
    return plan


def analyze_confirmation(
    *,
    matrix_path: Path,
    phase_arguments: list[tuple[Path, Path]],
    out_dir: Path,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise ConfirmationCycleError("confirmation analysis must run inside Slurm")
    if bootstrap_resamples != 20_000:
        raise ConfirmationCycleError("confirmation bootstrap count must remain 20000")
    matrix_path = matrix_path.resolve(strict=True)
    matrix = load_confirmation_matrix(matrix_path)
    matrix_sha256 = _sha256(matrix_path)
    if not phase_arguments:
        raise ConfirmationCycleError("confirmation analysis has no phases")
    if out_dir.exists():
        raise ConfirmationCycleError(f"confirmation analysis output exists: {out_dir}")
    out_dir.mkdir(parents=True)

    phase_records = []
    phase_groups = []
    for phase_index, (spec_path_value, results_root_value) in enumerate(
        phase_arguments, start=1
    ):
        spec_path = spec_path_value.resolve(strict=True)
        results_root = results_root_value.resolve(strict=True)
        groups = _phase_groups(
            phase_index=phase_index,
            spec_path=spec_path,
            results_root=results_root,
            matrix=matrix,
            matrix_sha256=matrix_sha256,
        )
        if phase_index > 1:
            plan = json.loads(spec_path.read_text(encoding="ascii"))
            if plan["parent_phases"] != phase_records:
                raise ConfirmationCycleError("confirmation parent phase provenance changed")
        phase_records.append(
            _phase_record(phase_index, spec_path, results_root, len(groups))
        )
        phase_groups.append((results_root, groups))

    for source_index in range(len(matrix["groups"])):
        presence = [source_index in groups for _, groups in phase_groups]
        first_missing = next(
            (index for index, present in enumerate(presence) if not present),
            len(presence),
        )
        if any(presence[first_missing:]):
            raise ConfirmationCycleError("stopped confirmation group reappeared")

    cell_rows = []
    comparison_rows = []
    none_key = _policy_key({"name": "none"})
    for source_group in matrix["groups"]:
        source_index = int(source_group["group_index"])
        base_requests = {
            _policy_key(request["policy"]): request
            for request in source_group["requests"]
        }
        cumulative_ids: dict[str, list[np.ndarray]] = {
            policy: [] for policy in base_requests
        }
        cumulative_failures: dict[str, list[np.ndarray]] = {
            policy: [] for policy in base_requests
        }
        cumulative_aggregates: dict[str, list[dict[str, Any]]] = {
            policy: [] for policy in base_requests
        }
        expected_start = 0
        for results_root, groups in phase_groups:
            requests = groups.get(source_index)
            if requests is None:
                break
            starts = {int(request["shot_start"]) for request in requests}
            shots_values = {int(request["shots"]) for request in requests}
            if starts != {expected_start} or len(shots_values) != 1:
                raise ConfirmationCycleError("confirmation phase ranges are not paired")
            phase_shots = shots_values.pop()
            reference_ids: np.ndarray | None = None
            for request in requests:
                policy = _policy_key(request["policy"])
                if policy not in base_requests:
                    raise ConfirmationCycleError("confirmation phase policy changed")
                run_root = results_root / f"group-{source_index:02d}" / request["run_id"]
                ids, failures, aggregate = _load_failure_view(run_root, request)
                if reference_ids is None:
                    reference_ids = ids
                elif not np.array_equal(reference_ids, ids):
                    raise ConfirmationCycleError("confirmation policy shot IDs differ")
                cumulative_ids[policy].append(ids)
                cumulative_failures[policy].append(failures)
                cumulative_aggregates[policy].append(aggregate)
            expected_start += phase_shots

        failures_by_policy: dict[str, np.ndarray] = {}
        rows_by_policy: dict[str, dict[str, Any]] = {}
        for policy, base_request in base_requests.items():
            ids = np.concatenate(cumulative_ids[policy])
            failures = np.concatenate(cumulative_failures[policy])
            if not np.array_equal(ids, np.arange(ids.size, dtype=np.uint64)):
                raise ConfirmationCycleError("confirmation cumulative IDs are not contiguous")
            failures_by_policy[policy] = failures
            failure_count = int(np.count_nonzero(failures))
            shots = int(failures.size)
            lower, upper = _wilson_interval(failure_count, shots)
            aggregates = cumulative_aggregates[policy]
            row = {
                "group_index": source_index,
                **source_group["physical_key"],
                "policy": policy,
                "policy_name": base_request["policy"]["name"],
                "policy_interval": base_request["policy"].get("interval"),
                "policy_fraction": base_request["policy"].get("fraction"),
                "phase_count": len(aggregates),
                "shots": shots,
                "logical_failures": failure_count,
                "logical_error_rate": failure_count / shots,
                "wilson_95_lower": lower,
                "wilson_95_upper": upper,
                "zero_failure_one_sided_95_upper": (
                    _zero_failure_upper(shots) if failure_count == 0 else None
                ),
                "catastrophic_shots": sum(
                    int(value["catastrophic_shots"]) for value in aggregates
                ),
                "reload_requests": sum(
                    int(value["reload_requests"]) for value in aggregates
                ),
                "reload_successes": sum(
                    int(value["reload_successes"]) for value in aggregates
                ),
                "missing_site_boundaries": sum(
                    int(value["missing_site_boundaries"]) for value in aggregates
                ),
                "wall_seconds": sum(float(value["wall_seconds"]) for value in aggregates),
                "compressed_npz_bytes": sum(
                    int(value["compressed_npz_bytes"]) for value in aggregates
                ),
                "sampling_status": _cell_status(failure_count, shots),
            }
            rows_by_policy[policy] = row
            cell_rows.append(row)

        baseline = failures_by_policy[none_key]
        baseline_rate = float(rows_by_policy[none_key]["logical_error_rate"])
        for policy, base_request in base_requests.items():
            if policy == none_key:
                continue
            seed = _bootstrap_seed(matrix_sha256, source_index, policy)
            comparison = paired_comparison(
                baseline,
                failures_by_policy[policy],
                bootstrap_resamples=bootstrap_resamples,
                bootstrap_seed=seed,
            ).as_dict()
            precision_status, half_width, threshold = _precision_status(
                baseline_rate=baseline_rate,
                lower=float(comparison["bootstrap_95_lower"]),
                upper=float(comparison["bootstrap_95_upper"]),
                shots=int(comparison["shots"]),
            )
            comparison_rows.append(
                {
                    "group_index": source_index,
                    **source_group["physical_key"],
                    "baseline_policy": none_key,
                    "candidate_policy": policy,
                    "candidate_policy_name": base_request["policy"]["name"],
                    "candidate_policy_interval": base_request["policy"].get(
                        "interval"
                    ),
                    "candidate_policy_fraction": base_request["policy"].get(
                        "fraction"
                    ),
                    "bootstrap_resamples": bootstrap_resamples,
                    "bootstrap_seed": seed,
                    **comparison,
                    "precision_half_width": half_width,
                    "precision_threshold": threshold,
                    "precision_status": precision_status,
                }
            )

    if len(cell_rows) != 40 or len(comparison_rows) != 32:
        raise ConfirmationCycleError("confirmation analysis is not 40 cells/32 comparisons")
    adjusted = benjamini_hochberg(
        np.asarray([row["sign_test_pvalue"] for row in comparison_rows])
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=matrix_sha256,
        phase_records=phase_records,
        cell_rows=cell_rows,
        comparison_rows=comparison_rows,
    )
    final = plan["group_count"] == 0
    precision_met = sum(
        row["precision_status"] == "precision_met" for row in comparison_rows
    )
    precision_fraction = precision_met / len(comparison_rows)
    for row, adjusted_pvalue in zip(comparison_rows, adjusted, strict=True):
        row["bh_adjusted_pvalue"] = float(adjusted_pvalue)
        row["fdr_q"] = FDR_Q
        if adjusted_pvalue <= FDR_Q and row["bootstrap_95_upper"] < 0.0:
            classification = "helpful"
        elif adjusted_pvalue <= FDR_Q and row["bootstrap_95_lower"] > 0.0:
            classification = "harmful"
        else:
            classification = "no_significant_difference"
        row["statistical_classification"] = classification
        row["evidence_classification"] = (
            "provisional"
            if not final
            else (
                "inconclusive_at_budget"
                if row["precision_status"] == "inconclusive_at_budget"
                else classification
            )
        )

    cells_path = out_dir / "confirmation-cells.parquet"
    comparisons_path = out_dir / "confirmation-comparisons.parquet"
    plan_path = out_dir / "continuation-plan.json"
    summary_path = out_dir / "analysis-summary.json"
    pd.DataFrame(cell_rows).to_parquet(cells_path, index=False)
    pd.DataFrame(comparison_rows).to_parquet(comparisons_path, index=False)
    _canonical_json(plan_path, plan)
    summary = {
        "schema_version": ANALYSIS_SCHEMA,
        "status": "final-confirmation" if final else "provisional",
        "slurm_job_id": slurm_job_id,
        "initial_matrix": str(matrix_path),
        "initial_matrix_sha256": matrix_sha256,
        "phases": phase_records,
        "cells": 40,
        "comparisons": 32,
        "total_cell_shots": sum(int(row["shots"]) for row in cell_rows),
        "bootstrap_resamples_per_comparison": bootstrap_resamples,
        "cell_sampling_status": {
            status: sum(row["sampling_status"] == status for row in cell_rows)
            for status in ("target_met", "continue", "inconclusive_at_budget")
        },
        "comparison_precision_status": {
            status: sum(row["precision_status"] == status for row in comparison_rows)
            for status in ("precision_met", "continue", "inconclusive_at_budget")
        },
        "precision_fraction": precision_fraction,
        "required_precision_fraction": REQUIRED_PRECISION_FRACTION,
        "precision_fraction_gate_met": precision_fraction
        >= REQUIRED_PRECISION_FRACTION,
        "next_phase_groups": plan["group_count"],
        "next_phase_cells": plan["cell_count"],
        "headline_claims_authorized": False,
        "artifacts": [
            cells_path.name,
            comparisons_path.name,
            plan_path.name,
            summary_path.name,
            "analysis-checksums.sha256",
        ],
    }
    _canonical_json(summary_path, summary)
    paths = [cells_path, comparisons_path, plan_path, summary_path]
    (out_dir / "analysis-checksums.sha256").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in sorted(paths)),
        encoding="ascii",
    )
    return summary


def run_confirmation_continuation(
    *,
    plan_path: Path,
    candidate_root: Path,
    output_root: Path,
    simulation_workers: int,
    validation_workers: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id or output_root.name != slurm_job_id:
        raise ConfirmationCycleError("confirmation continuation must match Slurm job")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if not 1 <= simulation_workers <= allocated or not 1 <= validation_workers <= allocated:
        raise ConfirmationCycleError("confirmation continuation workers exceed allocation")
    if not 1 <= timeout_seconds <= 10_800:
        raise ConfirmationCycleError("confirmation continuation timeout changed")
    plan_path = plan_path.resolve(strict=True)
    plan = json.loads(plan_path.read_text(encoding="ascii"))
    matrix_path = Path(plan["initial_matrix"]).resolve(strict=True)
    matrix = load_confirmation_matrix(matrix_path)
    groups = _validate_continuation_plan(plan, matrix, _sha256(matrix_path))
    candidate_root = candidate_root.resolve(strict=True)
    if (
        matrix["source_commit"] != FROZEN_CANDIDATE_COMMIT
        or _candidate_tree_sha256(candidate_root) != FROZEN_CANDIDATE_TREE_SHA256
    ):
        raise ConfirmationCycleError("confirmation continuation candidate changed")
    if not groups:
        raise ConfirmationCycleError("empty confirmation continuation was executed")
    if output_root.exists():
        raise ConfirmationCycleError(f"confirmation continuation output exists: {output_root}")
    staging = output_root.with_name(f".{output_root.name}.phase-{plan['phase_index']}.staging")
    if staging.exists():
        raise ConfirmationCycleError(f"confirmation continuation staging exists: {staging}")
    staging.mkdir(parents=True)

    tasks = []
    ordered = []
    for group in groups:
        source_index = int(group["source_group_index"])
        group_root = staging / f"group-{source_index:02d}"
        group_root.mkdir()
        for request_value in group["requests"]:
            request = SimulationRequest.from_dict(request_value)
            request_path = group_root / f"{request.run_id}.request.json"
            _canonical_json(request_path, request.as_dict())
            run_root = group_root / request.run_id
            tasks.append((candidate_root, request_path, run_root, timeout_seconds))
            ordered.append((group, request_path, run_root))
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=simulation_workers
    ) as executor:
        evidence = list(executor.map(_run_one, tasks))
    if _candidate_tree_sha256(candidate_root) != FROZEN_CANDIDATE_TREE_SHA256:
        raise ConfirmationCycleError("confirmation continuation candidate mutated")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=validation_workers
    ) as executor:
        validation = list(executor.map(_validate_one, [value[2] for value in ordered]))

    offset = 0
    group_summaries = []
    for group in groups:
        source_index = int(group["source_group_index"])
        group_evidence = evidence[offset : offset + 5]
        group_validation = validation[offset : offset + 5]
        offset += 5
        expected_ids = [request["run_id"] for request in group["requests"]]
        if [row["run_id"] for row in group_evidence] != expected_ids or [
            row["run_id"] for row in group_validation
        ] != expected_ids:
            raise ConfirmationCycleError("confirmation continuation result order changed")
        manifest = {
            "schema_version": CONTINUATION_GROUP_SCHEMA,
            "slurm_job_id": slurm_job_id,
            "plan_sha256": _sha256(plan_path),
            "phase_index": plan["phase_index"],
            "source_group_index": source_index,
            "runs": group_evidence,
            "validation": group_validation,
        }
        path = staging / f"group-{source_index:02d}/group-manifest.json"
        _canonical_json(path, manifest)
        group_summaries.append(
            {
                "source_group_index": source_index,
                "group_manifest": str(path.relative_to(staging)),
                "group_manifest_sha256": _sha256(path),
            }
        )
    summary_path = staging / "run-summary.json"
    summary = {
        "schema_version": CONTINUATION_RUN_SCHEMA,
        "status": "confirmation-continuation-complete",
        "slurm_job_id": slurm_job_id,
        "phase_index": plan["phase_index"],
        "plan": str(plan_path),
        "plan_sha256": _sha256(plan_path),
        "candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "candidate_tree_sha256": FROZEN_CANDIDATE_TREE_SHA256,
        "simulation_workers": simulation_workers,
        "validation_workers": validation_workers,
        "group_count": len(groups),
        "cell_count": 5 * len(groups),
        "total_shots": int(plan["total_requested_shots"]),
        "groups": group_summaries,
        "validation": "exact-replay-passed-for-every-run",
    }
    _canonical_json(summary_path, summary)
    checksum_paths = [
        summary_path,
        *[
            staging / str(group["group_manifest"]) for group in group_summaries
        ],
    ]
    (staging / "result-checksums.sha256").write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(staging).as_posix()}\n"
            for path in sorted(checksum_paths)
        ),
        encoding="ascii",
    )
    staging.rename(output_root)
    return summary


def _load_resume_phase_arguments(
    *, matrix_path: Path, resume_analysis: Path
) -> tuple[list[tuple[Path, Path]], dict[str, Any]]:
    """Load only a fully published, checksum-verified provisional analysis."""
    matrix_path = matrix_path.resolve(strict=True)
    matrix = load_confirmation_matrix(matrix_path)
    matrix_sha256 = _sha256(matrix_path)
    resume_root = resume_analysis.resolve(strict=True)
    _verify_checksum_manifest(
        resume_root, "analysis-checksums.sha256", ANALYSIS_CHECKSUM_NAMES
    )
    summary = _load_json_object(resume_root / "analysis-summary.json")
    phase_records = summary.get("phases")
    if (
        summary.get("schema_version") != ANALYSIS_SCHEMA
        or summary.get("status") != "provisional"
        or summary.get("initial_matrix") != str(matrix_path)
        or summary.get("initial_matrix_sha256") != matrix_sha256
        or not isinstance(phase_records, list)
        or not 1 <= len(phase_records) < 11
        or summary.get("next_phase_groups", 0) <= 0
        or summary.get("next_phase_cells", 0) <= 0
    ):
        raise ConfirmationCycleError("confirmation resume analysis is not provisional")

    phase_arguments: list[tuple[Path, Path]] = []
    accepted_records: list[dict[str, Any]] = []
    seen_groups: set[int] | None = None
    for phase_index, record in enumerate(phase_records, start=1):
        if not isinstance(record, dict) or record.get("phase_index") != phase_index:
            raise ConfirmationCycleError("confirmation resume phases are not sequential")
        spec_path = Path(str(record.get("spec"))).resolve(strict=True)
        results_root = Path(str(record.get("results_root"))).resolve(strict=True)
        groups = _phase_groups(
            phase_index=phase_index,
            spec_path=spec_path,
            results_root=results_root,
            matrix=matrix,
            matrix_sha256=matrix_sha256,
        )
        group_indexes = set(groups)
        if seen_groups is not None and not group_indexes <= seen_groups:
            raise ConfirmationCycleError("stopped confirmation group reappeared")
        seen_groups = group_indexes
        accepted = _phase_record(
            phase_index, spec_path, results_root, len(groups)
        )
        if record != accepted:
            raise ConfirmationCycleError("confirmation resume phase record changed")
        if phase_index > 1:
            phase_plan = _load_json_object(spec_path)
            if phase_plan.get("parent_phases") != accepted_records:
                raise ConfirmationCycleError(
                    "confirmation resume parent provenance changed"
                )
        accepted_records.append(accepted)
        phase_arguments.append((spec_path, results_root))

    continuation = _load_json_object(resume_root / "continuation-plan.json")
    groups = _validate_continuation_plan(continuation, matrix, matrix_sha256)
    if (
        continuation.get("phase_index") != len(accepted_records) + 1
        or continuation.get("parent_phases") != accepted_records
        or continuation.get("group_count") != summary["next_phase_groups"]
        or continuation.get("cell_count") != summary["next_phase_cells"]
        or len(groups) != summary["next_phase_groups"]
    ):
        raise ConfirmationCycleError("confirmation resume continuation changed")
    return phase_arguments, summary


def run_cycle(
    *,
    matrix_path: Path,
    initial_results: Path,
    candidate_root: Path,
    analysis_root: Path,
    phase_root: Path,
    simulation_workers: int,
    validation_workers: int,
    timeout_seconds: int,
    bootstrap_resamples: int,
    resume_analysis: Path | None = None,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise ConfirmationCycleError("confirmation cycle must run inside Slurm")
    cycle_summaries = []
    if resume_analysis is None:
        phases = [(matrix_path, initial_results)]
        first_analysis_phase = 1
    else:
        phases, resume_summary = _load_resume_phase_arguments(
            matrix_path=matrix_path,
            resume_analysis=resume_analysis,
        )
        cycle_summaries.append(resume_summary)
        plan_path = resume_analysis.resolve(strict=True) / "continuation-plan.json"
        first_analysis_phase = len(phases) + 1
        results = phase_root / f"phase-{first_analysis_phase}" / slurm_job_id
        run_confirmation_continuation(
            plan_path=plan_path,
            candidate_root=candidate_root,
            output_root=results,
            simulation_workers=simulation_workers,
            validation_workers=validation_workers,
            timeout_seconds=timeout_seconds,
        )
        phases.append((plan_path, results))

    for phase_index in range(first_analysis_phase, 12):
        analysis_out = analysis_root / f"phase-{phase_index}" / slurm_job_id
        analysis = analyze_confirmation(
            matrix_path=matrix_path,
            phase_arguments=phases,
            out_dir=analysis_out,
            bootstrap_resamples=bootstrap_resamples,
        )
        cycle_summaries.append(analysis)
        if analysis["next_phase_groups"] == 0:
            return {
                "status": "confirmation-cycle-complete",
                "slurm_job_id": slurm_job_id,
                "phase_count": phase_index,
                "final_analysis": str(analysis_out),
                "resumed_from": (
                    None if resume_analysis is None else str(resume_analysis)
                ),
                "summaries": cycle_summaries,
            }
        plan_path = analysis_out / "continuation-plan.json"
        next_phase = phase_index + 1
        results = phase_root / f"phase-{next_phase}" / slurm_job_id
        run_confirmation_continuation(
            plan_path=plan_path,
            candidate_root=candidate_root,
            output_root=results,
            simulation_workers=simulation_workers,
            validation_workers=validation_workers,
            timeout_seconds=timeout_seconds,
        )
        phases.append((plan_path, results))
    raise ConfirmationCycleError("confirmation cycle exceeded reachable doubling phases")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    cycle = commands.add_parser("cycle")
    cycle.add_argument("--matrix", type=Path, required=True)
    cycle.add_argument("--initial-results", type=Path, required=True)
    cycle.add_argument("--candidate-root", type=Path, required=True)
    cycle.add_argument("--analysis-root", type=Path, required=True)
    cycle.add_argument("--phase-root", type=Path, required=True)
    cycle.add_argument("--simulation-workers", type=int, required=True)
    cycle.add_argument("--validation-workers", type=int, required=True)
    cycle.add_argument("--timeout-seconds", type=int, default=10_800)
    cycle.add_argument("--bootstrap-resamples", type=int, default=20_000)
    cycle.add_argument("--resume-analysis", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command != "cycle":
        raise ConfirmationCycleError("unsupported confirmation cycle command")
    summary = run_cycle(
        matrix_path=args.matrix,
        initial_results=args.initial_results,
        candidate_root=args.candidate_root,
        analysis_root=args.analysis_root,
        phase_root=args.phase_root,
        simulation_workers=args.simulation_workers,
        validation_workers=args.validation_workers,
        timeout_seconds=args.timeout_seconds,
        bootstrap_resamples=args.bootstrap_resamples,
        resume_analysis=args.resume_analysis,
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
