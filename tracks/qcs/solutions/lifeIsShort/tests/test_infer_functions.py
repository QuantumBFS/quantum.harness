import builtins
import glob
import hashlib
import importlib.util
import io
import itertools
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from unittest import mock


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SOLUTION_DIR = os.path.dirname(TESTS_DIR)
SCRIPT = os.path.join(SOLUTION_DIR, "infer_functions.py")

DATASET_IDS = ("A", "B", "C", "D")
OPERATION_ORDER = (
    "addition",
    "absolute_difference",
    "multiplication",
    "sum_of_squares",
)
EXPECTED_MAPPING = {
    "A": "sum_of_squares",
    "B": "addition",
    "C": "multiplication",
    "D": "absolute_difference",
}

# Every expectation is a hand-checked literal.  Each input is the concatenation
# of two equal-width, least-significant-bit-first operands.
FIXTURE_ROWS = (
    (
        "100010",  # 1, 2
        {
            "addition": "1100000",             # 3
            "absolute_difference": "1000000",  # 1
            "multiplication": "0100000",        # 2
            "sum_of_squares": "1010000",        # 5
        },
    ),
    (
        "110010",  # 3, 2
        {
            "addition": "1010000",             # 5
            "absolute_difference": "1000000",  # 1
            "multiplication": "0110000",        # 6
            "sum_of_squares": "1011000",        # 13
        },
    ),
    (
        "001100",  # 4, 1
        {
            "addition": "1010000",             # 5
            "absolute_difference": "1100000",  # 3
            "multiplication": "0010000",        # 4
            "sum_of_squares": "1000100",        # 17
        },
    ),
    (
        "010010",  # 2, 2
        {
            "addition": "0010000",             # 4
            "absolute_difference": "0000000",  # 0
            "multiplication": "0010000",        # 4
            "sum_of_squares": "0001000",        # 8
        },
    ),
    (
        "111111",  # 7, 7
        {
            "addition": "0111000",             # 14
            "absolute_difference": "0000000",  # 0
            "multiplication": "1000110",        # 49
            "sum_of_squares": "0100011",        # 98
        },
    ),
)

DATASET_CASES = (
    ("A", "sum_of_squares", 0),
    ("B", "addition", 1),
    ("C", "multiplication", 2),
    ("D", "absolute_difference", 3),
)

EXPECTED_ROWS = {"A": 5, "B": 6, "C": 7, "D": 8}
EXPECTED_CANDIDATE_RANKINGS = {
    "A": (
        ("sum_of_squares", 5),
        ("addition", 0),
        ("absolute_difference", 0),
        ("multiplication", 0),
    ),
    "B": (
        ("addition", 6),
        ("multiplication", 1),
        ("absolute_difference", 0),
        ("sum_of_squares", 0),
    ),
    "C": (
        ("multiplication", 7),
        ("addition", 1),
        ("absolute_difference", 0),
        ("sum_of_squares", 0),
    ),
    "D": (
        ("absolute_difference", 8),
        ("addition", 0),
        ("multiplication", 0),
        ("sum_of_squares", 0),
    ),
}


