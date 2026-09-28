from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.two_mode_cross_validation import (
    aggregate_cross_validation,
    apply_cross_validation_gate,
    inherited_holdout_scales,
    panel_sha256,
    registered_cross_validation_folds,
    rules_sha256,
    run_cross_validation_shard,
)
from src.two_mode_observables import (
    EQUILIBRIUM,
    PULSE_NEG,
    PULSE_POS,
    JointObservablePanel,
    subset_joint_observable_panel,
)

ROOT = Path(__file__).resolve().parents[1]


def _panel() -> JointObservablePanel:
    t = np.asarray([50.0, 100.0, 150.0, 175.0, 200.0])
    x = np.asarray([-1.0, 1.0])
    q = t / 200.0
    names = (
        "amp_mu002_up",
        "amp_mu002_down",
        "amp_mu005_up",
        "amp_mu005_down",
        PULSE_POS,
        PULSE_NEG,
        EQUILIBRIUM,
        "amp_mu010_up",
        "amp_mu020_down",
    )
    metadata = {
        "amp_mu002_up": {
            "role": "primary_amplitude",
            "mu": 0.02,
            "orientation": 1,
        },
        "amp_mu002_down": {
            "role": "primary_amplitude",
            "mu": 0.02,
            "orientation": -1,
        },
        "amp_mu005_up": {
            "role": "primary_amplitude",
            "mu": 0.05,
            "orientation": 1,
        },
        "amp_mu005_down": {
            "role": "primary_amplitude",
            "mu": 0.05,
            "orientation": -1,
        },
        PULSE_POS: {
            "role": "two_mode_response",
            "mu": 0.02,
            "orientation": 1,
        },
        PULSE_NEG: {
            "role": "two_mode_response",
            "mu": 0.02,
            "orientation": -1,
        },
        EQUILIBRIUM: {
            "role": "two_mode_equilibrium",
            "mu": 0.02,
            "orientation": 1,
        },
        "amp_mu010_up": {
            "role": "primary_amplitude",
            "mu": 0.10,
            "orientation": 1,
        },
        "amp_mu020_down": {
            "role": "primary_amplitude",
            "mu": 0.20,
            "orientation": -1,
        },
    }
    profile = {}
    for index, name in enumerate(names, start=1):
        basis_d = index * np.outer(q, np.asarray([1.0, -0.5]))
        basis_l = index * np.outer(q**2, np.asarray([0.3, 0.7]))
        profile[name] = 0.8 * basis_d + 0.5 * basis_l
        metadata[name]["factor"] = index
    return JointObservablePanel(
        t=t,
        x=x,
        profile=profile,
        current={},
        response_cmm={},
        response_cjm={},
        response_even={},
        fcs_gamma={},
        fcs_logz={},
        masks={
            "train": t <= 150.0,
            "validation": t > 150.0,
            "blind": np.zeros(t.size, dtype=bool),
        },
        diagnostics={},
        metadata=metadata,
    )


def _rules() -> dict:
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
        "seed": 19,
        "parallel_starts": 1,
        "successful_starts_min": 1,
        "best_objective_relative_spread_max": 1.0,
    }
    return rules


def _predictor(name, parameters, panel, noise):
    result = {}
    q = panel.t / 200.0
    for condition_id in panel.profile:
        factor = float(panel.metadata[condition_id]["factor"])
        basis_d = factor * np.outer(q, np.asarray([1.0, -0.5]))
        basis_l = factor * np.outer(q**2, np.asarray([0.3, 0.7]))
        prediction = parameters.Dm * basis_d
        if name in {"scalar_surrogate", "independent_two_burgers", "coupled_two_mode"}:
            prediction += parameters.lambda_m * basis_l
        result[f"profile:{condition_id}"] = prediction
    return result


def test_registered_folds_exclude_amplitude_holdout_and_stress() -> None:
    folds = registered_cross_validation_folds(_panel())
    assert len(folds) == 9
    up = next(fold for fold in folds if fold.fold_id == "leave_orientation_up_out")
    down = next(
        fold for fold in folds if fold.fold_id == "leave_orientation_down_out"
    )
    assert set(up.held_out_conditions) == {
        "amp_mu002_up",
        "amp_mu005_up",
        PULSE_POS,
    }
    assert set(down.held_out_conditions) == {
        "amp_mu002_down",
        "amp_mu005_down",
        PULSE_NEG,
    }
    assert all(
        "amp_mu010_up" not in fold.training_conditions
        and "amp_mu020_down" not in fold.training_conditions
        for fold in folds
    )


