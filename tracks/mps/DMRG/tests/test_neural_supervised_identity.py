import unittest

import numpy as np

from scripts.neural_supervised_identity import (
    extract_patches,
    features_from_patches,
    local_decomposition,
    local_hamiltonian_density,
    weighted_density_gradient,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


class SupervisedIdentityTests(unittest.TestCase):
    def test_local_decomposition_sums_to_exact_13_term_hamiltonian(self) -> None:
        length = 15
        rng = np.random.default_rng(101)
        spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length, length))
        couplings = np.linspace(-0.03, 0.07, len(EVEN_SHAPES))
        orbits, multiplicities = local_decomposition(length)
        patches = extract_patches(spins, radius=3)
        local = local_hamiltonian_density(patches, couplings, orbits, multiplicities)
        exact = float(couplings @ OperatorBasis(length, EVEN_SHAPES).values(spins))
        self.assertAlmostEqual(float(local.sum()), exact, places=11)

    def test_patch_features_match_lattice_feature_grid(self) -> None:
        length = 15
        rng = np.random.default_rng(102)
        spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length, length))
        model = D4EvenLocalMLP.random(3, 7, 103, feature_mode="multiscale")
        patches = extract_patches(spins, radius=3)
        direct = features_from_patches(model, patches)
        np.testing.assert_allclose(
            direct, model.feature_grid(spins).reshape(length * length, -1), atol=0.0
        )

    def test_weighted_gradient_matches_finite_difference(self) -> None:
        rng = np.random.default_rng(104)
        model = D4EvenLocalMLP.random(3, 5, 105, feature_mode="multiscale")
        model.weight_out[:] = rng.normal(0.0, 0.1, model.hidden)
        features = rng.normal(size=(6, model.n_features))
        weights = rng.normal(size=6)
        gradient = weighted_density_gradient(model, features, weights)
        epsilon = 1e-6
        original = float(model.weight_in[1, 2])
        model.weight_in[1, 2] = original + epsilon
        plus = float(weights @ model.density_from_features(features))
        model.weight_in[1, 2] = original - epsilon
        minus = float(weights @ model.density_from_features(features))
        model.weight_in[1, 2] = original
        numerical = (plus - minus) / (2.0 * epsilon)
        self.assertAlmostEqual(gradient.weight_in[1, 2], numerical, places=8)


if __name__ == "__main__":
    unittest.main()
