import unittest

import numpy as np

from borncritical.conventions import ISING_K_CRITICAL, NISHIMORI_PC, nishimori_coupling
from borncritical.exact import BondFields, row_transfer_amplitude
from borncritical.rbim import (
    fermionic_log_partition,
    free_boundary_state,
    simulate_rbim_replica,
)


class RBIMTransferTests(unittest.TestCase):
    def test_free_boundary_state_has_expected_gram_matrix(self) -> None:
        state = free_boundary_state(4)
        np.testing.assert_allclose(state.T @ state, 4.0 * np.eye(4))

    def test_finite_fermionic_partition_matches_spin_transfer(self) -> None:
        vertical = np.array(
            [
                [1, 1, -1, 1],
                [1, -1, 1, 1],
                [-1, 1, 1, 1],
                [1, 1, 1, -1],
            ],
            dtype=np.int8,
        )
        horizontal = np.array(
            [
                [1, -1, 1, 1],
                [1, 1, -1, 1],
                [-1, 1, 1, 1],
            ],
            dtype=np.int8,
        )
        fields = BondFields(
            s_horizontal=vertical,
            s_vertical=horizontal,
        )
        sign, exact_log = row_transfer_amplitude(
            fields, nishimori_coupling(NISHIMORI_PC)
        )
        fermionic_log, error = fermionic_log_partition(
            vertical,
            horizontal,
            nishimori_coupling(NISHIMORI_PC),
            qr_interval=1,
        )
        self.assertEqual(sign, 1)
        self.assertAlmostEqual(fermionic_log, exact_log, delta=2.0e-11)
        self.assertLess(error, 1.0e-12)

    def test_qr_interval_does_not_change_finite_partition(self) -> None:
        rng = np.random.default_rng(7182818)
        vertical = rng.choice((-1, 1), size=(10, 6)).astype(np.int8)
        horizontal = rng.choice((-1, 1), size=(9, 6)).astype(np.int8)
        reference, _ = fermionic_log_partition(
            vertical, horizontal, nishimori_coupling(NISHIMORI_PC), qr_interval=1
        )
        candidate, _ = fermionic_log_partition(
            vertical, horizontal, nishimori_coupling(NISHIMORI_PC), qr_interval=5
        )
        self.assertAlmostEqual(reference, candidate, delta=2.0e-11)

    def test_keyed_replica_is_reproducible_and_block_complete(self) -> None:
        settings = dict(
            size=4,
            replica=3,
            p=0.0,
            coupling=ISING_K_CRITICAL,
            base_seed=20260727,
            qr_interval=2,
            burn_in_rows=80,
            measurement_rows=1024,
            block_size=256,
        )
        first = simulate_rbim_replica(**settings)
        second = simulate_rbim_replica(**settings)
        np.testing.assert_array_equal(first.block_phi, second.block_phi)
        self.assertEqual(first.block_phi.size, 4)
        self.assertTrue(np.all(np.isfinite(first.block_phi)))
        self.assertLess(first.maximum_orthogonality_error, 1.0e-12)


if __name__ == "__main__":
    unittest.main()
