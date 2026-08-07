from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import (  # noqa: E402
    NEG_I,
    ONE,
    POS_I,
    PauliWord,
)
from challenge233.sdp.blockade_quotient import (  # noqa: E402
    BlockadeQuotient,
    build_blockade_quotient,
)
from challenge233.sdp.conjugation_reduction import (  # noqa: E402
    ConjugationReduction,
    build_conjugation_reduction,
)
from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_local_kyfan_structure,
)
from challenge233.sdp.spatial_reduction import (  # noqa: E402
    SparseRationalTransform,
    build_global_d4_reduction,
    build_local_reflection_reduction,
    induced_quotient_action,
    verify_global_d4_reduction,
    verify_induced_quotient_action,
    verify_local_reflection_reduction,
    verify_quotient_group_action,
)
from challenge233.sdp.symmetry import (  # noqa: E402
    DihedralElement,
    dihedral_elements,
)


class SpatialReductionTests(unittest.TestCase):
    _global_cache = {}
    _local_cache = {}

    @classmethod
    def _global(cls, depth):
        if depth not in cls._global_cache:
            structure = build_global_kyfan_structure(
                4,
                depth,
                "sound",
            )
            quotient = build_blockade_quotient(
                4,
                structure.moment_basis,
            )
            gauge = build_conjugation_reduction(structure)
            blocks = build_global_d4_reduction(
                4,
                structure.moment_basis,
                quotient,
                gauge,
            )
            cls._global_cache[depth] = (
                structure,
                quotient,
                gauge,
                blocks,
            )
        return cls._global_cache[depth]

    @classmethod
    def _local(cls, level_index):
        if level_index not in cls._local_cache:
            level = LOCAL_LEVELS[level_index]
            window = tuple(range(level.range_sites))
            structure = build_local_kyfan_structure(
                20,
                level,
                "sound",
            )
            quotient = build_blockade_quotient(
                20,
                structure.moment_basis,
                window_sites=window,
            )
            gauge = build_conjugation_reduction(structure)
            blocks = build_local_reflection_reduction(
                20,
                structure.moment_basis,
                window,
                quotient,
                gauge,
            )
            cls._local_cache[level_index] = (
                structure,
                quotient,
                gauge,
                blocks,
            )
        return cls._local_cache[level_index]

    @staticmethod
    def _artificial_action_fixture():
        basis = (PauliWord(),) + tuple(
            PauliWord(((site, "X"),))
            for site in range(4)
        )
        quotient = BlockadeQuotient(
            selected_indices=(0, 1, 2, 3, 4),
            reconstruction=tuple(
                ((index, ONE),)
                for index in range(5)
            ),
            kernel=(),
            legal_inputs=(0,),
            output_count=16,
            action_rank=5,
            scope="global",
            window_sites=(0, 1, 2, 3),
        )
        gauge = ConjugationReduction(
            phases=(0, 0, 0, 0, 0),
            odd_variables=(),
            odd_equalities=(),
            real_blocks=(),
        )
        return basis, quotient, gauge

    def test_induced_actions_obey_the_full_group_law_exactly(self):
        basis, quotient, gauge = self._artificial_action_fixture()

        summary = verify_quotient_group_action(
            4,
            basis,
            quotient,
            gauge,
            dihedral_elements(4),
        )

        self.assertEqual(
            summary,
            {
                "status": "verified",
                "element_count": 8,
                "dimension": 5,
            },
        )

    def test_verifier_rejects_changed_induced_action_coefficient(self):
        basis, quotient, gauge = self._artificial_action_fixture()
        element = DihedralElement(1, False)
        action = induced_quotient_action(
            element,
            basis,
            quotient,
            gauge,
            size=4,
        )
        row, column, value = action.entries[0]
        corrupted = replace(
            action,
            entries=(
                (row, column, value + 1),
                *action.entries[1:],
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "induced quotient action",
        ):
            verify_induced_quotient_action(
                4,
                element,
                basis,
                quotient,
                gauge,
                corrupted,
            )

    def test_induced_action_applies_the_real_gauge_phase_ratio(self):
        basis = (
            PauliWord(((0, "X"),)),
            PauliWord(((1, "X"),)),
            PauliWord(((0, "Y"),)),
            PauliWord(((1, "Y"),)),
        )
        quotient = BlockadeQuotient(
            selected_indices=(0, 2),
            reconstruction=(
                ((0, ONE),),
                ((1, POS_I),),
                ((1, ONE),),
                ((0, NEG_I),),
            ),
            kernel=(),
            legal_inputs=(0,),
            output_count=8,
            action_rank=2,
            scope="global",
            window_sites=(0, 1, 2),
        )
        gauge = ConjugationReduction(
            phases=(0, 0, 1, 1),
            odd_variables=(),
            odd_equalities=(),
            real_blocks=(),
        )

        action = induced_quotient_action(
            DihedralElement(1, False),
            basis,
            quotient,
            gauge,
            size=3,
        )

        self.assertEqual(
            action,
            SparseRationalTransform(
                rows=2,
                columns=2,
                entries=(
                    (0, 1, Fraction(1)),
                    (1, 0, Fraction(1)),
                ),
            ),
        )

    def test_global_d4_inventory_keeps_generic_degree_two(self):
        _, quotient, _, blocks = self._global(4)

        by_label = {
            block.irrep_label: block for block in blocks
        }
        self.assertEqual(
            by_label["generic-k1-k3"].irrep_degree,
            2,
        )
        self.assertEqual(
            sum(
                block.irrep_degree * block.dimension
                for block in blocks
            ),
            quotient.action_rank,
        )

    def test_global_d4_diagnostic_inventory_is_exact(self):
        expected = {
            2: (13, 2, 11, 3, 11),
            3: (21, 5, 19, 6, 22),
            4: (27, 5, 24, 6, 25),
        }

        for depth, dimensions in expected.items():
            with self.subTest(depth=depth):
                structure, quotient, gauge, blocks = (
                    self._global(depth)
                )
                self.assertEqual(
                    tuple(block.dimension for block in blocks),
                    dimensions,
                )
                self.assertEqual(
                    sum(
                        block.irrep_degree * block.dimension
                        for block in blocks
                    ),
                    quotient.action_rank,
                )
                self.assertEqual(
                    verify_global_d4_reduction(
                        4,
                        structure.moment_basis,
                        quotient,
                        gauge,
                        blocks,
                    )["status"],
                    "verified",
                )

    def test_global_verifier_rejects_missing_sectors_and_degree(self):
        structure, quotient, gauge, blocks = self._global(2)
        for label in ("k0-", "kpi-", "generic-k1-k3"):
            with self.subTest(label=label):
                missing = tuple(
                    block
                    for block in blocks
                    if block.irrep_label != label
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "global D4 block inventory",
                ):
                    verify_global_d4_reduction(
                        4,
                        structure.moment_basis,
                        quotient,
                        gauge,
                        missing,
                    )
        generic_index = next(
            index
            for index, block in enumerate(blocks)
            if block.irrep_label == "generic-k1-k3"
        )
        wrong_degree = list(blocks)
        wrong_degree[generic_index] = replace(
            wrong_degree[generic_index],
            irrep_degree=1,
        )
        with self.assertRaisesRegex(
            ValueError,
            "global D4 irrep degree",
        ):
            verify_global_d4_reduction(
                4,
                structure.moment_basis,
                quotient,
                gauge,
                tuple(wrong_degree),
            )

    def test_global_verifier_rejects_kpi_projector_mutation(self):
        structure, quotient, gauge, blocks = self._global(2)
        corrupted = list(blocks)
        kpi_index = next(
            index
            for index, block in enumerate(blocks)
            if block.irrep_label == "kpi+"
        )
        corrupted[kpi_index] = replace(
            corrupted[kpi_index],
            transform=blocks[0].transform,
            dimension=blocks[0].dimension,
        )

        with self.assertRaisesRegex(
            ValueError,
            "global D4 block transform",
        ):
            verify_global_d4_reduction(
                4,
                structure.moment_basis,
                quotient,
                gauge,
                tuple(corrupted),
            )

    def test_local_reflection_keeps_even_and_odd(self):
        _, _, _, blocks = self._local(3)

        self.assertEqual(
            {block.irrep_label for block in blocks},
            {"reflection-even", "reflection-odd"},
        )

    def test_local_reflection_emits_zero_dimensional_odd_slice(self):
        basis = (PauliWord(),)
        quotient = BlockadeQuotient(
            selected_indices=(0,),
            reconstruction=(((0, ONE),),),
            kernel=(),
            legal_inputs=(0,),
            output_count=5,
            action_rank=1,
            scope="local",
            window_sites=(0, 1, 2),
        )
        gauge = ConjugationReduction(
            phases=(0,),
            odd_variables=(),
            odd_equalities=(),
            real_blocks=(),
        )

        blocks = build_local_reflection_reduction(
            5,
            basis,
            (0, 1, 2),
            quotient,
            gauge,
        )

        self.assertEqual(
            tuple(
                (block.irrep_label, block.dimension)
                for block in blocks
            ),
            (
                ("reflection-even", 1),
                ("reflection-odd", 0),
            ),
        )

    def test_n20_local_diagnostic_inventory_is_exact(self):
        expected = {
            0: (18, 11),
            1: (30, 25),
            2: (56, 51),
            3: (132, 108),
        }

        for level_index, dimensions in expected.items():
            with self.subTest(
                level=LOCAL_LEVELS[level_index].name
            ):
                structure, quotient, gauge, blocks = (
                    self._local(level_index)
                )
                self.assertEqual(
                    tuple(block.dimension for block in blocks),
                    dimensions,
                )
                self.assertEqual(
                    sum(block.dimension for block in blocks),
                    quotient.action_rank,
                )
                self.assertEqual(
                    verify_local_reflection_reduction(
                        20,
                        structure.moment_basis,
                        tuple(
                            range(
                                LOCAL_LEVELS[
                                    level_index
                                ].range_sites
                            )
                        ),
                        quotient,
                        gauge,
                        blocks,
                    )["status"],
                    "verified",
                )

    def test_local_verifier_rejects_missing_odd_and_full_group(self):
        level = LOCAL_LEVELS[0]
        structure, quotient, gauge, blocks = self._local(0)
        window = tuple(range(level.range_sites))

        with self.assertRaisesRegex(
            ValueError,
            "local reflection block inventory",
        ):
            verify_local_reflection_reduction(
                20,
                structure.moment_basis,
                window,
                quotient,
                gauge,
                blocks[:1],
            )

        translated = tuple(
            replace(
                block,
                internal_group=dihedral_elements(20),
            )
            for block in blocks
        )
        with self.assertRaisesRegex(
            ValueError,
            "local reflection internal group",
        ):
            verify_local_reflection_reduction(
                20,
                structure.moment_basis,
                window,
                quotient,
                gauge,
                translated,
            )


class SpatialReductionPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_spatial_reduction_boundary(self):
        from challenge233.sdp import (
            SparseRationalTransform as ExportedTransform,
            SpatialBlock as ExportedBlock,
            build_global_d4_reduction as exported_global,
            build_local_reflection_reduction as exported_local,
            induced_quotient_action as exported_action,
            verify_global_d4_reduction as exported_verify_global,
            verify_induced_quotient_action as exported_verify_action,
            verify_local_reflection_reduction as exported_verify_local,
            verify_quotient_group_action as exported_verify_group,
        )

        from challenge233.sdp.spatial_reduction import SpatialBlock

        self.assertIs(ExportedTransform, SparseRationalTransform)
        self.assertIs(ExportedBlock, SpatialBlock)
        self.assertIs(exported_global, build_global_d4_reduction)
        self.assertIs(exported_local, build_local_reflection_reduction)
        self.assertIs(exported_action, induced_quotient_action)
        self.assertIs(
            exported_verify_global,
            verify_global_d4_reduction,
        )
        self.assertIs(
            exported_verify_action,
            verify_induced_quotient_action,
        )
        self.assertIs(
            exported_verify_local,
            verify_local_reflection_reduction,
        )
        self.assertIs(
            exported_verify_group,
            verify_quotient_group_action,
        )


if __name__ == "__main__":
    unittest.main()
