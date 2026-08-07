"""Paired held-out selection for the preregistered two-mode hierarchy."""

from __future__ import annotations

from math import log
from typing import Any, Literal, Mapping

import numpy as np

from .two_mode_models import ModelName


Array = np.ndarray


def paired_time_block_bootstrap(
    baseline_loss_by_time: Array,
    candidate_loss_by_time: Array,
    t: Array,
    *,
    block_time: float,
    n_replicates: int,
    confidence: float,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap paired contiguous time blocks and relative loss improvement."""

    baseline = np.asarray(baseline_loss_by_time, dtype=float)
    candidate = np.asarray(candidate_loss_by_time, dtype=float)
    t = np.asarray(t, dtype=float)
    if (
        baseline.ndim != 1
        or baseline.shape != candidate.shape
        or baseline.shape != t.shape
        or baseline.size < 4
        or np.any(~np.isfinite(baseline))
        or np.any(~np.isfinite(candidate))
        or np.any(baseline <= 0)
        or np.any(candidate < 0)
        or np.any(np.diff(t) <= 0)
    ):
        raise ValueError("finite paired time losses on an increasing grid are required")
    if block_time <= 0 or n_replicates < 100 or not 0 < confidence < 1:
        raise ValueError("invalid paired bootstrap controls")
    dt = float(np.median(np.diff(t)))
    if not np.allclose(np.diff(t), dt, rtol=1e-6, atol=1e-12):
        raise ValueError("paired bootstrap requires a uniform time grid")
    steps = int(round(block_time / dt))
    if steps < 1 or not np.isclose(steps * dt, block_time, rtol=1e-6, atol=1e-12):
        raise ValueError("block_time must be an integer multiple of time spacing")
    complete = baseline.size // steps
    if complete < 2:
        raise ValueError("at least two complete time blocks are required")
    retained = complete * steps
    baseline_blocks = baseline[:retained].reshape(complete, steps)
    candidate_blocks = candidate[:retained].reshape(complete, steps)
    point = 1.0 - float(np.mean(candidate_blocks)) / float(
        np.mean(baseline_blocks)
    )
    rng = np.random.default_rng(int(seed))
    replicates = np.empty(n_replicates, dtype=float)
    for index in range(n_replicates):
        selection = rng.integers(0, complete, size=complete)
        replicates[index] = 1.0 - float(
            np.mean(candidate_blocks[selection])
        ) / float(np.mean(baseline_blocks[selection]))
    alpha = 0.5 * (1.0 - confidence)
    low, high = np.quantile(replicates, [alpha, 1.0 - alpha])
    return {
        "relative_improvement": point,
        "paired_ci_low": float(low),
        "paired_ci_high": float(high),
        "confidence": float(confidence),
        "n_replicates": int(n_replicates),
        "seed": int(seed),
        "block_time": float(block_time),
        "block_steps": steps,
        "complete_blocks": complete,
        "retained_time_points": retained,
        "excluded_partial_time_points": int(baseline.size - retained),
    }


def bic_from_fit(
    fit: Mapping[str, Any],
    *,
    phase: Literal["validation", "blind"] = "validation",
) -> float:
    rss = float(fit[f"{phase}_rss"])
    n = int(fit[f"{phase}_n"])
    k = len(fit["free_parameter_names"])
    if rss < 0 or n <= k or n < 2:
        raise ValueError("BIC requires nonnegative RSS and n>k")
    return n * log(max(rss / n, 1e-300)) + k * log(n)


def _paired(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    t: Array,
    bootstrap: Mapping[str, Any],
    phase: Literal["validation", "blind"],
) -> dict[str, Any]:
    return paired_time_block_bootstrap(
        np.asarray(baseline[f"{phase}_loss_by_time"]),
        np.asarray(candidate[f"{phase}_loss_by_time"]),
        t,
        block_time=float(bootstrap["block_time"]),
        n_replicates=int(bootstrap["replicates"]),
        confidence=float(bootstrap["confidence"]),
        seed=int(bootstrap["seed"]),
    )


def decide_two_mode_verdict(
    fits: Mapping[ModelName, Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    rules: Mapping[str, Any],
    *,
    phase: Literal["validation", "blind"],
) -> dict[str, Any]:
    """Apply the frozen hierarchy and return exactly one fail-closed status."""

    if diagnostics.get("observables_ready") is not True:
        return {"status": "insufficient_observables", "tested": False}
    if diagnostics.get("fcs_status") != "pass":
        return {"status": "fcs_validation_failed", "tested": False}
    if diagnostics.get("solver_status") != "pass":
        return {"status": "solver_unresolved", "tested": False}
    if diagnostics.get("symmetry_pass") is not True:
        return {
            "status": "memory_or_more_modes_required",
            "tested": True,
            "reason": "registered symmetry diagnostics failed",
        }
    required = {
        "scalar_surrogate",
        "independent_two_burgers",
        "coupled_two_mode",
    }
    if not required <= set(fits) or any(
        fits[name].get("status") != "fit_complete" for name in required
    ):
        return {
            "status": "memory_or_more_modes_required",
            "tested": True,
            "reason": "one or more registered fits failed",
        }

    thresholds = rules["thresholds"]
    bootstrap = rules["bootstrap"]
    t = np.asarray(diagnostics[f"{phase}_t"], dtype=float)
    scalar = fits["scalar_surrogate"]
    independent = fits["independent_two_burgers"]
    coupled = fits["coupled_two_mode"]
    independent_pair = _paired(
        scalar, independent, t=t, bootstrap=bootstrap, phase=phase
    )
    coupled_pair = _paired(
        scalar, coupled, t=t, bootstrap=bootstrap, phase=phase
    )
    rmse_max = float(thresholds["joint_normalized_rmse_max"])
    improvement_min = float(
        thresholds["two_mode_vs_scalar_improvement_min"]
    )
    ci_min = float(thresholds["paired_ci_low_min"])

    def passes(candidate: Mapping[str, Any], paired: Mapping[str, Any]) -> bool:
        return (
            float(paired["relative_improvement"]) >= improvement_min
            and float(paired["paired_ci_low"]) > ci_min
            and float(candidate[phase]["normalized_rmse"]) <= rmse_max
        )

    independent_pass = passes(independent, independent_pair)
    coupled_pass = passes(coupled, coupled_pair)
    bic_independent = bic_from_fit(independent, phase=phase)
    bic_coupled = bic_from_fit(coupled, phase=phase)
    coupled_over_independent = 1.0 - float(
        coupled[phase]["loss"]
    ) / float(independent[phase]["loss"])
    delta_bic = bic_independent - bic_coupled
    coupled_complexity_pass = (
        coupled_over_independent
        >= float(thresholds["coupled_vs_independent_improvement_min"])
        and delta_bic
        >= float(thresholds["coupled_vs_independent_delta_bic_min"])
    )
    evidence = {
        "independent_vs_scalar": independent_pair,
        "coupled_vs_scalar": coupled_pair,
        "coupled_vs_independent_improvement": coupled_over_independent,
        "bic_independent": bic_independent,
        "bic_coupled": bic_coupled,
        "delta_bic_independent_minus_coupled": delta_bic,
        "independent_pass": independent_pass,
        "coupled_pass": coupled_pass,
        "coupled_complexity_pass": coupled_complexity_pass,
    }

    if phase == "blind":
        selected = str(diagnostics.get("frozen_validation_selection", ""))
        if selected not in {
            "independent_two_burgers_supported",
            "coupled_two_mode_supported",
        }:
            return {
                "status": "memory_or_more_modes_required",
                "tested": False,
                "reason": "blind phase has no valid frozen validation selection",
                "evidence": evidence,
            }
        selected_model = (
            "independent_two_burgers"
            if selected.startswith("independent")
            else "coupled_two_mode"
        )
        selected_pass = independent_pass if selected_model.startswith("independent") else coupled_pass
        return {
            "status": (
                f"{selected_model}_blind_confirmed"
                if selected_pass
                else f"{selected_model}_blind_failed"
            ),
            "tested": True,
            "parameters_refit_on_blind_data": False,
            "evidence": evidence,
        }

    if coupled_pass and coupled_complexity_pass:
        status = "coupled_two_mode_supported"
    elif independent_pass:
        status = "independent_two_burgers_supported"
    elif float(scalar["validation"]["normalized_rmse"]) <= rmse_max:
        status = "scalar_surrogate_not_rejected"
    else:
        status = "memory_or_more_modes_required"
    return {"status": status, "tested": True, "evidence": evidence}