def fixture_csv(operation, duplicate_count=0):
    rows = list(FIXTURE_ROWS)
    rows.extend([FIXTURE_ROWS[0]] * duplicate_count)
    lines = ["input,output"]
    lines.extend(
        "{},{}".format(input_bits, outputs[operation])
        for input_bits, outputs in rows
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def write_valid_root(root):
    raw_by_id = {}
    for dataset_id, operation, duplicate_count in DATASET_CASES:
        dataset_dir = os.path.join(root, "mystery-{}".format(dataset_id))
        os.makedirs(dataset_dir)
        raw = fixture_csv(operation, duplicate_count)
        raw_by_id[dataset_id] = raw
        with open(os.path.join(dataset_dir, "train.csv"), "wb") as handle:
            handle.write(raw)
    return raw_by_id


def run_cli(arguments, cwd=None, hash_seed="17"):
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = hash_seed
    environment["LC_ALL"] = "C"
    return subprocess.run(
        [sys.executable, SCRIPT] + list(arguments),
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )


def load_inference_module(test_case):
    if not os.path.isfile(SCRIPT):
        test_case.fail("infer_functions.py has not been implemented")
    spec = importlib.util.spec_from_file_location(
        "life_is_short_infer_functions_test_target", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CorrectRecoveryTests(unittest.TestCase):
    def test_recovers_all_four_functions_and_reports_exact_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            raw_by_id = write_valid_root(root)
            completed = run_cli([root])

            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertEqual(completed.stderr, b"")
            report = json.loads(completed.stdout.decode("ascii"))

            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["argv"], [SCRIPT, root])
            self.assertEqual(report["dataset_root"], root)
            self.assertEqual(
                report["provenance"],
                {
                    "algorithm": "exhaustive_arithmetic_assignment_v1",
                    "deterministic": True,
                    "randomness_used": False,
                    "seed": None,
                    "standard_library_only": True,
                },
            )
            self.assertEqual(
                report["ranking_rule"],
                {
                    "assignment_primary": (
                        "descending sum of exact per-dataset accuracies"
                    ),
                    "candidate_primary": "descending exact accuracy",
                    "dataset_order": ["A", "B", "C", "D"],
                    "operation_order": list(OPERATION_ORDER),
                    "rank_style": "one-based ordinal; ties do not share ranks",
                    "tie_break": (
                        "operation-order indices assigned in dataset order"
                    ),
                },
            )

            self.assertEqual(
                [dataset["id"] for dataset in report["datasets"]],
                list(DATASET_IDS),
            )
            for dataset in report["datasets"]:
                dataset_id = dataset["id"]
                self.assertEqual(
                    dataset["relative_path"],
                    "mystery-{}/train.csv".format(dataset_id),
                )
                self.assertEqual(
                    dataset["sha256"],
                    hashlib.sha256(raw_by_id[dataset_id]).hexdigest(),
                )
                self.assertEqual(dataset["rows"], EXPECTED_ROWS[dataset_id])
                self.assertEqual(dataset["operand_width"], 3)
                self.assertEqual(dataset["output_width"], 7)
                self.assertEqual(
                    dataset["candidates"],
                    [
                        {
                            "accuracy": {
                                "denominator": EXPECTED_ROWS[dataset_id],
                                "numerator": correct,
                            },
                            "correct": correct,
                            "operation": operation,
                            "rank": rank,
                            "total": EXPECTED_ROWS[dataset_id],
                        }
                        for rank, (operation, correct) in enumerate(
                            EXPECTED_CANDIDATE_RANKINGS[dataset_id], 1
                        )
                    ],
                )

            assignments = report["assignments"]
            self.assertEqual(len(assignments), 24)
            self.assertEqual(
                [assignment["rank"] for assignment in assignments],
                list(range(1, 25)),
            )
            signatures = {
                tuple(assignment["mapping"][key] for key in DATASET_IDS)
                for assignment in assignments
            }
            self.assertEqual(len(signatures), 24)
            self.assertEqual(
                signatures, set(itertools.permutations(OPERATION_ORDER))
            )
            self.assertEqual(assignments[0]["mapping"], EXPECTED_MAPPING)
            self.assertEqual(assignments[0]["score"], {"numerator": 4, "denominator": 1})
            self.assertEqual(
                assignments[0]["mean_accuracy"],
                {"numerator": 1, "denominator": 1},
            )
            self.assertEqual(assignments[0]["correct"], 26)
            self.assertEqual(assignments[0]["total"], 26)
            self.assertEqual(
                assignments[0]["pooled_accuracy"],
                {"numerator": 1, "denominator": 1},
            )

            operation_index = {
                name: index for index, name in enumerate(OPERATION_ORDER)
            }
            observed_sort_keys = []
            for assignment in assignments:
                expected_correct = sum(
                    dict(EXPECTED_CANDIDATE_RANKINGS[dataset_id])[
                        assignment["mapping"][dataset_id]
                    ]
                    for dataset_id in DATASET_IDS
                )
                expected_total = sum(EXPECTED_ROWS.values())
                expected_score = sum(
                    (
                        Fraction(
                            dict(EXPECTED_CANDIDATE_RANKINGS[dataset_id])[
                                assignment["mapping"][dataset_id]
                            ],
                            EXPECTED_ROWS[dataset_id],
                        )
                        for dataset_id in DATASET_IDS
                    ),
                    Fraction(0, 1),
                )
                self.assertEqual(
                    assignment,
                    {
                        "correct": expected_correct,
                        "mapping": assignment["mapping"],
                        "mean_accuracy": {
                            "numerator": (expected_score / 4).numerator,
                            "denominator": (expected_score / 4).denominator,
                        },
                        "pooled_accuracy": {
                            "numerator": Fraction(
                                expected_correct, expected_total
                            ).numerator,
                            "denominator": Fraction(
                                expected_correct, expected_total
                            ).denominator,
                        },
                        "rank": assignment["rank"],
                        "score": {
                            "numerator": expected_score.numerator,
                            "denominator": expected_score.denominator,
                        },
                        "total": expected_total,
                    },
                )
                observed_sort_keys.append(
                    (
                        -expected_score,
                        tuple(
                            operation_index[assignment["mapping"][dataset_id]]
                            for dataset_id in DATASET_IDS
                        ),
                    )
                )
            self.assertEqual(observed_sort_keys, sorted(observed_sort_keys))


class DeterminismAndFilesystemTests(unittest.TestCase):
    def test_output_is_canonical_and_decoy_files_are_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            write_valid_root(root)
            decoy_paths = (
                os.path.join(root, "test.csv"),
                os.path.join(root, "withheld-output.json"),
                os.path.join(root, "mystery-A", "test.csv"),
                os.path.join(root, "mystery-B", "withheld.csv"),
                os.path.join(root, "mystery-E", "train.csv"),
                os.path.join(root, "nested", "mystery-C", "train.csv"),
            )
            for index, path in enumerate(decoy_paths):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as handle:
                    handle.write(
                        "decoy-{}-must-not-be-used\n".format(index).encode("ascii")
                    )
            before = {
                path: (
                    pathlib.Path(path).read_bytes(),
                    os.stat(path).st_mtime_ns,
                )
                for path in decoy_paths
            }

            with tempfile.TemporaryDirectory() as unrelated_cwd:
                first = run_cli([root], cwd=unrelated_cwd, hash_seed="1")
                second = run_cli([root], cwd=unrelated_cwd, hash_seed="987654")

            self.assertEqual(first.returncode, 0, first.stderr.decode())
            self.assertEqual(second.returncode, 0, second.stderr.decode())
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first.stderr, b"")
            self.assertEqual(second.stderr, b"")
            decoded = json.loads(first.stdout.decode("ascii"))
            canonical = (
                json.dumps(
                    decoded,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                + "\n"
            ).encode("ascii")
            self.assertEqual(first.stdout, canonical)
            after = {
                path: (
                    pathlib.Path(path).read_bytes(),
                    os.stat(path).st_mtime_ns,
                )
                for path in decoy_paths
            }
            self.assertEqual(after, before)

    def test_inference_opens_each_literal_training_path_once_without_scanning(self):
        with tempfile.TemporaryDirectory() as root:
            write_valid_root(root)
            decoy = os.path.join(root, "mystery-A", "test.csv")
            with open(decoy, "wb") as handle:
                handle.write(b"must not be read\n")

            expected_paths = [
                os.path.abspath(
                    os.path.join(
                        root,
                        "mystery-{}".format(dataset_id),
                        "train.csv",
                    )
                )
                for dataset_id in DATASET_IDS
            ]
            observed_opens = []
            real_open = builtins.open

            def guarded_open(path, mode="r", *args, **kwargs):
                absolute_path = os.path.abspath(str(path))
                observed_opens.append((absolute_path, mode))
                if absolute_path not in expected_paths:
                    raise AssertionError(
                        "unexpected filesystem read: {}".format(absolute_path)
                    )
                return real_open(path, mode, *args, **kwargs)

            def scanning_forbidden(*args, **kwargs):
                raise AssertionError("directory scanning is forbidden")

            patches = (
                mock.patch.object(os, "listdir", scanning_forbidden),
                mock.patch.object(os, "scandir", scanning_forbidden),
                mock.patch.object(os, "walk", scanning_forbidden),
                mock.patch.object(glob, "glob", scanning_forbidden),
                mock.patch.object(glob, "iglob", scanning_forbidden),
                mock.patch.object(pathlib.Path, "iterdir", scanning_forbidden),
                mock.patch.object(pathlib.Path, "glob", scanning_forbidden),
                mock.patch.object(pathlib.Path, "rglob", scanning_forbidden),
                mock.patch.object(pathlib.Path, "open", scanning_forbidden),
                mock.patch.object(pathlib.Path, "read_bytes", scanning_forbidden),
                mock.patch.object(pathlib.Path, "read_text", scanning_forbidden),
                mock.patch.object(io, "open", scanning_forbidden),
                mock.patch.object(os, "open", scanning_forbidden),
                mock.patch("builtins.open", side_effect=guarded_open),
            )
            previous_dont_write_bytecode = sys.dont_write_bytecode
            sys.dont_write_bytecode = True
            try:
                with patches[0], patches[1], patches[2], patches[3], \
                        patches[4], patches[5], patches[6], patches[7], \
                        patches[8], patches[9], patches[10], patches[11], \
                        patches[12], patches[13]:
                    module = load_inference_module(self)
                    report = module.infer(
                        root, argv=["infer_functions.py", root]
                    )
            finally:
                sys.dont_write_bytecode = previous_dont_write_bytecode

            self.assertEqual(
                observed_opens,
                [(path, "rb") for path in expected_paths],
            )
            self.assertEqual(
                [dataset["id"] for dataset in report["datasets"]],
                list(DATASET_IDS),
            )


class MalformedDataTests(unittest.TestCase):
    def test_rejects_malformed_training_data_without_partial_json_or_traceback(self):
        malformed_cases = (
            ("empty file", b"", "missing header"),
            (
                "wrong header",
                b"output,input\n1000000,100010\n",
                "header must be exactly",
            ),
            (
                "header only",
                b"input,output\n",
                "at least one sample",
            ),
            (
                "odd input width",
                b"input,output\n100,1000000\n",
                "two equal-width operands",
            ),
            (
                "nonbinary input",
                b"input,output\n100x10,1000000\n",
                "input must be a nonempty binary string",
            ),
            (
                "nonbinary output",
                b"input,output\n100010,100x000\n",
                "output must be a nonempty binary string",
            ),
            (
                "missing field",
                b"input,output\n100010\n",
                "exactly two CSV fields",
            ),
            (
                "extra field",
                b"input,output\n100010,1000000,extra\n",
                "exactly two CSV fields",
            ),
            (
                "blank record",
                b"input,output\n100010,1000000\n\n100010,1000000\n",
                "blank rows are not allowed",
            ),
            (
                "inconsistent operand width",
                b"input,output\n100010,1000000\n1010,1000000\n",
                "input width",
            ),
            (
                "inconsistent output width",
                b"input,output\n100010,1000000\n100010,100000\n",
                "output width",
            ),
            (
                "invalid UTF-8",
                b"input,output\n100010,\xff\n",
                "UTF-8",
            ),
            (
                "unclosed quote",
                b'input,output\n"100010,1000000\n',
                "invalid CSV",
            ),
        )

        for case_name, malformed, expected_error in malformed_cases:
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as root:
                    write_valid_root(root)
                    path = os.path.join(root, "mystery-A", "train.csv")
                    with open(path, "wb") as handle:
                        handle.write(malformed)
                    completed = run_cli([root])

                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, b"")
                stderr = completed.stderr.decode("utf-8")
                self.assertTrue(stderr.startswith("error: "), stderr)
                self.assertIn("mystery-A", stderr)
                self.assertIn(expected_error, stderr)
                self.assertNotIn("Traceback", stderr)

    def test_missing_fixed_training_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as root:
            write_valid_root(root)
            os.remove(os.path.join(root, "mystery-C", "train.csv"))
            completed = run_cli([root])

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, b"")
        stderr = completed.stderr.decode("utf-8")
        self.assertIn("mystery-C", stderr)
        self.assertIn("cannot read", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_cli_requires_exactly_one_dataset_root(self):
        missing = run_cli([])
        extra = run_cli(["first-root", "second-root"])

        for completed in (missing, extra):
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, b"")
            stderr = completed.stderr.decode("utf-8")
            self.assertIn("usage:", stderr)
            self.assertNotIn("Traceback", stderr)


if __name__ == "__main__":
    unittest.main()
