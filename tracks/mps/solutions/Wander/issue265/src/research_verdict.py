"""Preregistered, non-fitting verdict logic for the Burgers research program."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .research_protocol import DecisionRules


@dataclass(frozen=True)
class ResearchVerdict:
    """Component verdicts and auditable reasons."""

    overall: str
    universal_scalar: str
    finite_window_surrogate: str
    microscopic_moment_law: str
    two_mode: str
    reasons: dict[str, tuple[str, ...]]


def _number(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if value is None:
        return None
    result = float(value)
    return result if np.isfinite(result) else None


def _finite_window_verdict(
    evidence: dict[str, Any],
    rules: DecisionRules,
    numerical_floor: float,
) -> tuple[str, tuple[str, ...]]:
    finite = evidence.get("finite_window", {})
    error = _number(finite, "within_condition_integrated_error")
    ratio = _number(finite, "tangent_ratio")
    continuation = finite.get("long_continuation_exposes_ballistic_crossover")
    if error is None or ratio is None or continuation is None:
        return "unresolved", ("finite_window_evidence_incomplete",)

    error_limit = max(
        rules.threshold("finite_window_within_error_max"),
        3.0 * numerical_floor,
    )
    tangent_error = abs(ratio - 1.0)
    tangent_limit = rules.threshold("tangent_ratio_abs_error_max")
    reasons = (
        f"within_condition_error={error:.9g};limit={error_limit:.9g}",
        f"tangent_ratio_error={tangent_error:.9g};limit={tangent_limit:.9g}",
        f"ballistic_continuation={bool(continuation)}",
    )
    passed = error <= error_limit and tangent_error <= tangent_limit and bool(
        continuation
    )
    return ("supported" if passed else "rejected"), reasons


def _universal_verdict(
    evidence: dict[str, Any],
    rules: DecisionRules,
    numerical_floor: float,
) -> tuple[str, tuple[str, ...]]:
    coverage = evidence.get("coverage", {})
    enough_coverage = (
        int(coverage.get("n_primary_conditions", 0)) >= 8
        and bool(coverage.get("has_both_orientations", False))
        and bool(coverage.get("has_blinded_future_test", False))
    )
    if not enough_coverage:
        return (
            "unresolved",
            (
                f"n_primary_conditions={int(coverage.get('n_primary_conditions', 0))}",
                f"has_both_orientations={bool(coverage.get('has_both_orientations', False))}",
                f"has_blinded_future_test={bool(coverage.get('has_blinded_future_test', False))}",
            ),
        )

    universal = evidence.get("universal_scalar", {})
    required = (
        "spin_flip_defect",
        "loco_integrated_max",
        "loco_endpoint_max",
        "coefficient_relative_spread",
        "a_drift_exponent",
        "D_drift_exponent",
        "late_width_exponent_error",
    )
    values = {key: _number(universal, key) for key in required}
    if any(value is None for value in values.values()):
        return "unresolved", ("universal_scalar_evidence_incomplete",)

    spin_limit = 5.0 * numerical_floor
    checks = {
        "spin_flip": values["spin_flip_defect"] <= spin_limit,
        "loco_integrated": values["loco_integrated_max"]
        <= rules.threshold("universal_loco_integrated_max"),
        "loco_endpoint": values["loco_endpoint_max"]
        <= rules.threshold("universal_loco_endpoint_max"),
        "coefficient_spread": values["coefficient_relative_spread"]
        <= rules.threshold("coefficient_relative_spread_max"),
        "a_drift": abs(values["a_drift_exponent"])
        <= rules.threshold("window_drift_abs_max"),
        "D_drift": abs(values["D_drift_exponent"])
        <= rules.threshold("window_drift_abs_max"),
        "late_width": abs(values["late_width_exponent_error"])
        <= rules.threshold("late_width_exponent_abs_error_max"),
    }
    reasons = (
        f"spin_flip_defect={values['spin_flip_defect']:.9g};limit={spin_limit:.9g}",
        f"loco_integrated_max={values['loco_integrated_max']:.9g}",
        f"loco_endpoint_max={values['loco_endpoint_max']:.9g}",
        f"coefficient_relative_spread={values['coefficient_relative_spread']:.9g}",
        f"a_drift_exponent={values['a_drift_exponent']:.9g}",
        f"D_drift_exponent={values['D_drift_exponent']:.9g}",
        f"late_width_exponent_error={values['late_width_exponent_error']:.9g}",
    )
    if not all(checks.values()):
        failures = tuple(f"{name}_failed" for name, passed in checks.items() if not passed)
        return "rejected", failures + reasons

    proof_complete = bool(universal.get("field_identified", False)) and bool(
        universal.get("controlled_derivation", False)
    )
    return (
        "supported" if proof_complete else "not_rejected",
        reasons
        + (
            f"field_identified={bool(universal.get('field_identified', False))}",
            f"controlled_derivation={bool(universal.get('controlled_derivation', False))}",
        ),
    )


def _moment_verdict(evidence: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    moment = evidence.get("microscopic_moment", {})
    ratio = _number(moment, "A_width_over_A_GHD")
    if ratio is None:
        return "unresolved", ("microscopic_moment_evidence_incomplete",)
    tested = bool(moment.get("future_convergence_tested", False))
    if not tested:
        return (
            "not_rejected",
            (
                f"A_width_over_A_GHD={ratio:.9g}",
                "future_convergence_tested=False",
            ),
        )
    relative_error = abs(ratio - 1.0)
    state = "supported" if relative_error <= 0.05 else "rejected"
    return (
        state,
        (
            f"A_width_over_A_GHD={ratio:.9g}",
            f"relative_error={relative_error:.9g}",
            "future_convergence_tested=True",
        ),
    )


def _two_mode_verdict(
    evidence: dict[str, Any],
    rules: DecisionRules,
) -> tuple[str, tuple[str, ...]]:
    two_mode = evidence.get("two_mode", {})
    registered_status = str(two_mode.get("status", ""))
    registered = {
        "independent_two_burgers_supported",
        "coupled_two_mode_supported",
        "memory_or_more_modes_required",
        "scalar_surrogate_not_rejected",
        "insufficient_observables",
        "fcs_validation_failed",
        "solver_unresolved",
    }
    if registered_status in registered:
        return (
            registered_status,
            (
                f"registered_status={registered_status}",
                f"two_mode_tested={bool(two_mode.get('tested', False))}",
            ),
        )
    if not bool(two_mode.get("tested", False)):
        return "not_tested", ("two_mode_tested=False",)
    improvement = _number(two_mode, "relative_improvement")
    ci_low = _number(two_mode, "paired_ci_low")
    if improvement is None or ci_low is None:
        return "unresolved", ("two_mode_evidence_incomplete",)
    symmetry = bool(two_mode.get("symmetry_pass", False))
    joint = bool(two_mode.get("joint_observables_pass", False))
    limit = rules.threshold("two_mode_relative_improvement_min")
    passed = improvement >= limit and ci_low > 0 and symmetry and joint
    return (
        "supported" if passed else "rejected",
        (
            f"relative_improvement={improvement:.9g};limit={limit:.9g}",
            f"paired_ci_low={ci_low:.9g}",
            f"symmetry_pass={symmetry}",
            f"joint_observables_pass={joint}",
        ),
    )


def evaluate_verdict(
    evidence: dict[str, Any],
    rules: DecisionRules,
) -> ResearchVerdict:
    """Evaluate frozen rules without fitting or modifying evidence."""

    convergence = evidence.get("convergence", {})
    convergence_status = str(convergence.get("status", "missing"))
    if convergence_status == "tested" and not bool(convergence.get("accepted", False)):
        reason = str(convergence.get("reason", "convergence_failed"))
        return ResearchVerdict(
            overall="simulation_unresolved",
            universal_scalar="unresolved",
            finite_window_surrogate="unresolved",
            microscopic_moment_law="unresolved",
            two_mode="unresolved",
            reasons={
                "overall": (f"convergence_failed:{reason}",),
                "universal_scalar": ("convergence_gate_failed",),
                "finite_window_surrogate": ("convergence_gate_failed",),
                "microscopic_moment_law": ("convergence_gate_failed",),
                "two_mode": ("convergence_gate_failed",),
            },
        )
    numerical_floor = float(convergence.get("numerical_floor", 0.0))

    universal, universal_reasons = _universal_verdict(
        evidence,
        rules,
        numerical_floor,
    )
    finite, finite_reasons = _finite_window_verdict(
        evidence,
        rules,
        numerical_floor,
    )
    moment, moment_reasons = _moment_verdict(evidence)
    two_mode, two_mode_reasons = _two_mode_verdict(evidence, rules)

    if universal == "supported":
        overall = "universal_scalar_supported_for_identified_field"
    elif universal == "rejected" and two_mode == "supported":
        overall = "two_mode_supported_scalar_rejected"
    elif universal == "rejected" and two_mode in {
        "independent_two_burgers_supported",
        "coupled_two_mode_supported",
    }:
        overall = f"{two_mode}_scalar_rejected"
    elif two_mode == "memory_or_more_modes_required":
        overall = "memory_or_more_modes_required"
    elif universal == "rejected" and finite == "supported":
        overall = "physical_scalar_rejected_finite_surrogate_supported"
    elif universal == "rejected" and finite == "rejected" and two_mode == "rejected":
        overall = "memory_or_more_modes_required"
    else:
        overall = "insufficient_observables"

    return ResearchVerdict(
        overall=overall,
        universal_scalar=universal,
        finite_window_surrogate=finite,
        microscopic_moment_law=moment,
        two_mode=two_mode,
        reasons={
            "overall": (f"decision={overall}",),
            "universal_scalar": universal_reasons,
            "finite_window_surrogate": finite_reasons,
            "microscopic_moment_law": moment_reasons,
            "two_mode": two_mode_reasons,
        },
    )
