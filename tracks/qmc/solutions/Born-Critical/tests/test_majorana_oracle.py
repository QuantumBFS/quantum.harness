import numpy as np
import unittest

from borncritical.majorana_oracle import (
    clifford_residual,
    majorana_mx_layer,
    majorana_mz_layer,
    majorana_operators,
    parity_operator,
    project_parity,
    spin_mx_layer,
    spin_mz_layer,
)


class MajoranaOracleTests(unittest.TestCase):
    def test_jordan_wigner_majoranas_obey_clifford_algebra(self) -> None:
        gammas = majorana_operators(3)
        self.assertLess(clifford_residual(gammas), 2e-14)

    def test_x_layer_matches_majorana_bilinears(self) -> None:
        coefficients = np.array([0.11, -0.23, 0.07])
        self.assertLess(
            np.linalg.norm(
                spin_mx_layer(coefficients) - majorana_mx_layer(coefficients)
            ),
            2e-13,
        )

    def test_periodic_zz_layer_matches_within_fixed_parity_sector(self) -> None:
        coefficients = np.array([0.13, -0.09, 0.17, 0.04])
        for parity in (-1, 1):
            with self.subTest(parity=parity):
                projector = project_parity(4, parity)
                difference = spin_mz_layer(
                    coefficients, periodic=True
                ) - majorana_mz_layer(
                    coefficients, periodic=True, parity_sector=parity
                )
                self.assertLess(
                    np.linalg.norm(projector @ difference @ projector), 3e-13
                )

    def test_periodic_majorana_layer_requires_parity_sector(self) -> None:
        with self.assertRaisesRegex(ValueError, "parity_sector"):
            majorana_mz_layer(np.array([0.1, 0.2]), periodic=True)

    def test_parity_projectors_are_complete_and_orthogonal(self) -> None:
        identity = np.eye(8, dtype=np.complex128)
        even = project_parity(3, 1)
        odd = project_parity(3, -1)
        self.assertLess(np.linalg.norm(even + odd - identity), 1e-14)
        self.assertLess(np.linalg.norm(even @ odd), 1e-14)
        self.assertLess(np.linalg.norm(parity_operator(3) @ even - even), 1e-14)


if __name__ == "__main__":
    unittest.main()
