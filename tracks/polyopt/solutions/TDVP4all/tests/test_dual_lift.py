from fractions import Fraction
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.dual_certificate import DyadicFactor  # noqa: E402
from challenge233.sdp.dual_lift import (  # noqa: E402
    ExactLiftedIdentity,
    build_weighted_factor_orbit,
    exact_lifted_psd_contribution,
    lift_reduced_duals,
    literal_dense_residual_norm_bound,
    moment_residual_correction,
    physical_residual_correction,
    reconstruct_equality_multipliers,
)
from challenge233.sdp.kyfan import (  # noqa: E402
    MagnitudeWitness,
    MomentVariable,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_kyfan_instance,
)
from challenge233.sdp.kyfan_presolve import (  # noqa: E402
    build_kyfan_solver_reduction,
)
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    logical_structure_sha256,
)
from challenge233.sdp.algebra import ONE, PauliWord  # noqa: E402
from challenge233.sdp.symmetry import (  # noqa: E402
    dihedral_elements,
    word_orbit,
)


class DualLiftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.structure = build_global_kyfan_structure(4, 2, "sound")
        cls.reduction = build_kyfan_solver_reduction(
            cls.structure,
            logical_structure_sha256(cls.structure),
        )

    def assert_lift_matches_reduced_form(self, lifted, expected):
        constant, coefficients = exact_lifted_psd_contribution(
            self.structure,
            lifted,
        )
        original = RationalLinearForm(
            constant,
            tuple(enumerate(coefficients)),
        )
        parameterization = self.reduction.equality.parameterization
        offset = dict(parameterization.offset)
        columns = tuple(
            dict(column) for column in parameterization.nullspace
        )
        original_map = dict(original.terms)
        substituted = RationalLinearForm(
            original.constant
            + sum(
                coefficient * offset.get(variable, Fraction(0))
                for variable, coefficient in original_map.items()
            ),
            tuple(
                (
                    free_position,
                    sum(
                        coefficient
                        * column.get(variable, Fraction(0))
                        for variable, coefficient in original_map.items()
                    ),
                )
                for free_position, column in enumerate(columns)
            ),
        )
        self.assertEqual(substituted, expected)

    def test_generic_slice_is_averaged_over_full_d4(self):
        factor = DyadicFactor(
            rows=2,
            columns=1,
            requested_bits=0,
            used_bits=0,
            numerators=((1,), (0,)),
            storage="int64",
            overflow_bound=1,
        )

        lifted = build_weighted_factor_orbit(
            identifier="toy-generic",
            factor=factor,
            group_images=tuple(dihedral_elements(4)),
            phase_exponents=(0, 1),
            source_block="gamma",
            irrep_label="k1-generic",
            irrep_degree=2,
        )

        self.assertEqual(lifted.weight, Fraction(1, 8))
        self.assertEqual(len(lifted.group_images), 8)
        self.assertEqual(lifted.irrep_degree, 2)

    def test_physical_row_sum_matches_dense_n4_bound(self):
        residuals = {
            variable.index: Fraction(
                (variable.index % 3) - 1,
                16,
            )
            for variable in self.structure.variables
        }

        exact = physical_residual_correction(
            4,
            self.structure.variables,
            residuals,
        )
        dense = literal_dense_residual_norm_bound(
            4,
            self.structure.variables,
            residuals,
        )

        self.assertEqual(exact, dense)

    def test_reduced_generic_factor_is_lifted_to_full_test_basis(self):
        duals = []
        for block in self.reduction.psd_blocks:
            matrix = [
                [0.0] * block.dimension
                for _ in range(block.dimension)
            ]
            if (
                block.source_block == "gamma"
                and block.spatial_block
                == "global-d4-generic-k1-k3"
            ):
                matrix[0][0] = 1.0
            spatial = next(
                item
                for item in self.reduction.spatial
                if item.identifier == block.spatial_block
            )
            duals.append(
                {
                    "block": block.identifier,
                    "dimension": block.dimension,
                    "source_effect": block.source_block,
                    "spatial_block": block.spatial_block,
                    "irrep_label": spatial.irrep_label,
                    "irrep_degree": spatial.irrep_degree,
                    "matrix": matrix,
                }
            )

        lifted = lift_reduced_duals(
            self.structure,
            self.reduction,
            {"psd_duals": duals},
            factor_bits=8,
        )

        self.assertEqual(len(lifted), len(self.reduction.psd_blocks))
        generic = next(
            item
            for item in lifted
            if item.source_block == "gamma"
            and item.irrep_label == "generic-k1-k3"
        )
        self.assertEqual(generic.factor.rows, 67)
        self.assertEqual(generic.factor.columns, 1)
        denominator = 1 << generic.factor.used_bits
        values = tuple(
            Fraction(row[0], denominator)
            for row in generic.factor.numerators
        )
        self.assertEqual(values[1], Fraction(1, 2))
        self.assertEqual(values[52], Fraction(-1, 2))
        self.assertEqual(
            tuple(
                index
                for index, value in enumerate(values)
                if value
            ),
            (1, 52),
        )
        self.assertEqual(len(generic.group_images), 8)
        self.assertEqual(generic.irrep_degree, 2)

    def test_equality_reconstruction_cancels_every_pivot_exactly(self):
        instance = build_kyfan_instance(
            self.structure,
            Fraction(1, 2),
        )
        objective = dict(instance.objective.terms)
        expected = {
            row.identifier: Fraction(
                (index % 5) - 2,
                16,
            )
            for index, row in enumerate(
                self.reduction.kept_equalities
            )
        }
        psd = {
            variable.index: objective.get(
                variable.index,
                Fraction(0),
            )
            for variable in self.structure.variables
        }
        for row in self.reduction.kept_equalities:
            multiplier = expected[row.identifier]
            for variable, coefficient in row.form.terms:
                psd[variable] -= multiplier * coefficient

        reconstructed = reconstruct_equality_multipliers(
            instance,
            self.reduction,
            psd,
        )

        for identifier, multiplier in expected.items():
            self.assertEqual(reconstructed[identifier], multiplier)
        self.assertTrue(
            all(
                reconstructed[identifier] == 0
                for identifier in (
                    set(reconstructed) - set(expected)
                )
            )
        )

    def test_group_averaged_lift_matches_every_reduced_diagonal_form(self):
        duals = []
        expected = RationalLinearForm()
        for block in self.reduction.psd_blocks:
            matrix = [
                [0.0] * block.dimension
                for _ in range(block.dimension)
            ]
            matrix[0][0] = 1.0
            spatial = next(
                item
                for item in self.reduction.spatial
                if item.identifier == block.spatial_block
            )
            duals.append(
                {
                    "block": block.identifier,
                    "dimension": block.dimension,
                    "source_effect": block.source_block,
                    "spatial_block": block.spatial_block,
                    "irrep_label": spatial.irrep_label,
                    "irrep_degree": spatial.irrep_degree,
                    "matrix": matrix,
                }
            )
            diagonal = next(
                entry.form
                for entry in block.upper_entries
                if entry.row == 0 and entry.column == 0
            )
            expected = expected + diagonal
        lifted = lift_reduced_duals(
            self.structure,
            self.reduction,
            {"psd_duals": duals},
            factor_bits=8,
        )

        self.assert_lift_matches_reduced_form(lifted, expected)

        generic = next(
            item for item in lifted
            if item.irrep_degree == 2
            and item.source_block == "gamma"
        )
        with self.assertRaisesRegex(ValueError, "weight"):
            type(generic)(
                identifier=generic.identifier,
                weight=generic.weight,
                factor=generic.factor,
                group_images=generic.group_images[:-1],
                phase_exponents=generic.phase_exponents,
                source_block=generic.source_block,
                irrep_label=generic.irrep_label,
                irrep_degree=generic.irrep_degree,
            )

    def test_generic_offdiagonal_form_survives_exact_lift(self):
        generic_block = next(
            block
            for block in self.reduction.psd_blocks
            if block.source_block == "gamma"
            and block.spatial_block
            == "global-d4-generic-k1-k3"
        )
        self.assertGreaterEqual(generic_block.dimension, 2)
        duals = []
        for block in self.reduction.psd_blocks:
            matrix = [
                [0.0] * block.dimension
                for _ in range(block.dimension)
            ]
            if block.identifier == generic_block.identifier:
                for row in range(2):
                    for column in range(2):
                        matrix[row][column] = 1.0
            spatial = next(
                item
                for item in self.reduction.spatial
                if item.identifier == block.spatial_block
            )
            duals.append(
                {
                    "block": block.identifier,
                    "dimension": block.dimension,
                    "source_effect": block.source_block,
                    "spatial_block": block.spatial_block,
                    "irrep_label": spatial.irrep_label,
                    "irrep_degree": spatial.irrep_degree,
                    "matrix": matrix,
                }
            )
        entries = {
            (entry.row, entry.column): entry.form
            for entry in generic_block.upper_entries
        }
        expected = (
            entries.get((0, 0), RationalLinearForm())
            + entries.get((0, 1), RationalLinearForm()).scale(2)
            + entries.get((1, 1), RationalLinearForm())
        )

        def exact_fixture_factor(matrix, requested_bits):
            dimension = len(matrix)
            active = dimension >= 2 and matrix[0][1] == 1.0
            columns = 1 if active else 0
            return DyadicFactor(
                rows=dimension,
                columns=columns,
                requested_bits=requested_bits,
                used_bits=0,
                numerators=tuple(
                    (
                        (1,)
                        if active and row < 2
                        else ((0,) if active else ())
                    )
                    for row in range(dimension)
                ),
                storage="int64",
                overflow_bound=columns,
            )

        with patch(
            "challenge233.sdp.dual_lift.positive_dyadic_factor",
            side_effect=exact_fixture_factor,
        ):
            lifted = lift_reduced_duals(
                self.structure,
                self.reduction,
                {"psd_duals": duals},
                factor_bits=8,
            )

        self.assert_lift_matches_reduced_form(lifted, expected)

    def test_physical_row_sum_matches_dense_n5_bound(self):
        representatives = (
            PauliWord(((0, "X"),)),
            PauliWord(((0, "Y"), (2, "Y"))),
            PauliWord(((0, "Z"), (1, "X"))),
        )
        variables = tuple(
            MomentVariable(
                index,
                representative,
                word_orbit(representative, 5),
            )
            for index, representative in enumerate(representatives)
        )
        residuals = {
            0: Fraction(-1, 16),
            1: Fraction(3, 32),
            2: Fraction(1, 8),
        }

        exact = physical_residual_correction(
            5,
            variables,
            residuals,
        )
        dense = literal_dense_residual_norm_bound(
            5,
            variables,
            residuals,
        )

        self.assertEqual(exact, dense)

    def test_pseudo_moment_bound_requires_complete_witness_inventory(self):
        witnesses = (
            MagnitudeWitness(0, "gamma", 0, 1, ONE, Fraction(2)),
            MagnitudeWitness(1, "gamma", 0, 2, ONE, Fraction(2)),
        )
        residuals = {0: Fraction(-1, 8), 1: Fraction(3, 16)}

        self.assertEqual(
            moment_residual_correction(residuals, witnesses),
            Fraction(5, 8),
        )
        with self.assertRaisesRegex(ValueError, "inventory"):
            moment_residual_correction({0: Fraction(1)}, witnesses)

    def test_lifted_identity_selects_stronger_sound_route(self):
        identity = ExactLiftedIdentity(
            a=Fraction(3, 2),
            residuals=(Fraction(1, 8),),
            rho_mom=Fraction(1, 4),
            rho_op=Fraction(1, 8),
            rho=Fraction(1, 8),
            residual_route="physical-operator",
            a_cert=Fraction(11, 8),
        )

        self.assertEqual(identity.a_cert, Fraction(11, 8))


class DualLiftPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_exact_dual_lift_boundary(self):
        from challenge233.sdp import (
            ExactLiftedIdentity as ExportedIdentity,
            WeightedFactorOrbit as ExportedOrbit,
            build_weighted_factor_orbit as exported_builder,
            exact_lifted_psd_contribution as exported_contribution,
            lift_reduced_duals as exported_lift,
            literal_dense_residual_norm_bound as exported_dense,
            moment_residual_correction as exported_moment,
            physical_residual_correction as exported_physical,
            reconstruct_equality_multipliers as exported_equalities,
        )

        self.assertIs(ExportedIdentity, ExactLiftedIdentity)
        self.assertTrue(hasattr(ExportedOrbit, "__dataclass_fields__"))
        for function in (
            exported_builder,
            exported_contribution,
            exported_lift,
            exported_dense,
            exported_moment,
            exported_physical,
            exported_equalities,
        ):
            self.assertTrue(callable(function))


if __name__ == "__main__":
    unittest.main()
