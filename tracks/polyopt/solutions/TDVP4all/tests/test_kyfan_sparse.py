from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402
from challenge233.sdp.kyfan import (  # noqa: E402
    RealPSDBlock,
    build_global_kyfan_problem,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    KyFanInstance,
    KyFanStructure,
    SparseComplexEntry,
    SparseComplexPSDBlock,
    build_global_kyfan_structure,
    build_kyfan_instance,
    build_local_kyfan_structure,
    materialize_complex_blocks,
)


class SparseKyFanStructureTests(unittest.TestCase):
    def test_n4_upper_triangle_matches_legacy_complex_blocks(self):
        sparse = build_global_kyfan_structure(4, 2, "sound")
        legacy = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
            "sound",
        )
        instance = build_kyfan_instance(sparse, Fraction(1, 2))

        self.assertEqual(instance.objective, legacy.objective)
        self.assertEqual(
            materialize_complex_blocks(sparse.psd_blocks),
            legacy.unrealified_psd_blocks,
        )
        self.assertEqual(
            {row.identifier for row in sparse.equalities},
            {row.identifier for row in legacy.equalities},
        )

    def test_structure_is_reused_across_detuning_instances(self):
        structure = build_local_kyfan_structure(
            8,
            LOCAL_LEVELS[1],
            "sound",
        )

        left = build_kyfan_instance(structure, Fraction(0))
        right = build_kyfan_instance(structure, Fraction(1))

        self.assertIs(
            structure,
            build_local_kyfan_structure(
                8,
                LOCAL_LEVELS[1],
                "sound",
            ),
        )
        self.assertEqual(
            left.structure_fingerprint,
            right.structure_fingerprint,
        )
        self.assertNotEqual(left.objective, right.objective)

    def test_objective_overlay_is_rabi_plus_detuning_minus_number(self):
        structure = build_global_kyfan_structure(4, 2, "sound")

        instance = build_kyfan_instance(structure, Fraction(3, 10))

        self.assertEqual(
            instance.objective,
            structure.objective_components["rabi"]
            + structure.objective_components["minus-number"].scale(
                Fraction(3, 10)
            ),
        )
        self.assertEqual(
            instance.physical_contract["detuning"],
            "3/10",
        )

    def test_instance_accepts_delta_three_and_rejects_contract_escape(self):
        structure = build_global_kyfan_structure(4, 2, "sound")

        endpoint = build_kyfan_instance(structure, Fraction(3))
        self.assertEqual(endpoint.detuning, Fraction(3))
        self.assertEqual(endpoint.physical_contract["detuning"], "3/1")
        with self.assertRaisesRegex(TypeError, "exact rational"):
            build_kyfan_instance(structure, 0.5)
        with self.assertRaisesRegex(ValueError, r"\[0,3\]"):
            build_kyfan_instance(structure, Fraction(-1, 10))
        with self.assertRaisesRegex(ValueError, r"\[0,3\]"):
            build_kyfan_instance(structure, Fraction(61, 20))

    def test_n20_l0_stores_only_sparse_complex_upper_triangles(self):
        structure = build_local_kyfan_structure(
            20,
            LOCAL_LEVELS[0],
            "sound",
        )

        self.assertIsInstance(structure, KyFanStructure)
        self.assertFalse(
            any(
                isinstance(block, RealPSDBlock)
                for block in structure.psd_blocks
            )
        )
        for block in structure.psd_blocks:
            coordinates = tuple(
                (entry.row, entry.column)
                for entry in block.upper_entries
            )
            self.assertEqual(coordinates, tuple(sorted(set(coordinates))))
            self.assertTrue(
                all(row <= column for row, column in coordinates)
            )
            self.assertLessEqual(
                len(coordinates),
                block.dimension * (block.dimension + 1) // 2,
            )
        self.assertNotIn(
            "generic_realification_dimension",
            structure.statistics,
        )
        self.assertEqual(
            structure.statistics["bounded_variable_count"],
            structure.statistics["moment_variable_count"],
        )

    def test_sparse_records_reject_lower_or_duplicate_coordinates(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        entry = structure.psd_blocks[0].upper_entries[1]

        with self.assertRaisesRegex(ValueError, "upper triangular"):
            SparseComplexEntry(
                row=entry.column,
                column=entry.row,
                form=entry.form,
            )
        with self.assertRaisesRegex(ValueError, "unique and sorted"):
            SparseComplexPSDBlock(
                identifier="duplicate",
                dimension=structure.psd_blocks[0].dimension,
                upper_entries=(entry, entry),
                provenance={},
            )


class SparseKyFanPackageBoundaryTests(unittest.TestCase):
    def test_package_exports_sparse_structure_boundary(self):
        from challenge233.sdp import (
            KyFanInstance as ExportedInstance,
            KyFanStructure as ExportedStructure,
            build_kyfan_instance as exported_instance_builder,
            build_local_kyfan_structure as exported_local_builder,
        )

        self.assertIs(ExportedInstance, KyFanInstance)
        self.assertIs(ExportedStructure, KyFanStructure)
        self.assertIs(exported_instance_builder, build_kyfan_instance)
        self.assertIs(
            exported_local_builder,
            build_local_kyfan_structure,
        )


if __name__ == "__main__":
    unittest.main()
