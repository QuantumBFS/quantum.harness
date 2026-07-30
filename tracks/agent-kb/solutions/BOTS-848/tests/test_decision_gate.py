import importlib
import unittest


COMPLETE_EVIDENCE = {
    "source_traceable": True,
    "reference_valid": True,
    "adiabatic_ratio": 0.01,
}


class DecisionGateTests(unittest.TestCase):
    def load_api(self):
        try:
            module = importlib.import_module("src.decision_gate")
        except ModuleNotFoundError:
            self.fail("src.decision_gate has not been implemented")
        return module.select_correction_level

    def test_charge_dominated_mode_is_dfpt_safe_candidate(self):
        select = self.load_api()
        result = select(
            {"charge": 0.90, "internal": 0.06, "nonlocal": 0.04},
            COMPLETE_EVIDENCE,
        )
        self.assertEqual(result["decision"], "dfpt-safe")

    def test_internal_mode_requests_static_correction(self):
        select = self.load_api()
        result = select(
            {"charge": 0.20, "internal": 0.75, "nonlocal": 0.05},
            COMPLETE_EVIDENCE,
        )
        self.assertEqual(result["decision"], "static-correction")

    def test_large_energy_ratio_requests_dynamic_correction(self):
        select = self.load_api()
        evidence = dict(COMPLETE_EVIDENCE, adiabatic_ratio=0.25)
        result = select(
            {"charge": 0.95, "internal": 0.03, "nonlocal": 0.02},
            evidence,
        )
        self.assertEqual(result["decision"], "dynamic-correction")

    def test_missing_energy_scale_forces_abstention(self):
        select = self.load_api()
        evidence = {"source_traceable": True, "reference_valid": True}
        result = select(
            {"charge": 1.0, "internal": 0.0, "nonlocal": 0.0},
            evidence,
        )
        self.assertEqual(result["decision"], "abstain")
        self.assertIn("adiabatic_ratio", " ".join(result["reasons"]))

    def test_invalid_reference_state_forces_abstention(self):
        select = self.load_api()
        evidence = dict(COMPLETE_EVIDENCE, reference_valid=False)
        result = select(
            {"charge": 1.0, "internal": 0.0, "nonlocal": 0.0},
            evidence,
        )
        self.assertEqual(result["decision"], "abstain")

    def test_zero_perturbation_is_not_declared_safe(self):
        select = self.load_api()
        result = select(
            {"charge": 0.0, "internal": 0.0, "nonlocal": 0.0},
            COMPLETE_EVIDENCE,
        )
        self.assertEqual(result["decision"], "abstain")

    def test_negative_channel_weight_is_rejected(self):
        select = self.load_api()
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            select(
                {"charge": 1.1, "internal": -0.1, "nonlocal": 0.0},
                COMPLETE_EVIDENCE,
            )


if __name__ == "__main__":
    unittest.main()
