import importlib.util
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compute_baseline_ratio",
    ROOT / "scripts" / "compute-baseline-ratio.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BaselineRatioTests(unittest.TestCase):
    def test_propagates_statistics_and_cartesian_systematics(self):
        triangle = {
            "value": 4.8,
            "sigma_stat": 0.002,
            "sigma_sys": 0.003,
            "technical_gate": True,
            "primary_gate": True,
            "pilot_promotion_gate": True,
        }
        honeycomb = {
            "value": 2.0,
            "sigma_stat": 0.001,
            "sigma_sys": 0.002,
            "technical_gate": True,
            "primary_gate": True,
            "pilot_promotion_gate": False,
        }
        result = MODULE.compute(
            triangle,
            honeycomb,
            [
                {"fit_id": "p", "classification": "primary", "value": 4.8},
                {"fit_id": "up", "classification": "variant", "value": 4.81},
            ],
            [
                {"fit_id": "p", "classification": "primary", "value": 2.0},
                {"fit_id": "down", "classification": "variant", "value": 1.99},
            ],
            {
                "implementation_id": "independent-test",
                "lattices": {
                    "triangular": {
                        "value": 4.799,
                        "sigma_stat": 0.002,
                        "sigma_sys": 0.003,
                    },
                    "honeycomb": {
                        "value": 2.001,
                        "sigma_stat": 0.001,
                        "sigma_sys": 0.002,
                    },
                },
            },
        )
        expected_stat = 2.4 * math.sqrt((0.002 / 4.8) ** 2 + (0.001 / 2.0) ** 2)
        expected_sys = 4.81 / 1.99 - 2.4
        self.assertAlmostEqual(result["ratio"], 2.4)
        self.assertAlmostEqual(result["sigma_stat"], expected_stat)
        self.assertAlmostEqual(result["sigma_sys"], expected_sys)
        self.assertAlmostEqual(
            result["sigma_total"],
            math.hypot(expected_stat, expected_sys),
        )
        self.assertFalse(result["eligible_for_final_verdict"])
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertFalse(result["gates"]["pilot_promotion_ready"])
        self.assertTrue(result["gates"]["independent_route_passed_2sigma"])
        self.assertEqual(
            result["cross_method_check"]["implementation_id"],
            "independent-test",
        )


if __name__ == "__main__":
    unittest.main()
