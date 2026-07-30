#!/usr/bin/env python3

import unittest

from bdd_sat_refine import learn_output
from decision_diagram_learn_v2 import BDDManager, Sample


class LayeredSATTests(unittest.TestCase):
    def test_xor_needs_width_two(self) -> None:
        samples = [Sample((a, b), (a ^ b,)) for a in (0, 1) for b in (0, 1)]
        manager = BDDManager()
        result = learn_output(
            samples,
            [0, 1],
            0,
            manager,
            max_width=2,
            conflict_budget=100000,
            solver_name="cadical195",
        )
        self.assertEqual(result.width, 2)
        self.assertIsNotNone(result.root)
        for sample in samples:
            self.assertEqual(manager.evaluate_root(result.root, sample.bits), sample.output[0])

    def test_constant_uses_width_one(self) -> None:
        samples = [Sample((a, b), (1,)) for a in (0, 1) for b in (0, 1)]
        manager = BDDManager()
        result = learn_output(
            samples,
            [0, 1],
            0,
            manager,
            max_width=2,
            conflict_budget=100000,
            solver_name="cadical195",
        )
        self.assertEqual(result.width, 1)
        self.assertEqual(result.root, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
