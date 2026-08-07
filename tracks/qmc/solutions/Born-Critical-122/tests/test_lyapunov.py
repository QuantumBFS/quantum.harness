import unittest

import numpy as np

from borncritical.lyapunov import LyapunovQR
from borncritical.rng import StreamKey, make_rng


def random_near_identity_sequence(count: int, dimension: int) -> list[np.ndarray]:
    rng = make_rng(StreamKey(20260727, "kernel", dimension, 0, "matrices"))
    return [
        np.eye(dimension) + 0.01 * rng.normal(size=(dimension, dimension))
        for _ in range(count)
    ]


class LyapunovTests(unittest.TestCase):
    def test_qr_intervals_one_two_five_are_consistent(self) -> None:
        matrices = random_near_identity_sequence(500, 4)
        results = {}
        for interval in (1, 2, 5):
            product = LyapunovQR(4, interval)
            for matrix in matrices:
                product.push(matrix)
            results[interval] = product.finalize()
            self.assertLess(product.max_orthogonality_error, 1e-12)
        np.testing.assert_allclose(results[1], results[2], atol=5e-12, rtol=0)
        np.testing.assert_allclose(results[1], results[5], atol=5e-12, rtol=0)

    def test_one_hundred_thousand_layer_smoke_is_finite(self) -> None:
        matrices = random_near_identity_sequence(17, 2)
        product = LyapunovQR(2, 5)
        for index in range(100_000):
            product.push(matrices[index % len(matrices)])
        exponents = product.finalize()
        self.assertTrue(np.all(np.isfinite(exponents)))
        self.assertEqual(product.layer_count, 100_000)
        self.assertLess(product.max_orthogonality_error, 1e-10)

    def test_positive_diagonal_convention_is_interval_independent(self) -> None:
        matrices = [
            np.array([[-2.0, 0.2], [0.1, 0.5]]),
            np.array([[0.7, -0.3], [0.2, -1.4]]),
        ]
        once = LyapunovQR(2, 1)
        grouped = LyapunovQR(2, 2)
        for matrix in matrices:
            once.push(matrix)
            grouped.push(matrix)
        np.testing.assert_allclose(once.finalize(), grouped.finalize(), atol=1e-14)

    def test_complex_transfer_matrices_are_supported(self) -> None:
        product = LyapunovQR(2, 2, complex_valued=True)
        matrix = np.array(
            [[1.0 + 0.1j, 0.03], [0.02j, 0.9 - 0.05j]],
            dtype=np.complex128,
        )
        for _ in range(6):
            product.push(matrix)
        self.assertTrue(np.all(np.isfinite(product.finalize())))
        self.assertLess(product.max_orthogonality_error, 1e-12)

    def test_singular_and_nonfinite_transfers_fail_hard(self) -> None:
        product = LyapunovQR(2, 1)
        with self.assertRaises(np.linalg.LinAlgError):
            product.push(np.zeros((2, 2)))
        with self.assertRaises(ValueError):
            LyapunovQR(2, 1).push(np.array([[1.0, np.nan], [0.0, 1.0]]))


if __name__ == "__main__":
    unittest.main()
