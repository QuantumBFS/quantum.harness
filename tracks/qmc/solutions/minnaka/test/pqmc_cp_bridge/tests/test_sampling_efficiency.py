#!/usr/bin/env python3
"""Unit tests for final sampling-efficiency and field-pattern analysis."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_sampling_efficiency import (  # noqa: E402
    field_descriptor,
    worst_efficiency_rows,
)
from summarize_trace_dynamics import surprisal_metrics  # noqa: E402


class SamplingEfficiencyTest(unittest.TestCase):
    def test_worst_efficiency_uses_log_q_minus_log_true_weight(self) -> None:
        rows = [
            {
                "sample_id": index,
                "log_q_prop": -10.0 - index,
                "logabs_d_ti": -5.0 + 0.5 * index,
            }
            for index in range(100)
        ]
        selected = worst_efficiency_rows(rows, fraction=0.01)
        self.assertEqual([row["sample_id"] for row in selected], [99])

    def test_field_descriptor_identifies_constant_and_checkerboard(self) -> None:
        coordinates = [
            (x, y) for y in range(4) for x in range(4)
        ]
        constant = field_descriptor([1] * 16, coordinates)
        self.assertEqual(constant["abs_uniform"], 16)
        self.assertEqual(constant["abs_staggered"], 0)
        self.assertEqual(constant["domain_walls"], 0)
        self.assertEqual(constant["distance_constant"], 0)

        checker = [
            1 if (x + y) % 2 == 0 else -1
            for x, y in coordinates
        ]
        staggered = field_descriptor(checker, coordinates)
        self.assertEqual(staggered["abs_uniform"], 0)
        self.assertEqual(staggered["abs_staggered"], 16)
        self.assertEqual(staggered["domain_walls"], 32)
        self.assertEqual(staggered["distance_checkerboard"], 0)

    def test_surprisal_metrics_distinguish_rare_and_distributed_cost(self) -> None:
        result = surprisal_metrics(
            [0.5, 1.0e-3, 1.0e-7], [0, 0, 1]
        )
        self.assertEqual(result["count_q_lt_1e3"], 1)
        self.assertEqual(result["count_q_lt_1e6"], 1)
        self.assertEqual(result["peak_surprisal_slice"], 1)
        self.assertGreater(result["largest_event_surprisal"], 16.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
