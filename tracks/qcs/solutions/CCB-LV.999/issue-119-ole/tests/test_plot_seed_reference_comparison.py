import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOLUTION_DIR = Path(__file__).resolve().parents[1]
PLOT_SCRIPT = SOLUTION_DIR / "scripts" / "plot_seed_reference_comparison.py"


class PlotSeedReferenceComparisonTests(unittest.TestCase):
    def test_plot_contains_all_seeds_and_audited_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PLOT_SCRIPT),
                    "--output-dir",
                    tmp,
                ],
                cwd=SOLUTION_DIR,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"plot command failed:\nstdout={completed.stdout}\nstderr={completed.stderr}",
            )

            output_dir = Path(tmp)
            png = output_dir / "ole-seed-public-quantum-comparison.png"
            pdf = output_dir / "ole-seed-public-quantum-comparison.pdf"
            metadata_path = output_dir / "ole-seed-public-quantum-comparison.json"

            self.assertGreater(png.stat().st_size, 10_000)
            self.assertGreater(pdf.stat().st_size, 5_000)

            metadata = json.loads(metadata_path.read_text())
            self.assertEqual(metadata["seed_ids"], list(range(1, 21)))
            self.assertEqual(metadata["seed_count"], 20)
            self.assertEqual(metadata["current"]["chi192"]["mean"], 0.8185618334942539)
            self.assertEqual(metadata["current"]["chi512"]["mean"], 0.8183229131612796)
            self.assertEqual(metadata["references"]["bp_tn_chi192_raw"]["value"], 0.8202512915)
            self.assertEqual(metadata["references"]["bp_tn_chi512_raw"]["value"], 0.821658489)
            self.assertEqual(metadata["references"]["ibm_heron_r3"]["value"], 0.824)
            self.assertEqual(
                metadata["references"]["ibm_heron_r3"]["processing"],
                "global_rescaling",
            )
            self.assertIsNone(metadata["references"]["ibm_heron_r3"]["error_bound"])


if __name__ == "__main__":
    unittest.main()
