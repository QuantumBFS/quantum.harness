#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from decision_diagram_learn_v2 import (
    BDDManager,
    Sample,
    bits_for_xy,
    compile_bdd,
    learn_shared_bdd,
    write_netlist,
)
from independent_bdd_audit import evaluate, parse_netlist


class BDDRouteTests(unittest.TestCase):
    def test_complete_xor(self) -> None:
        samples = [Sample((a, b), (a ^ b,)) for a in (0, 1) for b in (0, 1)]
        manager, roots = learn_shared_bdd(samples, [0, 1], seed=42)
        builder, outputs = compile_bdd(manager, roots, 2)
        self.assertLessEqual(len(builder.lines), 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "xor.txt"
            write_netlist(path, builder, outputs, metadata=["unit test"])
            n_inputs, gates, parsed_outputs = parse_netlist(path)
            for sample in samples:
                self.assertEqual(
                    evaluate(n_inputs, gates, parsed_outputs, sample.bits), sample.output
                )

    def test_partial_constraints_preserved(self) -> None:
        samples = [
            Sample((0, 0, 0), (0, 1)),
            Sample((0, 1, 1), (1, 0)),
            Sample((1, 0, 1), (1, 1)),
            Sample((1, 1, 0), (0, 0)),
        ]
        for order in ([0, 1, 2], [2, 0, 1], [1, 2, 0]):
            manager, roots = learn_shared_bdd(samples, order, seed=42)
            for sample in samples:
                self.assertEqual(manager.evaluate(roots, sample.bits), sample.output)

    def test_phase_and_constant_extraction(self) -> None:
        manager = BDDManager()
        x0 = manager.intern(0, 0, 1)
        not_x0 = manager.intern(0, 1, 0)
        builder, outputs = compile_bdd(manager, [0, 1, x0, not_x0], 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "phase.txt"
            write_netlist(path, builder, outputs, metadata=["unit test"])
            n_inputs, gates, parsed_outputs = parse_netlist(path)
            for a in (0, 1):
                for b in (0, 1):
                    self.assertEqual(
                        evaluate(n_inputs, gates, parsed_outputs, (a, b)),
                        (0, 1, a, 1 - a),
                    )

    def test_bits_for_xy_encoding(self) -> None:
        self.assertEqual(bits_for_xy(13, 4, 4), (1, 0, 1, 1, 0, 0, 1, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
