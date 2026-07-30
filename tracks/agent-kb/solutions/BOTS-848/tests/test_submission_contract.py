from pathlib import Path
import hashlib
import re
import unittest


SOLUTION_ROOT = Path(__file__).resolve().parents[1]


class SubmissionContractTests(unittest.TestCase):
    def test_reproduction_guide_has_runnable_commands_and_expected_results(self):
        path = SOLUTION_ROOT / "REPRODUCE.md"
        self.assertTrue(path.is_file(), "REPRODUCE.md is the reviewer entry point")
        text = path.read_text(encoding="utf-8")

        required_fragments = (
            "Python 3.10",
            "JSON-compatible YAML",
            "make check",
            "python3 -m unittest discover -s tests -v",
            "python3 eval/evaluate.py",
            "python3 examples/run_example.py",
            "python3 examples/run_sparse_anchor.py",
            "make report-check",
            "Ran 48 tests",
            "14/14 cases passed",
            "held-out synthetic",
            "dense_high_level=600.000",
            "is_faster_than_dfpt=False",
            "measured_runtime=False",
            "physical_accuracy_established=False",
        )
        for fragment in required_fragments:
            self.assertIn(fragment, text)

    def test_results_argument_separates_evidence_from_open_claims(self):
        path = SOLUTION_ROOT / "RESULTS.md"
        self.assertTrue(path.is_file(), "RESULTS.md is the human-readable result argument")
        text = path.read_text(encoding="utf-8")

        required_headings = (
            "## Result in One Sentence",
            "## Why This Is Useful",
            "## Why the Result Is Credible",
            "## What Is Not Yet Proven",
            "## Falsification Tests",
        )
        for heading in required_headings:
            self.assertIn(heading, text)

        for evidence in ("44 -> 87 meV", "58 -> 50 meV", "70 -> 76 meV", "53 -> 45 meV"):
            self.assertIn(evidence, text)

        self.assertIn("## When It Can Be Faster", text)
        self.assertIn("not faster than a single DFPT calculation", text)
        self.assertIn("synthetic held-out", text)

    def test_documented_pdf_hash_matches_distributed_artifact(self):
        text = (SOLUTION_ROOT / "REPRODUCE.md").read_text(encoding="utf-8")
        documented = re.search(r"\b[0-9a-f]{64}\b", text)
        self.assertIsNotNone(documented, "REPRODUCE.md must record a SHA-256 digest")

        pdf_bytes = (SOLUTION_ROOT / "report" / "main.pdf").read_bytes()
        actual = hashlib.sha256(pdf_bytes).hexdigest()
        self.assertEqual(documented.group(0), actual)

    def test_readme_links_the_two_reviewer_entry_points(self):
        text = (SOLUTION_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[Reproduce the submission](REPRODUCE.md)", text)
        self.assertIn("[Read the result argument](RESULTS.md)", text)
        self.assertIn("sparse-anchor", text)
        self.assertIn("not a measured runtime speedup", text)


if __name__ == "__main__":
    unittest.main()
