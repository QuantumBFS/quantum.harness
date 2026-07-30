#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from decision_diagram_learn_v2 import Sample, compile_bdd, write_netlist
from independent_bitset_audit import parse
from zdd_shared_route import build_shared_zdd, expand_zdd_to_bdd


class SharedZDDTests(unittest.TestCase):
    def test_zero_suppression_and_expansion(self) -> None:
        samples = [
            Sample((0, 0), (1,)),
            Sample((1, 0), (1,)),
            Sample((0, 1), (0,)),
            Sample((1, 1), (0,)),
        ]
        zdd, roots = build_shared_zdd(samples, [0, 1])
        self.assertLessEqual(len(zdd.reachable(roots)), 1)
        bdd, bdd_roots = expand_zdd_to_bdd(zdd, roots)
        for sample in samples:
            self.assertEqual(bdd.evaluate(bdd_roots, sample.bits), sample.output)
        builder, outputs = compile_bdd(bdd, bdd_roots, 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zdd.txt"
            write_netlist(path, builder, outputs, metadata=["zdd test"])
            n_inputs, _, parsed_outputs = parse(path)
            self.assertEqual(n_inputs, 2)
            self.assertEqual(parsed_outputs, ["~x2"])

    def test_multiple_roots_share_nodes(self) -> None:
        samples = [
            Sample((0, 0), (0, 0)),
            Sample((1, 0), (1, 1)),
            Sample((0, 1), (1, 1)),
            Sample((1, 1), (0, 0)),
        ]
        zdd, roots = build_shared_zdd(samples, [0, 1])
        self.assertEqual(roots[0], roots[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
