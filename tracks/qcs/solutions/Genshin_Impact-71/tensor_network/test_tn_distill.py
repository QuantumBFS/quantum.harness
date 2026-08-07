#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from distill_mps_bdd import (
    build_shared_robdd,
    emit_mux_netlist,
    verify_serialized_netlist,
)


class DistillationTests(unittest.TestCase):
    def test_xor_and_or_multioutput_roundtrip(self) -> None:
        bits = np.asarray(
            [[(assignment >> bit) & 1 for bit in range(3)]
             for assignment in range(8)],
            dtype=np.int8,
        )
        predictions = np.column_stack(
            [bits[:, 0] ^ bits[:, 1], bits[:, 1] | bits[:, 2]]
        ).astype(np.int8)
        nodes, roots = build_shared_robdd(predictions, [0, 1, 2])
        self.assertGreater(len(nodes), 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.txt"
            emit_mux_netlist(path, 3, [0, 1, 2], nodes, roots)
            audit = verify_serialized_netlist(path, predictions)
            self.assertTrue(audit["equivalent_to_thresholded_mps"])
            self.assertEqual(audit["mismatching_output_truth_tables"], 0)

    def test_variable_order_preserves_function(self) -> None:
        bits = np.asarray(
            [[(assignment >> bit) & 1 for bit in range(4)]
             for assignment in range(16)],
            dtype=np.int8,
        )
        predictions = (bits[:, 0] ^ bits[:, 3])[:, None]
        order = [3, 1, 0, 2]
        nodes, roots = build_shared_robdd(predictions, order)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.txt"
            emit_mux_netlist(path, 4, order, nodes, roots)
            audit = verify_serialized_netlist(path, predictions)
            self.assertTrue(audit["equivalent_to_thresholded_mps"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
