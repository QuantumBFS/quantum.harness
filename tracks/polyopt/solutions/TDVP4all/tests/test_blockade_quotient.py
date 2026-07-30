from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    GaussianRational,
    ONE,
    PauliWord,
)
from challenge233.sdp.blockade_quotient import (  # noqa: E402
    BlockadeQuotient,
    build_blockade_quotient,
    exact_ldlt_pivots,
    kernel_localizer_rows,
    literal_pauli_action,
    slater_gram,
    verify_blockade_quotient,
)
from challenge233.sdp.hierarchy import (  # noqa: E402
    LOCAL_LEVELS,
    global_pauli_basis,
    local_pauli_basis,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
)


class LiteralPauliActionTests(unittest.TestCase):
    def test_y_action_matches_y_equals_i_x_z(self):
        output, phase = literal_pauli_action(
            PauliWord(((0, "Y"),)),
            0,
            (0,),
        )

        self.assertEqual(output, 1)
        self.assertEqual(
            phase,
            GaussianRational(Fraction(0), Fraction(-1)),
        )

    def test_x_y_z_actions_use_down_up_bit_convention(self):
        cases = (
            ("X", 0, 1, GaussianRational(Fraction(1))),
            ("X", 1, 0, GaussianRational(Fraction(1))),
            ("Y", 1, 0, GaussianRational(Fraction(0), Fraction(1))),
            ("Z", 0, 0, GaussianRational(Fraction(-1))),
            ("Z", 1, 1, GaussianRational(Fraction(1))),
        )
        for label, input_state, output, phase in cases:
            with self.subTest(label=label, input=input_state):
                self.assertEqual(
                    literal_pauli_action(
                        PauliWord(((3, label),)),
                        input_state,
                        (3,),
                    ),
                    (output, phase),
                )

    def test_action_rejects_word_outside_declared_sites(self):
        with self.assertRaisesRegex(ValueError, "declared sites"):
            literal_pauli_action(
                PauliWord(((2, "X"),)),
                0,
                (0, 1),
            )


