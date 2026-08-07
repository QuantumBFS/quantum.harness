from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.kyfan_presolve import (  # noqa: E402
    build_kyfan_solver_reduction,
    clarabel_hs_bytes,
    solver_reduction_payload,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
)
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    canonical_json_bytes,
    logical_structure_sha256,
)


class KyFanPresolveTests(unittest.TestCase):
    _cache = {}

    @classmethod
    def _reduction(cls, structure):
        key = (structure.size, structure.hierarchy)
        if key not in cls._cache:
            digest = logical_structure_sha256(structure)
            cls._cache[key] = build_kyfan_solver_reduction(
                structure,
                digest,
            )
        return cls._cache[key]

    def test_reduction_bytes_are_detuning_independent(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        digest = logical_structure_sha256(structure)

        first = build_kyfan_solver_reduction(structure, digest)
        second = build_kyfan_solver_reduction(structure, digest)
        first_bytes = canonical_json_bytes(
            solver_reduction_payload(first)
        )
        second_bytes = canonical_json_bytes(
            solver_reduction_payload(second)
        )

        self.assertEqual(first_bytes, second_bytes)
        self.assertNotIn(b"detuning", first_bytes)

    def test_global_reduction_emits_two_copies_of_every_d4_slice(self):
        structure = build_global_kyfan_structure(4, 2, "sound")

        reduction = self._reduction(structure)

        self.assertEqual(
            tuple(block.dimension for block in reduction.psd_blocks),
            2 * (13, 2, 11, 3, 11),
        )
        self.assertTrue(
            all(
                entry.row <= entry.column
                for block in reduction.psd_blocks
                for entry in block.upper_entries
            )
        )
        self.assertTrue(
            all(
                block.spatial_block
                in {
                    "global-d4-k0+",
                    "global-d4-k0-",
                    "global-d4-kpi+",
                    "global-d4-kpi-",
                    "global-d4-generic-k1-k3",
                }
                for block in reduction.psd_blocks
            )
        )

    def test_clarabel_hs_formula_counts_packed_symmetric_cones(self):
        self.assertEqual(
            clarabel_hs_bytes((2, 3)),
            8 * 3**2 + 8 * 6**2,
        )
        with self.assertRaisesRegex(ValueError, "dimension"):
            clarabel_hs_bytes((2, -1))


class KyFanPresolvePackageBoundaryTests(unittest.TestCase):
    def test_package_exports_presolve_boundary(self):
        from challenge233.sdp import (
            KyFanSolverReduction,
            ReducedRealPSDBlock,
            ReductionBinding,
            build_kyfan_solver_reduction as exported_builder,
            clarabel_hs_bytes as exported_hs,
            estimate_reduced_resources,
            export_solver_reduction,
            solver_reduction_payload as exported_payload,
            verify_kyfan_reduction,
        )

        self.assertTrue(
            hasattr(KyFanSolverReduction, "__dataclass_fields__")
        )
        self.assertTrue(
            hasattr(ReducedRealPSDBlock, "__dataclass_fields__")
        )
        self.assertTrue(
            hasattr(ReductionBinding, "__dataclass_fields__")
        )
        self.assertIs(exported_builder, build_kyfan_solver_reduction)
        self.assertIs(exported_hs, clarabel_hs_bytes)
        self.assertIs(exported_payload, solver_reduction_payload)
        self.assertTrue(callable(estimate_reduced_resources))
        self.assertTrue(callable(export_solver_reduction))
        self.assertTrue(callable(verify_kyfan_reduction))


if __name__ == "__main__":
    unittest.main()
