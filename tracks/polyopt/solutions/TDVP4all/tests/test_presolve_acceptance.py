from fractions import Fraction
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.kyfan_presolve import (  # noqa: E402
    build_kyfan_solver_reduction,
    solver_reduction_payload,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_kyfan_instance,
)
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    canonical_json_bytes,
    logical_structure_sha256,
)


class PresolveAcceptanceTests(unittest.TestCase):
    def test_n4_exact_inventory_and_detuning_overlay(self):
        expected_ranks = {2: 51, 3: 95, 4: 112}
        for degree, expected_rank in expected_ranks.items():
            with self.subTest(degree=degree):
                structure = build_global_kyfan_structure(
                    4,
                    degree,
                    "sound",
                )
                instances = tuple(
                    build_kyfan_instance(
                        structure,
                        Fraction(twentieths, 20),
                    )
                    for twentieths in range(61)
                )
                reduction = build_kyfan_solver_reduction(
                    structure,
                    logical_structure_sha256(structure),
                )

                self.assertEqual(
                    reduction.quotient.action_rank,
                    expected_rank,
                )
                self.assertEqual(
                    {
                        instance.structure_fingerprint
                        for instance in instances
                    },
                    {structure.logical_fingerprint()},
                )
                self.assertNotIn(
                    b"detuning",
                    canonical_json_bytes(
                        solver_reduction_payload(reduction)
                    ),
                )

if __name__ == "__main__":
    unittest.main()
