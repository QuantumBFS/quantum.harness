"""Continue and finalize the preregistered cost-sensitivity experiment."""

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

from .confirmation_cycle import _load_failure_view, _next_run_id
from .confirmation_run import (
    FROZEN_CANDIDATE_COMMIT,
    FROZEN_CANDIDATE_TREE_SHA256,
    _run_one,
    _validate_one,
)
from .config import SimulationRequest
from .dev_validator import _candidate_tree_sha256
from .discovery import (
    _load_previous_analysis,
    _policy_key,
    _sha256 as _discovery_sha256,
    _unpack_logical_failure_row,
    _validate_initial_matrix,
)
from .matrix import load_matrix
from .sensitivity import load_sensitivity_matrix
from .sensitivity_analysis import (
    COST_WEIGHTS,
    FDR_Q,
    MAX_SHOTS,
    _baseline_indices,
    _bootstrap_seed,
    _canonical_json,
    _sampling_status,
    _sha256,
    _wilson_interval,
    _zero_failure_upper,
)
from .stats import benjamini_hochberg, paired_comparison


CYCLE_SCHEMA = "q66-cost-sensitivity-cycle-v1"
PHASE_PLAN_SCHEMA = "q66-cost-sensitivity-continuation-plan-v1"
PHASE_RUN_SCHEMA = "q66-cost-sensitivity-continuation-run-v1"
PHASE_GROUP_SCHEMA = "q66-cost-sensitivity-continuation-group-v1"
FINAL_ANALYSIS_SCHEMA = "q66-cost-sensitivity-final-analysis-v1"


