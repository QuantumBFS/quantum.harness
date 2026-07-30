"""Contracts for the preregistered reload-cost sensitivity matrix."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from reload_qec.config import SimulationRequest
from reload_qec.sensitivity import (
    SensitivityError,
    generate_sensitivity_matrix,
    load_sensitivity_matrix,
    validate_sensitivity_matrix,
)
from reload_qec.sensitivity_run import (
    SensitivityRunError,
    run_initial_sensitivity,
)
from reload_qec.sensitivity_analysis import (
    COST_WEIGHTS,
    MAX_SHOTS,
    SensitivityAnalysisError,
    _sampling_status,
    analyze_initial_sensitivity,
)
from reload_qec.sensitivity_cycle import (
    SensitivityCycleError,
    _continuation_request,
    run_sensitivity_cycle,
)
from reload_qec.sensitivity_gate import (
    SensitivityGateError,
    require_final_discovery,
)
from reload_qec.final_audit import FinalAuditError, audit_public_gates


def test_cost_sensitivity_matrix_is_frozen_paired_and_nonredundant() -> None:
    instance_path = Path(os.environ["Q66_INSTANCE_FILE"])
    family_path = instance_path.with_name("cost_sensitivity_families.json")
    families = json.loads(family_path.read_text(encoding="utf-8"))
    matrix = generate_sensitivity_matrix(
        families,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shard_size=4_096,
    )
    assert matrix["group_count"] == 48
    assert matrix["cell_count"] == 192
    assert matrix["shots_per_cell"] == 20_000
    seeds_by_physical_key: dict[str, set[int]] = {}
    configurations_by_physical_key: dict[str, set[str]] = {}
    run_ids = set()
    for group in matrix["groups"]:
        assert len(group["requests"]) == 4
        assert group["baseline_reference"] == {
            "matrix_schema": "q66-discovery-matrix-v1",
            "physical_key": group["physical_key"],
            "policy": {"name": "none"},
        }
        physical_token = json.dumps(group["physical_key"], sort_keys=True)
        configurations_by_physical_key.setdefault(physical_token, set()).add(
            group["reload_configuration_id"]
        )
        group_seeds = {
            request["master_seed"] for request in group["requests"]
        }
        assert len(group_seeds) == 1
        seeds_by_physical_key.setdefault(physical_token, set()).update(group_seeds)
        assert any(value != 0 for value in group["reload"].values())
        for request in group["requests"]:
            parsed = SimulationRequest.from_dict(request)
            assert parsed.policy.name != "none"
            assert parsed.run_id not in run_ids
            run_ids.add(parsed.run_id)
    assert len(run_ids) == 192
    assert all(
        len(configurations) == 8
        for configurations in configurations_by_physical_key.values()
    )
    assert all(len(seeds) == 1 for seeds in seeds_by_physical_key.values())


def _matrix() -> dict:
    instance_path = Path(os.environ["Q66_INSTANCE_FILE"])
    family_path = instance_path.with_name("cost_sensitivity_families.json")
    families = json.loads(family_path.read_text(encoding="utf-8"))
    return generate_sensitivity_matrix(
        families,
        instance_file=instance_path,
        source_commit="0" * 40,
        environment_lock_sha256="1" * 64,
        shard_size=4_096,
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("group", "group identity changed"),
        ("request", "request changed"),
        ("provenance", "matrix provenance changed"),
    ),
)
def test_cost_sensitivity_matrix_rejects_drift(
    mutation: str, message: str
) -> None:
    changed = copy.deepcopy(_matrix())
    if mutation == "group":
        changed["groups"][0]["reload"]["delay_rounds"] = 2
    elif mutation == "request":
        changed["groups"][0]["requests"][0]["shots"] = 19_999
    else:
        changed["provenance"]["selection_rule"] = "after analysis"
    with pytest.raises(SensitivityError, match=message):
        validate_sensitivity_matrix(changed)


def test_cost_sensitivity_matrix_round_trips_strict_loader(tmp_path: Path) -> None:
    matrix = _matrix()
    path = tmp_path / "cost-sensitivity-matrix.json"
    path.write_text(json.dumps(matrix, sort_keys=True) + "\n", encoding="ascii")
    assert load_sensitivity_matrix(path) == matrix


def test_initial_cost_sensitivity_requires_slurm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(SensitivityRunError, match="inside Slurm"):
        run_initial_sensitivity(
            matrix_path=tmp_path / "matrix.json",
            candidate_root=tmp_path / "candidate",
            output_root=tmp_path / "output",
            simulation_workers=1,
            validation_workers=1,
            timeout_seconds=1,
        )


def test_initial_cost_sensitivity_rejects_array_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    monkeypatch.setenv("SLURM_ARRAY_TASK_ID", "0")
    with pytest.raises(SensitivityRunError, match="must be one job"):
        run_initial_sensitivity(
            matrix_path=tmp_path / "matrix.json",
            candidate_root=tmp_path / "candidate",
            output_root=tmp_path / "123",
            simulation_workers=1,
            validation_workers=1,
            timeout_seconds=1,
        )


@pytest.mark.parametrize(
    ("failures", "shots", "expected"),
    (
        (999, 20_000, "continue"),
        (1_000, 20_000, "target_met"),
        (999, MAX_SHOTS, "inconclusive_at_budget"),
    ),
)
def test_cost_sensitivity_sampling_status(
    failures: int, shots: int, expected: str
) -> None:
    assert _sampling_status(failures, shots) == expected


def test_cost_weights_are_frozen_before_results() -> None:
    assert COST_WEIGHTS == tuple(
        (lambda_r, lambda_t)
        for lambda_r in (0.0, 0.001, 0.01)
        for lambda_t in (0.0, 0.001, 0.01)
    )


def test_cost_analysis_requires_slurm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(SensitivityAnalysisError, match="inside Slurm"):
        analyze_initial_sensitivity(
            sensitivity_matrix_path=tmp_path / "sensitivity.json",
            sensitivity_results=tmp_path / "sensitivity-results",
            discovery_matrix_path=tmp_path / "discovery.json",
            discovery_analysis_root=tmp_path / "discovery-analysis",
            out_dir=tmp_path / "analysis",
            bootstrap_resamples=20_000,
        )


def test_cost_continuation_preserves_request_and_advances_shots() -> None:
    base = _matrix()["groups"][0]["requests"][0]
    continued = _continuation_request(base, 20_000, 20_000)
    parsed = SimulationRequest.from_dict(continued)
    assert parsed.shot_start == 20_000
    assert parsed.shots == 20_000
    assert parsed.master_seed == base["master_seed"]
    assert parsed.policy.as_dict() == base["policy"]
    assert parsed.reload.delay_rounds == base["reload"]["delay_rounds"]
    assert parsed.reload.reset_error_probability == base["reload"][
        "reset_error_probability"
    ]
    assert parsed.reload.failure_probability == base["reload"][
        "failure_probability"
    ]


def test_cost_cycle_requires_slurm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(SensitivityCycleError, match="inside Slurm"):
        run_sensitivity_cycle(
            matrix_path=tmp_path / "matrix.json",
            initial_results=tmp_path / "initial",
            initial_analysis=tmp_path / "initial-analysis",
            discovery_matrix_path=tmp_path / "discovery.json",
            discovery_analysis_root=tmp_path / "discovery-analysis",
            candidate_root=tmp_path / "candidate",
            output_root=tmp_path / "cycle",
            final_analysis_root=tmp_path / "final",
            workers=1,
            validation_workers=1,
            timeout_seconds=1,
            bootstrap_resamples=20_000,
        )


def test_cost_gate_requires_slurm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(SensitivityGateError, match="inside Slurm"):
        require_final_discovery(
            tmp_path / "analysis", tmp_path / "matrix.json"
        )


def test_public_final_audit_requires_slurm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(FinalAuditError, match="inside Slurm"):
        audit_public_gates(
            candidate_root=tmp_path / "candidate",
            discovery_analysis=tmp_path / "discovery",
            confirmation_analysis=tmp_path / "confirmation",
            sensitivity_analysis=tmp_path / "sensitivity",
            negative_controls_report=tmp_path / "controls.json",
            independent_evidence=tmp_path / "independent.md",
            report_path=tmp_path / "report.md",
            science_gate_path=tmp_path / "science.md",
            holdout_spend_path=tmp_path / "spend.json",
            out_dir=tmp_path / "audit",
        )
