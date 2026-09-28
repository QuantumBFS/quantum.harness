from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.run_two_mode_comparison import (
    _execute_dataset_path,
    accepted_convergence_floor,
    audit_available_inputs,
    run_registered_blind,
    run_registered_validation,
)
from src.two_mode_observables import JointObservablePanel

ROOT = Path(__file__).resolve().parents[1]


def _audit(
    tmp_path: Path,
    *,
    manifest: Path | None = None,
    phase: str = "validation",
    selection: Path | None = None,
):
    return audit_available_inputs(
        manifest_path=manifest
        or ROOT / "results_research_program" / "production_manifest_v2.json",
        base_manifest_path=ROOT / "results_research_program" / "manifest.json",
        rules_path=ROOT / "configs" / "two_mode_fcs_decision_rules_20260730.json",
        solver_budget_path=ROOT
        / "results_research_program"
        / "two_mode"
        / "solver_budget.json",
        reuse_attestations_path=tmp_path / "absent_attestations.json",
        phase=phase,
        selection_record_path=selection,
    )


def test_absent_v2_manifest_fails_closed(tmp_path: Path) -> None:
    summary, context = _audit(tmp_path, manifest=tmp_path / "missing.json")
    assert summary["status"] == "insufficient_observables"
    assert summary["tested"] is False
    assert context == {}


def test_explicit_data_root_maps_execute_rows_without_manifest_rewrite(
    tmp_path: Path,
) -> None:
    job = {
        "job_id": "amp_mu002_up__production_a__v2",
        "stage": "production_a",
        "output_path": "/developer/machine/frozen.npz",
    }
    assert _execute_dataset_path(job, data_root=None) == Path(
        "/developer/machine/frozen.npz"
    )
    assert _execute_dataset_path(job, data_root=tmp_path / "raw") == (
        tmp_path
        / "raw"
        / "production_a"
        / "amp_mu002_up__production_a__v2.npz"
    )


def test_current_state_reports_exact_missing_rows(tmp_path: Path) -> None:
    summary, context = _audit(tmp_path)
    assert summary["status"] == "insufficient_observables"
    assert summary["tested"] is False
    assert context == {}
    missing = summary["missing_observables"]
    assert len(missing) == 11
    assert any("amp_mu005_up__production_a__v2: reuse_attestation" == item for item in missing)
    assert any("equilibrium_m0__production_a__v2: dataset" == item for item in missing)


def test_nonpassing_solver_budget_blocks_before_data(tmp_path: Path) -> None:
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"status": "blocked"}))
    summary, _ = audit_available_inputs(
        manifest_path=ROOT
        / "results_research_program"
        / "production_manifest_v2.json",
        base_manifest_path=ROOT / "results_research_program" / "manifest.json",
        rules_path=ROOT / "configs" / "two_mode_fcs_decision_rules_20260730.json",
        solver_budget_path=budget,
        reuse_attestations_path=tmp_path / "absent.json",
        phase="validation",
        selection_record_path=None,
    )
    assert summary["status"] == "solver_unresolved"


def test_convergence_floor_uses_worst_accepted_condition() -> None:
    assert accepted_convergence_floor(
        {
            "accepted": True,
            "records": [
                {"accepted": True, "numerical_floor": 4e-4},
                {"accepted": True, "numerical_floor": 1.2e-3},
            ],
        }
    ) == 1.2e-3


def test_blind_phase_requires_frozen_selection(tmp_path: Path) -> None:
    summary, _ = _audit(tmp_path, phase="blind")
    assert summary["status"] == "insufficient_observables"
    assert summary["missing_observables"] == [
        "signed validation-selection record"
    ]


