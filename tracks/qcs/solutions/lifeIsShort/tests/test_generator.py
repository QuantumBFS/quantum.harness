import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOLUTION_DIR = Path(__file__).resolve().parents[1]
GENERATOR = SOLUTION_DIR / "generate_circuits.py"
EVALUATOR = SOLUTION_DIR / "evaluator.py"

SPECS = (
    ("mystery-A.txt", 16, 9, 64),
    ("mystery-B.txt", 14, 7, 128),
    ("mystery-C.txt", 12, 12, 512),
    ("mystery-D.txt", 10, 11, 1024),
)
SEMANTICS = (
    ("mystery-A.txt", 8, 9, lambda left, right: left + right),
    ("mystery-B.txt", 7, 7, lambda left, right: abs(left - right)),
    ("mystery-C.txt", 6, 12, lambda left, right: left * right),
    (
        "mystery-D.txt",
        5,
        11,
        lambda left, right: left * left + right * right,
    ),
)
OPERAND = re.compile(r"^~?[xw][1-9][0-9]*$")


class GeneratorCliTests(unittest.TestCase):
    def run_generator(self, output_directory):
        process = subprocess.Popen(
            [
                sys.executable,
                str(GENERATOR),
                "--output-dir",
                str(output_directory),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def run_evaluator(self, circuit_path, dataset_path):
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

    @staticmethod
    def lsb_bits(value, width):
        return "".join(str((value >> bit) & 1) for bit in range(width))

    def test_cli_emits_bounded_deterministic_official_netlists(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first_path = Path(first_directory)
                second_path = Path(second_directory)
                first_run = self.run_generator(first_path)
                second_run = self.run_generator(second_path)

                self.assertEqual(first_run[0], 0, msg=first_run[2])
                self.assertEqual(second_run[0], 0, msg=second_run[2])
                self.assertEqual(first_run[2], "")
                self.assertEqual(second_run[2], "")
                self.assertEqual(first_run[1], second_run[1])
                summary = json.loads(first_run[1])
                self.assertEqual(
                    set(summary), set(spec[0] for spec in SPECS)
                )

                for filename, input_width, output_width, gate_limit in SPECS:
                    with self.subTest(filename=filename):
                        first_bytes = (first_path / filename).read_bytes()
                        second_bytes = (second_path / filename).read_bytes()
                        self.assertEqual(first_bytes, second_bytes)
                        self.assertTrue(first_bytes.endswith(b"\n"))

                        record = summary[filename]
                        self.assertEqual(
                            record["sha256"],
                            hashlib.sha256(first_bytes).hexdigest(),
                        )

                        lines = first_bytes.decode("ascii").splitlines()
                        self.assertEqual(lines[0], "INPUTS {}".format(input_width))
                        self.assertTrue(lines[-1].startswith("OUTPUTS "))
                        outputs = lines[-1].split()[1:]
                        self.assertEqual(len(outputs), output_width)
                        self.assertTrue(all(OPERAND.match(value) for value in outputs))

                        gate_lines = lines[1:-1]
                        self.assertEqual(record["gate_count"], len(gate_lines))
                        self.assertLessEqual(len(gate_lines), gate_limit)
                        for index, line in enumerate(gate_lines, 1):
                            tokens = line.split()
                            self.assertEqual(len(tokens), 5)
                            self.assertEqual(tokens[0], "w{}".format(index))
                            self.assertEqual(tokens[1], "=")
                            self.assertIn(
                                tokens[2],
                                ("AND", "OR", "XOR", "NAND", "NOR", "XNOR"),
                            )
                            self.assertTrue(OPERAND.match(tokens[3]))
                            self.assertTrue(OPERAND.match(tokens[4]))

    def test_generated_netlists_match_exhaustive_arithmetic_semantics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            returncode, stdout, stderr = self.run_generator(temporary_path)
            self.assertEqual(returncode, 0, msg=stderr)

            for filename, operand_width, output_width, operation in SEMANTICS:
                rows = ["input,output"]
                for left in range(1 << operand_width):
                    for right in range(1 << operand_width):
                        input_bits = self.lsb_bits(
                            left, operand_width
                        ) + self.lsb_bits(right, operand_width)
                        output_bits = self.lsb_bits(
                            operation(left, right), output_width
                        )
                        rows.append("{},{}".format(input_bits, output_bits))
                dataset_path = temporary_path / "{}.csv".format(filename)
                dataset_path.write_text("\n".join(rows) + "\n", encoding="ascii")

                with self.subTest(filename=filename):
                    evaluated = self.run_evaluator(
                        temporary_path / filename, dataset_path
                    )
                    self.assertEqual(evaluated[0], 0, msg=evaluated[2])
                    metrics = json.loads(evaluated[1])
                    samples = 1 << (2 * operand_width)
                    self.assertEqual(metrics["samples"], samples)
                    self.assertEqual(metrics["exact_matches"], samples)
                    self.assertEqual(metrics["correct_bits"], samples * output_width)
                    self.assertEqual(metrics["exact_match_accuracy"], 1.0)
                    self.assertEqual(metrics["bit_accuracy"], 1.0)

    def test_repository_candidates_are_exact_generator_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            returncode, stdout, stderr = self.run_generator(temporary_path)
            self.assertEqual(returncode, 0, msg=stderr)

            for filename, _input_width, _output_width, _gate_limit in SPECS:
                with self.subTest(filename=filename):
                    repository_candidate = SOLUTION_DIR / filename
                    self.assertTrue(
                        repository_candidate.is_file(),
                        msg="missing generated candidate {}".format(
                            repository_candidate
                        ),
                    )
                    self.assertEqual(
                        repository_candidate.read_bytes(),
                        (temporary_path / filename).read_bytes(),
                    )


if __name__ == "__main__":
    unittest.main()
