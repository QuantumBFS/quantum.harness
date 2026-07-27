from __future__ import annotations

import sys
import unittest
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np

SOLUTION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION_DIR))

from landscapes import (  # noqa: E402
    hessian_vector_product,
    krylov_hessian_eigensystem,
    projection_fraction,
    random_subspace,
    subspace_metrics,
    traceless_hermitian_basis,
)


class LandscapeTests(unittest.TestCase):
    def test_generalized_gell_mann_basis(self) -> None:
        basis = np.asarray(traceless_hermitian_basis(4))
        self.assertEqual(basis.shape, (15, 4, 4))
        gram = np.einsum("aij,bij->ab", basis.conj(), basis)
        np.testing.assert_allclose(gram, np.eye(15), atol=1e-13)
        np.testing.assert_allclose(
            np.trace(basis, axis1=1, axis2=2), 0.0, atol=1e-13
        )

    def test_hvp_matches_explicit_quadratic_hessian(self) -> None:
        matrix = jnp.asarray([[3.0, 1.0], [1.0, 2.0]])
        loss = lambda x: 0.5 * x @ matrix @ x
        point = jnp.asarray([0.4, -0.2])
        vector = jnp.asarray([0.3, 0.7])
        np.testing.assert_allclose(
            hessian_vector_product(loss, point, vector),
            matrix @ vector,
            atol=1e-13,
        )

    def test_krylov_eigenpairs_match_quadratic_hessian(self) -> None:
        matrix = jnp.diag(jnp.asarray([5.0, 3.0, 1.0, 0.2]))
        loss = lambda x: 0.5 * x @ matrix @ x
        eigenvalues, eigenvectors = krylov_hessian_eigensystem(
            loss,
            jnp.zeros(4),
            2,
            tolerance=1e-12,
        )
        np.testing.assert_allclose(eigenvalues, [5.0, 3.0], atol=1e-10)
        projected = np.asarray(eigenvectors).T @ np.asarray(matrix)
        reconstructed = np.diag(eigenvalues) @ np.asarray(eigenvectors).T
        np.testing.assert_allclose(projected, reconstructed, atol=1e-10)

    def test_subspace_metrics_and_projection(self) -> None:
        basis = random_subspace(8, 3, seed=5)
        metrics = subspace_metrics(basis, basis)
        self.assertAlmostEqual(metrics.mean_overlap, 1.0, places=12)
        self.assertAlmostEqual(metrics.minimum_overlap, 1.0, places=12)
        self.assertAlmostEqual(metrics.largest_angle_degrees, 0.0, places=5)
        vector = basis[:, 0] + 2.0 * basis[:, 1]
        self.assertAlmostEqual(projection_fraction(vector, basis), 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
