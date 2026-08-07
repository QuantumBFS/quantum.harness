from __future__ import annotations

import copy

from src.two_mode_solver_budget import audit_ensemble_budget


def _summary(n: int, variance: float) -> dict[str, float | int]:
    return {
        "n_ensemble": n,
        "m_variance": variance,
        "phi_variance": variance * 1.001,
        "m_variance_relative_error": abs(variance - 0.25) / 0.25,
        "phi_variance_relative_error": abs(variance * 1.001 - 0.25) / 0.25,
        "max_conservation_error": 1e-14,
        "magnetization_current_skewness": 0.01,
    }


def test_accepts_converged_final_budget() -> None:
    summaries = [
        _summary(128, 0.23),
        _summary(256, 0.242),
        _summary(512, 0.248),
        _summary(1024, 0.249),
        _summary(2048, 0.250),
    ]
    audit = audit_ensemble_budget(
        summaries,
        relative_tolerance=0.02,
        conservation_tolerance=1e-12,
    )
    assert audit["status"] == "pass"
    assert audit["screening_ensemble"] == 1024
    assert audit["final_ensemble"] == 2048


def test_rejects_oscillating_final_observable() -> None:
    summaries = [
        _summary(128, 0.23),
        _summary(256, 0.24),
        _summary(512, 0.25),
        _summary(1024, 0.22),
        _summary(2048, 0.25),
    ]
    audit = audit_ensemble_budget(
        summaries,
        relative_tolerance=0.02,
        conservation_tolerance=1e-12,
    )
    assert audit["status"] == "blocked"
    assert audit["final_ensemble"] is None
    assert audit["requires_extended_budget"] is True


def test_rejects_broken_conservation() -> None:
    summaries = [
        _summary(128, 0.24),
        _summary(256, 0.247),
        _summary(512, 0.249),
        _summary(1024, 0.25),
        _summary(2048, 0.25),
    ]
    summaries[-1]["max_conservation_error"] = 1e-8
    audit = audit_ensemble_budget(
        summaries,
        relative_tolerance=0.02,
        conservation_tolerance=1e-12,
    )
    assert audit["status"] == "blocked"
    assert audit["final_checks"]["conservation"] is False


def test_rejects_final_budget_below_registered_minimum() -> None:
    summaries = [_summary(512, 0.249), _summary(1024, 0.25)]
    audit = audit_ensemble_budget(
        summaries,
        relative_tolerance=0.02,
        conservation_tolerance=1e-12,
    )
    assert audit["status"] == "blocked"
    assert audit["final_checks"]["minimum_final_ensemble"] is False
