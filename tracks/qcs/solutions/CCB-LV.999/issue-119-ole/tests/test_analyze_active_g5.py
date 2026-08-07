import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_active_g5.py"
if SCRIPT.is_file():
    MODULE_SPEC = importlib.util.spec_from_file_location("analyze_active_g5", SCRIPT)
    ANALYZER = importlib.util.module_from_spec(MODULE_SPEC)
    MODULE_SPEC.loader.exec_module(ANALYZER)
else:
    ANALYZER = None


def synthetic_records():
    records = []
    gib = 1024**3
    centers = {64: 0.84, 128: 0.85, 192: 0.855}
    for chi in (64, 128, 192):
        for seed in range(1, 21):
            records.append(
                {
                    "status": "success",
                    "cell_id": f"chi-{chi}-seed-{seed}",
                    "params": {"chi": chi, "seed": seed, "delta": "0.15"},
                    "settings": {
                        "bp_tolerance": 1e-8,
                        "normalize_tensors": True,
                    },
                    "result": {
                        "sample_value": centers[chi] + 0.0001 * (seed - 10.5),
                        "wall_seconds": 60.0 + chi / 2 + seed / 10,
                        "peak_rss_bytes": (1 + chi / 64) * gib + seed,
                        "max_truncation_error": 0.01 / chi,
                        "max_bp_residual": 1e-10,
                        "bp_nonconverged_layers": 0,
                        "max_layer_wall_seconds": 2.0 + chi / 128,
                        "mean_layer_wall_seconds": 1.0 + chi / 256,
                        "max_virtual_bond_dimension": chi,
                        "norm_defect_available_layers": 0,
                        "max_norm_defect": None,
                    },
                }
            )
    return records


class AnalyzerModuleTests(unittest.TestCase):
    def test_g5_analyzer_module_exists(self):
        self.assertIsNotNone(ANALYZER)


@unittest.skipIf(ANALYZER is None, "analyzer not implemented yet")
class ActiveG5AssessmentTests(unittest.TestCase):
    def test_complete_stable_pilot_passes_predeclared_gate(self):
        assessment = ANALYZER.assess_g5(
            synthetic_records(),
            expected_seeds=range(1, 21),
            observed_chis=(64, 128, 192),
            target_chis=(256, 384, 512),
            node_memory_bytes=1_500_000 * 1024**2,
            wall_cap_seconds=24 * 3600,
        )

        self.assertTrue(assessment["gate"]["go"])
        self.assertEqual(assessment["gate"]["failed_checks"], [])
        self.assertAlmostEqual(
            assessment["paired_drift"]["64_to_128"]["mean"],
            0.01,
        )
        self.assertAlmostEqual(
            assessment["paired_drift"]["128_to_192"]["mean"],
            0.005,
        )
        self.assertEqual(
            assessment["diagnostics"]["norm"],
            "unavailable_by_normalization",
        )
        self.assertGreater(
            assessment["predictions"]["512"]["wall_seconds"],
            assessment["per_chi"]["192"]["max_wall_seconds"],
        )
        self.assertGreater(
            assessment["predictions"]["512"]["peak_rss_bytes"],
            assessment["per_chi"]["192"]["max_peak_rss_bytes"],
        )

    def test_runaway_paired_drift_and_bp_failure_block_g6(self):
        records = synthetic_records()
        for record in records:
            if record["params"]["chi"] == 192:
                record["result"]["sample_value"] += 0.05
        records[-1]["result"]["bp_nonconverged_layers"] = 1

        assessment = ANALYZER.assess_g5(
            records,
            expected_seeds=range(1, 21),
            observed_chis=(64, 128, 192),
            target_chis=(256, 384, 512),
            node_memory_bytes=1_500_000 * 1024**2,
            wall_cap_seconds=24 * 3600,
        )

        self.assertFalse(assessment["gate"]["go"])
        self.assertIn("paired_drift_stable", assessment["gate"]["failed_checks"])
        self.assertIn("bp_stable", assessment["gate"]["failed_checks"])

    def test_missing_seed_blocks_g6_even_when_remaining_cells_are_stable(self):
        assessment = ANALYZER.assess_g5(
            synthetic_records()[:-1],
            expected_seeds=range(1, 21),
            observed_chis=(64, 128, 192),
            target_chis=(256, 384, 512),
            node_memory_bytes=1_500_000 * 1024**2,
            wall_cap_seconds=24 * 3600,
        )

        self.assertFalse(assessment["gate"]["go"])
        self.assertIn("complete_grid", assessment["gate"]["failed_checks"])
        self.assertEqual(assessment["resource_fit_status"], "withheld_incomplete_grid")
        self.assertEqual(assessment["resource_fits"], {})
        self.assertEqual(assessment["predictions"], {})
        self.assertFalse(assessment["gate"]["checks"]["memory_feasible"])
        self.assertFalse(assessment["gate"]["checks"]["wall_feasible"])

    def test_output_writer_emits_machine_readable_table_plot_and_summary(self):
        assessment = ANALYZER.assess_g5(
            synthetic_records(),
            expected_seeds=range(1, 21),
            observed_chis=(64, 128, 192),
            target_chis=(256, 384, 512),
            node_memory_bytes=1_500_000 * 1024**2,
            wall_cap_seconds=24 * 3600,
        )
        with tempfile.TemporaryDirectory() as tmp:
            outputs = ANALYZER.write_g5_outputs(assessment, Path(tmp))

            self.assertTrue(outputs["json"].is_file())
            self.assertTrue(outputs["csv"].is_file())
            self.assertTrue(outputs["plot"].is_file())
            self.assertGreater(outputs["plot"].stat().st_size, 1000)
            loaded = json.loads(outputs["json"].read_text(encoding="utf-8"))
            self.assertTrue(loaded["gate"]["go"])


if __name__ == "__main__":
    unittest.main()
