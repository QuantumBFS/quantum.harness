from __future__ import annotations

import numpy as np

from src.two_mode_model_selection import (
    bic_from_fit,
    decide_two_mode_verdict,
    paired_time_block_bootstrap,
)


RULES = {
    "bootstrap": {
        "replicates": 2000,
        "block_time": 10.0,
        "confidence": 0.95,
        "seed": 23,
    },
    "thresholds": {
        "two_mode_vs_scalar_improvement_min": 0.30,
        "paired_ci_low_min": 0.0,
        "coupled_vs_independent_improvement_min": 0.10,
        "coupled_vs_independent_delta_bic_min": 10.0,
        "joint_normalized_rmse_max": 1.5,
    },
}


def test_block_bootstrap_is_paired_reproducible_and_reports_remainder() -> None:
    t = np.arange(0.0, 45.0, 1.0)
    baseline = np.linspace(1.0, 2.0, t.size)
    candidate = 0.5 * baseline
    first = paired_time_block_bootstrap(
        baseline,
        candidate,
        t,
        block_time=10.0,
        n_replicates=1000,
        confidence=0.95,
        seed=5,
    )
    second = paired_time_block_bootstrap(
        baseline,
        candidate,
        t,
        block_time=10.0,
        n_replicates=1000,
        confidence=0.95,
        seed=5,
    )
    assert first == second
    assert first["relative_improvement"] == 0.5
    assert first["complete_blocks"] == 4
    assert first["excluded_partial_time_points"] == 5


def _fit(loss: float, *, k: int, n_time: int = 40) -> dict[str, object]:
    return {
        "status": "fit_complete",
        "free_parameter_names": [f"p{i}" for i in range(k)],
        "validation_loss_by_time": [loss] * n_time,
        "blind_loss_by_time": [loss] * n_time,
        "validation": {"loss": loss, "normalized_rmse": np.sqrt(loss)},
        "blind": {"loss": loss, "normalized_rmse": np.sqrt(loss)},
        "validation_rss": loss * 1000.0,
        "validation_n": 1000,
        "blind_rss": loss * 1000.0,
        "blind_n": 1000,
    }


def _diagnostics() -> dict[str, object]:
    return {
        "observables_ready": True,
        "fcs_status": "pass",
        "solver_status": "pass",
        "symmetry_pass": True,
        "validation_t": np.arange(0.0, 40.0, 1.0),
        "blind_t": np.arange(0.0, 40.0, 1.0),
    }


def test_selects_independent_when_coupled_complexity_gain_is_insufficient() -> None:
    fits = {
        "scalar_surrogate": _fit(1.0, k=2),
        "independent_two_burgers": _fit(0.5, k=2),
        "coupled_two_mode": _fit(0.47, k=5),
    }
    result = decide_two_mode_verdict(
        fits, _diagnostics(), RULES, phase="validation"
    )
    assert result["status"] == "independent_two_burgers_supported"
    assert result["evidence"]["coupled_complexity_pass"] is False


def test_selects_coupled_when_accuracy_and_bic_both_pass() -> None:
    fits = {
        "scalar_surrogate": _fit(1.0, k=2),
        "independent_two_burgers": _fit(0.7, k=2),
        "coupled_two_mode": _fit(0.3, k=5),
    }
    result = decide_two_mode_verdict(
        fits, _diagnostics(), RULES, phase="validation"
    )
    assert result["status"] == "coupled_two_mode_supported"
    assert result["evidence"]["delta_bic_independent_minus_coupled"] > 10.0


def test_positive_point_gain_with_nonpositive_ci_does_not_pass() -> None:
    rng = np.random.default_rng(7)
    scalar_loss = np.ones(40)
    candidate_loss = np.concatenate([np.full(20, 0.2), np.full(20, 1.7)])
    fits = {
        "scalar_surrogate": _fit(1.0, k=2),
        "independent_two_burgers": _fit(1.0, k=2),
        "coupled_two_mode": _fit(1.0, k=5),
    }
    fits["independent_two_burgers"]["validation_loss_by_time"] = candidate_loss.tolist()
    result = decide_two_mode_verdict(
        fits, _diagnostics(), RULES, phase="validation"
    )
    evidence = result["evidence"]["independent_vs_scalar"]
    assert evidence["relative_improvement"] > 0.0
    assert evidence["paired_ci_low"] <= 0.0
    assert result["status"] == "scalar_surrogate_not_rejected"


def test_missing_fcs_fails_before_model_selection() -> None:
    diagnostics = _diagnostics()
    diagnostics["fcs_status"] = "fail"
    assert (
        decide_two_mode_verdict({}, diagnostics, RULES, phase="validation")[
            "status"
        ]
        == "fcs_validation_failed"
    )


def test_blind_phase_does_not_refit_selected_family() -> None:
    fits = {
        "scalar_surrogate": _fit(1.0, k=2),
        "independent_two_burgers": _fit(0.5, k=2),
        "coupled_two_mode": _fit(0.48, k=5),
    }
    diagnostics = _diagnostics()
    diagnostics["frozen_validation_selection"] = (
        "independent_two_burgers_supported"
    )
    result = decide_two_mode_verdict(
        fits, diagnostics, RULES, phase="blind"
    )
    assert result["status"] == "independent_two_burgers_blind_confirmed"
    assert result["parameters_refit_on_blind_data"] is False
