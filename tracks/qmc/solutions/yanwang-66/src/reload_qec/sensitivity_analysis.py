"""Audit initial cost sensitivity against the finalized discovery baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .discovery import (
    _load_previous_analysis,
    _policy_key,
    _sha256 as _discovery_sha256,
    _unpack_logical_failure_row,
    _validate_initial_matrix,
)
from .matrix import load_matrix
from .sensitivity import load_sensitivity_matrix
from .sensitivity_run import (
    GROUP_SCHEMA,
    RUN_SCHEMA,
)
from .stats import benjamini_hochberg, paired_comparison
from .validate_artifacts import validate_run


ANALYSIS_SCHEMA = "q66-cost-sensitivity-analysis-v1"
FDR_Q = 0.05
MIN_FAILURES = 1_000
MAX_SHOTS = 20_000_000
COST_WEIGHTS = tuple(
    (lambda_r, lambda_t)
    for lambda_r in (0.0, 0.001, 0.01)
    for lambda_t in (0.0, 0.001, 0.01)
)


class SensitivityAnalysisError(RuntimeError):
    """Raised when cost-sensitivity or reused baseline evidence is invalid."""


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


def _wilson_interval(failures: int, shots: int) -> tuple[float, float]:
    if shots <= 0 or not 0 <= failures <= shots:
        raise SensitivityAnalysisError("invalid cost-sensitivity counts")
    z = 1.959963984540054
    rate = failures / shots
    denominator = 1.0 + z * z / shots
    center = (rate + z * z / (2.0 * shots)) / denominator
    radius = z * np.sqrt(
        rate * (1.0 - rate) / shots + z * z / (4.0 * shots * shots)
    ) / denominator
    return float(center - radius), float(center + radius)


def _sampling_status(failures: int, shots: int) -> str:
    if failures >= MIN_FAILURES:
        return "target_met"
    if shots >= MAX_SHOTS:
        return "inconclusive_at_budget"
    return "continue"


def _zero_failure_upper(shots: int) -> float:
    return float(1.0 - 0.05 ** (1.0 / shots))


def _bootstrap_seed(matrix_sha256: str, group_index: int, policy: str) -> int:
    digest = hashlib.sha256(
        b"q66-cost-sensitivity-bootstrap-v1\0"
        + matrix_sha256.encode("ascii")
        + group_index.to_bytes(4, "little")
        + policy.encode("ascii")
    ).digest()
    return int.from_bytes(digest[:8], "little")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise SensitivityAnalysisError(f"JSON artifact is not an object: {path}")
    return value


def _verify_root_checksums(root: Path, expected_names: set[str]) -> None:
    entries: dict[str, str] = {}
    for line in (root / "result-checksums.sha256").read_text(
        encoding="ascii"
    ).splitlines():
        digest, separator, name = line.partition("  ")
        if (
            separator != "  "
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not name
            or name in entries
            or "\\" in name
            or Path(name).is_absolute()
            or ".." in Path(name).parts
        ):
            raise SensitivityAnalysisError("invalid sensitivity root checksum")
        entries[name] = digest
    if set(entries) != expected_names:
        raise SensitivityAnalysisError("sensitivity root checksum coverage changed")
    for name, digest in entries.items():
        path = root / name
        if not path.is_file() or _sha256(path) != digest:
            raise SensitivityAnalysisError(f"sensitivity root checksum mismatch: {path}")


def _baseline_indices(discovery_matrix: dict[str, Any]) -> dict[str, int]:
    result = {}
    row_index = 0
    none = {"name": "none"}
    for group in discovery_matrix["groups"]:
        for request in group["requests"]:
            if request["policy"] == none:
                key = json.dumps(
                    group["physical_key"], sort_keys=True, separators=(",", ":")
                )
                result[key] = row_index
            row_index += 1
    if len(result) != 280 or row_index != 2_240:
        raise SensitivityAnalysisError("discovery baseline index is incomplete")
    return result


def analyze_initial_sensitivity(
    *,
    sensitivity_matrix_path: Path,
    sensitivity_results: Path,
    discovery_matrix_path: Path,
    discovery_analysis_root: Path,
    out_dir: Path,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise SensitivityAnalysisError("cost analysis must execute inside Slurm")
    if bootstrap_resamples != 20_000:
        raise SensitivityAnalysisError("cost bootstrap count must remain 20000")
    if out_dir.exists():
        raise SensitivityAnalysisError(f"cost analysis output exists: {out_dir}")

    sensitivity_matrix_path = sensitivity_matrix_path.resolve(strict=True)
    sensitivity_results = sensitivity_results.resolve(strict=True)
    discovery_matrix_path = discovery_matrix_path.resolve(strict=True)
    discovery_analysis_root = discovery_analysis_root.resolve(strict=True)
    sensitivity_matrix = load_sensitivity_matrix(sensitivity_matrix_path)
    sensitivity_matrix_sha256 = _sha256(sensitivity_matrix_path)
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
        raise SensitivityAnalysisError("discovery baseline is not final")
    first_discovery = discovery_matrix["groups"][0]["requests"][0]
    first_sensitivity = sensitivity_matrix["groups"][0]["requests"][0]
    if (
        sensitivity_matrix["source_commit"] != discovery_matrix["source_commit"]
        or sensitivity_matrix["environment_lock_sha256"]
        != discovery_matrix["environment_lock_sha256"]
        or _sha256(Path(first_sensitivity["instance_file"]))
        != _sha256(Path(first_discovery["instance_file"]))
    ):
        raise SensitivityAnalysisError("sensitivity/discovery provenance differs")

    summary = _read_json(sensitivity_results / "run-summary.json")
    if (
        summary.get("schema_version") != RUN_SCHEMA
        or summary.get("status") != "initial-cost-sensitivity-complete"
        or summary.get("matrix_sha256") != sensitivity_matrix_sha256
        or summary.get("matrix") != "cost-sensitivity-matrix.json"
        or _sha256(sensitivity_results / "cost-sensitivity-matrix.json")
        != sensitivity_matrix_sha256
        or summary.get("candidate_commit") != sensitivity_matrix["source_commit"]
        or summary.get("candidate_tree_sha256")
        != "829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482"
        or summary.get("group_count") != 48
        or summary.get("cell_count") != 192
        or summary.get("total_shots") != 3_840_000
        or summary.get("validation") != "exact-replay-passed-for-every-run"
    ):
        raise SensitivityAnalysisError("cost-sensitivity run summary changed")
    summary_groups = summary.get("groups")
    if not isinstance(summary_groups, list) or len(summary_groups) != 48:
        raise SensitivityAnalysisError("cost-sensitivity summary groups changed")
    expected_checksums = {
        "run-summary.json",
        str(summary.get("matrix")),
        *{f"group-{index:02d}/group-manifest.json" for index in range(48)},
    }
    _verify_root_checksums(sensitivity_results, expected_checksums)

    baseline_indices = _baseline_indices(discovery_matrix)
    cell_rows = []
    comparison_rows = []
    continuation_groups = []
    baseline_rates_by_group: dict[int, float] = {}
    for group, summary_group in zip(
        sensitivity_matrix["groups"], summary_groups, strict=True
    ):
        group_index = int(group["group_index"])
        relative_manifest = f"group-{group_index:02d}/group-manifest.json"
        if (
            not isinstance(summary_group, dict)
            or summary_group.get("group_index") != group_index
            or summary_group.get("group_manifest") != relative_manifest
            or summary_group.get("group_manifest_sha256")
            != _sha256(sensitivity_results / relative_manifest)
        ):
            raise SensitivityAnalysisError("cost-sensitivity group summary changed")
        group_manifest = _read_json(sensitivity_results / relative_manifest)
        expected_ids = [request["run_id"] for request in group["requests"]]
        if (
            group_manifest.get("schema_version") != GROUP_SCHEMA
            or group_manifest.get("slurm_job_id") != summary.get("slurm_job_id")
            or group_manifest.get("matrix_sha256") != sensitivity_matrix_sha256
            or group_manifest.get("group_index") != group_index
            or group_manifest.get("physical_key") != group["physical_key"]
            or group_manifest.get("reload_configuration_id")
            != group["reload_configuration_id"]
            or group_manifest.get("reload") != group["reload"]
            or group_manifest.get("baseline_reference")
            != group["baseline_reference"]
            or [row.get("run_id") for row in group_manifest.get("runs", [])]
            != expected_ids
            or [row.get("run_id") for row in group_manifest.get("validation", [])]
            != expected_ids
        ):
            raise SensitivityAnalysisError("cost-sensitivity group manifest changed")

        physical_key = group["physical_key"]
        physical_token = json.dumps(
            physical_key, sort_keys=True, separators=(",", ":")
        )
        baseline_index = baseline_indices[physical_token]
        baseline_shots = int(discovery.shot_counts[baseline_index])
        if baseline_shots < 20_000:
            raise SensitivityAnalysisError("discovery baseline is shorter than cost run")
        baseline = _unpack_logical_failure_row(
            discovery.packed_failures[baseline_index], baseline_shots
        )[:20_000]
        baseline_rates_by_group[group_index] = float(np.count_nonzero(baseline)) / len(
            baseline
        )
        group_needs_more = False
        for request_value in group["requests"]:
            run_id = str(request_value["run_id"])
            run = validate_run(
                sensitivity_results / f"group-{group_index:02d}" / run_id
            )
            if run.request.as_dict() != request_value:
                raise SensitivityAnalysisError("cost-sensitivity request changed")
            ids = np.asarray(run.labels["shot_id"])
            failures = np.asarray(run.labels["logical_failure"]).reshape(-1)
            expected_ids_array = np.arange(20_000, dtype=np.uint64)
            if not np.array_equal(ids, expected_ids_array):
                raise SensitivityAnalysisError("cost-sensitivity shot IDs changed")
            failure_count = int(np.count_nonzero(failures))
            lower, upper = _wilson_interval(failure_count, int(failures.size))
            status = _sampling_status(failure_count, int(failures.size))
            group_needs_more |= status == "continue"
            aggregate = run.manifest["aggregate"]
            n_sites = len(run.manifest["instance"]["site_order"])
            if n_sites <= 0:
                raise SensitivityAnalysisError("cost-sensitivity site count changed")
            policy = request_value["policy"]
            policy_key = _policy_key(policy)
            cell_rows.append(
                {
                    "group_index": group_index,
                    **physical_key,
                    "reload_configuration_id": group["reload_configuration_id"],
                    **group["reload"],
                    "policy": policy_key,
                    "policy_name": policy["name"],
                    "policy_interval": policy.get("interval"),
                    "policy_fraction": policy.get("fraction"),
                    "shots": int(failures.size),
                    "logical_failures": failure_count,
                    "logical_error_rate": failure_count / failures.size,
                    "wilson_95_lower": lower,
                    "wilson_95_upper": upper,
                    "zero_failure_one_sided_95_upper": (
                        _zero_failure_upper(int(failures.size))
                        if failure_count == 0
                        else None
                    ),
                    "reload_requests": int(aggregate["reload_requests"]),
                    "reload_successes": int(aggregate["reload_successes"]),
                    "reload_failures": int(aggregate["reload_failures"]),
                    "missing_site_boundaries": int(
                        aggregate["missing_site_boundaries"]
                    ),
                    "missing_occupancy": int(
                        aggregate["missing_site_boundaries"]
                    )
                    / (failures.size * (int(physical_key["rounds"]) + 1) * n_sites),
                    "reloads_per_site_round": int(aggregate["reload_successes"])
                    / (failures.size * int(physical_key["rounds"]) * n_sites),
                    "wall_seconds": float(aggregate["wall_seconds"]),
                    "reload_wait_site_rounds_per_shot": (
                        int(group["reload"]["delay_rounds"])
                        * int(aggregate["reload_successes"])
                        / failures.size
                    ),
                    "extra_rounds_per_shot": 0.0,
                    "sampling_status": status,
                }
            )
            seed = _bootstrap_seed(
                sensitivity_matrix_sha256, group_index, policy_key
            )
            comparison = paired_comparison(
                baseline,
                failures,
                bootstrap_resamples=bootstrap_resamples,
                bootstrap_seed=seed,
            ).as_dict()
            comparison_rows.append(
                {
                    "group_index": group_index,
                    **physical_key,
                    "reload_configuration_id": group["reload_configuration_id"],
                    "candidate_policy": policy_key,
                    "bootstrap_resamples": bootstrap_resamples,
                    "bootstrap_seed": seed,
                    **comparison,
                }
            )
        if group_needs_more:
            continuation_groups.append(group_index)

    if len(cell_rows) != 192 or len(comparison_rows) != 192:
        raise SensitivityAnalysisError("cost analysis is not 192 cells/comparisons")
    adjusted = benjamini_hochberg(
        np.asarray([row["sign_test_pvalue"] for row in comparison_rows])
    )
    final = not continuation_groups
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
            classification if final else "provisional"
        )

    cost_rows = []
    pareto_rows = []
    cells_by_group: dict[int, list[dict[str, Any]]] = {}
    for row in cell_rows:
        cells_by_group.setdefault(int(row["group_index"]), []).append(row)
    for group in sensitivity_matrix["groups"]:
        group_index = int(group["group_index"])
        alternatives = [
            {
                "policy": _policy_key({"name": "none"}),
                "logical_error_rate": baseline_rates_by_group[group_index],
                "reloads_per_site_round": 0.0,
                "extra_rounds_per_shot": 0.0,
            },
            *[
                {
                    "policy": row["policy"],
                    "logical_error_rate": float(row["logical_error_rate"]),
                    "reloads_per_site_round": float(row["reloads_per_site_round"]),
                    "extra_rounds_per_shot": float(row["extra_rounds_per_shot"]),
                }
                for row in cells_by_group[group_index]
            ],
        ]
        for alternative in alternatives:
            dominated = any(
                other is not alternative
                and all(
                    other[key] <= alternative[key]
                    for key in (
                        "logical_error_rate",
                        "reloads_per_site_round",
                        "extra_rounds_per_shot",
                    )
                )
                and any(
                    other[key] < alternative[key]
                    for key in (
                        "logical_error_rate",
                        "reloads_per_site_round",
                        "extra_rounds_per_shot",
                    )
                )
                for other in alternatives
            )
            pareto_rows.append(
                {
                    "group_index": group_index,
                    **group["physical_key"],
                    "reload_configuration_id": group["reload_configuration_id"],
                    **alternative,
                    "pareto_nondominated": not dominated,
                    "evidence_status": "final" if final else "provisional",
                }
            )
            for lambda_r, lambda_t in COST_WEIGHTS:
                extra_fraction = alternative["extra_rounds_per_shot"] / float(
                    group["physical_key"]["rounds"]
                )
                cost_rows.append(
                    {
                        "group_index": group_index,
                        **group["physical_key"],
                        "reload_configuration_id": group[
                            "reload_configuration_id"
                        ],
                        **alternative,
                        "lambda_r": lambda_r,
                        "lambda_t": lambda_t,
                        "cost_j": alternative["logical_error_rate"]
                        + lambda_r * alternative["reloads_per_site_round"]
                        + lambda_t * extra_fraction,
                        "evidence_status": "final" if final else "provisional",
                    }
                )

    out_dir.mkdir(parents=True)
    cells_path = out_dir / "sensitivity-cells.parquet"
    comparisons_path = out_dir / "sensitivity-comparisons.parquet"
    costs_path = out_dir / "sensitivity-costs.parquet"
    pareto_path = out_dir / "sensitivity-pareto.parquet"
    continuation_path = out_dir / "continuation-required.json"
    summary_path = out_dir / "analysis-summary.json"
    pd.DataFrame(cell_rows).to_parquet(cells_path, index=False)
    pd.DataFrame(comparison_rows).to_parquet(comparisons_path, index=False)
    pd.DataFrame(cost_rows).to_parquet(costs_path, index=False)
    pd.DataFrame(pareto_rows).to_parquet(pareto_path, index=False)
    _canonical_json(
        continuation_path,
        {
            "schema_version": "q66-cost-sensitivity-continuation-required-v1",
            "matrix_sha256": sensitivity_matrix_sha256,
            "group_count": len(continuation_groups),
            "groups": continuation_groups,
            "executable": False,
            "reason": "baseline extension and paired cost continuation must be planned",
        },
    )
    analysis_summary = {
        "schema_version": ANALYSIS_SCHEMA,
        "status": "final-cost-sensitivity" if final else "provisional",
        "slurm_job_id": slurm_job_id,
        "sensitivity_matrix": str(sensitivity_matrix_path),
        "sensitivity_matrix_sha256": sensitivity_matrix_sha256,
        "sensitivity_results": str(sensitivity_results),
        "discovery_matrix": str(discovery_matrix_path),
        "discovery_matrix_sha256": discovery_matrix_sha256,
        "discovery_analysis": str(discovery_analysis_root),
        "cells": 192,
        "comparisons": 192,
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
        "next_phase_groups": len(continuation_groups),
        "pareto_authorized": final,
        "headline_claims_authorized": False,
    }
    _canonical_json(summary_path, analysis_summary)
    artifacts = [
        cells_path,
        comparisons_path,
        costs_path,
        pareto_path,
        continuation_path,
        summary_path,
    ]
    (out_dir / "analysis-checksums.sha256").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in sorted(artifacts)),
        encoding="ascii",
    )
    return analysis_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sensitivity-matrix", type=Path, required=True)
    parser.add_argument("--sensitivity-results", type=Path, required=True)
    parser.add_argument("--discovery-matrix", type=Path, required=True)
    parser.add_argument("--discovery-analysis", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bootstrap-resamples", type=int, default=20_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze_initial_sensitivity(
        sensitivity_matrix_path=args.sensitivity_matrix,
        sensitivity_results=args.sensitivity_results,
        discovery_matrix_path=args.discovery_matrix,
        discovery_analysis_root=args.discovery_analysis,
        out_dir=args.out,
        bootstrap_resamples=args.bootstrap_resamples,
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
