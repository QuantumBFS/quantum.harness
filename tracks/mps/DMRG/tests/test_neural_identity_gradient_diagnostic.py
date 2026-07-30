import unittest

import numpy as np

from scripts.neural_identity_gradient_diagnostic import (
    batch_summary,
    compare_summaries,
    flatten_gradient,
    parameter_labels,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP


class IdentityGradientDiagnosticTests(unittest.TestCase):
    def test_gradient_flattening_matches_parameter_labels(self) -> None:
        model = D4EvenLocalMLP.random(
            radius=3, hidden=4, seed=201, feature_mode="multiscale"
        )
        gradient = model.gradient(
            np.ones((15, 15), dtype=np.int8)
        )
        self.assertEqual(flatten_gradient(gradient).size, len(parameter_labels(model)))

    def test_zero_batch_summary_does_not_reject_zero(self) -> None:
        batches = np.zeros((8, 3), dtype=np.float64)
        summary = batch_summary(batches, ["a", "b", "c"])
        self.assertTrue(summary["zero_not_rejected"])
        self.assertEqual(summary["maximum_absolute_z"], 0.0)

    def test_identical_summaries_are_consistent(self) -> None:
        rng = np.random.default_rng(202)
        batches = rng.normal(size=(12, 5))
        left = batch_summary(batches, [str(i) for i in range(5)])
        right = batch_summary(batches.copy(), [str(i) for i in range(5)])
        comparison = compare_summaries(left, right, [str(i) for i in range(5)])
        self.assertTrue(comparison["statistically_consistent"])
        self.assertEqual(comparison["mean_difference_l2_norm"], 0.0)


if __name__ == "__main__":
    unittest.main()
