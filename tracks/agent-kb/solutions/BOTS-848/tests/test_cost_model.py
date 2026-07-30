import importlib
import unittest


class CostModelTests(unittest.TestCase):
    def load_api(self):
        try:
            module = importlib.import_module("src.cost_model")
        except ModuleNotFoundError:
            self.fail("src.cost_model has not been implemented")
        return module.compare_corrected_to_baselines

    def test_sparse_high_level_correction_can_beat_dense_high_level_baseline(self):
        compare_corrected_to_baselines = self.load_api()
        result = compare_corrected_to_baselines(
            full_points=100,
            dfpt_cost_per_point=1.0,
            high_level_anchors=4,
            high_level_cost_per_point=5.0,
            inference_cost_per_point=0.01,
            training_cost=1.0,
        )

        self.assertAlmostEqual(result["dfpt_only_cost"], 100.0)
        self.assertAlmostEqual(result["dense_high_level_cost"], 600.0)
        self.assertAlmostEqual(result["corrected_cost"], 122.0)
        self.assertTrue(result["is_faster_than_dense_high_level"])
        self.assertFalse(result["is_faster_than_dfpt"])
        self.assertAlmostEqual(result["speedup_vs_dense_high_level"], 600.0 / 122.0)
        self.assertAlmostEqual(result["overhead_vs_dfpt"], 22.0)

    def test_corrected_workflow_can_be_slower_than_both_baselines(self):
        compare_corrected_to_baselines = self.load_api()
        result = compare_corrected_to_baselines(
            full_points=10,
            dfpt_cost_per_point=1.0,
            high_level_anchors=10,
            high_level_cost_per_point=1.0,
            inference_cost_per_point=1.0,
            training_cost=1.0,
        )

        self.assertFalse(result["is_faster_than_dense_high_level"])
        self.assertFalse(result["is_faster_than_dfpt"])
        self.assertLess(result["speedup_vs_dense_high_level"], 1.0)

    def test_training_cost_can_be_amortized_over_campaigns(self):
        compare_corrected_to_baselines = self.load_api()
        one_campaign = compare_corrected_to_baselines(
            full_points=100,
            dfpt_cost_per_point=1.0,
            high_level_anchors=4,
            high_level_cost_per_point=1.0,
            training_cost=500.0,
            inference_cost_per_point=0.01,
            campaigns=1,
        )
        twenty_campaigns = compare_corrected_to_baselines(
            full_points=100,
            dfpt_cost_per_point=1.0,
            high_level_anchors=4,
            high_level_cost_per_point=1.0,
            training_cost=500.0,
            inference_cost_per_point=0.01,
            campaigns=20,
        )

        self.assertFalse(one_campaign["is_faster_than_dense_high_level"])
        self.assertTrue(twenty_campaigns["is_faster_than_dense_high_level"])
        self.assertFalse(twenty_campaigns["is_faster_than_dfpt"])

    def test_zero_high_level_cost_reduces_dense_baseline_to_dfpt(self):
        compare_corrected_to_baselines = self.load_api()
        result = compare_corrected_to_baselines(
            full_points=10,
            dfpt_cost_per_point=1.0,
            high_level_anchors=1,
            high_level_cost_per_point=0.0,
        )

        self.assertEqual(result["dfpt_only_cost"], result["dense_high_level_cost"])
        self.assertEqual(result["corrected_cost"], result["dfpt_only_cost"])
        self.assertFalse(result["is_faster_than_dense_high_level"])
        self.assertFalse(result["is_faster_than_dfpt"])

    def test_invalid_point_counts_are_rejected(self):
        compare_corrected_to_baselines = self.load_api()
        invalid_cases = (
            {"full_points": 0, "high_level_anchors": 1},
            {"full_points": 10, "high_level_anchors": 0},
            {"full_points": 10, "high_level_anchors": 11},
            {"full_points": 10.5, "high_level_anchors": 5},
            {"full_points": 10, "high_level_anchors": 5, "campaigns": 0},
        )

        for case in invalid_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    compare_corrected_to_baselines(
                        dfpt_cost_per_point=1.0,
                        high_level_cost_per_point=1.0,
                        **case,
                    )

    def test_invalid_costs_are_rejected(self):
        compare_corrected_to_baselines = self.load_api()
        invalid_costs = (
            {"dfpt_cost_per_point": 0.0},
            {"dfpt_cost_per_point": -1.0},
            {"dfpt_cost_per_point": 1.0, "inference_cost_per_point": -0.1},
            {"dfpt_cost_per_point": 1.0, "training_cost": float("inf")},
            {"dfpt_cost_per_point": 1.0, "training_cost": 10**400},
            {"dfpt_cost_per_point": 1.0, "high_level_cost_per_point": "bad"},
        )

        for costs in invalid_costs:
            with self.subTest(costs=costs):
                parameters = {
                    "dfpt_cost_per_point": 1.0,
                    "high_level_cost_per_point": 1.0,
                }
                parameters.update(costs)
                with self.assertRaises(ValueError):
                    compare_corrected_to_baselines(
                        full_points=10,
                        high_level_anchors=2,
                        **parameters,
                    )

    def test_nonfinite_derived_cost_is_rejected(self):
        compare_corrected_to_baselines = self.load_api()

        with self.assertRaisesRegex(ValueError, "finite"):
            compare_corrected_to_baselines(
                full_points=2,
                dfpt_cost_per_point=1.0e308,
                high_level_anchors=1,
                high_level_cost_per_point=1.0,
            )

        with self.assertRaisesRegex(ValueError, "finite"):
            compare_corrected_to_baselines(
                full_points=10**400,
                dfpt_cost_per_point=1.0,
                high_level_anchors=1,
                high_level_cost_per_point=1.0,
            )


if __name__ == "__main__":
    unittest.main()
