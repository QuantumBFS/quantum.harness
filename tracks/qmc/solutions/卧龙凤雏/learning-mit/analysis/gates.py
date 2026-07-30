"""Exact machine-readable gates for scientific claim strength."""

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
    oracle_pass: bool,
    invariant_pass: bool,
    effective_sample_size: float,
    minimum_effective_sample_size: float,
    fit_stable: bool,
    alpha_stable: bool,
    casimir_amplitude: float,
    alpha: float,
) -> ClaimDecision:
    reasons = []
    xy_overlap = max(xy_interval[0], xy_reference[0]) <= min(
        xy_interval[1], xy_reference[1]
    )
    if not oracle_pass:
        reasons.append("required_oracle_failed")
    if not invariant_pass:
        reasons.append("gaussian_invariant_failed")
    if not xy_overlap:
        reasons.append("xy_reference_not_reproduced")
    if reasons:
        return ClaimDecision("validation_failed", False, None, tuple(reasons))

    if diii_width_count < 5:
        reasons.append("fewer_than_five_diii_widths")
    if not opposite_phase_evidence:
        reasons.append("diii_phase_sides_not_opposite")
    if effective_sample_size < minimum_effective_sample_size:
        reasons.append("effective_sample_size_too_small")
    if not fit_stable:
        reasons.append("casimir_fit_unstable")
    if not alpha_stable:
        reasons.append("anisotropy_unstable")
    if (
        not math.isfinite(casimir_amplitude)
        or not math.isfinite(alpha)
        or alpha <= 0
    ):
        reasons.append("nonfinite_candidate_parameter")
    if reasons:
        return ClaimDecision(
            "xy_reproduced_diii_inconclusive", False, None, tuple(reasons)
        )

    return ClaimDecision(
        status="xy_reproduced_diii_candidate",
        publish_central_charge=True,
        central_charge=casimir_amplitude / alpha,
        reasons=(),
    )
