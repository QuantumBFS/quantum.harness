from __future__ import annotations

import unittest

import numpy as np

from borncritical.born_circuit_oracle import apply_record_dense
from borncritical.metropolis_tn import (
    DenseRecordContraction,
    integrated_autocorrelation_time,
)


class DenseRecordContractionTests(unittest.TestCase):
    def test_matches_independent_dense_oracle(self) -> None:
        evaluator = DenseRecordContraction(4, 1)
        rng = np.random.default_rng(31)
        for _ in range(12):
            bits = rng.integers(0, 2, evaluator.variable_count, dtype=np.int8)
            probability, log_norm = apply_record_dense(4, 1, tuple(bits))
            self.assertAlmostEqual(evaluator.log_norm(bits), log_norm, places=13)
            self.assertAlmostEqual(
                evaluator.log_probability(bits), np.log(probability), places=13
            )

    def test_iid_autocorrelation_time(self) -> None:
        values = np.random.default_rng(99).normal(size=20_000)
        tau = integrated_autocorrelation_time(values)
        self.assertGreaterEqual(tau, 0.5)
        self.assertLess(tau, 0.6)


if __name__ == "__main__":
    unittest.main()
