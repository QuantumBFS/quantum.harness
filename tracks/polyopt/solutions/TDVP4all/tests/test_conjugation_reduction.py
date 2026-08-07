from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import GaussianRational, PauliWord  # noqa: E402
from challenge233.sdp.kyfan import (  # noqa: E402
    ComplexLinearForm,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    SparseComplexEntry,
    build_global_kyfan_structure,
)
from challenge233.sdp.conjugation_reduction import (  # noqa: E402
    ConjugationReduction,
    build_conjugation_reduction,
    verify_conjugation_reduction,
    word_y_parity,
)


class ConjugationReductionTests(unittest.TestCase):
    def setUp(self):
        self.structure = build_global_kyfan_structure(
            4,
            2,
            "sound",
        )

    def test_word_y_parity_uses_only_number_of_y_factors(self):
        self.assertEqual(word_y_parity(PauliWord()), 0)
        self.assertEqual(
            word_y_parity(
                PauliWord(((0, "X"), (1, "Y"), (3, "Z")))
            ),
            1,
        )
        self.assertEqual(
            word_y_parity(PauliWord(((0, "Y"), (2, "Y")))),
            0,
        )

    def test_phase_gauge_is_real_without_doubling_dimension(self):
        reduction = build_conjugation_reduction(self.structure)

        self.assertEqual(
            [block.dimension for block in reduction.real_blocks],
            [block.dimension for block in self.structure.psd_blocks],
        )
        self.assertTrue(
            all(
                isinstance(entry.form, RationalLinearForm)
                for block in reduction.real_blocks
                for entry in block.upper_entries
            )
        )

    def test_phases_match_hand_checked_x_y_basis_words(self):
        reduction = build_conjugation_reduction(self.structure)
        x_index = self.structure.moment_basis.index(
            PauliWord(((0, "X"),))
        )
        y_index = self.structure.moment_basis.index(
            PauliWord(((0, "Y"),))
        )
        yy_index = self.structure.moment_basis.index(
            PauliWord(((0, "Y"), (1, "Y")))
        )

        self.assertEqual(reduction.phases[x_index], 0)
        self.assertEqual(reduction.phases[y_index], 1)
        self.assertEqual(reduction.phases[yy_index], 0)

    def test_every_odd_y_variable_has_an_exact_zero_row(self):
        reduction = build_conjugation_reduction(self.structure)
        expected = {
            variable.index
            for variable in self.structure.variables
            if sum(
                label == "Y"
                for _, label in variable.representative.factors
            )
            % 2
        }

        self.assertEqual(set(reduction.odd_variables), expected)
        self.assertEqual(
            {
                row.identifier: row.form
                for row in reduction.odd_equalities
            },
            {
                f"conjugation-odd-y-{index}": RationalLinearForm(
                    terms=((index, Fraction(1)),)
                )
                for index in expected
            },
        )

    def test_inverse_phase_round_trip_is_exact_modulo_odd_rows(self):
        reduction = build_conjugation_reduction(self.structure)

        summary = verify_conjugation_reduction(
            self.structure,
            reduction,
        )

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(
            summary["checked_block_count"],
            len(self.structure.psd_blocks),
        )

    def test_verifier_rejects_mutated_phase_inventory(self):
        reduction = build_conjugation_reduction(self.structure)
        phases = list(reduction.phases)
        phases[0] = 1 - phases[0]

        with self.assertRaisesRegex(ValueError, "phase inventory"):
            verify_conjugation_reduction(
                self.structure,
                replace(reduction, phases=tuple(phases)),
            )

    def test_verifier_rejects_missing_odd_variable(self):
        reduction = build_conjugation_reduction(self.structure)

        with self.assertRaisesRegex(
            ValueError,
            "odd-Y variable inventory",
        ):
            verify_conjugation_reduction(
                self.structure,
                replace(
                    reduction,
                    odd_variables=reduction.odd_variables[1:],
                ),
            )

    def test_builder_rejects_imaginary_coefficient_after_gauge(self):
        gamma = self.structure.psd_blocks[0]
        entry = gamma.upper_entries[0]
        corrupted_entry = SparseComplexEntry(
            row=entry.row,
            column=entry.column,
            form=entry.form
            + ComplexLinearForm(
                imag=RationalLinearForm(
                    terms=((0, Fraction(1)),)
                )
            ),
        )
        corrupted_gamma = replace(
            gamma,
            upper_entries=(
                corrupted_entry,
                *gamma.upper_entries[1:],
            ),
        )
        corrupted_structure = replace(
            self.structure,
            psd_blocks=(
                corrupted_gamma,
                self.structure.psd_blocks[1],
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "did not produce a real entry",
        ):
            build_conjugation_reduction(corrupted_structure)


class ConjugationReductionPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_conjugation_reduction_boundary(self):
        from challenge233.sdp import (
            ConjugationReduction as ExportedReduction,
            build_conjugation_reduction as exported_builder,
            verify_conjugation_reduction as exported_verifier,
            word_y_parity as exported_parity,
        )

        self.assertIs(ExportedReduction, ConjugationReduction)
        self.assertIs(exported_builder, build_conjugation_reduction)
        self.assertIs(
            exported_verifier,
            verify_conjugation_reduction,
        )
        self.assertIs(exported_parity, word_y_parity)


if __name__ == "__main__":
    unittest.main()
