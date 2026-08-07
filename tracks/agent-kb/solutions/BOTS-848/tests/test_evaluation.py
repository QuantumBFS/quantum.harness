import importlib
import unittest


class EvaluationTests(unittest.TestCase):
    def test_reference_agent_passes_grounding_and_decision_cases(self):
        try:
            module = importlib.import_module("eval.evaluate")
        except ModuleNotFoundError:
            self.fail("eval/evaluate.py has not been implemented")
        result = module.run_evaluation()
        self.assertGreaterEqual(result["total"], 10)
        self.assertEqual(result["passed"], result["total"])
        self.assertAlmostEqual(result["metrics"]["decision_accuracy"], 1.0)
        self.assertAlmostEqual(result["metrics"]["citation_coverage"], 1.0)
        self.assertAlmostEqual(result["metrics"]["unsupported_claim_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
