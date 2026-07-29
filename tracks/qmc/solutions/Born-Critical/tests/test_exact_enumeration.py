import math
import unittest

import numpy as np

from borncritical.conventions import ISING_K_CRITICAL, NISHIMORI_PC, nishimori_coupling
from borncritical.exact import (
    BondFields,
    direct_amplitude,
    gauge_transform,
    row_transfer_amplitude,
)


class ExactEnumerationTests(unittest.TestCase):
    def assert_same_signed_log(
        self,
        left: tuple[int, float],
        right: tuple[int, float],
        tolerance: float = 2e-12,
    ) -> None:
        self.assertEqual(left[0], right[0])
        self.assertAlmostEqual(left[1], right[1], delta=tolerance)

    def test_clean_zero_coupling_counts_all_spin_states(self) -> None:
        fields = BondFields.clean(nx=3, ny=2)
        sign, log_abs = direct_amplitude(fields, coupling=0.0)
        self.assertEqual(sign, 1)
        self.assertAlmostEqual(
            log_abs, 6.0 * math.log(2.0), delta=2e-12
        )

    def test_clean_direct_sum_matches_row_transfer_matrix(self) -> None:
        fields = BondFields.clean(nx=3, ny=2)
        direct = direct_amplitude(fields, coupling=ISING_K_CRITICAL)
        transfer = row_transfer_amplitude(fields, coupling=ISING_K_CRITICAL)
        self.assert_same_signed_log(direct, transfer)

    def test_signed_selfdual_amplitude_matches_row_transfer_matrix(self) -> None:
        fields = BondFields(
            s_horizontal=np.array([[1, -1, 1], [-1, 1, 1]], dtype=np.int8),
            s_vertical=np.array([[1, -1, -1]], dtype=np.int8),
            t_horizontal=np.array([[-1, 1, 1], [1, -1, 1]], dtype=np.int8),
            t_vertical=np.array([[1, -1, 1]], dtype=np.int8),
        )
        direct = direct_amplitude(fields, coupling=ISING_K_CRITICAL)
        transfer = row_transfer_amplitude(fields, coupling=ISING_K_CRITICAL)
        self.assert_same_signed_log(direct, transfer, tolerance=2e-11)

    def test_rbim_partition_function_is_gauge_invariant(self) -> None:
        fields = BondFields(
            s_horizontal=np.array([[1, -1, 1], [-1, 1, 1]], dtype=np.int8),
            s_vertical=np.array([[1, -1, -1]], dtype=np.int8),
        )
        site_gauge = np.array([[1, -1, 1], [-1, -1, 1]], dtype=np.int8)
        transformed = gauge_transform(fields, site_gauge)
        self.assert_same_signed_log(
            direct_amplitude(fields, nishimori_coupling(NISHIMORI_PC)),
            direct_amplitude(transformed, nishimori_coupling(NISHIMORI_PC)),
        )

    def test_nishimori_weight_ratio_agrees_with_honecker_convention(self) -> None:
        coupling = nishimori_coupling(NISHIMORI_PC)
        standard_ratio = math.exp(2.0 * coupling)
        honecker_ratio = (1.0 - NISHIMORI_PC) / NISHIMORI_PC
        self.assertAlmostEqual(standard_ratio, honecker_ratio)

    def test_bond_fields_reject_non_binary_values(self) -> None:
        with self.assertRaisesRegex(ValueError, r"must contain only \+1 or -1"):
            BondFields(
                s_horizontal=np.array([[1, 0, 1]], dtype=np.int8),
                s_vertical=np.empty((0, 3), dtype=np.int8),
            )


if __name__ == "__main__":
    unittest.main()
