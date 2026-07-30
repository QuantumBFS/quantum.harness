import importlib
from pathlib import Path
import subprocess
import sys
import unittest


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = SOLUTION_ROOT / "examples" / "sparse_anchor_response.yaml"


class SparseAnchorExampleTests(unittest.TestCase):
    def load_runner(self):
        try:
            return importlib.import_module("examples.run_sparse_anchor")
        except ModuleNotFoundError:
            self.fail("examples.run_sparse_anchor has not been implemented")

    def test_synthetic_case_fits_and_scores_held_out_vectors(self):
        runner = self.load_runner()
        result = runner.run_case(CASE_PATH)

        self.assertEqual(result["validation_scope"], "software-contract-only")
        self.assertLess(result["held_out_metrics"]["relative_rmse"], 1.0e-10)
        self.assertGreater(abs(result["model"]["response_matrix"][0][1]), 0.05)
        self.assertTrue(result["anchor_accounting_matches"])
        self.assertTrue(result["cost"]["is_faster_than_dense_high_level"])
        self.assertFalse(result["cost"]["is_faster_than_dfpt"])
        self.assertFalse(result["measured_runtime"])
        self.assertFalse(result["physical_accuracy_established"])

    def test_cli_labels_the_cost_speedup_as_unmeasured(self):
        process = subprocess.run(
            [sys.executable, "examples/run_sparse_anchor.py"],
            cwd=SOLUTION_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("held-out synthetic", process.stdout)
        self.assertIn("is_faster_than_dense_high_level=True", process.stdout)
        self.assertIn("is_faster_than_dfpt=False", process.stdout)
        self.assertIn("measured_runtime=False", process.stdout)
        self.assertIn("physical_accuracy_established=False", process.stdout)


if __name__ == "__main__":
    unittest.main()