class SensitivityCycleError(RuntimeError):
    """Raised when cost continuation or its provenance is invalid."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise SensitivityCycleError(f"JSON artifact is not an object: {path}")
    return value


def _verify_checksum_manifest(
    root: Path, manifest_name: str, expected_names: set[str]
) -> None:
    entries: dict[str, str] = {}
    path = root / manifest_name
    for line in path.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        relative = Path(name)
        if (
            separator != "  "
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not name
            or name in entries
            or "\\" in name
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise SensitivityCycleError(f"invalid checksum entry in {path}")
        entries[name] = digest
    if set(entries) != expected_names:
        raise SensitivityCycleError(f"checksum coverage changed in {path}")
    for name, digest in entries.items():
        artifact = root / name
        if not artifact.is_file() or _sha256(artifact) != digest:
            raise SensitivityCycleError(f"checksum mismatch: {artifact}")


def _verify_initial_analysis(
    root: Path, matrix_sha256: str, initial_results: Path
) -> dict[str, Any]:
    expected = {
        "analysis-summary.json",
        "continuation-required.json",
        "sensitivity-cells.parquet",
        "sensitivity-comparisons.parquet",
        "sensitivity-costs.parquet",
        "sensitivity-pareto.parquet",
    }
    _verify_checksum_manifest(root, "analysis-checksums.sha256", expected)
    summary = _read_json(root / "analysis-summary.json")
    if (
        summary.get("schema_version") != "q66-cost-sensitivity-analysis-v1"
        or summary.get("sensitivity_matrix_sha256") != matrix_sha256
        or Path(str(summary.get("sensitivity_results"))).resolve()
        != initial_results.resolve()
        or summary.get("cells") != 192
        or summary.get("comparisons") != 192
        or summary.get("bootstrap_resamples_per_comparison") != 20_000
    ):
        raise SensitivityCycleError("initial sensitivity analysis changed")
    return summary


def _physical_token(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _continuation_request(
    base_value: dict[str, Any], shot_start: int, shots: int
) -> dict[str, Any]:
    if shot_start < 20_000 or shots <= 0 or shot_start + shots > MAX_SHOTS:
        raise SensitivityCycleError("invalid cost continuation shot range")
    value = dict(base_value)
    value["run_id"] = _next_run_id(str(base_value["run_id"]), shot_start, shots)
    value["shot_start"] = shot_start
    value["shots"] = shots
    value["shard_size"] = min(int(base_value["shard_size"]), shots)
    SimulationRequest.from_dict(value)
    return value


def _phase_plan(
    *,
    phase_index: int,
    matrix: dict[str, Any],
    matrix_path: Path,
    matrix_sha256: str,
    active_groups: list[int],
    group_shots: dict[int, int],
    baseline_requests: dict[str, dict[str, Any]],
    baseline_shots: dict[str, int],
) -> dict[str, Any]:
    groups = []
    baseline_targets: dict[str, int] = {}
    for source_index in active_groups:
        source = matrix["groups"][source_index]
        current = group_shots[source_index]
        increment = min(current, MAX_SHOTS - current)
        if increment <= 0:
            raise SensitivityCycleError("continuation requested at the shot cap")
        target = current + increment
        token = _physical_token(source["physical_key"])
        baseline_targets[token] = max(baseline_targets.get(token, 0), target)
        groups.append(
            {
                "source_group_index": source_index,
                "physical_key": source["physical_key"],
                "reload_configuration_id": source["reload_configuration_id"],
                "reload": source["reload"],
                "shot_start": current,
                "shots": increment,
                "requests": [
                    _continuation_request(value, current, increment)
                    for value in source["requests"]
                ],
            }
        )
    baselines = []
    for token in sorted(baseline_targets):
        current = baseline_shots[token]
        target = baseline_targets[token]
        if current >= target:
            continue
        baselines.append(
            {
                "physical_key": json.loads(token),
                "shot_start": current,
                "shots": target - current,
                "request": _continuation_request(
                    baseline_requests[token], current, target - current
                ),
            }
        )
    plan = {
        "schema_version": PHASE_PLAN_SCHEMA,
        "phase_index": phase_index,
        "initial_matrix": str(matrix_path),
        "initial_matrix_sha256": matrix_sha256,
        "source_commit": matrix["source_commit"],
        "environment_lock_sha256": matrix["environment_lock_sha256"],
        "stopping_rule": matrix["sampling"],
        "group_count": len(groups),
        "cell_count": 4 * len(groups),
        "baseline_extension_count": len(baselines),
        "total_requested_shots": sum(
            4 * int(group["shots"]) for group in groups
        )
        + sum(int(row["shots"]) for row in baselines),
        "groups": groups,
        "baseline_extensions": baselines,
    }
    _validate_phase_plan(plan, matrix, matrix_sha256)
    return plan


def _paired_request_view(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"run_id", "shots", "shot_start", "shard_size", "policy"}
    }


def _validate_phase_plan(
    plan: dict[str, Any], matrix: dict[str, Any], matrix_sha256: str
) -> None:
    expected_keys = {
        "schema_version",
        "phase_index",
        "initial_matrix",
        "initial_matrix_sha256",
        "source_commit",
        "environment_lock_sha256",
        "stopping_rule",
        "group_count",
        "cell_count",
        "baseline_extension_count",
        "total_requested_shots",
        "groups",
        "baseline_extensions",
    }
    if set(plan) != expected_keys or plan["schema_version"] != PHASE_PLAN_SCHEMA:
        raise SensitivityCycleError("cost continuation plan fields changed")
    if (
        type(plan["phase_index"]) is not int
        or not 2 <= plan["phase_index"] <= 12
        or plan["initial_matrix_sha256"] != matrix_sha256
        or plan["source_commit"] != matrix["source_commit"]
        or plan["environment_lock_sha256"] != matrix["environment_lock_sha256"]
        or plan["stopping_rule"] != matrix["sampling"]
    ):
        raise SensitivityCycleError("cost continuation provenance changed")
    groups = plan["groups"]
    baselines = plan["baseline_extensions"]
    if (
        not isinstance(groups, list)
        or not isinstance(baselines, list)
        or plan["group_count"] != len(groups)
        or plan["cell_count"] != 4 * len(groups)
        or plan["baseline_extension_count"] != len(baselines)
    ):
        raise SensitivityCycleError("cost continuation shape changed")
    seen_groups: set[int] = set()
    total = 0
    for group in groups:
        source_index = group.get("source_group_index")
        if (
            type(source_index) is not int
            or not 0 <= source_index < 48
            or source_index in seen_groups
        ):
            raise SensitivityCycleError("cost continuation group identity changed")
        seen_groups.add(source_index)
        source = matrix["groups"][source_index]
        if (
            group.get("physical_key") != source["physical_key"]
            or group.get("reload_configuration_id")
            != source["reload_configuration_id"]
            or group.get("reload") != source["reload"]
        ):
            raise SensitivityCycleError("cost continuation group physics changed")
        start = group.get("shot_start")
        shots = group.get("shots")
        requests = group.get("requests")
        if (
            type(start) is not int
            or type(shots) is not int
            or shots != min(start, MAX_SHOTS - start)
            or not isinstance(requests, list)
            or len(requests) != 4
        ):
            raise SensitivityCycleError("cost continuation is not paired doubling")
        for value, base in zip(requests, source["requests"], strict=True):
            request = SimulationRequest.from_dict(value)
            if (
                request.shot_start != start
                or request.shots != shots
                or request.master_seed != int(base["master_seed"])
                or request.policy.as_dict() != base["policy"]
                or _paired_request_view(value) != _paired_request_view(base)
            ):
                raise SensitivityCycleError("cost continuation request changed")
        total += 4 * shots
    seen_baselines: set[str] = set()
    for row in baselines:
        token = _physical_token(row.get("physical_key"))
        if token in seen_baselines:
            raise SensitivityCycleError("duplicate baseline extension")
        seen_baselines.add(token)
        start = row.get("shot_start")
        shots = row.get("shots")
        request = SimulationRequest.from_dict(row.get("request"))
        if (
            request.policy.as_dict() != {"name": "none"}
            or {
                "delay_rounds": request.reload.delay_rounds,
                "reset_error_probability": request.reload.reset_error_probability,
                "failure_probability": request.reload.failure_probability,
            }
            != {
                "delay_rounds": 0,
                "reset_error_probability": 0.0,
                "failure_probability": 0.0,
            }
            or request.shot_start != start
            or request.shots != shots
        ):
            raise SensitivityCycleError("baseline continuation request changed")
        total += int(shots)
    if plan["total_requested_shots"] != total:
        raise SensitivityCycleError("cost continuation shot total changed")


def _execute_phase(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    candidate_root: Path,
    results_root: Path,
    workers: int,
    validation_workers: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    job_id = os.environ["SLURM_JOB_ID"]
    staging = results_root.with_name(f".{job_id}.phase-{plan['phase_index']}.staging")
    if results_root.exists() or staging.exists():
        raise SensitivityCycleError("cost continuation phase output already exists")
    staging.mkdir(parents=True)
    plan_sha256 = _sha256(plan_path)
    tasks = []
    ordered: list[tuple[str, str, dict[str, Any], Path, Path]] = []
    for group in plan["groups"]:
        source_index = int(group["source_group_index"])
        group_name = f"group-{source_index:02d}"
        group_root = staging / group_name
        group_root.mkdir()
        for value in group["requests"]:
            request = SimulationRequest.from_dict(value)
            request_path = group_root / f"{request.run_id}.request.json"
            _canonical_json(request_path, request.as_dict())
            run_root = group_root / request.run_id
            tasks.append((candidate_root, request_path, run_root, timeout_seconds))
            ordered.append(("candidate", group_name, value, request_path, run_root))
    for index, row in enumerate(plan["baseline_extensions"]):
        group_name = f"baseline-{index:02d}"
        group_root = staging / group_name
        group_root.mkdir()
        value = row["request"]
        request = SimulationRequest.from_dict(value)
        request_path = group_root / f"{request.run_id}.request.json"
        _canonical_json(request_path, request.as_dict())
        run_root = group_root / request.run_id
        tasks.append((candidate_root, request_path, run_root, timeout_seconds))
        ordered.append(("baseline", group_name, value, request_path, run_root))

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        evidence = list(executor.map(_run_one, tasks))
    if _candidate_tree_sha256(candidate_root) != FROZEN_CANDIDATE_TREE_SHA256:
        raise SensitivityCycleError("candidate tree mutated during cost continuation")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=validation_workers
    ) as executor:
        validation = list(executor.map(_validate_one, [row[4] for row in ordered]))
    if len(evidence) != len(ordered) or len(validation) != len(ordered):
        raise SensitivityCycleError("cost continuation task count changed")

    expected_checksums = {"run-summary.json"}
    summary_groups = []
    offset = 0
    for group in plan["groups"]:
        source_index = int(group["source_group_index"])
        group_name = f"group-{source_index:02d}"
        group_evidence = evidence[offset : offset + 4]
        group_validation = validation[offset : offset + 4]
        offset += 4
        expected_ids = [value["run_id"] for value in group["requests"]]
        if (
            [row["run_id"] for row in group_evidence] != expected_ids
            or [row["run_id"] for row in group_validation] != expected_ids
            or len({row["shot_id_sha256"] for row in group_validation}) != 1
        ):
            raise SensitivityCycleError("cost continuation pairing changed")
        manifest = {
            "schema_version": PHASE_GROUP_SCHEMA,
            "kind": "candidate-group",
            "slurm_job_id": job_id,
            "phase_index": plan["phase_index"],
            "plan_sha256": plan_sha256,
            "source_group_index": source_index,
            "physical_key": group["physical_key"],
            "reload_configuration_id": group["reload_configuration_id"],
            "reload": group["reload"],
            "runs": group_evidence,
            "validation": group_validation,
        }
        path = staging / group_name / "group-manifest.json"
        _canonical_json(path, manifest)
        relative = path.relative_to(staging).as_posix()
        expected_checksums.add(relative)
        summary_groups.append(
            {
                "kind": "candidate-group",
                "source_group_index": source_index,
                "manifest": relative,
                "manifest_sha256": _sha256(path),
            }
        )
    for index, row in enumerate(plan["baseline_extensions"]):
        group_name = f"baseline-{index:02d}"
        run_evidence = evidence[offset]
        run_validation = validation[offset]
        offset += 1
        if run_evidence["run_id"] != row["request"]["run_id"] or run_validation[
            "run_id"
        ] != row["request"]["run_id"]:
            raise SensitivityCycleError("baseline extension identity changed")
        manifest = {
            "schema_version": PHASE_GROUP_SCHEMA,
            "kind": "baseline-extension",
            "slurm_job_id": job_id,
            "phase_index": plan["phase_index"],
            "plan_sha256": plan_sha256,
            "physical_key": row["physical_key"],
            "runs": [run_evidence],
            "validation": [run_validation],
        }
        path = staging / group_name / "group-manifest.json"
        _canonical_json(path, manifest)
        relative = path.relative_to(staging).as_posix()
        expected_checksums.add(relative)
        summary_groups.append(
            {
                "kind": "baseline-extension",
                "physical_key": row["physical_key"],
                "manifest": relative,
                "manifest_sha256": _sha256(path),
            }
        )
    if offset != len(ordered):
        raise SensitivityCycleError("cost continuation result ordering changed")
    summary = {
        "schema_version": PHASE_RUN_SCHEMA,
        "status": "cost-sensitivity-continuation-complete",
        "slurm_job_id": job_id,
        "phase_index": plan["phase_index"],
        "plan": str(plan_path),
        "plan_sha256": plan_sha256,
        "candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "candidate_tree_sha256": FROZEN_CANDIDATE_TREE_SHA256,
        "simulation_workers": workers,
        "validation_workers": validation_workers,
        "groups": summary_groups,
        "candidate_group_count": plan["group_count"],
        "baseline_extension_count": plan["baseline_extension_count"],
        "cell_count": len(ordered),
        "total_shots": plan["total_requested_shots"],
        "validation": "exact-replay-passed-for-every-run",
    }
    _canonical_json(staging / "run-summary.json", summary)
    (staging / "result-checksums.sha256").write_text(
        "".join(
            f"{_sha256(staging / name)}  {name}\n"
            for name in sorted(expected_checksums)
        ),
        encoding="ascii",
    )
    staging.rename(results_root)
    return summary


def _initial_failures_and_aggregates(
    matrix: dict[str, Any], initial_results: Path
) -> tuple[
    dict[int, dict[str, list[np.ndarray]]],
    dict[int, dict[str, list[dict[str, Any]]]],
]:
    failures: dict[int, dict[str, list[np.ndarray]]] = {}
    aggregates: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for group in matrix["groups"]:
        index = int(group["group_index"])
        failures[index] = {}
        aggregates[index] = {}
        reference_ids = None
        for value in group["requests"]:
            policy = _policy_key(value["policy"])
            run_root = initial_results / f"group-{index:02d}" / value["run_id"]
            ids, logical, aggregate = _load_failure_view(run_root, value)
            if reference_ids is None:
                reference_ids = ids
            elif not np.array_equal(reference_ids, ids):
                raise SensitivityCycleError("initial cost policies are not paired")
            failures[index][policy] = [logical]
            aggregates[index][policy] = [aggregate]
    return failures, aggregates


def _baseline_state(
    discovery_matrix: dict[str, Any], discovery: Any
) -> tuple[
    dict[str, list[np.ndarray]], dict[str, int], dict[str, dict[str, Any]]
]:
    indices = _baseline_indices(discovery_matrix)
    arrays: dict[str, list[np.ndarray]] = {}
    shots: dict[str, int] = {}
    requests: dict[str, dict[str, Any]] = {}
    row = 0
    for group in discovery_matrix["groups"]:
        for request in group["requests"]:
            if request["policy"] == {"name": "none"}:
                token = _physical_token(group["physical_key"])
                index = indices[token]
                count = int(discovery.shot_counts[index])
                arrays[token] = [
                    _unpack_logical_failure_row(
                        discovery.packed_failures[index], count
                    )
                ]
                shots[token] = count
                requests[token] = request
            row += 1
    if len(arrays) != 280 or row != 2_240:
        raise SensitivityCycleError("discovery baseline state is incomplete")
    return arrays, shots, requests


def _load_phase_results(
    *,
    plan_path: Path,
    results_root: Path,
    candidate_failures: dict[int, dict[str, list[np.ndarray]]],
    candidate_aggregates: dict[int, dict[str, list[dict[str, Any]]]],
    baseline_failures: dict[str, list[np.ndarray]],
    baseline_shots: dict[str, int],
) -> None:
    plan = _read_json(plan_path)
    summary = _read_json(results_root / "run-summary.json")
    expected = {"run-summary.json"}
    for row in summary.get("groups", []):
        if not isinstance(row, dict) or not isinstance(row.get("manifest"), str):
            raise SensitivityCycleError("cost phase summary groups changed")
        expected.add(row["manifest"])
        path = results_root / row["manifest"]
        if _sha256(path) != row.get("manifest_sha256"):
            raise SensitivityCycleError("cost phase group checksum changed")
    _verify_checksum_manifest(results_root, "result-checksums.sha256", expected)
    if (
        summary.get("schema_version") != PHASE_RUN_SCHEMA
        or summary.get("status") != "cost-sensitivity-continuation-complete"
        or summary.get("phase_index") != plan["phase_index"]
        or summary.get("plan_sha256") != _sha256(plan_path)
        or summary.get("validation") != "exact-replay-passed-for-every-run"
    ):
        raise SensitivityCycleError("cost continuation summary changed")
    for group in plan["groups"]:
        index = int(group["source_group_index"])
        reference_ids = None
        for value in group["requests"]:
            policy = _policy_key(value["policy"])
            run_root = results_root / f"group-{index:02d}" / value["run_id"]
            ids, logical, aggregate = _load_failure_view(run_root, value)
            if reference_ids is None:
                reference_ids = ids
            elif not np.array_equal(reference_ids, ids):
                raise SensitivityCycleError("continued cost policies are not paired")
            candidate_failures[index][policy].append(logical)
            candidate_aggregates[index][policy].append(aggregate)
    for index, row in enumerate(plan["baseline_extensions"]):
        value = row["request"]
        token = _physical_token(row["physical_key"])
        run_root = results_root / f"baseline-{index:02d}" / value["run_id"]
        ids, logical, _ = _load_failure_view(run_root, value)
        if int(ids[0]) != baseline_shots[token]:
            raise SensitivityCycleError("baseline extension is not contiguous")
        baseline_failures[token].append(logical)
        baseline_shots[token] += int(logical.size)


def _final_analysis(
    *,
    matrix: dict[str, Any],
    matrix_path: Path,
    matrix_sha256: str,
    discovery_matrix_path: Path,
    discovery_matrix_sha256: str,
    discovery_analysis_root: Path,
    phase_records: list[dict[str, Any]],
    candidate_failures: dict[int, dict[str, list[np.ndarray]]],
    candidate_aggregates: dict[int, dict[str, list[dict[str, Any]]]],
    baseline_failures: dict[str, list[np.ndarray]],
    out_dir: Path,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    if out_dir.exists():
        raise SensitivityCycleError(f"final cost analysis exists: {out_dir}")
    cell_rows = []
    comparison_rows = []
    baseline_rates: dict[int, float] = {}
    for group in matrix["groups"]:
        index = int(group["group_index"])
        token = _physical_token(group["physical_key"])
        baseline_all = np.concatenate(baseline_failures[token])
        group_lengths = {
            sum(part.size for part in parts)
            for parts in candidate_failures[index].values()
        }
        if len(group_lengths) != 1:
            raise SensitivityCycleError("final cost group lost pairing")
        shots = group_lengths.pop()
        baseline = baseline_all[:shots]
        if baseline.size != shots:
            raise SensitivityCycleError("final cost baseline is too short")
        baseline_rates[index] = float(np.count_nonzero(baseline)) / shots
        for value in group["requests"]:
            policy = _policy_key(value["policy"])
            logical = np.concatenate(candidate_failures[index][policy])
            failure_count = int(np.count_nonzero(logical))
            lower, upper = _wilson_interval(failure_count, shots)
            aggregates = candidate_aggregates[index][policy]
            n_sites = 49
            reload_successes = sum(
                int(row["reload_successes"]) for row in aggregates
            )
            missing = sum(
                int(row["missing_site_boundaries"]) for row in aggregates
            )
            row = {
                "group_index": index,
                **group["physical_key"],
                "reload_configuration_id": group["reload_configuration_id"],
                **group["reload"],
                "policy": policy,
                "policy_name": value["policy"]["name"],
                "policy_interval": value["policy"].get("interval"),
                "policy_fraction": value["policy"].get("fraction"),
                "phase_count": len(aggregates),
                "shots": shots,
                "logical_failures": failure_count,
                "logical_error_rate": failure_count / shots,
                "wilson_95_lower": lower,
                "wilson_95_upper": upper,
                "zero_failure_one_sided_95_upper": (
                    _zero_failure_upper(shots) if failure_count == 0 else None
                ),
                "reload_requests": sum(
                    int(item["reload_requests"]) for item in aggregates
                ),
                "reload_successes": reload_successes,
                "reload_failures": sum(
                    int(item["reload_failures"]) for item in aggregates
                ),
                "missing_site_boundaries": missing,
                "missing_occupancy": missing
                / (shots * (int(group["physical_key"]["rounds"]) + 1) * n_sites),
                "reloads_per_site_round": reload_successes
                / (shots * int(group["physical_key"]["rounds"]) * n_sites),
                "wall_seconds": sum(
                    float(item["wall_seconds"]) for item in aggregates
                ),
                "reload_wait_site_rounds_per_shot": int(
                    group["reload"]["delay_rounds"]
                )
                * reload_successes
                / shots,
                "extra_rounds_per_shot": 0.0,
                "sampling_status": _sampling_status(failure_count, shots),
            }
            cell_rows.append(row)
            seed = _bootstrap_seed(matrix_sha256, index, policy)
            comparison_rows.append(
                {
                    "group_index": index,
                    **group["physical_key"],
                    "reload_configuration_id": group["reload_configuration_id"],
                    "candidate_policy": policy,
                    "bootstrap_resamples": bootstrap_resamples,
                    "bootstrap_seed": seed,
                    **paired_comparison(
                        baseline,
                        logical,
                        bootstrap_resamples=bootstrap_resamples,
                        bootstrap_seed=seed,
                    ).as_dict(),
                }
            )
    if len(cell_rows) != 192 or len(comparison_rows) != 192:
        raise SensitivityCycleError("final cost analysis is not 192 cells")
    if any(row["sampling_status"] == "continue" for row in cell_rows):
        raise SensitivityCycleError("final cost analysis stopped before its rule")
    adjusted = benjamini_hochberg(
        np.asarray([row["sign_test_pvalue"] for row in comparison_rows])
    )
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
        row["evidence_classification"] = classification

    cells_by_group: dict[int, list[dict[str, Any]]] = {}
    for row in cell_rows:
        cells_by_group.setdefault(int(row["group_index"]), []).append(row)
    cost_rows = []
    pareto_rows = []
    for group in matrix["groups"]:
        index = int(group["group_index"])
        alternatives = [
            {
                "policy": _policy_key({"name": "none"}),
                "logical_error_rate": baseline_rates[index],
                "reloads_per_site_round": 0.0,
                "extra_rounds_per_shot": 0.0,
            },
            *[
                {
                    "policy": row["policy"],
                    "logical_error_rate": float(row["logical_error_rate"]),
                    "reloads_per_site_round": float(row["reloads_per_site_round"]),
                    "extra_rounds_per_shot": 0.0,
                }
                for row in cells_by_group[index]
            ],
        ]
        for alternative in alternatives:
            keys = (
                "logical_error_rate",
                "reloads_per_site_round",
                "extra_rounds_per_shot",
            )
            dominated = any(
                other is not alternative
                and all(other[key] <= alternative[key] for key in keys)
                and any(other[key] < alternative[key] for key in keys)
                for other in alternatives
            )
            pareto_rows.append(
                {
                    "group_index": index,
                    **group["physical_key"],
                    "reload_configuration_id": group["reload_configuration_id"],
                    **alternative,
                    "pareto_nondominated": not dominated,
                    "evidence_status": "final",
                }
            )
            for lambda_r, lambda_t in COST_WEIGHTS:
                cost_rows.append(
                    {
                        "group_index": index,
                        **group["physical_key"],
                        "reload_configuration_id": group[
                            "reload_configuration_id"
                        ],
                        **alternative,
                        "lambda_r": lambda_r,
                        "lambda_t": lambda_t,
                        "cost_j": alternative["logical_error_rate"]
                        + lambda_r * alternative["reloads_per_site_round"]
                        + lambda_t
                        * alternative["extra_rounds_per_shot"]
                        / float(group["physical_key"]["rounds"]),
                        "evidence_status": "final",
                    }
                )

    out_dir.mkdir(parents=True)
    cells_path = out_dir / "sensitivity-cells.parquet"
    comparisons_path = out_dir / "sensitivity-comparisons.parquet"
    costs_path = out_dir / "sensitivity-costs.parquet"
    pareto_path = out_dir / "sensitivity-pareto.parquet"
    summary_path = out_dir / "analysis-summary.json"
    pd.DataFrame(cell_rows).to_parquet(cells_path, index=False)
    pd.DataFrame(comparison_rows).to_parquet(comparisons_path, index=False)
    pd.DataFrame(cost_rows).to_parquet(costs_path, index=False)
    pd.DataFrame(pareto_rows).to_parquet(pareto_path, index=False)
    summary = {
        "schema_version": FINAL_ANALYSIS_SCHEMA,
        "status": "final-cost-sensitivity",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "sensitivity_matrix": str(matrix_path),
        "sensitivity_matrix_sha256": matrix_sha256,
        "discovery_matrix": str(discovery_matrix_path),
        "discovery_matrix_sha256": discovery_matrix_sha256,
        "discovery_analysis": str(discovery_analysis_root),
        "phases": phase_records,
        "cells": 192,
        "comparisons": 192,
        "total_cell_shots": sum(int(row["shots"]) for row in cell_rows),
        "bootstrap_resamples_per_comparison": bootstrap_resamples,
        "cost_weights": [
            {"lambda_r": lambda_r, "lambda_t": lambda_t}
            for lambda_r, lambda_t in COST_WEIGHTS
        ],
        "cost_rows": len(cost_rows),
        "pareto_rows": len(pareto_rows),
        "sampling_status": {
            status: sum(row["sampling_status"] == status for row in cell_rows)
            for status in ("target_met", "continue", "inconclusive_at_budget")
        },
        "next_phase_groups": 0,
        "pareto_authorized": True,
        "headline_claims_authorized": False,
    }
    _canonical_json(summary_path, summary)
    artifacts = [
        cells_path,
        comparisons_path,
        costs_path,
        pareto_path,
        summary_path,
    ]
    (out_dir / "analysis-checksums.sha256").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in sorted(artifacts)),
        encoding="ascii",
    )
    return summary


def run_sensitivity_cycle(
    *,
    matrix_path: Path,
    initial_results: Path,
    initial_analysis: Path,
    discovery_matrix_path: Path,
    discovery_analysis_root: Path,
    candidate_root: Path,
    output_root: Path,
    final_analysis_root: Path,
    workers: int,
    validation_workers: int,
    timeout_seconds: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    job_id = os.environ.get("SLURM_JOB_ID")
    if not job_id:
        raise SensitivityCycleError("cost sensitivity cycle must execute inside Slurm")
    if os.environ.get("SLURM_ARRAY_TASK_ID") is not None:
        raise SensitivityCycleError("cost sensitivity cycle must be one allocation")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if not 1 <= workers <= allocated or not 1 <= validation_workers <= allocated:
        raise SensitivityCycleError("cost cycle workers exceed the allocation")
    if not 1 <= timeout_seconds <= 10_800 or bootstrap_resamples != 20_000:
        raise SensitivityCycleError("cost cycle runtime/statistics changed")
    if output_root.name != job_id or final_analysis_root.name != job_id:
        raise SensitivityCycleError("cost cycle output differs from Slurm job ID")
    if output_root.exists() or final_analysis_root.exists():
        raise SensitivityCycleError("cost cycle output already exists")

    matrix_path = matrix_path.resolve(strict=True)
    initial_results = initial_results.resolve(strict=True)
    initial_analysis = initial_analysis.resolve(strict=True)
    discovery_matrix_path = discovery_matrix_path.resolve(strict=True)
    discovery_analysis_root = discovery_analysis_root.resolve(strict=True)
    candidate_root = candidate_root.resolve(strict=True)
    matrix = load_sensitivity_matrix(matrix_path)
    matrix_sha256 = _sha256(matrix_path)
    if matrix["source_commit"] != FROZEN_CANDIDATE_COMMIT:
        raise SensitivityCycleError("cost matrix candidate commit changed")
    if _candidate_tree_sha256(candidate_root) != FROZEN_CANDIDATE_TREE_SHA256:
        raise SensitivityCycleError("cost cycle candidate tree changed")
    _verify_initial_analysis(initial_analysis, matrix_sha256, initial_results)

    discovery_matrix = load_matrix(discovery_matrix_path)
    _validate_initial_matrix(discovery_matrix)
    discovery_matrix_sha256 = _discovery_sha256(discovery_matrix_path)
    discovery = _load_previous_analysis(
        analysis_root=discovery_analysis_root,
        matrix_path=discovery_matrix_path,
        matrix=discovery_matrix,
        matrix_sha256=discovery_matrix_sha256,
    )
    if (
        discovery.summary.get("status") != "final-discovery"
        or discovery.summary.get("next_phase_groups") != 0
    ):
        raise SensitivityCycleError("cost cycle requires final discovery")

    candidate_failures, candidate_aggregates = _initial_failures_and_aggregates(
        matrix, initial_results
    )
    baseline_failures, baseline_shots, baseline_requests = _baseline_state(
        discovery_matrix, discovery
    )
    required_tokens = {
        _physical_token(group["physical_key"]) for group in matrix["groups"]
    }
    if not required_tokens <= set(baseline_failures):
        raise SensitivityCycleError("headline baselines are missing from discovery")

    output_root.mkdir(parents=True)
    phase_records = [
        {
            "phase_index": 1,
            "kind": "initial",
            "spec": str(matrix_path),
            "spec_sha256": matrix_sha256,
            "results_root": str(initial_results),
            "analysis_root": str(initial_analysis),
            "group_count": 48,
        }
    ]
    group_shots = {index: 20_000 for index in range(48)}
    phase_index = 2
    while True:
        active_groups = []
        for index in range(48):
            policies = candidate_failures[index]
            sizes = {sum(part.size for part in value) for value in policies.values()}
            if len(sizes) != 1:
                raise SensitivityCycleError("cost group cumulative shots differ")
            shots = sizes.pop()
            group_shots[index] = shots
            if any(
                _sampling_status(
                    int(np.count_nonzero(np.concatenate(parts))), shots
                )
                == "continue"
                for parts in policies.values()
            ):
                active_groups.append(index)
        if not active_groups:
            break
        plan = _phase_plan(
            phase_index=phase_index,
            matrix=matrix,
            matrix_path=matrix_path,
            matrix_sha256=matrix_sha256,
            active_groups=active_groups,
            group_shots=group_shots,
            baseline_requests=baseline_requests,
            baseline_shots=baseline_shots,
        )
        plan_path = output_root / f"phase-{phase_index}-plan.json"
        _canonical_json(plan_path, plan)
        results_root = output_root / f"phase-{phase_index}"
        _execute_phase(
            plan_path=plan_path,
            plan=plan,
            candidate_root=candidate_root,
            results_root=results_root,
            workers=workers,
            validation_workers=validation_workers,
            timeout_seconds=timeout_seconds,
        )
        _load_phase_results(
            plan_path=plan_path,
            results_root=results_root,
            candidate_failures=candidate_failures,
            candidate_aggregates=candidate_aggregates,
            baseline_failures=baseline_failures,
            baseline_shots=baseline_shots,
        )
        phase_records.append(
            {
                "phase_index": phase_index,
                "kind": "continuation",
                "spec": str(plan_path),
                "spec_sha256": _sha256(plan_path),
                "results_root": str(results_root),
                "result_checksums_sha256": _sha256(
                    results_root / "result-checksums.sha256"
                ),
                "group_count": len(active_groups),
                "baseline_extension_count": plan["baseline_extension_count"],
            }
        )
        phase_index += 1

    summary = _final_analysis(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=matrix_sha256,
        discovery_matrix_path=discovery_matrix_path,
        discovery_matrix_sha256=discovery_matrix_sha256,
        discovery_analysis_root=discovery_analysis_root,
        phase_records=phase_records,
        candidate_failures=candidate_failures,
        candidate_aggregates=candidate_aggregates,
        baseline_failures=baseline_failures,
        out_dir=final_analysis_root,
        bootstrap_resamples=bootstrap_resamples,
    )
    cycle_summary = {
        "schema_version": CYCLE_SCHEMA,
        "status": "complete",
        "slurm_job_id": job_id,
        "candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "candidate_tree_sha256": FROZEN_CANDIDATE_TREE_SHA256,
        "phases": phase_records,
        "final_analysis": str(final_analysis_root),
        "final_analysis_checksums_sha256": _sha256(
            final_analysis_root / "analysis-checksums.sha256"
        ),
        "final_sampling_status": summary["sampling_status"],
    }
    _canonical_json(output_root / "cycle-summary.json", cycle_summary)
    return cycle_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--initial-results", type=Path, required=True)
    parser.add_argument("--initial-analysis", type=Path, required=True)
    parser.add_argument("--discovery-matrix", type=Path, required=True)
    parser.add_argument("--discovery-analysis", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--final-analysis-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--validation-workers", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=10_800)
    parser.add_argument("--bootstrap-resamples", type=int, default=20_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_sensitivity_cycle(
        matrix_path=args.matrix,
        initial_results=args.initial_results,
        initial_analysis=args.initial_analysis,
        discovery_matrix_path=args.discovery_matrix,
        discovery_analysis_root=args.discovery_analysis,
        candidate_root=args.candidate_root,
        output_root=args.output_root,
        final_analysis_root=args.final_analysis_root,
        workers=args.workers,
        validation_workers=args.validation_workers,
        timeout_seconds=args.timeout_seconds,
        bootstrap_resamples=args.bootstrap_resamples,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
