import hashlib
import json
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from challenge233.sdp.kyfan import (  # noqa: E402
    build_global_kyfan_problem,
    build_local_kyfan_problem,
)
from challenge233.sdp.hierarchy import LOCAL_LEVELS  # noqa: E402
from challenge233.sdp.kyfan_artifact import (  # noqa: E402
    export_kyfan_problem,
)
from challenge233.sdp.verify_kyfan_problem import (  # noqa: E402
    verify_kyfan_problem,
)


def rewrite_problem(output_directory, mutate):
    output_directory = Path(output_directory)
    problem_path = output_directory / "problem.json"
    manifest_path = output_directory / "manifest.json"
    payload = json.loads(problem_path.read_text(encoding="utf-8"))
    mutate(payload)
    problem_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["problem_sha256"] = hashlib.sha256(
        problem_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def corrupt_xz_phase(payload):
    x_index = payload["moment_basis"].index([[0, "X"]])
    z_index = payload["moment_basis"].index([[0, "Z"]])
    entry = payload["unrealified_psd_blocks"][0]["entries"][
        x_index
    ][z_index]
    variable, coefficient = entry["imag"]["terms"][0]
    numerator, denominator = coefficient.split("/")
    entry["imag"]["terms"][0] = [
        variable,
        f"{-int(numerator)}/{denominator}",
    ]


def delete_right_support(payload):
    target = next(
        index
        for index, row in enumerate(payload["equalities"])
        if row["provenance"].get("localizer_kind")
        == "right-support"
    )
    del payload["equalities"][target]


def relabel_safe_sandwich(payload):
    target = next(
        row
        for row in payload["equalities"]
        if row["provenance"].get("localizer_kind")
        == "safe-sandwich"
    )
    target["provenance"]["localizer_kind"] = "bare-pauli-sandwich"


def delete_reflected_clique_image(payload):
    target = next(
        index
        for index, image in enumerate(payload["clique_images"])
        if image["reflected"]
    )
    del payload["clique_images"][target]


def corrupt_identity_constrained_trace(payload):
    identity = next(
        row
        for row in payload["constrained_trace_table"]
        if row["word"] == []
    )
    identity["value"] += 1


def corrupt_realification_sign(payload):
    gamma = next(
        block
        for block in payload["psd_blocks"]
        if block["identifier"] == "gamma"
    )
    target = next(
        entry
        for row in gamma["entries"]
        for entry in row
        if entry["terms"]
    )
    variable, coefficient = target["terms"][0]
    numerator, denominator = coefficient.split("/")
    target["terms"][0] = [
        variable,
        f"{-int(numerator)}/{denominator}",
    ]


def delete_magnitude_witness(payload):
    del payload["magnitude_witnesses"][0]


class KyFanProblemArtifactTests(unittest.TestCase):
    def setUp(self):
        self.problem = build_global_kyfan_problem(
            4,
            Fraction(1, 2),
            2,
        )

    def test_problem_export_is_deterministic_and_independently_checked(self):
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            export_kyfan_problem(self.problem, first)
            export_kyfan_problem(self.problem, second)
            self.assertEqual(
                (Path(first) / "problem.json").read_bytes(),
                (Path(second) / "problem.json").read_bytes(),
            )
            summary = verify_kyfan_problem(first)
        self.assertEqual(summary["size"], 4)
        self.assertEqual(summary["detuning"], "1/2")
        self.assertTrue(summary["sound_localizers"])
        self.assertEqual(summary["status"], "verified")

    def _assert_mutation_rejected(self, mutation, message):
        with TemporaryDirectory() as directory:
            export_kyfan_problem(self.problem, directory)
            rewrite_problem(directory, mutation)
            with self.assertRaisesRegex(ValueError, message):
                verify_kyfan_problem(directory)

    def test_rejects_corrupted_xz_phase(self):
        self._assert_mutation_rejected(
            corrupt_xz_phase,
            "moment product",
        )

    def test_rejects_missing_right_support_localizer(self):
        self._assert_mutation_rejected(
            delete_right_support,
            "right-support localizer",
        )

    def test_rejects_bare_pauli_sandwich_label(self):
        self._assert_mutation_rejected(
            relabel_safe_sandwich,
            "safe-sandwich localizer semantics",
        )

    def test_rejects_missing_reflected_clique_image(self):
        self._assert_mutation_rejected(
            delete_reflected_clique_image,
            "clique image",
        )

    def test_rejects_corrupted_constrained_trace(self):
        self._assert_mutation_rejected(
            corrupt_identity_constrained_trace,
            "constrained trace",
        )

    def test_rejects_corrupted_realification(self):
        self._assert_mutation_rejected(
            corrupt_realification_sign,
            "realification",
        )

    def test_rejects_missing_psd_magnitude_witness(self):
        self._assert_mutation_rejected(
            delete_magnitude_witness,
            "PSD magnitude witness",
        )

    def test_rejects_manifest_hash_mismatch(self):
        with TemporaryDirectory() as directory:
            export_kyfan_problem(self.problem, directory)
            manifest_path = Path(directory) / "manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["problem_sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_kyfan_problem(directory)

    def test_checker_does_not_import_candidate_problem_modules(self):
        source = (
            ROOT
            / "src/challenge233/sdp/verify_kyfan_problem.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "challenge233.sdp.algebra",
            "challenge233.sdp.localizers",
            "challenge233.sdp.constrained_trace",
            "challenge233.sdp.hierarchy",
            "challenge233.sdp.kyfan",
        ):
            self.assertNotIn(forbidden, source)

    def test_copied_artifact_is_checked_without_solver_state(self):
        with TemporaryDirectory() as directory:
            first = Path(directory) / "first"
            copied = Path(directory) / "copied"
            export_kyfan_problem(self.problem, first)
            shutil.copytree(first, copied)
            summary = verify_kyfan_problem(copied)
        self.assertEqual(summary["status"], "verified")

    def test_local_l0_problem_round_trips_with_complete_orbit_map(self):
        problem = build_local_kyfan_problem(
            5,
            Fraction(1, 2),
            LOCAL_LEVELS[0],
        )
        with TemporaryDirectory() as directory:
            export_kyfan_problem(problem, directory)
            summary = verify_kyfan_problem(directory)
        self.assertEqual(summary["hierarchy"], "L0")
        self.assertEqual(summary["size"], 5)

    def test_module_cli_prints_verified_summary(self):
        with TemporaryDirectory() as directory:
            export_kyfan_problem(self.problem, directory)
            environment = {
                **dict(os.environ),
                "PYTHONPATH": str(ROOT / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "challenge233.sdp.verify_kyfan_problem",
                    directory,
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "verified")


if __name__ == "__main__":
    unittest.main()
