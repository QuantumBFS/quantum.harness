import json
from fractions import Fraction
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_kyfan_instance,
    build_local_kyfan_structure,
)
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    canonical_json_bytes,
    export_kyfan_instance,
    export_shared_structure,
    instance_payload,
    logical_structure_sha256,
    structure_payload,
)


class KyFanV2ArtifactTests(unittest.TestCase):
    def test_two_detunings_share_identical_structure_bytes(self):
        structure = build_local_kyfan_structure(
            8,
            LOCAL_LEVELS[0],
            "sound",
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            binding_a = export_shared_structure(
                structure,
                root / "shared",
            )
            binding_b = export_shared_structure(
                structure,
                root / "shared",
            )

            self.assertEqual(
                binding_a.structure_sha256,
                binding_b.structure_sha256,
            )
            self.assertEqual(
                binding_a.structure_path.read_bytes(),
                binding_b.structure_path.read_bytes(),
            )
            self.assertEqual(
                binding_a.structure_sha256,
                logical_structure_sha256(structure),
            )

    def test_structure_payload_has_no_cell_or_solver_fields(self):
        structure = build_global_kyfan_structure(4, 2, "sound")

        payload = structure_payload(structure)
        encoded = canonical_json_bytes(payload)

        for forbidden in (
            b'"detuning"',
            b'"objective"',
            b'"trial_manifest"',
            b'"solver"',
            b'"resource_placement"',
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(payload["schema_version"], 2)
        self.assertIn("objective_components", payload)
        self.assertIn("blockade_action_table", payload)

    def test_instance_overlay_binds_shared_structure(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        instance = build_kyfan_instance(
            structure,
            Fraction(3, 10),
        )
        digest = logical_structure_sha256(structure)

        payload = instance_payload(instance, digest)

        self.assertEqual(payload["structure_sha256"], digest)
        self.assertEqual(payload["detuning"], "3/10")
        self.assertNotIn("trial_manifest", payload)
        self.assertIsNone(payload["trial_manifest_sha256"])
        self.assertEqual(
            payload["objective"],
            {
                "constant": (
                    f"{instance.objective.constant.numerator}/"
                    f"{instance.objective.constant.denominator}"
                ),
                "terms": [
                    [
                        index,
                        (
                            f"{coefficient.numerator}/"
                            f"{coefficient.denominator}"
                        ),
                    ]
                    for index, coefficient in instance.objective.terms
                ],
            },
        )

    def test_cell_manifest_uses_normalized_relative_references(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        instance = build_kyfan_instance(
            structure,
            Fraction(1, 2),
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            binding = export_shared_structure(
                structure,
                root / "shared",
            )
            problem_directory = (
                root / "cells" / "n4-delta-1-2" / "problem"
            )
            export_kyfan_instance(
                instance,
                binding,
                problem_directory,
            )

            manifest = json.loads(
                (problem_directory / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )

        for key in (
            "structure_reference",
            "structure_manifest_reference",
        ):
            reference = manifest[key]
            self.assertFalse(Path(reference).is_absolute())
            self.assertEqual(reference, Path(reference).as_posix())
            self.assertNotIn(".", Path(reference).parts)
        self.assertEqual(
            manifest["structure_sha256"],
            binding.structure_sha256,
        )


class KyFanV2PackageBoundaryTests(unittest.TestCase):
    def test_package_exports_v2_artifact_boundary(self):
        from challenge233.sdp import (
            StructureBinding,
            canonical_json_bytes as exported_json_bytes,
            export_kyfan_instance as exported_instance,
            export_shared_structure as exported_structure,
            logical_structure_sha256 as exported_digest,
        )
        import challenge233.sdp as package

        self.assertTrue(hasattr(StructureBinding, "__dataclass_fields__"))
        self.assertIs(exported_json_bytes, canonical_json_bytes)
        self.assertIs(exported_instance, export_kyfan_instance)
        self.assertIs(exported_structure, export_shared_structure)
        self.assertIs(exported_digest, logical_structure_sha256)
        self.assertIn("verify_kyfan_structure", package.__all__)


if __name__ == "__main__":
    unittest.main()
