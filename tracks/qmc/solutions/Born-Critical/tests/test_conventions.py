import math
import unittest

from borncritical.conventions import (
    CLEAN_ISING_C,
    ISING_K_CRITICAL,
    NISHIMORI_C_TARGET,
    NISHIMORI_PC,
    SELFDUAL_C_TARGET,
    SELFDUAL_THETA,
    honecker_beta,
    nishimori_coupling,
    selfdual_couplings,
)


class ConventionTests(unittest.TestCase):
    def test_frozen_numerical_targets(self) -> None:
        self.assertEqual(CLEAN_ISING_C, 0.5)
        self.assertEqual(NISHIMORI_PC, 0.1092212)
        self.assertEqual(NISHIMORI_C_TARGET, 0.464)
        self.assertEqual(SELFDUAL_C_TARGET, 0.447)

    def test_clean_and_selfdual_coupling_conventions(self) -> None:
        beta, beta_prime = selfdual_couplings(SELFDUAL_THETA)
        expected_beta = math.log1p(math.sqrt(2.0))
        self.assertAlmostEqual(ISING_K_CRITICAL, 0.5 * expected_beta)
        self.assertAlmostEqual(beta, expected_beta)
        self.assertAlmostEqual(beta_prime, expected_beta)

    def test_nishimori_normalization_and_honecker_factor_of_two(self) -> None:
        coupling = nishimori_coupling(NISHIMORI_PC)
        self.assertAlmostEqual(
            math.exp(-2.0 * coupling),
            NISHIMORI_PC / (1.0 - NISHIMORI_PC),
        )
        self.assertAlmostEqual(honecker_beta(NISHIMORI_PC), 2.0 * coupling)

    def test_nishimori_rejects_out_of_branch_probabilities(self) -> None:
        for bad_p in (-0.1, 0.0, 0.5, 0.75, 1.0):
            with self.subTest(p=bad_p):
                with self.assertRaisesRegex(ValueError, "0 < p < 0.5"):
                    nishimori_coupling(bad_p)

    def test_selfdual_couplings_reject_singular_angles(self) -> None:
        for bad_theta in (-0.1, 0.0, math.pi / 2, 2.0):
            with self.subTest(theta=bad_theta):
                with self.assertRaisesRegex(ValueError, "0 < theta < pi/2"):
                    selfdual_couplings(bad_theta)


if __name__ == "__main__":
    unittest.main()
