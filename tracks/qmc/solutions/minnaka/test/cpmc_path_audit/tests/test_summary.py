import importlib.util
import math
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_summary", ROOT / "summarize.py"
)
SUMMARY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SUMMARY)


class SummaryScoreTest(unittest.TestCase):
    def test_under_sampling_score(self):
        record = {
            "log_abs_d": math.log(2.0),
            "log_q": math.log(0.1),
            "log_abs_weight": math.log(3.0),
            "min_log_abs_weight": math.log(0.3),
            "linear_bottleneck": math.log(100.0),
            "alive": True,
        }
        scores = SUMMARY.record_scores(record, math.log(10.0))
        self.assertAlmostEqual(scores["under_sampling"], math.log10(2.0))
        self.assertAlmostEqual(scores["bottleneck"], 2.0)

    def test_dead_path_has_no_sampling_score(self):
        record = {
            "log_abs_d": 0.0,
            "log_q": -math.inf,
            "log_abs_weight": -math.inf,
            "min_log_abs_weight": -2.0,
            "linear_bottleneck": 1.0,
            "alive": False,
        }
        scores = SUMMARY.record_scores(record, math.log(4.0))
        self.assertIsNone(scores["under_sampling"])
        self.assertIsNone(scores["bottleneck"])

    def test_quantiles(self):
        values = [0.0, 1.0, 2.0, 3.0, 4.0]
        self.assertEqual(SUMMARY.sample_quantile(values, 0.0), 0.0)
        self.assertEqual(SUMMARY.sample_quantile(values, 0.5), 2.0)
        self.assertEqual(SUMMARY.sample_quantile(values, 1.0), 4.0)


if __name__ == "__main__":
    unittest.main()