def test_registered_fold_rules_fail_closed_on_phase_or_task_drift() -> None:
    rules = _rules()
    controls = dict(rules["cross_validation"])
    controls["evaluation_phase"] = "train"
    with pytest.raises(ValueError, match="validation phase"):
        registered_cross_validation_folds(_panel(), controls)

    rules["cross_validation"]["expected_shards"] = 26
    folds = registered_cross_validation_folds(
        _panel(), rules["cross_validation"]
    )
    assert len(folds) == 9
    with pytest.raises(ValueError, match="shard count"):
        aggregate_cross_validation(
            panel=_panel(),
            rules=rules,
            shards=[],
        )


def test_holdout_scale_never_reads_held_out_values() -> None:
    panel = _panel()
    fold = next(
        fold
        for fold in registered_cross_validation_folds(panel)
        if fold.fold_id == "leave_condition_amp_mu002_up_out"
    )
    training = subset_joint_observable_panel(
        panel, set(fold.training_conditions)
    )
    holdout = subset_joint_observable_panel(
        panel, set(fold.held_out_conditions)
    )
    train_scales, first = inherited_holdout_scales(
        training,
        holdout,
        numerical_floor=1e-8,
    )
    corrupted = JointObservablePanel(
        **{
            **holdout.__dict__,
            "profile": {
                "amp_mu002_up": 1e12
                * holdout.profile["amp_mu002_up"]
            },
        }
    )
    _, second = inherited_holdout_scales(
        training,
        corrupted,
        numerical_floor=1e-8,
    )
    assert train_scales
    assert first == second


def test_cross_validation_shard_refits_only_training_conditions() -> None:
    panel = _panel()
    fold = next(
        fold
        for fold in registered_cross_validation_folds(panel)
        if fold.fold_id == "leave_condition_amp_mu002_up_out"
    )
    result = run_cross_validation_shard(
        model="independent_two_burgers",
        fold=fold,
        panel=panel,
        rules=_rules(),
        screening_predictor=_predictor,
        final_predictor=_predictor,
        quantum_numerical_floor=1e-8,
    )
    assert result["status"] == "fit_complete"
    assert result["parameters_refit_on_held_out_data"] is False
    np.testing.assert_allclose(result["free"], [0.8, 0.5], atol=1e-4)
    assert result["heldout"]["validation"]["normalized_rmse"] < 1e-4


def test_aggregate_and_gate_require_registered_generalization() -> None:
    panel = _panel()
    rules = _rules()
    folds = registered_cross_validation_folds(panel)
    models = rules["cross_validation"]["models"]
    losses = {
        "scalar_surrogate": 2.0,
        "independent_two_burgers": 1.0,
        "coupled_two_mode": 0.8,
    }
    shards = []
    for model in models:
        for fold in folds:
            loss = losses[model]
            shards.append(
                {
                    "status": "fit_complete",
                    "model": model,
                    "fold": {
                        "fold_id": fold.fold_id,
                        "kind": fold.kind,
                    },
                    "panel_sha256": panel_sha256(panel),
                    "rules_sha256": rules_sha256(rules),
                    "parameters_refit_on_held_out_data": False,
                    "training_scales_sha256": f"training-{fold.fold_id}",
                    "holdout_scales_sha256": f"holdout-{fold.fold_id}",
                    "quantum_numerical_floor": 1e-8,
                    "heldout": {
                        "validation": {
                            "loss": loss,
                            "normalized_rmse": np.sqrt(loss),
                        },
                        "validation_rss": 10.0 * loss,
                        "validation_n": 10,
                    },
                }
            )
    summary = aggregate_cross_validation(
        panel=panel,
        rules=rules,
        shards=shards,
    )
    assert summary["status"] == "complete"
    assert summary["expected_shards"] == 27
    assert summary["comparisons"]["independent_vs_scalar"]["pass"] is True
    gated = apply_cross_validation_gate(
        {
            "status": "coupled_two_mode_supported",
            "evidence": {"independent_pass": True},
        },
        summary,
    )
    assert gated["status"] == "coupled_two_mode_supported"

    summary["comparisons"]["coupled_vs_independent"]["pass"] = False
    downgraded = apply_cross_validation_gate(
        {
            "status": "coupled_two_mode_supported",
            "evidence": {"independent_pass": True},
        },
        summary,
    )
    assert downgraded["status"] == "independent_two_burgers_supported"
