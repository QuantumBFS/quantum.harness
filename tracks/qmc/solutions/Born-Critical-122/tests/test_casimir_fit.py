import unittest

import numpy as np

from borncritical.casimir_fit import (
    design_matrix,
    fit_bootstrap_samples,
    fit_casimir,
)


class CasimirFitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sizes = np.array([6, 8, 10, 12, 16, 20, 24, 32], dtype=float)
        self.errors = np.full(self.sizes.shape, 1.0e-6)

    def test_m1_recovers_known_free_energy_casimir_coefficient(self) -> None:
        expected_c = 0.464
        values = (
            1.234
            + np.pi * expected_c / (6.0 * self.sizes**2)
            + 0.17 / self.sizes**4
        )
        result = fit_casimir(
            self.sizes,
            values,
            errors=self.errors,
            model="M1",
            quantity="phi",
        )
        self.assertAlmostEqual(result.central_charge, expected_c, delta=1e-11)
        self.assertLess(result.chi_squared, 1e-16)
        self.assertTrue(result.well_conditioned)

    def test_m1_recovers_shannon_sign(self) -> None:
        expected_c = 0.447
        values = (
            0.81
            - np.pi * expected_c / (6.0 * self.sizes**2)
            - 0.04 / self.sizes**4
        )
        result = fit_casimir(
            self.sizes,
            values,
            errors=self.errors,
            model="M1",
            quantity="shannon",
        )
        self.assertAlmostEqual(result.central_charge, expected_c, delta=1e-11)

    def test_m0_and_full_covariance_paths_agree(self) -> None:
        values = 0.7 + np.pi * 0.5 / (6.0 * self.sizes**2)
        diagonal = fit_casimir(
            self.sizes,
            values,
            errors=self.errors,
            model="M0",
            quantity="phi",
        )
        covariance = fit_casimir(
            self.sizes,
            values,
            covariance=np.diag(self.errors**2),
            model="M0",
            quantity="phi",
        )
        np.testing.assert_allclose(
            diagonal.coefficients, covariance.coefficients, atol=0.0, rtol=0.0
        )

    def test_bootstrap_failures_remain_visible(self) -> None:
        values = 0.7 + np.pi * 0.5 / (6.0 * self.sizes**2)
        samples = np.stack((values, values + 1e-7, values))
        samples[2, 3] = np.nan
        charges, failures = fit_bootstrap_samples(
            self.sizes,
            samples,
            errors=self.errors,
            model="M0",
            quantity="phi",
        )
        self.assertEqual(failures, 1)
        self.assertTrue(np.isnan(charges[2]))
        self.assertTrue(np.all(np.isfinite(charges[:2])))

    def test_invalid_fit_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            design_matrix(np.array([4.0, 4.0, 8.0]), "M0")
        with self.assertRaises(ValueError):
            fit_casimir(
                self.sizes[:2],
                np.ones(2),
                errors=np.ones(2),
                model="M0",
                quantity="phi",
            )
        with self.assertRaises(ValueError):
            fit_casimir(
                self.sizes,
                np.ones_like(self.sizes),
                errors=np.ones_like(self.sizes),
                covariance=np.eye(self.sizes.size),
                model="M0",
                quantity="phi",
            )


if __name__ == "__main__":
    unittest.main()