def _synthetic_joint_case():
    t = np.arange(0.0, 251.0, 10.0)
    q = t / 250.0
    basis_d = np.outer(q, np.asarray([1.0, -0.5, 0.2]))
    basis_l = np.outer(q**2, np.asarray([0.3, 0.7, -0.4]))
    basis_a = np.outer(q**3, np.asarray([-0.2, 0.1, 0.5]))
    observed = 0.8 * basis_d + 0.5 * basis_l
    panel = JointObservablePanel(
        t=t,
        x=np.arange(3.0),
        profile={"synthetic": observed},
        current={},
        response_cmm={},
        response_cjm={},
        response_even={},
        fcs_gamma={},
        fcs_logz={},
        masks={
            "train": (t >= 50.0) & (t <= 150.0),
            "validation": (t > 150.0) & (t <= 200.0),
            "blind": (t > 200.0) & (t <= 250.0),
        },
        diagnostics={
            "pulse_spin_flip_magnetization_max_abs": 0.0,
            "pulse_even_current_max_abs": 0.0,
        },
    )

    def predictor(name, parameters, panel, noise):
        prediction = parameters.Dm * basis_d
        if name in {"independent_two_burgers", "coupled_two_mode"}:
            prediction = prediction + parameters.lambda_m * basis_l
        if name == "coupled_two_mode":
            prediction = prediction + parameters.alpha * basis_a
        return {"profile:synthetic": prediction}

    rules = json.loads(
        (
            ROOT
            / "configs"
            / "two_mode_fcs_decision_rules_20260730.json"
        ).read_text()
    )
    rules["optimization"] = {
        "multistarts": 3,
        "maxiter": 100,
        "seed": 13,
    }
    rules["bootstrap"] = {
        "replicates": 200,
        "block_time": 10.0,
        "confidence": 0.95,
        "seed": 13,
    }
    rules["forward_model"].update(
        {"screening_ensemble": 8, "final_ensemble": 8}
    )
    rules["cross_validation"] = {"required": False}
    budget = {
        "status": "pass",
        "screening_ensemble": 8,
        "final_ensemble": 8,
        "config_sha256": "synthetic",
        "forward_refinement": {
            "status": "pass",
            "levels": {
                "screening": {
                    "spatial_stride": 4,
                    "dt_internal": 0.2,
                },
                "final": {
                    "spatial_stride": 2,
                    "dt_internal": 0.1,
                },
            },
        },
    }
    return panel, predictor, rules, budget


def test_ready_validation_path_runs_models_and_freezes_selection() -> None:
    panel, predictor, rules, budget = _synthetic_joint_case()
    result = run_registered_validation(
        panel=panel,
        rules=rules,
        solver_budget=budget,
        screening_predictor=predictor,
        final_predictor=predictor,
    )
    assert result["tested"] is True
    assert result["status"] == "independent_two_burgers_supported"
    assert len(result["analysis_sha256"]) == 64
    assert result["parameters_refit_on_blind_data"] is False
    assert set(result["fits"]) == {
        "gaussian_diffusion",
        "scalar_surrogate",
        "independent_two_burgers",
        "coupled_two_mode",
    }


def test_required_cross_validation_fails_closed_before_model_fit() -> None:
    panel, predictor, rules, budget = _synthetic_joint_case()
    rules["cross_validation"] = {"required": True}
    result = run_registered_validation(
        panel=panel,
        rules=rules,
        solver_budget=budget,
        screening_predictor=predictor,
        final_predictor=predictor,
    )
    assert result["status"] == "simulation_unresolved"
    assert result["tested"] is False
    assert "leave-one-orientation/condition-out" in result["explanation"]


def test_blind_path_scores_frozen_parameters_without_refit() -> None:
    panel, predictor, rules, budget = _synthetic_joint_case()
    selection = run_registered_validation(
        panel=panel,
        rules=rules,
        solver_budget=budget,
        screening_predictor=predictor,
        final_predictor=predictor,
    )
    result = run_registered_blind(
        panel=panel,
        rules=rules,
        solver_budget=budget,
        selection=selection,
        final_predictor=predictor,
    )
    assert result["status"] == "independent_two_burgers_blind_confirmed"
    assert result["parameters_refit_on_blind_data"] is False
    assert result["validation_analysis_sha256"] == selection["analysis_sha256"]
