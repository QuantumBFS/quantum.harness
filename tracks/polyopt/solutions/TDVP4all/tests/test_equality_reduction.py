from dataclasses import replace
from fractions import Fraction
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.blockade_quotient import (  # noqa: E402
    build_blockade_quotient,
    kernel_localizer_rows,
)
from challenge233.sdp.conjugation_reduction import (  # noqa: E402
    build_conjugation_reduction,
)
from challenge233.sdp.equality_reduction import (  # noqa: E402
    AffineParameterization,
    EqualityReduction,
    compress_equalities,
    verify_equality_reduction,
)
from challenge233.sdp.kyfan import (  # noqa: E402
    LinearEquality,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_local_kyfan_structure,
)
from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402


def _row(identifier, constant, terms):
    return LinearEquality(
        identifier=identifier,
        form=RationalLinearForm(
            constant=constant,
            terms=terms,
        ),
        provenance={"source": identifier},
    )


class EqualityReductionTests(unittest.TestCase):
    def test_proportional_rows_keep_all_provenance(self):
        rows = (
            _row("a", Fraction(1), ((0, Fraction(2)),)),
            _row("b", Fraction(-3), ((0, Fraction(-6)),)),
        )

        result = compress_equalities(rows, 1, ())

        self.assertEqual(result.row_rank, 1)
        self.assertEqual(result.kept_identifiers, ("a",))
        self.assertEqual(
            result.duplicate_map,
            {
                "b": {
                    "kept_identifier": "a",
                    "scale_to_kept": Fraction(-3),
                    "provenance": {"source": "b"},
                },
            },
        )
        self.assertEqual(
            result.statistics["parameterization_input_row_count"],
            1,
        )
        self.assertEqual(
            result.span_map["b"],
            (("a", Fraction(-3)),),
        )
        self.assertEqual(
            result.statistics["row_provenance"],
            {
                "a": {"source": "a"},
                "b": {"source": "b"},
            },
        )

    def test_nonzero_constant_row_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "inconsistent-equality-system",
        ):
            compress_equalities(
                (_row("bad", Fraction(1), ()),),
                2,
                (),
            )

    def test_affine_parameterization_matches_hand_solution(self):
        rows = (
            _row(
                "solve",
                Fraction(-3),
                (
                    (0, Fraction(1)),
                    (1, Fraction(2)),
                ),
            ),
        )

        result = compress_equalities(rows, 2, ())

        self.assertEqual(result.pivot_columns, (0,))
        self.assertEqual(result.parameterization.free_variables, (1,))
        self.assertEqual(
            result.parameterization.offset,
            ((0, Fraction(3)),),
        )
        self.assertEqual(
            result.parameterization.nullspace,
            (
                (
                    (0, Fraction(-2)),
                    (1, Fraction(1)),
                ),
            ),
        )

    def test_parameterized_view_is_selected_when_it_reduces_fill_and_kkt(self):
        rows = (_row("zero-x0", Fraction(0), ((0, Fraction(1)),)),)
        affine = (
            RationalLinearForm(
                terms=((0, Fraction(1)), (1, Fraction(1)))
            ),
        )

        result = compress_equalities(rows, 2, affine)

        self.assertEqual(result.selected_view, "parameterized")
        self.assertEqual(
            result.statistics["selection_reason"],
            "parameterized-within-fill-cap-and-lower-kkt-proxy",
        )

    def test_row_reduced_view_is_selected_when_parameterization_exceeds_cap(self):
        terms = tuple(
            (index, Fraction(1))
            for index in range(11)
        )
        rows = (_row("dense-pivot", Fraction(0), terms),)
        affine = tuple(
            RationalLinearForm(terms=((0, Fraction(1)),))
            for _ in range(3)
        )

        result = compress_equalities(
            rows,
            11,
            affine,
            fill_cap=Fraction(2),
        )

        self.assertEqual(result.selected_view, "row-reduced")
        self.assertEqual(
            result.statistics["selection_reason"],
            "parameterized-fill-exceeds-cap",
        )
        self.assertEqual(
            result.statistics["row_reduced_affine_nonzeros"],
            3,
        )
        self.assertEqual(
            result.statistics["parameterized_affine_nonzeros"],
            30,
        )

    def test_fill_cap_must_be_positive_and_exact(self):
        rows = (_row("zero-x0", Fraction(0), ((0, Fraction(1)),)),)
        for bad in (0, Fraction(-1), 2.0):
            with self.subTest(fill_cap=bad):
                with self.assertRaisesRegex(
                    (TypeError, ValueError),
                    "fill cap",
                ):
                    compress_equalities(rows, 1, (), fill_cap=bad)

    def test_verifier_rejects_mutated_span_coefficient(self):
        rows = (
            _row("a", Fraction(1), ((0, Fraction(2)),)),
            _row("b", Fraction(-3), ((0, Fraction(-6)),)),
        )
        result = compress_equalities(rows, 1, ())
        bad_span = dict(result.span_map)
        bad_span["b"] = (("a", Fraction(-2)),)

        with self.assertRaisesRegex(ValueError, "span map"):
            verify_equality_reduction(
                rows,
                1,
                (),
                replace(result, span_map=bad_span),
            )

    def test_verifier_rejects_mutated_duplicate_scale(self):
        rows = (
            _row("a", Fraction(1), ((0, Fraction(2)),)),
            _row("b", Fraction(-3), ((0, Fraction(-6)),)),
        )
        result = compress_equalities(rows, 1, ())
        bad_duplicate_map = {
            **result.duplicate_map,
            "b": {
                **result.duplicate_map["b"],
                "scale_to_kept": Fraction(-2),
            },
        }

        with self.assertRaisesRegex(ValueError, "duplicate map"):
            verify_equality_reduction(
                rows,
                1,
                (),
                replace(result, duplicate_map=bad_duplicate_map),
            )

    def test_verifier_rejects_mutated_row_provenance(self):
        rows = (_row("a", Fraction(1), ((0, Fraction(2)),)),)
        result = compress_equalities(rows, 1, ())
        bad_statistics = {
            **result.statistics,
            "row_provenance": {
                "a": {"source": "invented"},
            },
        }

        with self.assertRaisesRegex(ValueError, "row provenance"):
            verify_equality_reduction(
                rows,
                1,
                (),
                replace(result, statistics=bad_statistics),
            )

    def test_verifier_rejects_mutated_nullspace_entry(self):
        rows = (
            _row(
                "solve",
                Fraction(-3),
                (
                    (0, Fraction(1)),
                    (1, Fraction(2)),
                ),
            ),
        )
        result = compress_equalities(rows, 2, ())
        bad_parameterization = replace(
            result.parameterization,
            nullspace=(
                (
                    (0, Fraction(-1)),
                    (1, Fraction(1)),
                ),
            ),
        )

        with self.assertRaisesRegex(ValueError, "nullspace"):
            verify_equality_reduction(
                rows,
                2,
                (),
                replace(
                    result,
                    parameterization=bad_parameterization,
                ),
            )

    def test_verifier_rejects_mutated_selection_reason_or_fill_cap(self):
        rows = (_row("zero-x0", Fraction(0), ((0, Fraction(1)),)),)
        affine = (
            RationalLinearForm(
                terms=((0, Fraction(1)), (1, Fraction(1)))
            ),
        )
        result = compress_equalities(rows, 2, affine)
        bad_statistics = {
            **result.statistics,
            "selection_reason": "invented",
        }

        with self.assertRaisesRegex(ValueError, "selection reason"):
            verify_equality_reduction(
                rows,
                2,
                affine,
                replace(result, statistics=bad_statistics),
            )
        with self.assertRaisesRegex(ValueError, "fill cap"):
            verify_equality_reduction(
                rows,
                2,
                affine,
                result,
                fill_cap=Fraction(1),
            )

    def test_n4_production_rows_round_trip_exactly(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        gauge = build_conjugation_reduction(structure)
        quotient = build_blockade_quotient(
            4,
            structure.moment_basis,
        )
        rows = (
            *structure.equalities,
            *gauge.odd_equalities,
            *kernel_localizer_rows(structure, quotient),
        )
        affine = (
            *gauge.real_blocks,
            *structure.objective_components.values(),
        )

        result = compress_equalities(
            rows,
            len(structure.variables),
            affine,
        )
        summary = verify_equality_reduction(
            rows,
            len(structure.variables),
            affine,
            result,
        )

        self.assertEqual(summary["status"], "verified")
        self.assertLess(result.row_rank, len(rows))
        self.assertEqual(
            len(result.parameterization.free_variables),
            len(structure.variables) - result.row_rank,
        )

    @unittest.skipUnless(
        os.environ.get(
            "CHALLENGE233_RUN_N20_EQUALITY_INVENTORY"
        )
        == "1",
        "N=20 L0-L3 exact inventory exceeds the local compute budget",
    )
    def test_n20_l0_l3_production_rank_inventory_is_exact(self):
        expected = {
            "L0": (25, 8),
            "L1": (95, 16),
            "L2": (95, 16),
            "L3": (384, 39),
        }

        for level in LOCAL_LEVELS:
            with self.subTest(level=level.name):
                structure = build_local_kyfan_structure(
                    20,
                    level,
                    "sound",
                )
                gauge = build_conjugation_reduction(structure)
                quotient = build_blockade_quotient(
                    20,
                    structure.moment_basis,
                    tuple(range(level.range_sites)),
                )
                rows = (
                    *structure.equalities,
                    *gauge.odd_equalities,
                    *kernel_localizer_rows(structure, quotient),
                )
                affine = (
                    *gauge.real_blocks,
                    *structure.objective_components.values(),
                )

                result = compress_equalities(
                    rows,
                    len(structure.variables),
                    affine,
                )

                self.assertEqual(
                    (
                        result.row_rank,
                        len(result.parameterization.free_variables),
                    ),
                    expected[level.name],
                )


class EqualityReductionPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_equality_reduction_boundary(self):
        from challenge233.sdp import (
            AffineParameterization as ExportedParameterization,
            EqualityReduction as ExportedReduction,
            compress_equalities as exported_compress,
            verify_equality_reduction as exported_verify,
        )

        self.assertIs(
            ExportedParameterization,
            AffineParameterization,
        )
        self.assertIs(ExportedReduction, EqualityReduction)
        self.assertIs(exported_compress, compress_equalities)
        self.assertIs(exported_verify, verify_equality_reduction)


if __name__ == "__main__":
    unittest.main()
