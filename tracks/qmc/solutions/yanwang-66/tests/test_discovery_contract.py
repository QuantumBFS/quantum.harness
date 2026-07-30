"""Focused contracts for discovery aggregation and lockstep continuation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from reload_qec.artifacts import MANIFEST_SCHEMA
from reload_qec.discovery import (
    DiscoveryError,
    Phase,
    _continuation_bundles,
    _continuation_plan,
    _initial_bundle_task_index,
    _load_previous_analysis,
    _pack_logical_failure_row,
    _run_continuation_group,
    _sampling_status,
    _unpack_logical_failure_row,
    _validate_executable_plan,
    _validate_initial_matrix,
    _write_logical_failure_state,
)
from reload_qec.matrix import generate_matrix


def initial_matrix() -> dict:
    instance_path = Path(os.environ["Q66_INSTANCE_FILE"])
    families = json.loads(
        instance_path.with_name("benchmark_families.json").read_text(
            encoding="utf-8"
        )
    )
    return generate_matrix(
        families,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shots=20_000,
        shard_size=4_096,
    )


def test_generated_initial_matrix_matches_frozen_discovery_contract() -> None:
    _validate_initial_matrix(initial_matrix())


def test_initial_bundle_map_covers_every_group_once_with_182_tasks() -> None:
    task_ids = [_initial_bundle_task_index(index) for index in range(280)]
    assert set(task_ids) == set(range(182))
    assert task_ids[:70] == [task for task in range(18) for _ in range(4)][:70]
    assert task_ids[70:140] == [
        task for task in range(18, 42) for _ in range(3)
    ][:70]
    assert task_ids[140:210] == list(range(42, 112))
    assert task_ids[210:] == list(range(112, 182))


def test_continuation_keeps_eight_policies_on_one_doubled_range() -> None:
    matrix = initial_matrix()
    rows = []
    for group in matrix["groups"]:
        for policy_index, request in enumerate(group["requests"]):
            needs_more = group["group_index"] == 7 and policy_index == 3
            rows.append(
                {
                    "group_index": group["group_index"],
                    "policy": json.dumps(request["policy"], sort_keys=True),
                    "shots": 20_000,
                    "sampling_status": "continue" if needs_more else "target_met",
                }
            )
    phase = Phase(
        phase_index=1,
        spec_path=Path("initial-matrix.json"),
        spec_sha256="a" * 64,
        results_root=Path("phase-1/123"),
        kind="initial",
        groups={},
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_sha256="a" * 64,
        phases=[phase],
        cell_rows=rows,
    )
    assert plan["group_count"] == 1
    assert plan["cell_count"] == 8
    group = plan["groups"][0]
    assert group["source_group_index"] == 7
    assert group["shot_start"] == 20_000
    assert group["shots"] == 20_000
    assert {request["shot_start"] for request in group["requests"]} == {20_000}
    assert {request["shots"] for request in group["requests"]} == {20_000}
    assert len({request["run_id"] for request in group["requests"]}) == 8
    _validate_executable_plan(plan)
    assert _continuation_bundles(plan) == [(0,)]


def test_phase_two_continuation_bundles_fit_scheduler_limit() -> None:
    matrix = initial_matrix()
    rows = [
        {
            "group_index": group["group_index"],
            "policy": json.dumps(request["policy"], sort_keys=True),
            "shots": 20_000,
            "sampling_status": "continue",
        }
        for group in matrix["groups"]
        for request in group["requests"]
    ]
    phase = Phase(
        phase_index=1,
        spec_path=Path("initial-matrix.json"),
        spec_sha256="a" * 64,
        results_root=Path("phase-1/123"),
        kind="initial",
        groups={},
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_sha256="a" * 64,
        phases=[phase],
        cell_rows=rows,
    )
    bundles = _continuation_bundles(plan)
    assert len(bundles) == 5
    assert [index for bundle in bundles for index in bundle] == list(range(280))


def test_parallel_continuation_bundles_cover_every_reachable_shot_range() -> None:
    matrix = initial_matrix()
    phase = Phase(
        phase_index=2,
        spec_path=Path("phase-2-plan.json"),
        spec_sha256="b" * 64,
        results_root=Path("phase-2/456"),
        kind="continuation",
        groups={},
    )
    reachable_ranges = (
        (1, 20_000, 20_000, 5),
        (2, 40_000, 40_000, 7),
        (3, 80_000, 80_000, 11),
        (4, 160_000, 160_000, 20),
        (5, 320_000, 320_000, 43),
        (6, 640_000, 640_000, 112),
        (7, 1_280_000, 720_000, 112),
    )
    for (
        phase_count,
        cumulative_shots,
        next_shots,
        expected_bundles,
    ) in reachable_ranges:
        rows = [
            {
                "group_index": group["group_index"],
                "policy": json.dumps(request["policy"], sort_keys=True),
                "shots": cumulative_shots,
                "sampling_status": "continue",
            }
            for group in matrix["groups"]
            for request in group["requests"]
        ]
        plan = _continuation_plan(
            matrix=matrix,
            matrix_sha256="a" * 64,
            phases=[phase] * phase_count,
            cell_rows=rows,
        )
        assert {group["shots"] for group in plan["groups"]} == {next_shots}
        bundles = _continuation_bundles(plan)
        assert len(bundles) == expected_bundles
        assert [index for bundle in bundles for index in bundle] == list(
            range(280)
        )


def test_logical_failure_state_is_bit_packed_with_checked_padding() -> None:
    values = np.asarray([0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1], dtype=np.uint8)
    packed = _pack_logical_failure_row(values)
    assert packed.shape == (2,)
    np.testing.assert_array_equal(
        _unpack_logical_failure_row(packed, len(values)), values
    )

    corrupted = packed.copy()
    corrupted[-1] |= np.uint8(0b10000000)
    with pytest.raises(DiscoveryError, match="padding is nonzero"):
        _unpack_logical_failure_row(corrupted, len(values))


def test_logical_failure_state_uses_one_checksummed_row_per_cell(
    tmp_path: Path,
) -> None:
    values = np.asarray([0, 1, 0, 1, 1, 0, 0, 0, 1], dtype=np.uint8)
    row = _pack_logical_failure_row(values)
    packed_path, shots_path, metadata = _write_logical_failure_state(
        out_dir=tmp_path,
        packed_rows=[row] * 2_240,
        shot_counts=[len(values)] * 2_240,
    )
    packed = np.load(packed_path, allow_pickle=False)
    shots = np.load(shots_path, allow_pickle=False)
    assert packed.shape == (2_240, 2)
    assert shots.shape == (2_240,)
    assert np.all(shots == len(values))
    assert metadata == {
        "encoding": "numpy-packbits-little",
        "row_order": "discovery-cells.parquet",
        "rows": 2_240,
        "max_shots": len(values),
    }


def test_previous_analysis_loads_without_historical_raw_results(
    tmp_path: Path,
) -> None:
    matrix = initial_matrix()
    matrix_path = tmp_path / "discovery-matrix.json"
    matrix_path.write_text(json.dumps(matrix, sort_keys=True), encoding="ascii")
    matrix_sha256 = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    cell_rows = []
    packed_rows = []
    continue_values = np.zeros(20_000, dtype=np.uint8)
    continue_values[:3] = 1
    completed_values = np.zeros(20_000, dtype=np.uint8)
    completed_values[:400] = 1
    for group in matrix["groups"]:
        for request in group["requests"]:
            policy = request["policy"]
            failures = 3 if group["group_index"] == 0 else 400
            status = "continue" if failures < 400 else "target_met"
            cell_rows.append(
                {
                    "group_index": group["group_index"],
                    **group["physical_key"],
                    "policy": json.dumps(
                        policy, sort_keys=True, separators=(",", ":")
                    ),
                    "policy_name": policy["name"],
                    "policy_interval": policy.get("interval"),
                    "policy_fraction": policy.get("fraction"),
                    "zero_failure_one_sided_95_upper": None,
                    "phase_count": 1,
                    "run_ids": json.dumps([request["run_id"]]),
                    "shots": 20_000,
                    "logical_failures": failures,
                    "sampling_status": status,
                }
            )
            values = continue_values if status == "continue" else completed_values
            packed_rows.append(_pack_logical_failure_row(values))
    cells_path = analysis_root / "discovery-cells.parquet"
    pd.DataFrame(cell_rows).to_parquet(cells_path, index=False)
    comparisons_path = analysis_root / "discovery-comparisons.parquet"
    comparisons_path.write_bytes(b"state-loader-fixture")
    packed_path, shots_path, state_metadata = _write_logical_failure_state(
        out_dir=analysis_root,
        packed_rows=packed_rows,
        shot_counts=[20_000] * 2_240,
    )
    plan_path = analysis_root / "continuation-plan.json"
    phase = Phase(
        phase_index=1,
        spec_path=matrix_path,
        spec_sha256=matrix_sha256,
        results_root=tmp_path / "offline-phase-1",
        kind="initial",
        groups={},
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_sha256=matrix_sha256,
        phases=[phase],
        cell_rows=cell_rows,
    )
    plan_path.write_text(json.dumps(plan), encoding="ascii")
    summary_path = analysis_root / "analysis-summary.json"
    artifact_names = {
        cells_path.name,
        comparisons_path.name,
        packed_path.name,
        shots_path.name,
        plan_path.name,
        summary_path.name,
        "analysis-checksums.sha256",
    }
    summary = {
        "schema_version": "q66-discovery-analysis-v1",
        "status": "provisional",
        "initial_matrix": str(matrix_path),
        "initial_matrix_sha256": matrix_sha256,
        "phases": [
            {
                "phase_index": 1,
                "kind": "initial",
                "spec": str(matrix_path),
                "spec_sha256": matrix_sha256,
                "results_root": str(tmp_path / "offline-phase-1"),
                "group_count": 280,
            }
        ],
        "logical_failure_state": state_metadata,
        "cells": 2_240,
        "comparisons": 1_960,
        "total_cell_shots": 2_240 * 20_000,
        "cell_sampling_status": {"continue": 8, "target_met": 2_232},
        "group_sampling_status": {"continue": 1, "target_met": 279},
        "next_phase_groups": 1,
        "next_phase_cells": 8,
        "artifacts": sorted(artifact_names),
    }
    summary_path.write_text(json.dumps(summary), encoding="ascii")
    checksummed = sorted(artifact_names - {"analysis-checksums.sha256"})
    (analysis_root / "analysis-checksums.sha256").write_text(
        "".join(
            f"{hashlib.sha256((analysis_root / name).read_bytes()).hexdigest()}"
            f"  {name}\n"
            for name in checksummed
        ),
        encoding="ascii",
    )

    previous = _load_previous_analysis(
        analysis_root=analysis_root,
        matrix_path=matrix_path,
        matrix=matrix,
        matrix_sha256=matrix_sha256,
    )
    assert len(previous.phases) == 1
    assert not previous.phases[0].results_root.exists()
    assert previous.packed_failures.shape == (2_240, 2_500)
    assert np.all(previous.shot_counts == 20_000)

    cells = pd.read_parquet(cells_path)
    cells.loc[0, "logical_failures"] = 4
    cells.to_parquet(cells_path, index=False)
    checksums_path = analysis_root / "analysis-checksums.sha256"
    checksum_lines = checksums_path.read_text(encoding="ascii").splitlines()
    checksums_path.write_text(
        "\n".join(
            (
                f"{hashlib.sha256(cells_path.read_bytes()).hexdigest()}"
                f"  {cells_path.name}"
                if line.endswith(f"  {cells_path.name}")
                else line
            )
            for line in checksum_lines
        )
        + "\n",
        encoding="ascii",
    )
    with pytest.raises(DiscoveryError, match="failure counts differ"):
        _load_previous_analysis(
            analysis_root=analysis_root,
            matrix_path=matrix_path,
            matrix=matrix,
            matrix_sha256=matrix_sha256,
        )


def test_completed_continuation_group_can_resume_after_requeue(
    tmp_path: Path,
) -> None:
    matrix = initial_matrix()
    group = {
        "phase_group_index": 0,
        "source_group_index": 0,
        "shots": 20_000,
        "requests": matrix["groups"][0]["requests"],
    }
    plan = {"phase_index": 2}
    plan_path = tmp_path / "continuation-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="ascii")
    plan_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    output_root = tmp_path / "123"
    group_root = output_root / "group-000"
    group_root.mkdir(parents=True)
    run_ids = []
    for request in group["requests"]:
        run_id = request["run_id"]
        run_ids.append(run_id)
        run_root = group_root / run_id
        run_root.mkdir()
        manifest_path = run_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": MANIFEST_SCHEMA,
                    "status": "completed",
                    "run_id": run_id,
                    "request": request,
                    "source_commit": request["provenance"]["source_commit"],
                },
                sort_keys=True,
            ),
            encoding="ascii",
        )
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        (run_root / "checksums.sha256").write_text(
            f"{digest}  manifest.json\n", encoding="ascii"
        )
    expected = {
        "schema_version": "q66-discovery-continuation-group-v1",
        "plan_sha256": plan_sha256,
        "phase_index": 2,
        "phase_group_index": 0,
        "source_group_index": 0,
        "slurm_array_job_id": "123",
        "slurm_array_task_id": "0",
        "runs": run_ids,
    }
    (group_root / "group-manifest.json").write_text(
        json.dumps(expected), encoding="ascii"
    )

    assert (
        _run_continuation_group(
            plan_path=plan_path,
            plan=plan,
            group=group,
            array_job_id="123",
            array_task_id="0",
            output_root=output_root,
        )
        == expected
    )

    (group_root / run_ids[0] / "manifest.json").write_text(
        "{}", encoding="ascii"
    )
    with pytest.raises(DiscoveryError, match="invalid completed continuation"):
        _run_continuation_group(
            plan_path=plan_path,
            plan=plan,
            group=group,
            array_job_id="123",
            array_task_id="0",
            output_root=output_root,
        )


def test_sampling_status_does_not_call_underpowered_budget_result_negative() -> None:
    assert _sampling_status(399, 20_000) == "continue"
    assert _sampling_status(400, 20_000) == "target_met"
    assert _sampling_status(399, 2_000_000) == "inconclusive_at_budget"
