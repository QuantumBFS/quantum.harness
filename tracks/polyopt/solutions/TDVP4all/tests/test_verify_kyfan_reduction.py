import hashlib
import json
from fractions import Fraction
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.kyfan_presolve import (  # noqa: E402
    build_kyfan_solver_reduction,
)
from challenge233.sdp.kyfan_sparse import (  # noqa: E402
    build_kyfan_instance,
    build_global_kyfan_structure,
    build_local_kyfan_structure,
)
from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402
from challenge233.sdp.kyfan_v2_artifact import (  # noqa: E402
    canonical_json_bytes,
    export_shared_structure,
    export_solver_reduction,
    export_kyfan_instance,
    logical_structure_sha256,
)
from challenge233.sdp.verify_kyfan_reduction import (  # noqa: E402
    verify_kyfan_reduction,
)


class KyFanReductionVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temporary = TemporaryDirectory()
        cls._root = Path(cls._temporary.name)
        structure = build_global_kyfan_structure(4, 2, "sound")
        reduction = build_kyfan_solver_reduction(
            structure,
            logical_structure_sha256(structure),
        )
        binding = export_shared_structure(
            structure,
            cls._root / "shared",
        )
        cls._base = export_solver_reduction(
            reduction,
            binding,
        ).directory
        cls._mutation_index = 0

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def _mutated(self, mutate, *, refresh_hash=True):
        type(self)._mutation_index += 1
        destination = (
            self._base.parent
            / f"mutation-{type(self)._mutation_index}"
        )
        shutil.copytree(self._base, destination)
        reduction_path = destination / "solver-reduction.json"
        payload = json.loads(
            reduction_path.read_text(encoding="utf-8")
        )
        mutate(payload)
        reduction_bytes = canonical_json_bytes(payload)
        reduction_path.write_bytes(reduction_bytes)
        if refresh_hash:
            manifest_path = destination / "manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["reduction_bytes"] = len(reduction_bytes)
            manifest["reduction_sha256"] = hashlib.sha256(
                reduction_bytes
            ).hexdigest()
            manifest_path.write_bytes(
                canonical_json_bytes(manifest)
            )
        return destination

    def test_exported_reduction_is_independently_recomputed(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        reduction = build_kyfan_solver_reduction(
            structure,
            logical_structure_sha256(structure),
        )
        with TemporaryDirectory() as directory:
            binding = export_shared_structure(
                structure,
                Path(directory) / "shared",
            )
            reduction_binding = export_solver_reduction(
                reduction,
                binding,
            )
            problem_directory = (
                Path(directory) / "cells/n4-d2/problem"
            )
            export_kyfan_instance(
                build_kyfan_instance(
                    structure,
                    Fraction(1, 2),
                ),
                binding,
                problem_directory,
                reduction_binding,
            )

            summary = verify_kyfan_reduction(
                problem_directory
            )

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["structure_sha256"], binding.structure_sha256)
        self.assertEqual(
            summary["reduction_sha256"],
            reduction_binding.reduction_sha256,
        )
        self.assertEqual(
            summary["reduced_psd_dimensions"],
            [13, 2, 11, 3, 11] * 2,
        )

    def test_checker_does_not_import_candidate_reduction_module(self):
        source = (
            ROOT
            / "src/challenge233/sdp/verify_kyfan_reduction.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("import challenge233.sdp.kyfan_presolve", source)
        self.assertNotIn("from challenge233.sdp.kyfan_presolve", source)

    def test_reduction_payload_contains_no_cell_overlay(self):
        structure = build_global_kyfan_structure(4, 2, "sound")
        reduction = build_kyfan_solver_reduction(
            structure,
            logical_structure_sha256(structure),
        )
        with TemporaryDirectory() as directory:
            binding = export_shared_structure(
                structure,
                Path(directory) / "shared",
            )
            reduction_binding = export_solver_reduction(
                reduction,
                binding,
            )
            payload = json.loads(
                reduction_binding.reduction_path.read_text(
                    encoding="utf-8"
                )
            )

        for forbidden in (
            "detuning",
            "trial_manifest",
            "solver_status",
            "cell_identifier",
        ):
            self.assertNotIn(forbidden, payload)

    def test_checker_rejects_changed_odd_y_phase(self):
        def mutate(payload):
            phases = payload["conjugation"]["phases"]
            phases[1] = 1 - phases[1]

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "conjugation phase inventory",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_changed_legal_domain(self):
        def mutate(payload):
            payload["quotient"]["legal_inputs"].pop()

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "legal-input domain",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_removed_periodic_wrap(self):
        def mutate(payload):
            payload["quotient"]["legal_inputs"] = [
                state
                for state in range(16)
                if all(
                    not (
                        (state >> site) & 1
                        and (state >> (site + 1)) & 1
                    )
                    for site in range(3)
                )
            ]

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "legal-input domain",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_changed_kernel_coefficient(self):
        def mutate(payload):
            coefficient = payload["quotient"]["kernel"][0][0][1]
            coefficient["real"] = (
                "2/1"
                if coefficient["real"] != "2/1"
                else "3/1"
            )

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "quotient kernel",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_changed_generic_degree(self):
        def mutate(payload):
            generic = next(
                block
                for block in payload["spatial"]
                if block["irrep_label"] == "generic-k1-k3"
            )
            generic["irrep_degree"] = 1

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "spatial block irrep_degree",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_missing_local_reflection_parity(self):
        structure = build_local_kyfan_structure(
            8,
            LOCAL_LEVELS[0],
            "sound",
        )
        reduction = build_kyfan_solver_reduction(
            structure,
            logical_structure_sha256(structure),
        )
        binding = export_shared_structure(
            structure,
            self._root / "local-shared",
        )
        reduction_binding = export_solver_reduction(
            reduction,
            binding,
        )
        original_base = self._base
        self._base = reduction_binding.directory
        try:
            path = self._mutated(
                lambda payload: payload["spatial"].pop()
            )
        finally:
            self._base = original_base

        with self.assertRaisesRegex(
            ValueError,
            "spatial block inventory",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_changed_equality_span(self):
        def mutate(payload):
            span_map = payload["equality"]["span_map"]
            term = next(
                terms[0]
                for terms in span_map.values()
                if terms
            )
            term[1] = "-1/1" if term[1] == "1/1" else "1/1"

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "span-map reconstruction",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_changed_equality_nullspace(self):
        def mutate(payload):
            nullspace = payload["equality"][
                "parameterization"
            ]["nullspace"]
            term = next(column[0] for column in nullspace if column)
            term[1] = "-1/1" if term[1] == "1/1" else "1/1"

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "parameterization nullspace",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_source_hash_change(self):
        def mutate(payload):
            hashes = payload["source_file_sha256"]
            key = sorted(hashes)[0]
            hashes[key] = "0" * 64

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "source SHA-256",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_unbound_reduction_hash(self):
        def mutate(payload):
            statistics = payload["statistics"]
            statistics["reduced_psd_nonzeros"] += 1

        path = self._mutated(
            mutate,
            refresh_hash=False,
        )
        with self.assertRaisesRegex(
            ValueError,
            "reduction SHA-256 binding",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_raw_direct_solver_view(self):
        def mutate(payload):
            block = payload["psd_blocks"][0]
            block["dimension"] = payload["statistics"][
                "original_test_dimension"
            ]

        path = self._mutated(mutate)
        with self.assertRaisesRegex(
            ValueError,
            "reduced PSD block metadata",
        ):
            verify_kyfan_reduction(path)

    def test_checker_rejects_detuning_in_reduction(self):
        path = self._mutated(
            lambda payload: payload.update({"detuning": "1/2"})
        )
        with self.assertRaisesRegex(
            ValueError,
            "solver reduction keys mismatch",
        ):
            verify_kyfan_reduction(path)


if __name__ == "__main__":
    unittest.main()
