import math
import unittest

import numpy as np

from borncritical.born_circuit_oracle import enumerate_circuit_distribution
from borncritical.gaussian_born import (
    GaussianBornCircuit,
    MajoranaTransferQR,
    apply_branch,
    branch_probability,
    plus_state_correlator,
    purity_residual,
    vortex_indicators,
)


class GaussianBornTests(unittest.TestCase):
    def test_each_branch_is_normalized_and_preserves_purity(self) -> None:
        state = plus_state_correlator(4)
        for outcome in (-1, 1):
            probability = branch_probability(state, 1, 2, outcome, 0.7)
            updated, log_probability, _ = apply_branch(
                state, 1, 2, outcome, 0.7
            )
            self.assertAlmostEqual(probability, math.exp(log_probability))
            self.assertLess(purity_residual(updated), 2e-12)
        self.assertAlmostEqual(
            branch_probability(state, 1, 2, -1, 0.7)
            + branch_probability(state, 1, 2, 1, 0.7),
            1.0,
        )

    def test_gaussian_full_distribution_matches_dense_spin_oracle(self) -> None:
        outcomes = enumerate_circuit_distribution(
            size=2, layers=2, max_variables=8
        )
        total_variation = 0.5 * sum(
            abs(item.probability - item.gaussian_probability)
            for item in outcomes
        )
        self.assertLess(total_variation, 1e-11)
        self.assertAlmostEqual(
            sum(item.probability for item in outcomes), 1.0, delta=2e-14
        )

    def test_vacuum_enumeration_forbids_negative_wilson_loop(self) -> None:
        outcomes = enumerate_circuit_distribution(
            size=4, layers=1, vacuum_only=True, max_variables=8
        )
        self.assertTrue(all(sum(item.bits[:4]) % 2 == 0 for item in outcomes))
        total_variation = 0.5 * sum(
            abs(item.probability - item.gaussian_probability)
            for item in outcomes
        )
        self.assertLess(total_variation, 1e-11)

    def test_vortex_observables_are_kinks_not_negative_gate_density(self) -> None:
        previous_s = np.array([1, 1, -1, -1], dtype=np.int8)
        current_s = np.array([1, -1, -1, 1], dtype=np.int8)
        previous_t = np.array([1, -1, -1, 1], dtype=np.int8)
        current_t = np.array([-1, -1, 1, 1], dtype=np.int8)
        e, m = vortex_indicators(
            previous_s, current_s, previous_t, current_t
        )
        np.testing.assert_array_equal(e, [True, False, True, False])
        np.testing.assert_array_equal(m, [False, True, False, True])

    def test_sampled_layers_keep_probability_diagnostics_finite(self) -> None:
        circuit = GaussianBornCircuit(size=4)
        rng = np.random.default_rng(20260728)
        for _ in range(20):
            layer = circuit.sample_layer(rng)
            self.assertLessEqual(layer.max_probability_normalization_error, 1e-15)
            self.assertLess(layer.purity_residual, 2e-10)
            self.assertTrue(math.isfinite(layer.log_probability))
            self.assertTrue(math.isfinite(layer.log_norm))

    def test_majorana_qr_is_finite_and_particle_hole_symmetric(self) -> None:
        transfer = MajoranaTransferQR(size=4, qr_interval=3)
        rng = np.random.default_rng(17)
        for layer in range(12):
            for site in range(4):
                transfer.apply_gate(2 * site, 2 * site + 1, 1, 0.4)
            transfer.finish_layer()
        exponents = transfer.exponents(12)
        self.assertTrue(np.all(np.isfinite(exponents)))
        np.testing.assert_allclose(exponents, -exponents[::-1], atol=2e-13)
        self.assertLess(transfer.maximum_orthogonality_error, 2e-14)


if __name__ == "__main__":
    unittest.main()
