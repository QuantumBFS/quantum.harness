#!/usr/bin/env python3

import unittest

from bdd_prefix_occam_v3 import PrefixEncoding, learn_output
from decision_diagram_learn_v2 import BDDManager, Sample


class PrefixOccamTests(unittest.TestCase):
    def test_compresses_shared_prefixes_and_learns_xor(self) -> None:
        samples = [Sample((a, b), (a ^ b,)) for a in (0, 1) for b in (0, 1)]
        encoding = PrefixEncoding(samples, [0, 1], 0, 1)
        self.assertEqual([len(items) for items in encoding.prefixes], [1, 2, 4])
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
        self.assertEqual(result.reachable_cost, 5)
        for sample in samples:
            self.assertEqual(manager.evaluate_root(result.root, sample.bits), sample.output[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
