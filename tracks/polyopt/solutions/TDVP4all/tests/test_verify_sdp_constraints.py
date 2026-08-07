import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.algebra import PauliWord  # noqa: E402
from challenge233.sdp.artifact import (  # noqa: E402
    export_constraint_map,
)
from challenge233.sdp.basis import close_word_basis  # noqa: E402
from challenge233.sdp.constraints import (  # noqa: E402
    build_constraint_map,
)
from challenge233.sdp.verify_constraint_map import (  # noqa: E402
    ConstraintVerificationError,
    verify_constraint_map,
)


def build_valid_map():
    basis = close_word_basis(
        (
            PauliWord(),
            PauliWord(((0, "X"),)),
            PauliWord(((0, "Z"),)),
        ),
        size=4,
    )
    return build_constraint_map(
        size=4,
        moment_basis=basis,
        localizer_basis=basis,
    )


def export_valid_map(output_directory: Path) -> None:
    export_constraint_map(build_valid_map(), output_directory)


def rewrite_payload(output_directory: Path, mutate) -> None:
    output_directory = Path(output_directory)
    data_path = output_directory / "constraint-map.json"
    manifest_path = output_directory / "manifest.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    mutate(payload)
    data_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    manifest["data_sha256"] = hashlib.sha256(
        data_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def corrupt_xz_phase(payload):
    x_index = payload["moment_basis"].index([[0, "X"]])
    z_index = payload["moment_basis"].index([[0, "Z"]])
    entry = next(
        item
        for item in payload["moment_entries"]
        if item["row"] == x_index
        and item["column"] == z_index
    )
    entry["polynomial"][0]["coefficient"]["imag"] = "1/1"


def delete_reflected_localizer(payload):
    target = next(
        index
        for index, row in enumerate(payload["zero_localizers"])
        if row["site"] == payload["size"] - 1
    )
    del payload["zero_localizers"][target]


def corrupt_reflection_permutation(payload):
    reflection_index = payload["group_elements"].index(
        {"shift": 0, "reflected": True}
    )
    permutation = payload["moment_basis_permutations"][
        reflection_index
    ]
    permutation[0], permutation[1] = (
        permutation[1],
        permutation[0],
    )


def remove_negative_momentum(payload):
    generic = next(
        item
        for item in payload["irrep_catalog"]
        if len(item["momenta"]) == 2
    )
    generic["momenta"] = generic["momenta"][:1]


def corrupt_reflection_parity(payload):
    self_inverse = next(
        item
        for item in payload["irrep_catalog"]
        if item["label"] == "k=0,r=+1"
    )
    self_inverse["reflection_parity"] = -1


def add_forbidden_state_invariance(payload):
    payload["moment_invariance_equalities"] = []


class ConstraintArtifactTests(unittest.TestCase):
    def test_independent_checker_accepts_complete_map(self):
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            export_valid_map(output_directory)
            summary = verify_constraint_map(output_directory)
            manifest = json.loads(
                (output_directory / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(summary["size"], 4)
        self.assertEqual(summary["group_order"], 8)
        self.assertEqual(summary["localizer_site_count"], 4)
        self.assertEqual(summary["status"], "verified")
        self.assertEqual(
            manifest["purpose"],
            "legacy-structural-arbitrary-sandwich-not-solver-input",
        )
        self.assertEqual(
            manifest["localizer_semantics"],
            "unsound-for-state-support",
        )

    def test_checker_accepts_odd_size_and_distinct_bases(self):
        moment_basis = close_word_basis(
            (PauliWord(((0, "X"),)),),
            size=5,
        )
        constraint_map = build_constraint_map(
            size=5,
            moment_basis=moment_basis,
            localizer_basis=(PauliWord(),),
        )
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            export_constraint_map(
                constraint_map,
                output_directory,
            )
            summary = verify_constraint_map(output_directory)

        self.assertEqual(summary["size"], 5)
        self.assertEqual(summary["group_order"], 10)
        self.assertEqual(summary["localizer_site_count"], 5)

    def test_export_is_byte_deterministic(self):
        constraint_map = build_valid_map()
        with TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first"
            second = Path(temporary_directory) / "second"
            export_constraint_map(constraint_map, first)
            export_constraint_map(constraint_map, second)
            for filename in (
                "constraint-map.json",
                "manifest.json",
            ):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        (first / filename).read_bytes(),
                        (second / filename).read_bytes(),
                    )

    def test_checker_has_no_candidate_sdp_imports(self):
        verifier_path = (
            ROOT
            / "src/challenge233/sdp/verify_constraint_map.py"
        )
        tree = ast.parse(
            verifier_path.read_text(encoding="utf-8")
        )
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(
                    alias.name for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(node.module or "")
        self.assertFalse(
            any(
                module.startswith("challenge233.sdp")
                for module in imported_modules
            ),
            imported_modules,
        )

    def _assert_mutation_rejected(self, mutation, message):
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            export_valid_map(output_directory)
            rewrite_payload(output_directory, mutation)
            with self.assertRaisesRegex(
                ConstraintVerificationError,
                message,
            ):
                verify_constraint_map(output_directory)

    def test_rejects_corrupted_xz_moment_phase(self):
        self._assert_mutation_rejected(
            corrupt_xz_phase,
            "moment product",
        )

    def test_rejects_missing_reflected_localizer(self):
        self._assert_mutation_rejected(
            delete_reflected_localizer,
            "localizer row count",
        )

    def test_rejects_corrupted_reflection_permutation(self):
        self._assert_mutation_rejected(
            corrupt_reflection_permutation,
            "reflection permutation",
        )

    def test_rejects_missing_negative_momentum_partner(self):
        self._assert_mutation_rejected(
            remove_negative_momentum,
            "momentum pair",
        )

    def test_rejects_corrupted_self_inverse_reflection_parity(self):
        self._assert_mutation_rejected(
            corrupt_reflection_parity,
            "reflection parity",
        )

    def test_rejects_forbidden_state_moment_invariance(self):
        self._assert_mutation_rejected(
            add_forbidden_state_invariance,
            "unknown key",
        )

    def test_module_cli_accepts_valid_and_rejects_mutated_map(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        with TemporaryDirectory() as temporary_directory:
            valid_directory = Path(temporary_directory) / "valid"
            invalid_directory = Path(temporary_directory) / "invalid"
            export_valid_map(valid_directory)
            export_valid_map(invalid_directory)
            rewrite_payload(
                invalid_directory,
                add_forbidden_state_invariance,
            )
            valid = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "challenge233.sdp.verify_constraint_map",
                    str(valid_directory),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )
            invalid = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "challenge233.sdp.verify_constraint_map",
                    str(invalid_directory),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )

        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(
            json.loads(valid.stdout)["status"],
            "verified",
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("unknown key", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
