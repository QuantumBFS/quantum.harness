from pathlib import Path
import unittest


SOLUTION_ROOT = Path(__file__).resolve().parents[1]


class AgentSkillContractTests(unittest.TestCase):
    def test_skill_exposes_grounded_scientific_contract(self):
        skill_path = SOLUTION_ROOT / "agent" / "SKILL.md"
        workflow_path = SOLUTION_ROOT / "agent" / "workflow.md"
        if not skill_path.exists() or not workflow_path.exists():
            self.fail("agent/SKILL.md and agent/workflow.md have not been implemented")

        skill = skill_path.read_text(encoding="utf-8")
        workflow = workflow_path.read_text(encoding="utf-8")
        combined = skill + "\n" + workflow

        self.assertTrue(skill.startswith("---\nname: dfpt-channel-research-agent\n"))
        self.assertIn("description: Use when", skill)
        for status in (
            "established-theory",
            "exact-constraint",
            "numerical-evidence",
            "working-hypothesis",
            "open-question",
        ):
            self.assertIn(status, combined)
        for decision in (
            "dfpt-safe",
            "static-correction",
            "dynamic-correction",
            "abstain",
        ):
            self.assertIn(decision, combined)
        self.assertIn("source_traceable", combined)
        self.assertIn("falsification", combined.lower())
        self.assertIn("fit_response_matrix", combined)
        self.assertIn("compare_corrected_to_baselines", combined)
        self.assertIn("measured_runtime", combined)
        self.assertIn("physical_accuracy_established", combined)
        self.assertIn("operator basis", combined.lower())


if __name__ == "__main__":
    unittest.main()
