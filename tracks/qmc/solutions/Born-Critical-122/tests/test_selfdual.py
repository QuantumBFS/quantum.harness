import math
import unittest

from borncritical.selfdual import run_selfdual_trajectory


class SelfDualTrajectoryTests(unittest.TestCase):
    def test_short_trajectory_has_finite_block_diagnostics(self) -> None:
        result = run_selfdual_trajectory(
            size=4,
            replica=0,
            seed=20260728,
            burnin_rows=8,
            measurement_rows=32,
            block_rows=8,
            qr_interval=2,
        )
        self.assertEqual(len(result.blocks), 4)
        self.assertLessEqual(result.maximum_probability_normalization_error, 1e-15)
        self.assertLess(result.maximum_covariance_purity_residual, 2e-9)
        self.assertLess(result.maximum_qr_orthogonality_error, 2e-14)
        for block in result.blocks:
            self.assertEqual(block.spacetime_sublayers, 2 * block.rows)
            self.assertTrue(math.isfinite(block.shannon_rate))
            self.assertTrue(math.isfinite(block.rao_blackwell_shannon_rate))
            self.assertTrue(0.0 <= block.e_density <= 1.0)
            self.assertTrue(0.0 <= block.m_density <= 1.0)


if __name__ == "__main__":
    unittest.main()
