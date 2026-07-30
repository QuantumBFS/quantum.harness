import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "plot_available_analysis.py"


class PlotAvailableAnalysisTest(unittest.TestCase):
    def test_plot_writes_nonempty_png_from_literal_summary(self):
        spec = importlib.util.spec_from_file_location("plot_available_analysis", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        summary = {
            "status": "gate-pending",
            "primary_diagnostic": {
                "R": 2.2362,
                "R_covariance_stderr": 0.0004,
                "sqrt5": 2.23606797749979,
            },
            "stability_diagnostic": {
                "accepted_matched_windows": [
                    {"model": "M1", "L_min": 12, "yt_mode": "fixed", "R": 2.2357},
                    {"model": "M2", "L_min": 16, "yt_mode": "fixed", "R": 2.2359},
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "window_stability.png"
            module.plot_analysis(summary, output)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
