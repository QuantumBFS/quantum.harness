"""SCNet-only checks for the frozen public validator matrix."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

import pytest

from reload_qec.dev_matrix import DevMatrixError, generate_dev_matrix
from reload_qec.negative_controls import _make_control_tree_owner_writable
from reload_qec.dev_score import DevScoreError, aggregate_score
from reload_qec.dev_validator import RUNNER_SCHEMA, repetition_request
from reload_qec.sandbox import (
    MAX_ADDRESS_SPACE_BYTES,
    SANDBOX_SCHEMA,
    network_denial_preflight,
)


def _family() -> tuple[Path, dict]:
    instance_path = Path(os.environ["Q66_INSTANCE_FILE"])
    family_path = instance_path.with_name("dev_validator_families.json")
    return instance_path, json.loads(family_path.read_text(encoding="utf-8"))


def test_dev_validator_matrix_is_complete_paired_and_frozen() -> None:
    instance_path, family = _family()
    matrix = generate_dev_matrix(
        family,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
    )
    assert matrix["cell_count"] == 16
    assert matrix["workload_count"] == 4
    assert matrix["policies_per_workload"] == 4
    assert matrix["warmup_runs"] == 1
    assert matrix["timed_runs"] == 3
    run_ids = {cell["request"]["run_id"] for cell in matrix["cells"]}
    assert len(run_ids) == 16
    for workload_index in range(4):
        cells = [
            cell
            for cell in matrix["cells"]
            if cell["workload_index"] == workload_index
        ]
        assert [cell["policy_index"] for cell in cells] == [0, 1, 2, 3]
        assert len({cell["request"]["master_seed"] for cell in cells}) == 1
        assert {
            (cell["request"]["shot_start"], cell["request"]["shots"])
            for cell in cells
        } == {(0, 2_048)}
    assert len(
        {
            cell["request"]["master_seed"]
            for cell in matrix["cells"]
        }
    ) == 4


def test_dev_validator_matrix_rejects_parameter_drift() -> None:
    instance_path, family = _family()
    changed = copy.deepcopy(family)
    changed["workloads"][0]["noise"]["p_loss"] = 0.0
    with pytest.raises(DevMatrixError, match="values/order changed"):
        generate_dev_matrix(
            changed,
            instance_file=instance_path,
            source_commit="0" * 40,
            environment_lock_sha256="1" * 64,
        )


def test_validator_repetitions_use_disjoint_shot_ranges() -> None:
    instance_path, family = _family()
    matrix = generate_dev_matrix(
        family,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
    )
    base_request = matrix["cells"][0]["request"]
    requests = [repetition_request(base_request, index) for index in range(4)]
    assert [request["shot_start"] for request in requests] == [0, 2048, 4096, 6144]
    assert len({request["run_id"] for request in requests}) == 4


def test_candidate_network_is_denied_by_kernel() -> None:
    assert os.environ.get("SLURM_JOB_ID"), "sandbox proof must run inside Slurm"
    report = network_denial_preflight(sys.executable)
    assert report == {
        "schema_version": SANDBOX_SCHEMA,
        "network_isolation": "seccomp-bpf-errno-eperm",
        "process_group_isolation": "seccomp-bpf-errno-eperm",
        "no_new_privs": 1,
        "seccomp_mode": 2,
        "setpgid_errno": 1,
        "setsid_errno": 1,
        "socket_errno": 1,
        "address_space_limit_bytes": MAX_ADDRESS_SPACE_BYTES,
    }


def test_read_only_negative_control_copy_is_made_writable(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    source_root = candidate_root / "src/reload_qec"
    source_root.mkdir(parents=True)
    candidate_file = source_root / "candidate.py"
    candidate_file.write_text("pass\n", encoding="ascii")
    candidate_file.chmod(0o444)
    source_root.chmod(0o555)
    (candidate_root / "src").chmod(0o555)
    candidate_root.chmod(0o555)

    _make_control_tree_owner_writable(candidate_root)

    for path in (candidate_root, candidate_root / "src", source_root, candidate_file):
        assert path.stat().st_mode & stat.S_IWUSR


def _synthetic_score_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    instance_path, family = _family()
    matrix = generate_dev_matrix(
        family,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
    )
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(matrix, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    matrix_sha256 = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    results_root = tmp_path / "123456"
    for cell in matrix["cells"]:
        cell_index = cell["cell_index"]
        base_request = cell["request"]
        distance = base_request["distance"]
        candidate_seconds = 2.0 if distance == 3 else 4.0
        runs = []
        for repetition in range(4):
            request_value = repetition_request(base_request, repetition)
            runs.append(
                {
                    "repetition": repetition,
                    "timing_role": "warmup" if repetition == 0 else "timed",
                    "run_id": request_value["run_id"],
                    "shot_start": request_value["shot_start"],
                    "shots": request_value["shots"],
                    "validation": "exact-replay-passed",
                    "return_code": 0,
                    "timed_out": False,
                    "process_cleanup": {
                        "background_processes_detected": False,
                        "background_process_ids": [],
                        "background_process_signals": [],
                        "process_group_cleared": True,
                    },
                    "candidate_wall_seconds": candidate_seconds,
                    "validator_wall_seconds": 1.0,
                    "children_max_rss_kib": 1024,
                }
            )
        cell_root = results_root / f"cell-{cell_index:02d}"
        cell_root.mkdir(parents=True)
        report = {
            "schema_version": RUNNER_SCHEMA,
            "status": "passed",
            "slurm_array_job_id": results_root.name,
            "slurm_array_task_id": str(cell_index),
            "matrix": str(matrix_path),
            "matrix_sha256": matrix_sha256,
            "cell_index": cell_index,
            "workload_id": cell["workload_id"],
            "candidate_root": "/synthetic/candidate",
            "candidate_id": "synthetic",
            "candidate_tree_sha256": "2" * 64,
            "sandbox": {
                "schema_version": SANDBOX_SCHEMA,
                "network_isolation": "seccomp-bpf-errno-eperm",
                "process_group_isolation": "seccomp-bpf-errno-eperm",
                "no_new_privs": 1,
                "seccomp_mode": 2,
                "setpgid_errno": 1,
                "setsid_errno": 1,
                "socket_errno": 1,
                "address_space_limit_bytes": MAX_ADDRESS_SPACE_BYTES,
            },
            "filesystem_guard": (
                "candidate-tree-sha256-before-and-after-every-run"
            ),
            "timeout_seconds": 2700,
            "runs": runs,
        }
        (cell_root / "runner-report.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="ascii"
        )
    return matrix_path, results_root, tmp_path / "score.json"


def test_dev_score_uses_median_validated_throughput(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    matrix_path, results_root, score_path = _synthetic_score_inputs(tmp_path)
    monkeypatch.setenv("SLURM_JOB_ID", "999999")
    report = aggregate_score(
        matrix_path=matrix_path,
        results_root=results_root,
        out_path=score_path,
    )
    assert report["validated_shots_d3"] == 16_384
    assert report["validated_shots_d5"] == 16_384
    assert report["q3"] == 1_024.0
    assert report["q5"] == 512.0
    assert math.isclose(report["score"], math.sqrt(1_024.0 * 512.0))


def test_dev_score_rejects_a_non_replayed_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    matrix_path, results_root, score_path = _synthetic_score_inputs(tmp_path)
    report_path = results_root / "cell-00" / "runner-report.json"
    report = json.loads(report_path.read_text(encoding="ascii"))
    report["runs"][2]["validation"] = "candidate-process-failed"
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="ascii"
    )
    monkeypatch.setenv("SLURM_JOB_ID", "999999")
    with pytest.raises(DevScoreError, match="invalid runner evidence"):
        aggregate_score(
            matrix_path=matrix_path,
            results_root=results_root,
            out_path=score_path,
        )


def test_dev_score_rejects_background_process_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    matrix_path, results_root, score_path = _synthetic_score_inputs(tmp_path)
    report_path = results_root / "cell-00" / "runner-report.json"
    report = json.loads(report_path.read_text(encoding="ascii"))
    report["runs"][0]["process_cleanup"] = {
        "background_processes_detected": True,
        "background_process_ids": [12345],
        "background_process_signals": ["SIGTERM"],
        "process_group_cleared": True,
    }
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="ascii"
    )
    monkeypatch.setenv("SLURM_JOB_ID", "999999")
    with pytest.raises(DevScoreError, match="invalid runner evidence"):
        aggregate_score(
            matrix_path=matrix_path,
            results_root=results_root,
            out_path=score_path,
        )


def test_dev_score_rejects_missing_sandbox_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    matrix_path, results_root, score_path = _synthetic_score_inputs(tmp_path)
    report_path = results_root / "cell-00" / "runner-report.json"
    report = json.loads(report_path.read_text(encoding="ascii"))
    del report["sandbox"]
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="ascii"
    )
    monkeypatch.setenv("SLURM_JOB_ID", "999999")
    with pytest.raises(DevScoreError, match="sandbox evidence mismatch"):
        aggregate_score(
            matrix_path=matrix_path,
            results_root=results_root,
            out_path=score_path,
        )
