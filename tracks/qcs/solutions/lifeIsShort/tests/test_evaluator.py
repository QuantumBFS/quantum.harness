import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock


SOLUTION_DIR = Path(__file__).resolve().parents[1]
EVALUATOR = SOLUTION_DIR / "evaluator.py"
CONTROL_RUNNER = SOLUTION_DIR / "run_controls.py"
CONTROLS_DIR = SOLUTION_DIR / "controls"


class EvaluatorCliTests(unittest.TestCase):
    def run_evaluator(self, circuit_text, dataset_text, as_json=True):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        temporary_path = Path(temporary_directory.name)
        circuit_path = temporary_path / "circuit.txt"
        dataset_path = temporary_path / "dataset.csv"
        circuit_path.write_text(circuit_text, encoding="utf-8")
        dataset_path.write_text(dataset_text, encoding="utf-8")
        command = [sys.executable, str(EVALUATOR)]
        if as_json:
            command.append("--json")
        command.extend([str(circuit_path), str(dataset_path)])
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def test_documented_gate_language_scores_with_free_inversion(self):
        circuit_text = """\
# Every documented binary gate is exercised.
INPUTS 2
w1 = AND x1 x2
w2 = OR x1 x2
w3 = XOR x1 x2
w4 = NAND x1 x2
w5 = NOR x1 x2
w6 = XNOR x1 x2
w7 = XOR ~x1 w1
w8 = XOR ~w7 x1  # wire inversion
OUTPUTS w1 w2 w3 w4 w5 w6 ~w1 w8
"""
        dataset_text = """\
input,output
00,00011110
01,01110010
10,01110010
11,11000101
"""
        returncode, stdout, stderr = self.run_evaluator(
            circuit_text, dataset_text
        )

        self.assertEqual(returncode, 0, msg=stderr)
        metrics = json.loads(stdout)
        self.assertEqual(metrics["samples"], 4)
        self.assertEqual(metrics["exact_matches"], 4)
        self.assertEqual(metrics["exact_match_accuracy"], 1.0)
        self.assertEqual(metrics["correct_bits"], 32)
        self.assertEqual(metrics["total_bits"], 32)
        self.assertEqual(metrics["bit_accuracy"], 1.0)
        self.assertEqual(metrics["official_free_inversion_gate_count"], 8)
        self.assertGreater(metrics.get("peak_memory_bytes", 0), 0)
        self.assertEqual(
            metrics.get("peak_memory_measurement"),
            "resource.getrusage(RUSAGE_SELF).ru_maxrss; Linux KiB converted to bytes",
        )

    def test_default_output_uses_the_official_julia_metric_labels(self):
        returncode, stdout, stderr = self.run_evaluator(
            "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n",
            "input,output\n00,0\n01,1\n",
            as_json=False,
        )

        self.assertEqual(returncode, 0, msg=stderr)
        self.assertEqual(
            stdout,
            "gates:            1  (inverters free)\n"
            "samples:          2\n"
            "exact-match acc:  1.0\n"
            "bit accuracy:     1.0\n",
        )
        self.assertEqual(stderr, "")

    def test_exact_match_and_bit_accuracy_use_distinct_denominators(self):
        returncode, stdout, stderr = self.run_evaluator(
            "INPUTS 2\nOUTPUTS x1 x2\n",
            "input,output\n"
            "00,00\n"
            "01,00\n"
            "10,11\n"
            "11,00\n",
        )

        self.assertEqual(returncode, 0, msg=stderr)
        metrics = json.loads(stdout)
        self.assertEqual(metrics["samples"], 4)
        self.assertEqual(metrics["exact_matches"], 1)
        self.assertEqual(metrics["exact_match_accuracy"], 0.25)
        self.assertEqual(metrics["correct_bits"], 4)
        self.assertEqual(metrics["total_bits"], 8)
        self.assertEqual(metrics["bit_accuracy"], 0.5)
        self.assertEqual(metrics["official_free_inversion_gate_count"], 0)

    def test_malformed_netlists_are_rejected_without_tracebacks(self):
        malformed_cases = [
            (
                "INPUTS 2 extra\nOUTPUTS x1\n",
                "INPUTS requires exactly one positive decimal integer",
            ),
            (
                "INPUTS 2\nINPUTS 2\nOUTPUTS x1\n",
                "duplicate INPUTS declaration",
            ),
            (
                "w1 = XOR x1 x2\nINPUTS 2\nOUTPUTS w1\n",
                "INPUTS must be the first statement",
            ),
            (
                "INPUTS 0\nOUTPUTS x1\n",
                "INPUTS requires exactly one positive decimal integer",
            ),
            (
                "INPUTS 2\nq1 = XOR x1 x2\nOUTPUTS w1\n",
                "gate target must be w followed by a positive decimal integer",
            ),
            (
                "INPUTS 2\nw0 = XOR x1 x2\nOUTPUTS w0\n",
                "gate target must be w followed by a positive decimal integer",
            ),
            (
                "INPUTS 2\nw01 = XOR x1 x2\nOUTPUTS w1\n",
                "gate target must be w followed by a positive decimal integer",
            ),
            (
                "INPUTS 2\nw1 = XOR ~~x1 x2\nOUTPUTS w1\n",
                "bad operand '~~x1'",
            ),
            (
                "INPUTS 2\nw2 = XOR w1 x1\nw1 = AND x1 x2\nOUTPUTS w2\n",
                "wire w1 used before definition",
            ),
            (
                "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w9\n",
                "wire w9 used before definition",
            ),
            (
                "INPUTS 2\nw1 = XOR x1 x2\nw1 = AND x1 x2\nOUTPUTS w1\n",
                "wire w1 defined twice",
            ),
            (
                "INPUTS 2\nw1 = IMPLIES x1 x2\nOUTPUTS w1\n",
                "unknown operation 'IMPLIES'",
            ),
            (
                "INPUTS 2\nOUTPUTS\n",
                "OUTPUTS requires at least one operand",
            ),
            (
                "INPUTS 2\nOUTPUTS x1\nw1 = XOR x1 x2\n",
                "statements are not allowed after OUTPUTS",
            ),
            (
                "INPUTS 2\nOUTPUTS x1\nOUTPUTS x2\n",
                "duplicate OUTPUTS declaration",
            ),
            (
                "INPUTS 2\nOUTPUTS x3\n",
                "input x3 out of range 1..2",
            ),
            (
                "INPUTS 2\nw1 = XOR z1 x2\nOUTPUTS w1\n",
                "bad operand 'z1'",
            ),
            (
                "OUTPUTS x1\n",
                "INPUTS must be the first statement",
            ),
        ]
        dataset_text = "input,output\n00,0\n"

        for circuit_text, expected_message in malformed_cases:
            with self.subTest(expected_message=expected_message):
                returncode, stdout, stderr = self.run_evaluator(
                    circuit_text, dataset_text
                )
                self.assertEqual(returncode, 2)
                self.assertEqual(stdout, "")
                self.assertTrue(stderr.startswith("error: "), msg=stderr)
                self.assertIn(expected_message, stderr)
                self.assertNotIn("Traceback", stderr)

    def test_malformed_datasets_are_rejected_without_tracebacks(self):
        circuit_text = "INPUTS 2\nOUTPUTS x1\n"
        malformed_cases = [
            (
                "",
                "missing header; expected exactly 'input,output'",
            ),
            (
                "inputs,output\n00,0\n",
                "header must be exactly 'input,output'",
            ),
            (
                "input,output\n",
                "dataset must contain at least one sample",
            ),
            (
                "input,output\n00,0,extra\n",
                "expected exactly two CSV fields",
            ),
            (
                "input,output\n00,0\n\n01,0\n",
                "blank rows are not allowed",
            ),
            (
                "input,output\n0a,0\n",
                "input must be a nonempty binary string",
            ),
            (
                "input,output\n00,2\n",
                "output must be a nonempty binary string",
            ),
            (
                "input,output\n0,0\n",
                "input width 1 does not match INPUTS 2",
            ),
            (
                "input,output\n00,01\n",
                "output width 2 does not match circuit outputs 1",
            ),
            (
                "input,output\n 00,0\n",
                "input must be a nonempty binary string",
            ),
            (
                "input,output\n00,\n",
                "output must be a nonempty binary string",
            ),
        ]

        for dataset_text, expected_message in malformed_cases:
            with self.subTest(expected_message=expected_message):
                returncode, stdout, stderr = self.run_evaluator(
                    circuit_text, dataset_text
                )
                self.assertEqual(returncode, 2)
                self.assertEqual(stdout, "")
                self.assertTrue(stderr.startswith("error: "), msg=stderr)
                self.assertIn(expected_message, stderr)
                self.assertNotIn("Traceback", stderr)

    def test_public_four_bit_control_circuits_match_exhaustive_truth(self):
        controls = [
            (
                "practice-add-n4.txt",
                5,
                17,
                lambda left, right: left + right,
            ),
            (
                "practice-mul-n4.txt",
                8,
                128,
                lambda left, right: left * right,
            ),
        ]

        for filename, output_width, gate_count, arithmetic in controls:
            rows = ["input,output"]
            for left in range(16):
                for right in range(16):
                    input_bits = self.lsb_bits(left, 4) + self.lsb_bits(
                        right, 4
                    )
                    output_bits = self.lsb_bits(
                        arithmetic(left, right), output_width
                    )
                    rows.append("{},{}".format(input_bits, output_bits))
            dataset_text = "\n".join(rows) + "\n"

            with self.subTest(filename=filename):
                returncode, stdout, stderr = self.run_evaluator_path(
                    CONTROLS_DIR / filename, dataset_text
                )
                self.assertEqual(returncode, 0, msg=stderr)
                metrics = json.loads(stdout)
                self.assertEqual(metrics["samples"], 256)
                self.assertEqual(metrics["exact_matches"], 256)
                self.assertEqual(metrics["exact_match_accuracy"], 1.0)
                self.assertEqual(metrics["bit_accuracy"], 1.0)
                self.assertEqual(
                    metrics["official_free_inversion_gate_count"],
                    gate_count,
                )

    @staticmethod
    def lsb_bits(value, width):
        return "".join(str((value >> bit) & 1) for bit in range(width))

    def run_evaluator_path(self, circuit_path, dataset_text):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        dataset_path = Path(temporary_directory.name) / "dataset.csv"
        dataset_path.write_text(dataset_text, encoding="utf-8")
        process = subprocess.Popen(
            [
                sys.executable,
                str(EVALUATOR),
                "--json",
                str(circuit_path),
                str(dataset_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def test_control_runner_rejects_an_unverified_release_asset(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            asset_path = temporary_path / "occam-circuit.zip"
            results_root = temporary_path / "results"
            asset_path.write_bytes(b"not-release\n")
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(CONTROL_RUNNER),
                    "--asset",
                    str(asset_path),
                    "--results-root",
                    str(results_root),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            stdout, stderr = process.communicate()
            result_entries = (
                list(results_root.iterdir()) if results_root.exists() else []
            )

        self.assertEqual(process.returncode, 2)
        self.assertEqual(stdout, "")
        self.assertIn("release asset verification failed", stderr)
        self.assertIn("expected 61068 bytes", stderr)
        self.assertIn(
            "c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b",
            stderr,
        )
        self.assertIn("got 12 bytes", stderr)
        self.assertIn(
            "138a9ee5ca05e8ffbb42421176422ab1df45fed30dd59832f97443a6698c3b62",
            stderr,
        )
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(result_entries, [])

    def test_runner_invocation_preserves_the_entered_script_token(self):
        sys.path.insert(0, str(SOLUTION_DIR))
        self.addCleanup(sys.path.remove, str(SOLUTION_DIR))
        import run_controls

        build_invocation = getattr(run_controls, "build_invocation", None)
        actual = (
            build_invocation(
                "tracks/qcs/solutions/lifeIsShort/run_controls.py",
                ["--asset", "/tmp/occam-circuit.zip"],
            )
            if build_invocation is not None
            else None
        )

        self.assertEqual(
            actual,
            [
                sys.executable,
                "tracks/qcs/solutions/lifeIsShort/run_controls.py",
                "--asset",
                "/tmp/occam-circuit.zip",
            ],
        )

    def test_control_runner_uses_runtime_inputs_only(self):
        sys.path.insert(0, str(SOLUTION_DIR))
        self.addCleanup(sys.path.remove, str(SOLUTION_DIR))
        import run_controls

        control_results = [
            {
                "name": "practice-add-n4-public-training",
                "metrics": {
                    "exact_match_accuracy": 1.0,
                    "bit_accuracy": 1.0,
                    "official_free_inversion_gate_count": 17,
                },
                "matched_expected_metrics": True,
            },
            {
                "name": "practice-mul-n4-public-training",
                "metrics": {
                    "exact_match_accuracy": 1.0,
                    "bit_accuracy": 1.0,
                    "official_free_inversion_gate_count": 128,
                },
                "matched_expected_metrics": True,
            },
            {
                "name": "official-adder8-mystery-A-public-training",
                "metrics": {
                    "exact_match_accuracy": 1.0,
                    "bit_accuracy": 1.0,
                    "official_free_inversion_gate_count": 37,
                },
                "matched_expected_metrics": True,
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_inputs = Path(temporary_directory) / "runtime-inputs"
            runtime_inputs.mkdir()
            run_directory = Path(temporary_directory) / "run"
            run_directory.mkdir()
            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "SOLUTION_DIR",
                        runtime_inputs,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "validate_release_asset",
                        return_value=b"release",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "_new_run_directory",
                        return_value=run_directory,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls, "_release_files", return_value={}
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "_copy_control_circuits",
                        return_value={},
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "_run_focused_tests",
                        return_value={"exit_code": 0},
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "_run_python_control",
                        side_effect=control_results,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls,
                        "_official_julia_control",
                        return_value={"authoritative": True},
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        run_controls, "_source_hashes", return_value={}
                    )
                )
                manifest_path = run_controls.run_controls(
                    "release.zip",
                    Path(temporary_directory) / "results",
                    ["run_controls.py"],
                )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertNotIn("preserved_user_pngs", manifest)
        self.assertEqual(manifest["controls"], control_results)
        self.assertTrue(
            manifest["verification"]["all_expected_metrics_matched"]
        )

    def test_source_hashes_exclude_internal_implementation_plan(self):
        sys.path.insert(0, str(SOLUTION_DIR))
        self.addCleanup(sys.path.remove, str(SOLUTION_DIR))
        import run_controls

        source_hashes = run_controls._source_hashes()
        internal_plan = str(
            (SOLUTION_DIR / "EVALUATOR_IMPLEMENTATION_PLAN.md").relative_to(
                run_controls.REPOSITORY_ROOT
            )
        )
        evaluator = str(EVALUATOR.relative_to(run_controls.REPOSITORY_ROOT))
        control_runner = str(
            CONTROL_RUNNER.relative_to(run_controls.REPOSITORY_ROOT)
        )

        self.assertNotIn(internal_plan, source_hashes)
        self.assertIn(evaluator, source_hashes)
        self.assertIn(control_runner, source_hashes)


if __name__ == "__main__":
    unittest.main()
