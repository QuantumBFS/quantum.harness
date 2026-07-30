"""Exact machine-readable gates for effective-central-charge claim strength."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ClaimDecision:
    status: str
    publish_central_charge: bool
    central_charge: float | None
    reasons: tuple[str, ...]


def evaluate_claim_gates(
    *,
    xy_interval: tuple[float, float],
    xy_reference: tuple[float, float],
    diii_width_count: int,
    opposite_phase_evidence: bool,
    streams_per_width: int,
    complete_blocks: int,
    oracle_pass: bool,
    invariant_pass: bool,
    casimir_fit_stable: bool,
    alpha_stable: bool,
    entanglement_c_eff: float,
    entanglement_standard_error: float,
    casimir_c_eff: float,
    casimir_standard_error: float,
    bootstrap_failure_fraction: float,
) -> ClaimDecision:
    validation_reasons = []
    xy_overlap = max(xy_interval[0], xy_reference[0]) <= min(
        xy_interval[1], xy_reference[1]
    )
    if not oracle_pass:
        validation_reasons.append("required_oracle_failed")
    if not invariant_pass:
        validation_reasons.append("gaussian_invariant_failed")
    if not xy_overlap:
        validation_reasons.append("xy_reference_not_reproduced")
    if validation_reasons:
        return ClaimDecision("unavailable", False, None, tuple(validation_reasons))
    if diii_width_count < 4:
        return ClaimDecision(
            "unavailable", False, None, ("fewer_than_four_diii_widths",)
        )
    if (
        not math.isfinite(bootstrap_failure_fraction)
        or bootstrap_failure_fraction > 0.05
    ):
        return ClaimDecision(
            "unavailable",
            False,
            None,
            ("bootstrap_failure_rate_exceeds_5_percent",),
        )
    estimates = (entanglement_c_eff, casimir_c_eff)
    errors = (entanglement_standard_error, casimir_standard_error)
    if not all(math.isfinite(value) for value in estimates + errors) or any(
        error < 0 for error in errors
    ):
        return ClaimDecision(
            "unavailable", False, None, ("nonfinite_effective_central_charge",)
        )

    reasons = []
    if not opposite_phase_evidence:
        reasons.append("diii_transition_not_bracketed")
    if diii_width_count < 5:
        reasons.append("fewer_than_five_diii_widths")
    if streams_per_width < 4:
        reasons.append("fewer_than_four_streams_per_width")
    if complete_blocks < 32:
        reasons.append("fewer_than_32_complete_blocks")
    if not casimir_fit_stable:
        reasons.append("casimir_fit_unstable")
    if not alpha_stable:
        reasons.append("anisotropy_unstable")
    combined = 1.96 * math.sqrt(
        entanglement_standard_error**2 + casimir_standard_error**2
    )
    if abs(entanglement_c_eff - casimir_c_eff) > combined:
        reasons.append("estimator_disagreement")

    if reasons:
        return ClaimDecision(
            "exploratory", False, casimir_c_eff, tuple(reasons)
        )
    return ClaimDecision("candidate", True, casimir_c_eff, ())
