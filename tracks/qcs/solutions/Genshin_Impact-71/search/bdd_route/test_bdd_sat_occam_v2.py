#!/usr/bin/env python3

import unittest

from bdd_sat_occam_v2 import learn_occam_output
from decision_diagram_learn_v2 import BDDManager, Sample


class OccamSATTests(unittest.TestCase):
    def test_xor_minimizes_reachable_states(self) -> None:
        samples = [Sample((a, b), (a ^ b,)) for a in (0, 1) for b in (0, 1)]
        manager = BDDManager()
        result = learn_occam_output(
            samples,
            [0, 1],
            0,
            manager,
            max_width=2,
            conflict_budget=100000,
            solver_name="cadical195",
        )
        self.assertEqual(result.width, 2)
        self.assertEqual(result.reachable_state_cost, 5)
        self.assertIsNotNone(result.root)
        for sample in samples:
            self.assertEqual(manager.evaluate_root(result.root, sample.bits), sample.output[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