class BlockadeQuotientTests(unittest.TestCase):
    def test_global_domain_uses_periodic_inputs_and_all_outputs(self):
        basis = global_pauli_basis(4, 1)
        quotient = build_blockade_quotient(4, basis)

        self.assertEqual(quotient.scope, "global")
        self.assertEqual(quotient.legal_inputs, (0, 1, 2, 4, 5, 8, 10))
        self.assertNotIn(9, quotient.legal_inputs)
        self.assertEqual(quotient.output_count, 16)

    def test_local_domain_is_open_blockaded_but_outputs_are_unrestricted(self):
        basis = local_pauli_basis(20, 0, LOCAL_LEVELS[0])
        quotient = build_blockade_quotient(
            20,
            basis,
            window_sites=(0, 1, 2),
        )

        self.assertEqual(quotient.scope, "local")
        self.assertEqual(quotient.legal_inputs, (0, 1, 2, 4, 5))
        self.assertIn(5, quotient.legal_inputs)
        self.assertEqual(quotient.output_count, 8)

    def test_wrapped_or_colliding_window_falls_back_to_global_domain(self):
        basis = global_pauli_basis(4, 1)

        for sites in ((3, 0), (0, 1, 0)):
            with self.subTest(sites=sites):
                quotient = build_blockade_quotient(
                    4,
                    basis,
                    window_sites=sites,
                )
                self.assertEqual(quotient.scope, "global")
                self.assertEqual(
                    quotient.window_sites,
                    (0, 1, 2, 3),
                )
                self.assertEqual(quotient.output_count, 16)

    def test_global_rank_inventory_is_exact(self):
        expected = {2: 51, 3: 95, 4: 112}

        for weight, rank in expected.items():
            with self.subTest(weight=weight):
                quotient = build_blockade_quotient(
                    4,
                    global_pauli_basis(4, weight),
                )
                self.assertEqual(quotient.action_rank, rank)

    def test_n20_local_rank_inventory_is_exact(self):
        expected = {
            "L0": 29,
            "L1": 55,
            "L2": 107,
            "L3": 240,
        }

        for level in LOCAL_LEVELS:
            with self.subTest(level=level.name):
                sites = tuple(range(level.range_sites))
                quotient = build_blockade_quotient(
                    20,
                    local_pauli_basis(20, 0, level),
                    window_sites=sites,
                )
                self.assertEqual(
                    quotient.action_rank,
                    expected[level.name],
                )

    def test_reconstruction_and_kernel_are_exactly_verified(self):
        basis = global_pauli_basis(4, 2)
        quotient = build_blockade_quotient(4, basis)

        summary = verify_blockade_quotient(4, basis, quotient)

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["action_rank"], 51)
        self.assertEqual(
            len(quotient.kernel),
            len(basis) - quotient.action_rank,
        )

    def test_verifier_rejects_restricted_output_domain(self):
        basis = global_pauli_basis(4, 2)
        quotient = build_blockade_quotient(4, basis)

        with self.assertRaisesRegex(ValueError, "output domain"):
            verify_blockade_quotient(
                4,
                basis,
                replace(
                    quotient,
                    output_count=len(quotient.legal_inputs),
                ),
            )

    def test_verifier_rejects_changed_kernel_coefficient(self):
        basis = global_pauli_basis(4, 2)
        quotient = build_blockade_quotient(4, basis)
        first = quotient.kernel[0]
        corrupted = (
            (
                first[0][0],
                first[0][1] + ONE,
            ),
            *first[1:],
        )

        with self.assertRaisesRegex(ValueError, "kernel"):
            verify_blockade_quotient(
                4,
                basis,
                replace(
                    quotient,
                    kernel=(corrupted, *quotient.kernel[1:]),
                ),
            )

    def test_kernel_localizers_are_explicit_right_ideal_rows(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        quotient = build_blockade_quotient(
            4,
            structure.moment_basis,
        )

        rows = kernel_localizer_rows(structure, quotient)

        self.assertTrue(rows)
        self.assertTrue(
            all(
                row.identifier.startswith(
                    "blockade-right-ideal-localizer-"
                )
                for row in rows
            )
        )
        self.assertEqual(
            {
                row.provenance["localizer_kind"]
                for row in rows
            },
            {"blockade-right-ideal"},
        )

    def test_selected_slater_gram_is_strictly_positive(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        quotient = build_blockade_quotient(
            4,
            structure.moment_basis,
        )

        pivots = exact_ldlt_pivots(
            slater_gram(structure, quotient)
        )

        self.assertEqual(len(pivots), quotient.action_rank)
        self.assertTrue(all(pivot > 0 for pivot in pivots))

    def test_ldlt_rejects_nonsymmetric_or_nonpositive_matrix(self):
        with self.assertRaisesRegex(ValueError, "symmetric"):
            exact_ldlt_pivots(
                (
                    (Fraction(1), Fraction(1)),
                    (Fraction(0), Fraction(1)),
                )
            )
        with self.assertRaisesRegex(ValueError, "positive definite"):
            exact_ldlt_pivots(
                (
                    (Fraction(1), Fraction(1)),
                    (Fraction(1), Fraction(1)),
                )
            )


class BlockadeQuotientPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_blockade_quotient_boundary(self):
        from challenge233.sdp import (
            BlockadeQuotient as ExportedQuotient,
            build_blockade_quotient as exported_builder,
            exact_ldlt_pivots as exported_ldlt,
            kernel_localizer_rows as exported_rows,
            literal_pauli_action as exported_action,
            slater_gram as exported_gram,
            verify_blockade_quotient as exported_verifier,
        )

        self.assertIs(ExportedQuotient, BlockadeQuotient)
        self.assertIs(exported_builder, build_blockade_quotient)
        self.assertIs(exported_ldlt, exact_ldlt_pivots)
        self.assertIs(exported_rows, kernel_localizer_rows)
        self.assertIs(exported_action, literal_pauli_action)
        self.assertIs(exported_gram, slater_gram)
        self.assertIs(exported_verifier, verify_blockade_quotient)


if __name__ == "__main__":
    unittest.main()
