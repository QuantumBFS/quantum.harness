"""Contracts for the independent-seed headline confirmation matrix."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

import reload_qec.confirmation_cycle as confirmation_cycle_module

from reload_qec.config import RequestError, SimulationRequest
from reload_qec.confirmation import (
    ConfirmationError,
    generate_confirmation_matrix,
    validate_confirmation_matrix,
)
from reload_qec.confirmation_cycle import (
    MAX_SHOTS,
    ConfirmationCycleError,
    _cell_status,
    _continuation_plan,
    _precision_status,
    _sha256,
    _validate_continuation_plan,
)
from reload_qec.matrix import _canonical_bytes


def _family() -> tuple[Path, dict]:
    instance_path = Path(os.environ["Q66_INSTANCE_FILE"])
    family_path = instance_path.with_name("confirmation_families.json")
    return instance_path, json.loads(family_path.read_text(encoding="utf-8"))


def test_confirmation_matrix_is_frozen_paired_and_seed_independent() -> None:
    instance_path, families = _family()
    matrix = generate_confirmation_matrix(
        families,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shard_size=4_096,
    )
    assert matrix["group_count"] == 8
    assert matrix["cell_count"] == 40
    assert matrix["shots_per_cell"] == 20_000
    assert matrix["sampling"]["minimum_logical_failures_per_cell"] == 1_000
    assert matrix["sampling"]["maximum_shots_per_cell"] == 20_000_000
    assert matrix["sampling"]["paired_precision"] == {
        "confidence": 0.95,
        "required_comparison_fraction": 0.8,
        "half_width_rule": "max(0.2 * p_L(none), 0.0001)",
    }
    run_ids = set()
    seeds = set()
    for group in matrix["groups"]:
        assert len(group["requests"]) == 5
        group_seeds = {request["master_seed"] for request in group["requests"]}
        assert len(group_seeds) == 1
        confirmation_seed = group_seeds.pop()
        discovery_seed = int.from_bytes(
            hashlib.sha256(
                b"q66-discovery-seed-v1\0"
                + _canonical_bytes(group["physical_key"])
            ).digest()[:8],
            "little",
        )
        assert confirmation_seed != discovery_seed
        seeds.add(confirmation_seed)
        assert [request["policy"] for request in group["requests"]] == [
            {"name": "none"},
            {"name": "immediate"},
            {"name": "periodic", "interval": 5},
            {"name": "periodic", "interval": 10},
            {"name": "threshold", "fraction": 0.05},
        ]
        for request_value in group["requests"]:
            request = SimulationRequest.from_dict(request_value)
            assert request.shot_start == 0
            assert request.shots == 20_000
            assert request.reload.delay_rounds == 0
            assert request.reload.reset_error_probability == 0.0
            assert request.reload.failure_probability == 0.0
            assert request.run_id not in run_ids
            run_ids.add(request.run_id)
    assert len(seeds) == 8
    assert len(run_ids) == 40


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("shots", 19_999, "confirmation request changed"),
        ("master_seed", 7, "confirmation request changed"),
        ("run_id", "changed", "confirmation run ID changed"),
    ),
)
def test_confirmation_matrix_rejects_request_drift(
    field: str, value: object, message: str
) -> None:
    instance_path, family = _family()
    matrix = generate_confirmation_matrix(
        family,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shard_size=4_096,
    )
    changed = copy.deepcopy(matrix)
    changed["groups"][0]["requests"][0][field] = value
    with pytest.raises((ConfirmationError, RequestError), match=message):
        validate_confirmation_matrix(changed)


def _cycle_matrix(tmp_path: Path) -> tuple[Path, dict]:
    _, families = _family()
    matrix = generate_confirmation_matrix(
        families,
        instance_file=tmp_path / "surface-code-instances.jsonl",
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shard_size=4_096,
    )
    path = (tmp_path / "confirmation-matrix.json").resolve()
    path.write_text(json.dumps(matrix, sort_keys=True) + "\n", encoding="ascii")
    return path, matrix


def _phase_record(index: int, group_count: int = 8) -> dict:
    return {
        "phase_index": index,
        "spec": f"/frozen/phase-{index}.json",
        "spec_sha256": f"{index:064x}",
        "results_root": f"/results/phase-{index}/12345",
        "group_count": group_count,
    }


def _stopping_rows(
    matrix: dict,
    *,
    shots: int,
    continuing_cell: tuple[int, int] | None = None,
    continuing_comparison: tuple[int, int] | None = None,
) -> tuple[list[dict], list[dict]]:
    cells = []
    comparisons = []
    for group in matrix["groups"]:
        group_index = group["group_index"]
        for policy_index in range(5):
            cells.append(
                {
                    "group_index": group_index,
                    "shots": shots,
                    "sampling_status": (
                        "continue"
                        if continuing_cell == (group_index, policy_index)
                        else "target_met"
                    ),
                }
            )
        for comparison_index in range(4):
            comparisons.append(
                {
                    "group_index": group_index,
                    "precision_status": (
                        "continue"
                        if continuing_comparison
                        == (group_index, comparison_index)
                        else "precision_met"
                    ),
                }
            )
    return cells, comparisons


@pytest.mark.parametrize(
    ("failures", "shots", "expected"),
    (
        (999, 20_000, "continue"),
        (1_000, 20_000, "target_met"),
        (999, MAX_SHOTS, "inconclusive_at_budget"),
        (1_000, MAX_SHOTS, "target_met"),
    ),
)
def test_confirmation_cell_stopping_status(
    failures: int, shots: int, expected: str
) -> None:
    assert _cell_status(failures, shots) == expected


def test_confirmation_precision_rule_and_budget_status() -> None:
    status, half_width, threshold = _precision_status(
        baseline_rate=0.01,
        lower=-0.001,
        upper=0.003,
        shots=20_000,
    )
    assert status == "precision_met"
    assert half_width == pytest.approx(0.002)
    assert threshold == pytest.approx(0.002)
    cap_status, cap_half_width, cap_threshold = _precision_status(
        baseline_rate=0.0,
        lower=-0.0002,
        upper=0.0002,
        shots=MAX_SHOTS,
    )
    assert cap_status == "inconclusive_at_budget"
    assert cap_half_width == pytest.approx(0.0002)
    assert cap_threshold == pytest.approx(0.0001)


def test_confirmation_continuation_keeps_five_policies_paired(
    tmp_path: Path,
) -> None:
    matrix_path, matrix = _cycle_matrix(tmp_path)
    cells, comparisons = _stopping_rows(
        matrix,
        shots=20_000,
        continuing_cell=(0, 0),
        continuing_comparison=(1, 0),
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=_sha256(matrix_path),
        phase_records=[_phase_record(1)],
        cell_rows=cells,
        comparison_rows=comparisons,
    )
    assert plan["phase_index"] == 2
    assert [group["source_group_index"] for group in plan["groups"]] == [0, 1]
    assert all(group["shot_start"] == 20_000 for group in plan["groups"])
    assert all(group["shots"] == 20_000 for group in plan["groups"])
    assert all(len(group["requests"]) == 5 for group in plan["groups"])
    for group in plan["groups"]:
        assert [request["policy"] for request in group["requests"]] == [
            {"name": "none"},
            {"name": "immediate"},
            {"name": "periodic", "interval": 5},
            {"name": "periodic", "interval": 10},
            {"name": "threshold", "fraction": 0.05},
        ]


def test_confirmation_does_not_drop_last_imprecise_comparison_at_eighty_percent(
    tmp_path: Path,
) -> None:
    matrix_path, matrix = _cycle_matrix(tmp_path)
    cells, comparisons = _stopping_rows(
        matrix,
        shots=20_000,
        continuing_comparison=(0, 0),
    )
    precision_fraction = sum(
        row["precision_status"] == "precision_met" for row in comparisons
    ) / 32
    assert precision_fraction > 0.8
    plan = _continuation_plan(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=_sha256(matrix_path),
        phase_records=[_phase_record(1)],
        cell_rows=cells,
        comparison_rows=comparisons,
    )
    assert [group["source_group_index"] for group in plan["groups"]] == [0]


def test_confirmation_final_doubling_stops_exactly_at_cap(tmp_path: Path) -> None:
    matrix_path, matrix = _cycle_matrix(tmp_path)
    cells, comparisons = _stopping_rows(
        matrix,
        shots=10_240_000,
        continuing_cell=(0, 0),
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=_sha256(matrix_path),
        phase_records=[_phase_record(index) for index in range(1, 11)],
        cell_rows=cells,
        comparison_rows=comparisons,
    )
    assert plan["phase_index"] == 11
    assert plan["groups"][0]["shot_start"] == 10_240_000
    assert plan["groups"][0]["shots"] == 9_760_000
    assert plan["groups"][0]["shot_start"] + plan["groups"][0]["shots"] == MAX_SHOTS


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("phase", "phase provenance changed"),
        ("shot_start", "not paired doubling"),
        ("seed", "request changed"),
    ),
)
def test_confirmation_continuation_rejects_provenance_drift(
    tmp_path: Path, mutation: str, message: str
) -> None:
    matrix_path, matrix = _cycle_matrix(tmp_path)
    cells, comparisons = _stopping_rows(
        matrix,
        shots=20_000,
        continuing_cell=(0, 0),
    )
    plan = _continuation_plan(
        matrix=matrix,
        matrix_path=matrix_path,
        matrix_sha256=_sha256(matrix_path),
        phase_records=[_phase_record(1)],
        cell_rows=cells,
        comparison_rows=comparisons,
    )
    changed = copy.deepcopy(plan)
    if mutation == "phase":
        changed["phase_index"] = 3
    elif mutation == "shot_start":
        changed["groups"][0]["shot_start"] = 40_000
    else:
        changed["groups"][0]["requests"][0]["master_seed"] = 7
    with pytest.raises((ConfirmationCycleError, RequestError), match=message):
        _validate_continuation_plan(changed, matrix, _sha256(matrix_path))


def test_confirmation_cycle_resumes_after_last_accepted_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    matrix = tmp_path / "matrix.json"
    initial = tmp_path / "initial"
    candidate = tmp_path / "candidate"
    analysis_root = tmp_path / "analysis"
    phase_root = tmp_path / "continuation"
    resume = analysis_root / "phase-3" / "old-job"
    resume.mkdir(parents=True)
    (resume / "continuation-plan.json").write_text("{}\n", encoding="ascii")
    phases = [
        (tmp_path / f"spec-{index}.json", tmp_path / f"results-{index}")
        for index in range(1, 4)
    ]
    resume_summary = {"status": "provisional", "next_phase_groups": 8}
    continuation_calls: list[tuple[Path, Path]] = []
    analysis_calls: list[tuple[int, int]] = []

    monkeypatch.setenv("SLURM_JOB_ID", "new-job")
    monkeypatch.setattr(
        confirmation_cycle_module,
        "_load_resume_phase_arguments",
        lambda **_: (phases.copy(), resume_summary),
    )

    def fake_continuation(**kwargs: object) -> dict:
        continuation_calls.append(
            (Path(kwargs["plan_path"]), Path(kwargs["output_root"]))
        )
        return {}

    def fake_analysis(**kwargs: object) -> dict:
        phase_arguments = kwargs["phase_arguments"]
        out_dir = Path(kwargs["out_dir"])
        analysis_calls.append((len(phase_arguments), int(out_dir.parent.name[6:])))
        return {"next_phase_groups": 0, "status": "final-confirmation"}

    monkeypatch.setattr(
        confirmation_cycle_module,
        "run_confirmation_continuation",
        fake_continuation,
    )
    monkeypatch.setattr(
        confirmation_cycle_module, "analyze_confirmation", fake_analysis
    )
    result = confirmation_cycle_module.run_cycle(
        matrix_path=matrix,
        initial_results=initial,
        candidate_root=candidate,
        analysis_root=analysis_root,
        phase_root=phase_root,
        simulation_workers=8,
        validation_workers=8,
        timeout_seconds=10_800,
        bootstrap_resamples=20_000,
        resume_analysis=resume,
    )

    assert continuation_calls == [
        (
            resume / "continuation-plan.json",
            phase_root / "phase-4" / "new-job",
        )
    ]
    assert analysis_calls == [(4, 4)]
    assert result["phase_count"] == 4
    assert result["resumed_from"] == str(resume)
