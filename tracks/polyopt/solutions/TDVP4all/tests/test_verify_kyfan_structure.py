import hashlib
import json
from fractions import Fraction
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_global_kyfan_structure,
    build_kyfan_instance,
    build_local_kyfan_structure,
)
from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    canonical_json_bytes,
    export_kyfan_instance,
    export_shared_structure,
    structure_payload,
)
from challenge233.sdp.verify_kyfan_structure import (  # noqa: E402
    resolve_bound_path,
    validate_structure_payload,
    verify_bound_kyfan_structure,
    verify_kyfan_structure,
)


def _block(payload, identifier="gamma"):
    return next(
        block
        for block in payload["psd_blocks"]
        if block["identifier"] == identifier
    )


def _rewrite_json(path, mutate):
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_bytes(canonical_json_bytes(payload))


class KyFanStructureCheckerTests(unittest.TestCase):
    def setUp(self):
        self.structure = build_global_kyfan_structure(
            4,
            2,
            "sound",
        )

    def test_checker_accepts_exact_sparse_structure(self):
        with TemporaryDirectory() as directory:
            binding = export_shared_structure(
                self.structure,
                Path(directory) / "shared",
            )
            summary = verify_kyfan_structure(binding.directory)

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["size"], 4)
        self.assertEqual(summary["hierarchy"], "global-d2")
        self.assertTrue(summary["sound_localizers"])

    def test_checker_accepts_local_structure_and_bound_instance(self):
        structure = build_local_kyfan_structure(
            8,
            LOCAL_LEVELS[0],
            "sound",
        )
        instance = build_kyfan_instance(
            structure,
            Fraction(3),
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            binding = export_shared_structure(
                structure,
                root / "shared",
            )
            problem = root / "cells" / "cell" / "problem"
            export_kyfan_instance(instance, binding, problem)

            summary = verify_bound_kyfan_structure(problem, root)

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["hierarchy"], "L0")
        self.assertEqual(summary["detuning"], "3/1")

    def test_checker_rejects_lower_triangle_entry(self):
        payload = structure_payload(self.structure)
        block = next(
            item
            for item in payload["psd_blocks"]
            if any(
                entry["row"] < entry["column"]
                for entry in item["upper_entries"]
            )
        )
        entry = next(
            item
            for item in block["upper_entries"]
            if item["row"] < item["column"]
        )
        entry["row"], entry["column"] = (
            entry["column"],
            entry["row"],
        )

        with self.assertRaisesRegex(ValueError, "upper triangle"):
            validate_structure_payload(payload)

    def test_checker_rejects_duplicate_sparse_coordinate(self):
        payload = structure_payload(self.structure)
        block = _block(payload)
        block["upper_entries"].append(
            dict(block["upper_entries"][0])
        )

        with self.assertRaisesRegex(ValueError, "duplicate sparse coordinate"):
            validate_structure_payload(payload)

    def test_checker_rejects_detuning_in_structure(self):
        payload = structure_payload(self.structure)
        payload["detuning"] = "1/2"

        with self.assertRaisesRegex(ValueError, "keys mismatch"):
            validate_structure_payload(payload)

    def test_checker_rejects_changed_xz_phase(self):
        payload = structure_payload(self.structure)
        x_index = payload["moment_basis"].index([[0, "X"]])
        z_index = payload["moment_basis"].index([[0, "Z"]])
        row, column = sorted((x_index, z_index))
        entry = next(
            item
            for item in _block(payload)["upper_entries"]
            if (item["row"], item["column"]) == (row, column)
        )
        variable, coefficient = entry["form"]["imag"]["terms"][0]
        numerator, denominator = coefficient.split("/")
        entry["form"]["imag"]["terms"][0] = [
            variable,
            f"{-int(numerator)}/{denominator}",
        ]

        with self.assertRaisesRegex(ValueError, "moment product"):
            validate_structure_payload(payload)

    def test_checker_rejects_missing_right_support_localizer(self):
        payload = structure_payload(self.structure)
        target = next(
            index
            for index, row in enumerate(payload["equalities"])
            if row["provenance"].get("localizer_kind")
            == "right-support"
        )
        del payload["equalities"][target]

        with self.assertRaisesRegex(ValueError, "right-support localizer"):
            validate_structure_payload(payload)

    def test_checker_rejects_missing_reflected_clique_image(self):
        payload = structure_payload(self.structure)
        target = next(
            index
            for index, image in enumerate(payload["clique_images"])
            if image["reflected"]
        )
        del payload["clique_images"][target]

        with self.assertRaisesRegex(ValueError, "clique image"):
            validate_structure_payload(payload)

    def test_checker_rejects_changed_constrained_trace(self):
        payload = structure_payload(self.structure)
        target = next(
            row
            for row in payload["constrained_trace_table"]
            if row["value"] != {"real": "0/1", "imag": "0/1"}
        )
        target["value"]["real"] = "999/1"

        with self.assertRaisesRegex(ValueError, "constrained trace"):
            validate_structure_payload(payload)

    def test_resolver_rejects_escape_and_absolute_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "cells" / "cell" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")

            for reference in (
                "../../../../escape.json",
                str((root / "absolute.json").resolve()),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "artifact reference",
                ):
                    resolve_bound_path(manifest, reference, root)

    def test_resolver_rejects_symlink_leaving_run_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            outside = Path(directory) / "outside"
            manifest = root / "cells" / "cell" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            outside.mkdir()
            (root / "escape").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(
                ValueError,
                "artifact reference",
            ):
                resolve_bound_path(
                    manifest,
                    "../../../escape/structure.json",
                    root,
                )

    def test_stale_shared_manifest_rejects_refreshed_cell_hash(self):
        instance = build_kyfan_instance(
            self.structure,
            Fraction(1, 2),
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            binding = export_shared_structure(
                self.structure,
                root / "shared",
            )
            problem = root / "cells" / "cell" / "problem"
            export_kyfan_instance(instance, binding, problem)

            _rewrite_json(
                binding.structure_path,
                lambda payload: payload["provenance"].update(
                    {"tampered": True}
                ),
            )
            changed_digest = hashlib.sha256(
                binding.structure_path.read_bytes()
            ).hexdigest()
            cell_manifest_path = problem / "manifest.json"
            _rewrite_json(
                cell_manifest_path,
                lambda payload: payload.update(
                    {"structure_sha256": changed_digest}
                ),
            )

            with self.assertRaisesRegex(
                ValueError,
                "shared manifest",
            ):
                verify_bound_kyfan_structure(problem, root)

    def test_checker_has_no_candidate_builder_imports(self):
        source = (
            ROOT
            / "src/challenge233/sdp/verify_kyfan_structure.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "challenge233.sdp.kyfan import",
            "challenge233.sdp.kyfan_sparse",
            "challenge233.sdp.kyfan_v2_artifact",
            "challenge233.sdp.exact_linalg",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
