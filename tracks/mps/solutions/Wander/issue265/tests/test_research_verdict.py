from __future__ import annotations

import unittest
from pathlib import Path

from src.research_protocol import load_decision_rules
from src.research_verdict import evaluate_verdict


ROOT = Path(__file__).resolve().parents[1]


def decision_rules():
    return load_decision_rules(ROOT / "configs" / "burgers_decision_rules.json")


def public_pilot_evidence() -> dict:
    return {
        "coverage": {
            "n_primary_conditions": 1,
            "has_both_orientations": False,
            "has_blinded_future_test": False,
            "has_current_observable": False,
            "has_fcs": False,
        },
        "convergence": {"status": "not_available_legacy"},
        "universal_scalar": {
            "field_identified": False,
            "controlled_derivation": False,
        },
        "finite_window": {
            "within_condition_integrated_error": 0.00167,
            "tangent_ratio": 0.9992,
            "long_continuation_exposes_ballistic_crossover": True,
        },
        "microscopic_moment": {
            "A_width_over_A_GHD": 0.956,
            "future_convergence_tested": False,
        },
        "two_mode": {"tested": False},
    }


class ResearchVerdictTests(unittest.TestCase):
    def test_public_pilot_cannot_decide_universality(self) -> None:
        verdict = evaluate_verdict(public_pilot_evidence(), decision_rules())
        self.assertEqual(verdict.universal_scalar, "unresolved")
        self.assertEqual(verdict.finite_window_surrogate, "supported")
        self.assertEqual(verdict.microscopic_moment_law, "not_rejected")
        self.assertEqual(verdict.two_mode, "not_tested")
        self.assertEqual(verdict.overall, "insufficient_observables")

    def test_low_convergence_returns_unresolved_not_falsified(self) -> None:
        evidence = public_pilot_evidence()
        evidence["convergence"] = {
            "status": "tested",
            "accepted": False,
            "reason": "bond_unresolved",
        }
        verdict = evaluate_verdict(evidence, decision_rules())
        self.assertEqual(verdict.overall, "simulation_unresolved")
        self.assertEqual(verdict.universal_scalar, "unresolved")

    def test_symmetry_failure_rejects_universal_physical_scalar(self) -> None:
        evidence = public_pilot_evidence()
        evidence["coverage"] = {
            "n_primary_conditions": 12,
            "has_both_orientations": True,
            "has_blinded_future_test": True,
            "has_current_observable": True,
            "has_fcs": False,
        }
        evidence["convergence"] = {
            "status": "tested",
            "accepted": True,
            "numerical_floor": 0.001,
        }
        evidence["universal_scalar"] = {
            "field_identified": True,
            "controlled_derivation": False,
            "spin_flip_defect": 0.02,
            "loco_integrated_max": 0.005,
            "loco_endpoint_max": 0.01,
            "coefficient_relative_spread": 0.05,
            "a_drift_exponent": 0.01,
            "D_drift_exponent": -0.02,
            "late_width_exponent_error": 0.02,
        }
        verdict = evaluate_verdict(evidence, decision_rules())
        self.assertEqual(verdict.universal_scalar, "rejected")
        self.assertTrue(
            any(
                "spin_flip" in reason
                for reason in verdict.reasons["universal_scalar"]
            )
        )

    def test_two_mode_can_be_supported_after_scalar_rejection(self) -> None:
        evidence = public_pilot_evidence()
        evidence["coverage"].update(
            {
                "n_primary_conditions": 12,
                "has_both_orientations": True,
                "has_blinded_future_test": True,
                "has_current_observable": True,
                "has_fcs": True,
            }
        )
        evidence["convergence"] = {
            "status": "tested",
            "accepted": True,
            "numerical_floor": 0.001,
        }
        evidence["universal_scalar"] = {
            "field_identified": True,
            "controlled_derivation": False,
            "spin_flip_defect": 0.02,
            "loco_integrated_max": 0.03,
            "loco_endpoint_max": 0.05,
            "coefficient_relative_spread": 0.3,
            "a_drift_exponent": -0.3,
            "D_drift_exponent": 0.3,
            "late_width_exponent_error": 0.2,
        }
        evidence["two_mode"] = {
            "tested": True,
            "relative_improvement": 0.42,
            "paired_ci_low": 0.18,
            "symmetry_pass": True,
            "joint_observables_pass": True,
        }
        verdict = evaluate_verdict(evidence, decision_rules())
        self.assertEqual(verdict.universal_scalar, "rejected")
        self.assertEqual(verdict.two_mode, "supported")
        self.assertEqual(verdict.overall, "two_mode_supported_scalar_rejected")

    def test_registered_independent_and_coupled_verdicts_remain_distinct(self) -> None:
        for registered in (
            "independent_two_burgers_supported",
            "coupled_two_mode_supported",
        ):
            evidence = public_pilot_evidence()
            evidence["two_mode"] = {
                "status": registered,
                "tested": True,
            }
            verdict = evaluate_verdict(evidence, decision_rules())
            self.assertEqual(verdict.two_mode, registered)

    def test_registered_memory_outcome_is_not_collapsed_to_rejected(self) -> None:
        evidence = public_pilot_evidence()
        evidence["two_mode"] = {
            "status": "memory_or_more_modes_required",
            "tested": True,
        }
        verdict = evaluate_verdict(evidence, decision_rules())
        self.assertEqual(verdict.two_mode, "memory_or_more_modes_required")
        self.assertEqual(verdict.overall, "memory_or_more_modes_required")


if __name__ == "__main__":
    unittest.main()
