import csv
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


def write_valid_run(output_directory: Path) -> None:
    output_directory.mkdir()
    data_path = output_directory / "ed-gap.csv"
    fieldnames = [
        "size",
        "detuning",
        "basis_dimension",
        "e0",
        "e1",
        "e2",
        "e3",
        "gap",
        "residual_0",
        "residual_1",
        "residual_2",
        "residual_3",
        "max_residual",
        "hermiticity_max_abs",
        "matrix_nnz",
        "wall_seconds",
    ]
    with data_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "size": 4,
                "detuning": 0.0,
                "basis_dimension": 7,
                "e0": -2.0,
                "e1": -1.5,
                "e2": -1.0,
                "e3": -0.5,
                "gap": 0.5,
                "residual_0": 1e-13,
                "residual_1": 2e-13,
                "residual_2": 3e-13,
                "residual_3": 4e-13,
                "max_residual": 4e-13,
                "hermiticity_max_abs": 0.0,
                "matrix_nnz": 12,
                "wall_seconds": 0.01,
            }
        )

    states_path = output_directory / "basis-states-N0004.npy"
    states_path.write_bytes(b"fixture basis ordering")
    manifest = {
        "point_count": 1,
        "sizes": [4],
        "detunings": [0.0],
        "data_file": data_path.name,
        "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "basis_state_files": {
            "4": {
                "path": states_path.name,
                "count": 7,
                "sha256": hashlib.sha256(states_path.read_bytes()).hexdigest(),
            }
        },
        "source_file_sha256": {
            relative_path: hashlib.sha256(
                (ROOT / relative_path).read_bytes()
            ).hexdigest()
            for relative_path in (
                "src/challenge233/basis/pxp.py",
                "src/challenge233/ed/pxp_gap.py",
            )
        },
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


class PXPEDArtifactVerifierTests(unittest.TestCase):
    def test_valid_run_reports_checked_summary(self):
        from challenge233.ed.verify_pxp_gap import verify_run

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            summary = verify_run(output_directory)

        self.assertEqual(summary["point_count"], 1)
        self.assertEqual(summary["minimum_gap"], 0.5)
        self.assertEqual(summary["maximum_residual"], 4e-13)
        self.assertEqual(summary["maximum_hermiticity_error"], 0.0)

    def test_rejects_corrupted_csv_checksum(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            with (output_directory / "ed-gap.csv").open("a") as handle:
                handle.write("corruption\n")

            with self.assertRaisesRegex(VerificationError, "data SHA-256"):
                verify_run(output_directory)

    def test_rejects_gap_inconsistent_with_eigenvalues(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            data_path = output_directory / "ed-gap.csv"
            with data_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["gap"] = "0.6"
            with data_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["data_sha256"] = hashlib.sha256(
                data_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "gap"):
                verify_run(output_directory)

    def test_rejects_wrong_periodic_blockade_dimension(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            data_path = output_directory / "ed-gap.csv"
            with data_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["basis_dimension"] = "8"
            with data_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["data_sha256"] = hashlib.sha256(
                data_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "Lucas"):
                verify_run(output_directory)

    def test_rejects_large_eigenpair_residual(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            data_path = output_directory / "ed-gap.csv"
            with data_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["residual_3"] = "1e-5"
            rows[0]["max_residual"] = "1e-5"
            with data_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["data_sha256"] = hashlib.sha256(
                data_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "residual"):
                verify_run(output_directory)

    def test_rejects_nonhermitian_sparse_operator(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            data_path = output_directory / "ed-gap.csv"
            with data_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["hermiticity_max_abs"] = "1e-6"
            with data_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["data_sha256"] = hashlib.sha256(
                data_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "Hermiticity"):
                verify_run(output_directory)

    def test_rejects_incomplete_cartesian_grid(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["sizes"] = [4, 5]
            states_path = output_directory / "basis-states-N0005.npy"
            states_path.write_bytes(b"fixture N=5 basis ordering")
            manifest["basis_state_files"]["5"] = {
                "path": states_path.name,
                "count": 11,
                "sha256": hashlib.sha256(states_path.read_bytes()).hexdigest(),
            }
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "grid"):
                verify_run(output_directory)

    def test_rejects_corrupted_basis_ordering_file(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            with (output_directory / "basis-states-N0004.npy").open("ab") as handle:
                handle.write(b"corruption")

            with self.assertRaisesRegex(VerificationError, "basis-state SHA-256"):
                verify_run(output_directory)

    def test_rejects_source_hash_mismatch(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["source_file_sha256"][
                "src/challenge233/ed/pxp_gap.py"
            ] = "0" * 64
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "source SHA-256"):
                verify_run(output_directory)

    def test_rejects_unsorted_low_energy_values(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            data_path = output_directory / "ed-gap.csv"
            with data_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["e2"] = "-1.75"
            with data_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["data_sha256"] = hashlib.sha256(
                data_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "eigenvalue order"):
                verify_run(output_directory)

    def test_rejects_incorrect_maximum_residual(self):
        from challenge233.ed.verify_pxp_gap import (
            VerificationError,
            verify_run,
        )

        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            data_path = output_directory / "ed-gap.csv"
            with data_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = list(rows[0])
            rows[0]["max_residual"] = "1e-14"
            with data_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = output_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["data_sha256"] = hashlib.sha256(
                data_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest))

            with self.assertRaisesRegex(VerificationError, "maximum residual"):
                verify_run(output_directory)

    def test_module_cli_prints_verified_json_summary(self):
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "run"
            write_valid_run(output_directory)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "challenge233.ed.verify_pxp_gap",
                    str(output_directory),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=30,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["point_count"], 1)


if __name__ == "__main__":
    unittest.main()
