import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


TESTS_DIR = Path(__file__).resolve().parent
SOLUTION_DIR = TESTS_DIR.parent
SCRIPT = SOLUTION_DIR / "generate_test_outputs.py"

EXPECTED_ASSET_BYTES = 61068
EXPECTED_ASSET_SHA256 = (
    "c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b"
)
EXPECTED_OUTPUT_SHA256 = {
    "A": "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
    "B": "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
    "C": "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
    "D": "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
}

CASES = (
    {
        "id": "A",
        "operation": "addition",
        "input_width": 16,
        "output_width": 9,
        "rows": 2000,
        "member": "occam-circuit/datasets/mystery-A/test_inputs.csv",
        "inputs": (
            "1000000001000000",  # 1, 2
            "0010000010000000",  # 4, 1
            "1000000001000000",  # duplicate: row order must be preserved
        ),
        "expected_prefix": (
            "input,output",
            "1000000001000000,110000000",  # 1 + 2 = 3
            "0010000010000000,101000000",  # 4 + 1 = 5
            "1000000001000000,110000000",
        ),
    },
    {
        "id": "B",
        "operation": "absolute_difference",
        "input_width": 14,
        "output_width": 7,
        "rows": 2000,
        "member": "occam-circuit/datasets/mystery-B/test_inputs.csv",
        "inputs": (
            "10000000100000",  # 1, 2
            "11000001000000",  # 3, 1
            "10000000100000",
        ),
        "expected_prefix": (
            "input,output",
            "10000000100000,1000000",  # abs(1 - 2) = 1
            "11000001000000,0100000",  # abs(3 - 1) = 2
            "10000000100000,1000000",
        ),
    },
    {
        "id": "C",
        "operation": "multiplication",
        "input_width": 12,
        "output_width": 12,
        "rows": 1500,
        "member": "occam-circuit/datasets/mystery-C/test_inputs.csv",
        "inputs": (
            "110000101000",  # 3, 5
            "010000001000",  # 2, 4
            "110000101000",
        ),
        "expected_prefix": (
            "input,output",
            "110000101000,111100000000",  # 3 * 5 = 15
            "010000001000,000100000000",  # 2 * 4 = 8
            "110000101000,111100000000",
        ),
    },
    {
        "id": "D",
        "operation": "sum_of_squares",
        "input_width": 10,
        "output_width": 11,
        "rows": 624,
        "member": "occam-circuit/datasets/mystery-D/test_inputs.csv",
        "inputs": (
            "1100000100",  # 3, 4
            "1000001000",  # 1, 2
            "1100000100",
        ),
        "expected_prefix": (
            "input,output",
            "1100000100,10011000000",  # 3**2 + 4**2 = 25
            "1000001000,10100000000",  # 1**2 + 2**2 = 5
            "1100000100,10011000000",
        ),
    },
)


