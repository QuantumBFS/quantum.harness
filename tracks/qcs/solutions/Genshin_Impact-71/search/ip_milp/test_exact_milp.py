import unittest

import numpy as np

from exact_milp import evaluate_synth, solve_exact, zero_gate_literal


class ExactMilpTests(unittest.TestCase):
    def setUp(self):
        rows = np.arange(8)
        self.signals = {
            "a": ((rows >> 0) & 1).astype(bool),
            "b": ((rows >> 1) & 1).astype(bool),
            "c": ((rows >> 2) & 1).astype(bool),
        }

    def test_zero_gate_literal(self):
        self.assertEqual(
            zero_gate_literal(self.signals, ~self.signals["b"]), "~b"
        )
        self.assertIsNone(
            zero_gate_literal(
                self.signals, self.signals["a"] ^ self.signals["b"]
            )
        )

    def test_one_gate_and(self):
        target = self.signals["a"] & self.signals["b"]
        result = solve_exact(self.signals, target, 1, time_limit=30)
        self.assertEqual(result.status, "OPTIMAL_FEASIBLE")
        self.assertTrue(
            np.array_equal(evaluate_synth(result.gates, self.signals), target)
        )

    def test_two_gate_infeasible_for_three_way_xor(self):
        target = self.signals["a"] ^ self.signals["b"] ^ self.signals["c"]
        one = solve_exact(self.signals, target, 1, time_limit=30)
        self.assertEqual(one.status, "PROVEN_INFEASIBLE")
        two = solve_exact(self.signals, target, 2, time_limit=30)
        self.assertEqual(two.status, "OPTIMAL_FEASIBLE")
        self.assertTrue(
            np.array_equal(evaluate_synth(two.gates, self.signals), target)
        )


if __name__ == "__main__":
    unittest.main()
