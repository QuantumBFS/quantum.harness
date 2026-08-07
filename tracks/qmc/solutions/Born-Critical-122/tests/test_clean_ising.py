import math
import unittest

import numpy as np

from borncritical.clean_ising import (
    CRITICAL_PHI_INFINITY,
    critical_log_dominant_eigenvalue,
    critical_phi,
    direct_torus_log_partition,
    explicit_dominant_eigenpair,
    symmetric_transfer_matrix,
    transfer_torus_log_partition,
)


class CleanIsingTests(unittest.TestCase):
    def test_symmetric_transfer_is_positive_and_symmetric(self) -> None:
        transfer = symmetric_transfer_matrix(4)
        self.assertEqual(transfer.shape, (16, 16))
        self.assertTrue(np.all(transfer > 0.0))
        np.testing.assert_array_equal(transfer, transfer.T)

    def test_explicit_perron_root_matches_critical_dispersion(self) -> None:
        for circumference in (2, 4, 6):
            with self.subTest(circumference=circumference):
                explicit = explicit_dominant_eigenpair(circumference)
                analytic = critical_log_dominant_eigenvalue(circumference)
                self.assertAlmostEqual(
                    explicit.log_eigenvalue, analytic, delta=2.0e-12
                )
                self.assertLess(explicit.relative_residual, 3.0e-14)

    def test_direct_torus_sum_matches_trace_of_transfer_power(self) -> None:
        direct = direct_torus_log_partition(3, 3)
        transfer = transfer_torus_log_partition(3, 3)
        self.assertAlmostEqual(direct, transfer, delta=2.0e-12)

    def test_critical_phi_approaches_exact_limit_from_above(self) -> None:
        values = [critical_phi(size) for size in (8, 16, 32, 64)]
        self.assertTrue(all(value > CRITICAL_PHI_INFINITY for value in values))
        self.assertTrue(all(a > b for a, b in zip(values, values[1:])))
        leading = [
            (value - CRITICAL_PHI_INFINITY) * size**2
            for value, size in zip(values, (8, 16, 32, 64))
        ]
        self.assertAlmostEqual(leading[-1], math.pi / 12.0, delta=2.0e-4)

    def test_frozen_formula_rejects_odd_circumference(self) -> None:
        with self.assertRaises(ValueError):
            critical_log_dominant_eigenvalue(5)


if __name__ == "__main__":
    unittest.main()
