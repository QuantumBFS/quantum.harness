from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO

import numpy as np

import reproduce
from scripts.analyze_even_trajectory import analyze_directory
from scripts.assess_paper_rg_gate import assess_gate


class ReproductionEntryPointTests(unittest.TestCase):
    def test_paper_defaults_match_l45_supplement_parameters(self) -> None:
        args = reproduce.build_parser().parse_args(["paper", "--dry-run"])
        self.assertEqual(args.length, 45)
        self.assertEqual(args.coupling, 0.436)
        self.assertEqual(args.steps, 3000)
        self.assertEqual(args.sweeps, 20)
        self.assertEqual(args.walkers, 16)
        self.assertEqual(args.mu, 5e-5)
        self.assertTrue(args.validate)

    def test_candidate_defaults_run_both_pair_ties(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["candidate26", "--coupling", "0.436", "--dry-run"]
        )
        self.assertEqual(args.pair_tie, "both")
        self.assertEqual(args.threshold, 0.001)
        self.assertTrue(args.validate)

    def test_candidate_coupling_is_required(self) -> None:
        parser = reproduce.build_parser()
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["candidate26"])

    def test_full_workflow_requires_explicit_preset(self) -> None:
        parser = reproduce.build_parser()
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["full"])

    def test_formal_full_preset_contains_paper_scale_measurements(self) -> None:
        settings = reproduce.FULL_PRESETS["formal"]
        self.assertEqual(settings["rounds"], 5)
        self.assertEqual(settings["steps"], 3000)
        self.assertEqual(settings["walkers"], 16)
        self.assertEqual(settings["jacobian_runs"], 16)
        self.assertEqual(settings["jacobian_measurements"], 1_000_000)

    def test_fixed_point_defaults_use_predeclared_complete_vector_gates(self) -> None:
        args = reproduce.build_parser().parse_args(
            [
                "fixed-point",
                "--map-input",
                "rg2",
                "--jacobian",
                "jacobian.npz",
                "--dry-run",
            ]
        )
        self.assertEqual(args.steps, 3000)
        self.assertEqual(args.walkers, 16)
        self.assertEqual(args.absolute_tolerance, 1e-3)
        self.assertEqual(args.relative_tolerance, 5e-3)

    def test_fixed_point_repeat_v2_has_only_preregistered_repeat_choices(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["fixed-point-repeat-v2", "--repeat", "1", "--dry-run"]
        )
        self.assertEqual(args.repeat, 1)
        self.assertEqual(
            reproduce.V2_REPEAT_SEEDS[1]["jacobian"], 202608101
        )

    def test_fixed_point_repeat_v3_has_calibration_and_confirmation_seeds(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["fixed-point-repeat-v3", "--repeat", "1", "--dry-run"]
        )
        self.assertEqual(args.repeat, 1)
        seeds = reproduce.V3_REPEAT_SEEDS[1]
        self.assertNotEqual(seeds["base_calibration"], seeds["base_confirmation"])
        self.assertNotEqual(seeds["fixed_calibration"], seeds["fixed_confirmation"])

    def test_v3_audit_requires_explicit_completed_repeats(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["audit-fixed-point-v3", "--repeats", "1", "2", "--dry-run"]
        )
        self.assertEqual(args.repeats, [1, 2])
        self.assertEqual(args.handler, reproduce._audit_fixed_point_v3)

    def test_v4_pilot_freezes_distinct_seed_families(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["fixed-point-v4-pilot", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._fixed_point_v4_pilot)
        self.assertEqual(len(set(reproduce.V4_PILOT_SEEDS.values())), 8)

    def test_v4_batch_diagnostic_has_frozen_third_seed(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["fixed-point-v4-batch-diagnostic", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._fixed_point_v4_batch_diagnostic)
        self.assertEqual(reproduce.V4_PILOT_SEEDS["jacobian_third"], 202610521)

    def test_v5_table1_repeat_uses_stratified_manifest(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["table1-v5-repeat", "--repeat", "1", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._table1_v5_repeat)
        manifests = []
        for repeat in (1, 2, 3):
            path = Path("config") / f"v5_table1_repeat{repeat}_seeds.json"
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        streams = [
            (record["entropy"], tuple(record["spawn_key"]))
            for manifest in manifests
            for record in manifest["run_seed_sequences"]
        ]
        self.assertEqual(len(streams), 48)
        self.assertEqual(len(set(streams)), 48)

    def test_direct_paper_table1_repeats_freeze_independent_streams(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["paper-table1-repeat", "--repeat", "1", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._paper_table1_repeat)
        streams = []
        scalar_seeds = []
        for repeat in (1, 2, 3):
            _, manifest = reproduce._paper_table1_manifest(repeat)
            self.assertEqual(manifest["rg"]["steps"], 3000)
            self.assertEqual(manifest["jacobian"]["measurements_per_run"], 1_000_000)
            streams.extend(
                (record["entropy"], tuple(record["spawn_key"]))
                for record in manifest["run_seed_sequences"]
            )
            scalar_seeds.extend(manifest["rg"]["seeds"])
            scalar_seeds.append(manifest["frozen_validation"]["seed"])
            scalar_seeds.append(manifest["bootstrap_seed"])
        self.assertEqual(len(streams), 48)
        self.assertEqual(len(set(streams)), 48)
        self.assertEqual(len(scalar_seeds), len(set(scalar_seeds)))

    def test_direct_paper_table1_assessment_defaults_to_three_repeats(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["paper-table1-assess", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._assess_paper_table1)
        self.assertEqual(args.bootstrap, 10_000)

    def test_rg2_hard_gate_requires_complete_coupling_vector_and_moments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "summary.json").write_text(
                json.dumps(
                    {
                        "operator_names": [f"op{index}" for index in range(13)],
                        "final_renormalized_couplings": [0.0] * 13,
                    }
                ),
                encoding="utf-8",
            )
            (path / "convergence.json").write_text(
                json.dumps(
                    {
                        "late_statistics_status": "ESTIMATED_FROM_LATE_WINDOW_CHUNKS",
                        "covariance_status": "POSITIVE_DEFINITE",
                        "coupling_drift_90_to_100_percent": [0.0] * 13,
                        "max_abs_coupling_drift_90_to_100_percent": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            validation = {
                "independent_runs": 16,
                "measurement_sweeps_per_run": 1000,
                "family_alpha": 0.05,
                "familywise_status": "PASS",
                "z_scores_against_uniform_target": [0.0] * 13,
                "max_abs_z": 0.0,
                "bonferroni_critical_abs_z": 2.9,
            }
            (path / "frozen_validation.json").write_text(
                json.dumps(validation), encoding="utf-8"
            )
            report = assess_gate(
                path,
                max_coupling_drift=0.001,
                expected_operators=13,
                minimum_validation_runs=16,
                minimum_validation_measurements=1000,
                expected_family_alpha=0.05,
            )
            self.assertEqual(report["status"], "PASS")
            validation["familywise_status"] = "FAIL"
            validation["max_abs_z"] = 4.0
            (path / "frozen_validation.json").write_text(
                json.dumps(validation), encoding="utf-8"
            )
            failed = assess_gate(
                path,
                max_coupling_drift=0.001,
                expected_operators=13,
                minimum_validation_runs=16,
                minimum_validation_measurements=1000,
                expected_family_alpha=0.05,
            )
            self.assertEqual(failed["status"], "FAIL")
            self.assertIn(
                "all_13_frozen_moments_pass_bonferroni", failed["failed_gates"]
            )

    def test_short_smoke_trajectory_is_explicitly_statistically_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "summary.json").write_text(
                json.dumps({"length": 45}), encoding="utf-8"
            )
            np.savez(
                path / "trajectory.npz",
                running_bias=np.zeros((2, 13)),
                mean_operators=np.zeros((2, 13)),
                covariance=np.zeros((2, 13, 13)),
            )
            report = analyze_directory(path)
            serialized = (path / "convergence.json").read_text(encoding="utf-8")
            self.assertEqual(
                report["late_statistics_status"],
                "INSUFFICIENT_LATE_WINDOW_FOR_STANDARD_ERROR",
            )
            self.assertIsNone(report["max_abs_late_z"])
            self.assertIsNone(report["mean_covariance_condition_number"])
            self.assertEqual(report["coupling_drift_90_to_100_percent"], [0.0] * 13)
            self.assertNotIn("NaN", serialized)


if __name__ == "__main__":
    unittest.main()
