from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    NEG_ONE,
    ONE,
)
from challenge233.sdp.exact_linalg import (  # noqa: E402
    ExactColumnBasis,
    ExactRowBasis,
    gaussian_column_basis,
    primitive_integer_row,
    rational_row_basis,
    verify_column_reconstruction,
    verify_row_reconstruction,
)


class PrimitiveIntegerRowTests(unittest.TestCase):
    def test_signed_scale_reconstructs_original_rational_row(self):
        values = (
            Fraction(-1, 2),
            Fraction(1, 3),
            Fraction(0),
        )

        primitive, scale = primitive_integer_row(values)

        self.assertEqual(primitive, (3, -2, 0))
        self.assertEqual(scale, Fraction(-1, 6))
        self.assertEqual(
            values,
            tuple(scale * entry for entry in primitive),
        )

    def test_zero_row_has_unit_scale(self):
        self.assertEqual(
            primitive_integer_row((Fraction(0), Fraction(0))),
            ((0, 0), Fraction(1)),
        )


class GaussianColumnBasisTests(unittest.TestCase):
    def test_every_original_column_is_reconstructed_exactly(self):
        imag = GaussianRational(Fraction(0), Fraction(1))
        columns = (
            {0: ONE},
            {1: imag},
            {0: ONE, 1: imag},
        )

        result = gaussian_column_basis(columns)

        self.assertEqual(result.selected, (0, 1))
        self.assertEqual(
            result.reconstruction,
            (
                ((0, ONE),),
                ((1, ONE),),
                ((0, ONE), (1, ONE)),
            ),
        )
        self.assertEqual(
            result.kernel,
            (((0, NEG_ONE), (1, NEG_ONE), (2, ONE)),),
        )
        self.assertEqual(result.pivots, (0, 1))
        verify_column_reconstruction(columns, result)

    def test_mutated_reconstruction_is_rejected(self):
        columns = ({0: ONE}, {0: ONE})
        result = gaussian_column_basis(columns)
        mutated = replace(
            result,
            reconstruction=(
                result.reconstruction[0],
                ((0, NEG_ONE),),
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "column reconstruction",
        ):
            verify_column_reconstruction(columns, mutated)

    def test_pivots_remain_parallel_to_selected_columns(self):
        result = gaussian_column_basis(({5: ONE}, {2: ONE}))

        self.assertEqual(result.selected, (0, 1))
        self.assertEqual(result.pivots, (5, 2))


class RationalRowBasisTests(unittest.TestCase):
    def test_proportional_row_recovers_signed_rational_multiplier(self):
        rows = (
            (Fraction(1, 2), Fraction(1, 3)),
            (Fraction(-7, 10), Fraction(-7, 15)),
        )

        result = rational_row_basis(rows)

        self.assertEqual(result.selected, (0,))
        self.assertEqual(result.pivot_columns, (0,))
        self.assertEqual(
            result.reconstruction,
            (
                ((0, Fraction(1)),),
                ((0, Fraction(-7, 5)),),
            ),
        )
        self.assertEqual(result.primitive_rows, ((3, 2), (3, 2)))
        verify_row_reconstruction(rows, result)

    def test_bad_modular_hint_falls_back_to_exact_stable_order(self):
        rows = (
            (Fraction(1, 2), Fraction(1)),
            (Fraction(0), Fraction(1)),
        )

        result = rational_row_basis(rows, modular_primes=(2,))

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.selected, (0, 1))
        verify_row_reconstruction(rows, result)

    def test_inconsistent_affine_row_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "inconsistent-equality-system",
        ):
            rational_row_basis(((Fraction(1), Fraction(0), Fraction(0)),))

    def test_mutated_row_reconstruction_is_rejected(self):
        rows = (
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(2), Fraction(0)),
        )
        result = rational_row_basis(rows)
        mutated = replace(
            result,
            reconstruction=(
                result.reconstruction[0],
                ((0, Fraction(3)),),
            ),
        )

        with self.assertRaisesRegex(ValueError, "row reconstruction"):
            verify_row_reconstruction(rows, mutated)

    def test_pivots_remain_parallel_to_selected_rows(self):
        rows = (
            (Fraction(0), Fraction(0), Fraction(1)),
            (Fraction(0), Fraction(1), Fraction(0)),
        )

        result = rational_row_basis(rows)

        self.assertEqual(result.selected, (0, 1))
        self.assertEqual(result.pivot_columns, (2, 1))

    def test_good_modular_hint_avoids_full_exact_selection_prepass(self):
        rows = tuple(
            (
                Fraction(0),
                Fraction(index == 0),
                Fraction(index == 1),
            )
            for index in range(2)
        )

        with patch(
            "challenge233.sdp.exact_linalg._select_exact_rows",
            side_effect=AssertionError("unexpected exact prepass"),
        ):
            result = rational_row_basis(
                rows,
                modular_primes=(2305843009213693951,),
            )

        self.assertFalse(result.used_fallback)
        self.assertEqual(result.selected, (0, 1))
        verify_row_reconstruction(rows, result)


class ExactLinalgPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_stable_exact_reduction_types(self):
        from challenge233.sdp import (
            ExactColumnBasis as ExportedColumnBasis,
            ExactRowBasis as ExportedRowBasis,
            gaussian_column_basis as exported_column_basis,
            primitive_integer_row as exported_primitive_row,
            rational_row_basis as exported_row_basis,
        )

        self.assertIs(ExportedColumnBasis, ExactColumnBasis)
        self.assertIs(ExportedRowBasis, ExactRowBasis)
        self.assertIs(exported_column_basis, gaussian_column_basis)
        self.assertIs(exported_primitive_row, primitive_integer_row)
        self.assertIs(exported_row_basis, rational_row_basis)


if __name__ == "__main__":
    unittest.main()