def load_generator():
    if not SCRIPT.is_file():
        raise AssertionError(
            "generate_test_outputs.py has not been implemented"
        )
    module_name = "life_is_short_generate_test_outputs_test_target"
    spec = importlib.util.spec_from_file_location(module_name, str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SOLUTION_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.path[0]
    return module


def fixture_release(overrides=None):
    overrides = overrides or {}
    member_bytes = {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_STORED
    ) as archive:
        for case in CASES:
            inputs = list(case["inputs"])
            inputs.extend(
                ["0" * case["input_width"]]
                * (case["rows"] - len(inputs))
            )
            payload = (
                "input\n" + "\n".join(inputs) + "\n"
            ).encode("ascii")
            payload = overrides.get(case["member"], payload)
            member_bytes[case["member"]] = payload
            archive.writestr(case["member"], payload)

        archive.writestr(
            "occam-circuit/datasets/mystery-A/test_outputs.csv",
            b"withheld output decoy: must never be read\n",
        )
        archive.writestr(
            "occam-circuit/secret/withheld-test-output.csv",
            b"withheld output decoy: must never be read\n",
        )
    return buffer.getvalue(), member_bytes


@contextlib.contextmanager
def accept_fixture_release(module, release_bytes):
    with mock.patch.object(
        module, "EXPECTED_ASSET_BYTES", len(release_bytes)
    ), mock.patch.object(
        module,
        "EXPECTED_ASSET_SHA256",
        hashlib.sha256(release_bytes).hexdigest(),
    ):
        yield


def invoke_main(module, release_path, output_directory):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        returncode = module.main(
            [
                "--asset",
                str(release_path),
                "--output-dir",
                str(output_directory),
            ]
        )
    return returncode, stdout.getvalue(), stderr.getvalue()


class DeterministicDeliverableTests(unittest.TestCase):
    def test_generates_strict_ordered_outputs_and_canonical_provenance(self):
        """Catches wrong semantics, endianness, widths, order, or JSON bytes."""

        module = load_generator()
        release_bytes, member_bytes = fixture_release()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            asset = root / "official.zip"
            asset.write_bytes(release_bytes)
            first_output = root / "first"
            second_output = root / "second"

            with accept_fixture_release(module, release_bytes):
                first = invoke_main(module, asset, first_output)
                second = invoke_main(module, asset, second_output)

            self.assertEqual(first[0], 0, msg=first[2])
            self.assertEqual(second[0], 0, msg=second[2])
            self.assertEqual(first[2], "")
            self.assertEqual(second[2], "")
            self.assertEqual(first[1], second[1])

            report = json.loads(first[1])
            canonical = (
                json.dumps(
                    report,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                + "\n"
            )
            self.assertEqual(first[1], canonical)
            self.assertEqual(
                report["schema"],
                "challenge71-public-test-predictions/v1",
            )
            self.assertEqual(
                report["classification"],
                (
                    "public-input predictions and candidate-circuit "
                    "self-consistency; not hidden-test accuracy"
                ),
            )
            self.assertEqual(
                report["determinism"],
                {"randomness": "none", "seed": None},
            )
            self.assertEqual(
                report["official_release"],
                {
                    "bytes": len(release_bytes),
                    "sha256": hashlib.sha256(release_bytes).hexdigest(),
                },
            )
            self.assertEqual(
                report["safety"],
                {
                    "archive_member_listing_requested": False,
                    "member_payload_scope": (
                        "four literal public test_inputs.csv paths"
                    ),
                    "non_input_member_payloads_read": False,
                },
            )
            self.assertEqual(
                [record["dataset"] for record in report["predictions"]],
                ["mystery-A", "mystery-B", "mystery-C", "mystery-D"],
            )

            for case, record in zip(CASES, report["predictions"]):
                relative = (
                    Path("mystery-{}".format(case["id"]))
                    / "test_outputs.csv"
                )
                first_bytes = (first_output / relative).read_bytes()
                second_bytes = (second_output / relative).read_bytes()
                self.assertEqual(first_bytes, second_bytes)
                self.assertTrue(first_bytes.endswith(b"\n"))
                self.assertNotIn(b"\r", first_bytes)
                if os.name == "posix":
                    self.assertEqual(
                        stat.S_IMODE(
                            (first_output / relative).stat().st_mode
                        ),
                        0o644,
                    )

                lines = first_bytes.decode("ascii").splitlines()
                self.assertEqual(
                    tuple(lines[:4]), case["expected_prefix"]
                )
                self.assertEqual(len(lines), case["rows"] + 1)
                original_inputs = []
                for line in lines[1:]:
                    fields = line.split(",")
                    self.assertEqual(len(fields), 2)
                    input_bits, output_bits = fields
                    self.assertEqual(
                        len(input_bits), case["input_width"]
                    )
                    self.assertEqual(
                        len(output_bits), case["output_width"]
                    )
                    self.assertLessEqual(set(input_bits), {"0", "1"})
                    self.assertLessEqual(set(output_bits), {"0", "1"})
                    original_inputs.append(input_bits)

                expected_inputs = (
                    member_bytes[case["member"]]
                    .decode("ascii")
                    .splitlines()[1:]
                )
                self.assertEqual(original_inputs, expected_inputs)

                output_hash = hashlib.sha256(first_bytes).hexdigest()
                candidate = (
                    SOLUTION_DIR
                    / "mystery-{}.txt".format(case["id"])
                )
                self.assertEqual(
                    record["input"],
                    {
                        "archive_member": case["member"],
                        "rows": case["rows"],
                        "sha256": hashlib.sha256(
                            member_bytes[case["member"]]
                        ).hexdigest(),
                        "width": case["input_width"],
                    },
                )
                self.assertEqual(
                    record["output"]["bytes"], len(first_bytes)
                )
                self.assertEqual(
                    record["output"]["format"],
                    "input,output CSV; ASCII; LF; trailing LF",
                )
                self.assertEqual(
                    record["output"]["repository_relative_path"],
                    "predictions/mystery-{}/test_outputs.csv".format(
                        case["id"]
                    ),
                )
                self.assertEqual(
                    record["output"]["rows"], case["rows"]
                )
                self.assertEqual(
                    record["output"]["sha256"], output_hash
                )
                self.assertEqual(
                    record["output"]["width"], case["output_width"]
                )
                self.assertEqual(
                    record["candidate_circuit"]["relative_path"],
                    "mystery-{}.txt".format(case["id"]),
                )
                self.assertEqual(
                    record["candidate_circuit"]["sha256"],
                    hashlib.sha256(candidate.read_bytes()).hexdigest(),
                )
                circuit = module.evaluator.parse_netlist(
                    candidate.read_text(encoding="ascii"),
                    source=str(candidate),
                )
                self.assertEqual(
                    record["candidate_circuit"]["gate_count"],
                    len(circuit.gates),
                )
                self.assertTrue(
                    record["candidate_circuit"][
                        "all_public_input_rows_match"
                    ]
                )
                self.assertEqual(
                    record["encoding"], "LSB-first fixed width"
                )
                self.assertEqual(
                    record["operation"], case["operation"]
                )
                self.assertEqual(
                    record["published_commitment"],
                    {
                        "algorithm": "sha256",
                        "sha256": EXPECTED_OUTPUT_SHA256[case["id"]],
                        "whole_file_identity_match": (
                            output_hash
                            == EXPECTED_OUTPUT_SHA256[case["id"]]
                        ),
                    },
                )


class ArchiveBoundaryTests(unittest.TestCase):
    def test_reads_only_four_literal_public_input_members_without_scanning(self):
        """Catches enumeration, wildcard discovery, or withheld-member reads."""

        module = load_generator()
        release_bytes, _member_bytes = fixture_release()
        observed_reads = []
        real_zipfile = zipfile.ZipFile

        class LiteralReadOnlyArchive(object):
            def __init__(self, *args, **kwargs):
                self._archive = real_zipfile(*args, **kwargs)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self._archive.close()
                return False

            def read(self, member, *args, **kwargs):
                observed_reads.append(member)
                return self._archive.read(member, *args, **kwargs)

            def __getattr__(self, name):
                raise AssertionError(
                    "unexpected ZIP API access: {}".format(name)
                )

        def scanning_forbidden(*args, **kwargs):
            raise AssertionError("archive or filesystem scanning is forbidden")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            asset = root / "official.zip"
            asset.write_bytes(release_bytes)

            with accept_fixture_release(module, release_bytes), \
                    mock.patch.object(
                        module.zipfile,
                        "ZipFile",
                        side_effect=LiteralReadOnlyArchive,
                    ), mock.patch.object(
                        os, "listdir", side_effect=scanning_forbidden
                    ), mock.patch.object(
                        os, "scandir", side_effect=scanning_forbidden
                    ), mock.patch.object(
                        os, "walk", side_effect=scanning_forbidden
                    ), mock.patch.object(
                        module.Path, "glob", side_effect=scanning_forbidden
                    ), mock.patch.object(
                        module.Path, "rglob", side_effect=scanning_forbidden
                    ), mock.patch.object(
                        module.Path, "iterdir", side_effect=scanning_forbidden
                    ):
                module.generate_outputs(asset, root / "predictions")

        self.assertEqual(
            observed_reads,
            [case["member"] for case in CASES],
        )
        self.assertTrue(
            all(
                "test_outputs" not in member
                and "withheld" not in member
                for member in observed_reads
            )
        )

    def test_rejects_wrong_asset_before_zip_access_or_output_writes(self):
        """Catches accepting a repacked asset or validating after extraction."""

        module = load_generator()
        wrong_bytes = b"x" * EXPECTED_ASSET_BYTES

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            asset = root / "wrong.zip"
            asset.write_bytes(wrong_bytes)
            sentinel = (
                root
                / "predictions"
                / "mystery-A"
                / "test_outputs.csv"
            )
            sentinel.parent.mkdir(parents=True)
            sentinel.write_bytes(b"user sentinel\n")

            with mock.patch.object(
                module.zipfile,
                "ZipFile",
                side_effect=AssertionError(
                    "ZIP must not be opened before hash verification"
                ),
            ):
                with self.assertRaises(module.PredictionGenerationError) as raised:
                    module.generate_outputs(asset, root / "predictions")

            message = str(raised.exception)
            self.assertIn(EXPECTED_ASSET_SHA256, message)
            self.assertIn(
                hashlib.sha256(wrong_bytes).hexdigest(), message
            )
            self.assertEqual(sentinel.read_bytes(), b"user sentinel\n")
            self.assertFalse(
                (
                    root
                    / "predictions"
                    / "mystery-B"
                    / "test_outputs.csv"
                ).exists()
            )


class StrictValidationAndAtomicityTests(unittest.TestCase):
    @staticmethod
    def valid_payload(case):
        inputs = list(case["inputs"])
        inputs.extend(
            ["0" * case["input_width"]]
            * (case["rows"] - len(inputs))
        )
        return ("input\n" + "\n".join(inputs) + "\n").encode("ascii")

    def test_rejects_malformed_public_inputs_before_any_output_write(self):
        """Catches permissive CSV parsing, width drift, and row-count drift."""

        module = load_generator()
        case = CASES[0]
        valid = self.valid_payload(case)
        valid_lines = valid.decode("ascii").splitlines()
        malformed_cases = (
            ("wrong header", valid.replace(b"input\n", b"inputs\n", 1)),
            (
                "extra field",
                (
                    "input\n{},decoy\n{}\n".format(
                        valid_lines[1],
                        "\n".join(valid_lines[2:]),
                    )
                ).encode("ascii"),
            ),
            (
                "blank row",
                (
                    "input\n{}\n\n{}\n".format(
                        valid_lines[1],
                        "\n".join(valid_lines[2:]),
                    )
                ).encode("ascii"),
            ),
            (
                "nonbinary",
                (
                    "input\n{}2{}\n{}\n".format(
                        valid_lines[1][:1],
                        valid_lines[1][2:],
                        "\n".join(valid_lines[2:]),
                    )
                ).encode("ascii"),
            ),
            (
                "wrong width",
                (
                    "input\n{}\n{}\n".format(
                        "0" * (case["input_width"] + 1),
                        "\n".join(valid_lines[2:]),
                    )
                ).encode("ascii"),
            ),
            (
                "too few rows",
                ("\n".join(valid_lines[:-1]) + "\n").encode("ascii"),
            ),
            (
                "too many rows",
                valid + ("0" * case["input_width"] + "\n").encode("ascii"),
            ),
            ("non-ASCII", valid + b"\xff"),
        )

        for label, malformed in malformed_cases:
            with self.subTest(label=label):
                release_bytes, _member_bytes = fixture_release(
                    {case["member"]: malformed}
                )
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    asset = root / "official.zip"
                    asset.write_bytes(release_bytes)
                    output_root = root / "predictions"
                    sentinels = {}
                    for candidate_case in CASES:
                        destination = (
                            output_root
                            / "mystery-{}".format(candidate_case["id"])
                            / "test_outputs.csv"
                        )
                        destination.parent.mkdir(parents=True)
                        destination.write_bytes(
                            "sentinel-{}\n".format(
                                candidate_case["id"]
                            ).encode("ascii")
                        )
                        sentinels[destination] = destination.read_bytes()

                    with accept_fixture_release(module, release_bytes):
                        with self.assertRaises(
                            module.PredictionGenerationError
                        ) as raised:
                            module.generate_outputs(asset, output_root)

                    self.assertIn(case["member"], str(raised.exception))
                    self.assertEqual(
                        {
                            path: path.read_bytes()
                            for path in sentinels
                        },
                        sentinels,
                    )

    def test_atomic_replace_failure_preserves_existing_outputs_and_cleans_temps(self):
        """Catches direct truncation or leaked staging files on write failure."""

        module = load_generator()
        release_bytes, _member_bytes = fixture_release()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            asset = root / "official.zip"
            asset.write_bytes(release_bytes)
            output_root = root / "predictions"
            sentinels = {}
            for case in CASES:
                destination = (
                    output_root
                    / "mystery-{}".format(case["id"])
                    / "test_outputs.csv"
                )
                destination.parent.mkdir(parents=True)
                destination.write_bytes(
                    "sentinel-{}\n".format(case["id"]).encode("ascii")
                )
                sentinels[destination] = destination.read_bytes()

            with accept_fixture_release(module, release_bytes), \
                    mock.patch.object(
                        os,
                        "replace",
                        side_effect=OSError("simulated atomic replace failure"),
                    ):
                with self.assertRaises(
                    module.PredictionGenerationError
                ) as raised:
                    module.generate_outputs(asset, output_root)

            self.assertIn(
                "simulated atomic replace failure", str(raised.exception)
            )
            self.assertEqual(
                {path: path.read_bytes() for path in sentinels},
                sentinels,
            )
            self.assertEqual(
                sorted(
                    path.name
                    for path in output_root.rglob("*")
                    if path.is_file()
                ),
                ["test_outputs.csv"] * 4,
            )

    def test_late_replace_failure_never_leaves_a_partial_csv(self):
        """Documents per-file atomicity when a later destination fails."""

        module = load_generator()
        release_bytes, _member_bytes = fixture_release()
        real_replace = os.replace
        replace_calls = []

        def fail_second_replace(source, destination):
            replace_calls.append((source, destination))
            if len(replace_calls) == 2:
                raise OSError("simulated second replace failure")
            return real_replace(source, destination)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            asset = root / "official.zip"
            asset.write_bytes(release_bytes)
            output_root = root / "predictions"
            sentinels = {}
            for case in CASES:
                destination = (
                    output_root
                    / "mystery-{}".format(case["id"])
                    / "test_outputs.csv"
                )
                destination.parent.mkdir(parents=True)
                destination.write_bytes(
                    "sentinel-{}\n".format(case["id"]).encode("ascii")
                )
                sentinels[case["id"]] = (
                    destination,
                    destination.read_bytes(),
                )

            with accept_fixture_release(module, release_bytes), \
                    mock.patch.object(
                        os, "replace", side_effect=fail_second_replace
                    ):
                with self.assertRaises(
                    module.PredictionGenerationError
                ):
                    module.generate_outputs(asset, output_root)

            first_bytes = sentinels["A"][0].read_bytes()
            self.assertNotEqual(first_bytes, sentinels["A"][1])
            self.assertTrue(first_bytes.startswith(b"input,output\n"))
            self.assertTrue(first_bytes.endswith(b"\n"))
            for dataset_id in ("B", "C", "D"):
                destination, sentinel = sentinels[dataset_id]
                self.assertEqual(destination.read_bytes(), sentinel)
            self.assertEqual(
                sorted(
                    path.name
                    for path in output_root.rglob("*")
                    if path.is_file()
                ),
                ["test_outputs.csv"] * 4,
            )

    def test_candidate_disagreement_fails_before_writing_predictions(self):
        """Catches arithmetic output that is not reproduced by the candidate."""

        module = load_generator()
        release_bytes, _member_bytes = fixture_release()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate_root = root / "candidates"
            candidate_root.mkdir()
            for case in CASES:
                filename = "mystery-{}.txt".format(case["id"])
                (candidate_root / filename).write_bytes(
                    (SOLUTION_DIR / filename).read_bytes()
                )
            (candidate_root / "mystery-A.txt").write_text(
                "INPUTS 16\n"
                "w1 = XOR x1 x1\n"
                "OUTPUTS w1 w1 w1 w1 w1 w1 w1 w1 w1\n",
                encoding="ascii",
            )

            asset = root / "official.zip"
            asset.write_bytes(release_bytes)
            output_root = root / "predictions"
            sentinel = output_root / "mystery-A" / "test_outputs.csv"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_bytes(b"user sentinel\n")

            with accept_fixture_release(module, release_bytes), \
                    mock.patch.object(
                        module, "SOLUTION_DIR", candidate_root
                    ):
                with self.assertRaises(
                    module.PredictionGenerationError
                ) as raised:
                    module.generate_outputs(asset, output_root)

            self.assertIn(
                "candidate circuit disagrees", str(raised.exception)
            )
            self.assertEqual(sentinel.read_bytes(), b"user sentinel\n")
            self.assertFalse(
                (
                    output_root
                    / "mystery-B"
                    / "test_outputs.csv"
                ).exists()
            )


class RepositoryDeliverableTests(unittest.TestCase):
    def test_prediction_files_match_whole_file_commitments_and_candidates(self):
        """Catches artifact drift without treating self-consistency as accuracy."""

        module = load_generator()
        for case in CASES:
            with self.subTest(dataset=case["id"]):
                prediction_path = (
                    SOLUTION_DIR
                    / "predictions"
                    / "mystery-{}".format(case["id"])
                    / "test_outputs.csv"
                )
                raw = prediction_path.read_bytes()
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    EXPECTED_OUTPUT_SHA256[case["id"]],
                )
                self.assertTrue(raw.endswith(b"\n"))

                lines = raw.decode("ascii").splitlines()
                self.assertEqual(lines[0], "input,output")
                self.assertEqual(len(lines), case["rows"] + 1)
                rows = []
                for line in lines[1:]:
                    fields = line.split(",")
                    self.assertEqual(len(fields), 2)
                    input_bits, output_bits = fields
                    self.assertEqual(
                        len(input_bits), case["input_width"]
                    )
                    self.assertEqual(
                        len(output_bits), case["output_width"]
                    )
                    self.assertLessEqual(set(input_bits), {"0", "1"})
                    self.assertLessEqual(set(output_bits), {"0", "1"})
                    rows.append((input_bits, output_bits))

                candidate_path = (
                    SOLUTION_DIR
                    / "mystery-{}.txt".format(case["id"])
                )
                circuit = module.evaluator.parse_netlist(
                    candidate_path.read_text(encoding="ascii"),
                    source=str(candidate_path),
                )
                metrics = module.evaluator.evaluate(circuit, rows)
                self.assertEqual(
                    metrics["exact_matches"], case["rows"]
                )
                self.assertEqual(
                    metrics["correct_bits"],
                    case["rows"] * case["output_width"],
                )


if __name__ == "__main__":
    unittest.main()
