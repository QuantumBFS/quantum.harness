import math
import unittest

import numpy as np

from borncritical.blocking import StreamingBlockAccumulator


class BlockingTests(unittest.TestCase):
    def test_batch_matches_manual_block_means(self) -> None:
        values = np.arange(24, dtype=np.float64).reshape(12, 2)
        blocks = StreamingBlockAccumulator(block_size=3, n_observables=2)
        blocks.add_batch(values)
        expected = values.reshape(4, 3, 2).mean(axis=1)
        np.testing.assert_allclose(blocks.completed_blocks, expected)
        self.assertEqual(blocks.n_total_samples, 12)
        self.assertEqual(blocks.n_complete_samples, 12)

    def test_partial_block_is_not_used_in_summary(self) -> None:
        blocks = StreamingBlockAccumulator(block_size=2, n_observables=1)
        blocks.add_batch(np.array([[1.0], [3.0], [1000.0]]))
        blocks.add_batch(np.array([[5.0], [7.0]]))
        summary = blocks.summary()
        expected_block_means = np.array([2.0, 502.5])
        self.assertAlmostEqual(summary.mean[0], expected_block_means.mean())
        self.assertEqual(summary.n_complete_samples, 4)
        self.assertEqual(summary.n_total_samples, 5)
        self.assertEqual(blocks.current_count, 1)

    def test_standard_error_comes_from_complete_blocks(self) -> None:
        blocks = StreamingBlockAccumulator(block_size=2, n_observables=1)
        blocks.add_batch(np.array([[0.0], [2.0], [2.0], [4.0]]))
        summary = blocks.summary()
        self.assertAlmostEqual(summary.mean[0], 2.0)
        self.assertAlmostEqual(summary.standard_deviation[0], math.sqrt(2.0))
        self.assertAlmostEqual(summary.standard_error[0], 1.0)

    def test_export_restore_preserves_partial_and_complete_state(self) -> None:
        blocks = StreamingBlockAccumulator(block_size=4, n_observables=2)
        blocks.add_batch(np.arange(18, dtype=np.float64).reshape(9, 2))
        metadata, arrays = blocks.export_state()
        restored = StreamingBlockAccumulator.from_state(
            metadata, arrays["current_sum"], arrays["completed_blocks"]
        )
        restored.add_batch(np.array([[18.0, 19.0], [20.0, 21.0], [22.0, 23.0]]))
        blocks.add_batch(np.array([[18.0, 19.0], [20.0, 21.0], [22.0, 23.0]]))
        np.testing.assert_array_equal(
            restored.completed_blocks, blocks.completed_blocks
        )
        np.testing.assert_array_equal(restored.current_sum, blocks.current_sum)

    def test_invalid_or_nonfinite_observations_are_rejected(self) -> None:
        blocks = StreamingBlockAccumulator(block_size=2, n_observables=2)
        with self.assertRaises(ValueError):
            blocks.add([1.0])
        with self.assertRaises(ValueError):
            blocks.add([1.0, np.nan])
        with self.assertRaises(ValueError):
            blocks.add_batch(np.array([[1.0, np.inf]]))
        with self.assertRaises(RuntimeError):
            blocks.summary()


if __name__ == "__main__":
    unittest.main()
