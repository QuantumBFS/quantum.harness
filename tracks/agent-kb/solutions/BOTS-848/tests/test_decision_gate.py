import importlib
import unittest


COMPLETE_EVIDENCE = {
    "source_traceable": True,
    "reference_valid": True,
    "adiabatic_ratio": 0.01,
    "uniform_q_zero": True,
    "full_space_common_shift": True,
}


def weights(global_charge, site_charge, internal, nonlocal_weight):
    return {
        "global_charge": global_charge,
        "site_charge": site_charge,
        "internal": internal,
        "nonlocal": nonlocal_weight,
    }


class DecisionGateTests(unittest.TestCase):
    def load_api(self):
        try:
            module = importlib.import_module("src.decision_gate")
        except ModuleNotFoundError:
            self.fail("src.decision_gate has not been implemented")
        return module.select_correction_level

    def test_global_charge_dominated_uniform_mode_is_dfpt_safe_candidate(self):
        select = self.load_api()
        result = select(weights(0.90, 0.04, 0.03, 0.03), COMPLETE_EVIDENCE)
        self.assertEqual(result["decision"], "dfpt-safe")

    def test_global_charge_dominated_nonuniform_mode_forces_abstention(self):
        select = self.load_api()
        evidence = dict(COMPLETE_EVIDENCE, uniform_q_zero=False)
        result = select(weights(0.90, 0.04, 0.03, 0.03), evidence)
        self.assertEqual(result["decision"], "abstain")
        self.assertIn("uniform_q_zero", " ".join(result["reasons"]))

    def test_uniform_q_zero_must_be_boolean(self):
        select = self.load_api()
        for invalid in (1, 0, "true", None):
            with self.subTest(invalid=invalid):
                evidence = dict(COMPLETE_EVIDENCE, uniform_q_zero=invalid)
                with self.assertRaisesRegex(ValueError, "uniform_q_zero"):
                    select(weights(1.0, 0.0, 0.0, 0.0), evidence)

    def test_projected_identity_without_full_space_common_shift_abstains(self):
        select = self.load_api()
        evidence = dict(COMPLETE_EVIDENCE, full_space_common_shift=False)
        result = select(weights(1.0, 0.0, 0.0, 0.0), evidence)

        self.assertEqual(result["decision"], "abstain")
        self.assertIn("full_space_common_shift", " ".join(result["reasons"]))

    def test_full_space_common_shift_must_be_boolean(self):
        select = self.load_api()
        for invalid in (1, 0, "true", None):
            with self.subTest(invalid=invalid):
                evidence = dict(COMPLETE_EVIDENCE, full_space_common_shift=invalid)
                with self.assertRaisesRegex(ValueError, "full_space_common_shift"):
                    select(weights(1.0, 0.0, 0.0, 0.0), evidence)

    def test_missing_full_space_common_shift_forces_abstention(self):
        select = self.load_api()
        evidence = {
            name: value
            for name, value in COMPLETE_EVIDENCE.items()
            if name != "full_space_common_shift"
        }
        result = select(weights(1.0, 0.0, 0.0, 0.0), evidence)

        self.assertEqual(result["decision"], "abstain")
        self.assertIn("full_space_common_shift", " ".join(result["reasons"]))

    def test_missing_uniform_q_zero_forces_abstention(self):
        select = self.load_api()
        evidence = {name: value for name, value in COMPLETE_EVIDENCE.items() if name != "uniform_q_zero"}
        result = select(weights(1.0, 0.0, 0.0, 0.0), evidence)
        self.assertEqual(result["decision"], "abstain")
        self.assertIn("uniform_q_zero", " ".join(result["reasons"]))

    def test_site_charge_mode_requests_static_correction(self):
        select = self.load_api()
        result = select(weights(0.20, 0.75, 0.0, 0.05), COMPLETE_EVIDENCE)
        self.assertEqual(result["decision"], "static-correction")

    def test_all_non_global_channels_contribute_to_static_correction_weight(self):
        select = self.load_api()
        result = select(weights(0.79, 0.07, 0.07, 0.07), COMPLETE_EVIDENCE)
        self.assertEqual(result["decision"], "static-correction")

    def test_large_energy_ratio_has_priority_over_static_and_uniformity_gates(self):
        select = self.load_api()
        evidence = dict(COMPLETE_EVIDENCE, adiabatic_ratio=0.25, uniform_q_zero=False)
        result = select(weights(0.20, 0.70, 0.05, 0.05), evidence)
        self.assertEqual(result["decision"], "dynamic-correction")

    def test_missing_energy_scale_forces_abstention(self):
        select = self.load_api()
        evidence = {"source_traceable": True, "reference_valid": True, "uniform_q_zero": True}
        result = select(weights(1.0, 0.0, 0.0, 0.0), evidence)
        self.assertEqual(result["decision"], "abstain")
        self.assertIn("adiabatic_ratio", " ".join(result["reasons"]))

    def test_invalid_reference_state_forces_abstention(self):
        select = self.load_api()
        evidence = dict(COMPLETE_EVIDENCE, reference_valid=False)
        result = select(weights(1.0, 0.0, 0.0, 0.0), evidence)
        self.assertEqual(result["decision"], "abstain")

    def test_zero_perturbation_is_not_declared_safe(self):
        select = self.load_api()
        result = select(weights(0.0, 0.0, 0.0, 0.0), COMPLETE_EVIDENCE)
        self.assertEqual(result["decision"], "abstain")

    def test_negative_channel_weight_is_rejected(self):
        select = self.load_api()
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            select(weights(1.1, -0.1, 0.0, 0.0), COMPLETE_EVIDENCE)

    def test_channel_weights_reject_booleans_and_nonfinite_values(self):
        select = self.load_api()
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite real"):
                    select(weights(invalid, 0.0, 0.0, 0.0), COMPLETE_EVIDENCE)

    def test_thresholds_reject_booleans_and_nonfinite_values(self):
        select = self.load_api()
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite real"):
                    select(
                        weights(1.0, 0.0, 0.0, 0.0),
                        COMPLETE_EVIDENCE,
                        thresholds={"charge_safe_weight": invalid},
                    )

    def test_adiabatic_ratio_rejects_booleans_and_nonfinite_values(self):
        select = self.load_api()
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                evidence = dict(COMPLETE_EVIDENCE, adiabatic_ratio=invalid)
                with self.assertRaisesRegex(ValueError, "finite nonnegative real"):
                    select(weights(1.0, 0.0, 0.0, 0.0), evidence)

    def test_invalid_ratio_is_rejected_before_scientific_abstention(self):
        select = self.load_api()
        for flag_name in ("source_traceable", "reference_valid"):
            with self.subTest(flag_name=flag_name):
                evidence = dict(
                    COMPLETE_EVIDENCE,
                    adiabatic_ratio=float("nan"),
                    **{flag_name: False},
                )
                with self.assertRaisesRegex(ValueError, "finite nonnegative real"):
                    select(weights(1.0, 0.0, 0.0, 0.0), evidence)


if __name__ == "__main__":
    unittest.main()
