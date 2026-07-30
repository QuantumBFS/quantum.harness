import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYZER = REPO_ROOT / "scripts" / "analyze-honeycomb-baseline.py"

SIZES = [10, 12, 14, 16, 18, 20]
FIELDS = [2.1025, 2.1125, 2.1225, 2.1325, 2.1425, 2.1525, 2.1625]
SEEDS = [61001, 61002]
TRUE_HC = 2.13250
TRUE_Q_STAR = 0.6149
Y_T = 1.587
Y_I = -0.815
SOURCE_COMMIT = "a" * 40
SBATCH_BYTES = b"#!/bin/bash\n# frozen synthetic scheduler\n"
SBATCH_SHA256 = hashlib.sha256(SBATCH_BYTES).hexdigest()


def deterministic_json(record):
    return (
        json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def synthetic_spacetime_binder(size, field, *, reverse_slope=False):
    x_value = (field - TRUE_HC) * size**Y_T
    linear_coefficient = 0.020 if reverse_slope else -0.020
    return (
        TRUE_Q_STAR
        + linear_coefficient * x_value
        + 0.0010 * x_value**2
        - 0.00010 * x_value**3
        + 0.020 * size**Y_I
    )


def proposal(
    *,
    analysis_overrides=None,
    gate_overrides=None,
    sbatch_script="scripts/run-honeycomb-baseline-array.sbatch",
):
    cells = [
        {
            "cell_id": f"cell-{index:04d}",
            "params": {"L": size, "h": field, "seed": seed},
        }
        for index, (size, field, seed) in enumerate(
            itertools.product(SIZES, FIELDS, SEEDS), start=1
        )
    ]
    analysis = {
        "estimator_id": "spacetime_binder_q",
        "diagnostic_estimator_id": "equal_time_binder_q",
        "sizes": list(SIZES),
        "fields": list(FIELDS),
        "seeds": list(SEEDS),
        "primary_field_window": [
            2.1125,
            2.1225,
            2.1325,
            2.1425,
            2.1525,
        ],
        "crossing_field_window": list(FIELDS),
        "y_t": Y_T,
        "y_i": Y_I,
        "primary_terms": ["a1", "a2", "a3", "b1"],
        "bootstrap_resamples": 16,
        "bootstrap_seed": 148010,
        "crossing_bootstrap_resamples": 16,
        "crossing_bootstrap_seed": 148011,
        "profile_grid_points": 31,
        "covariance_estimator": "independent-chain-diagonal",
        "optimizer": "bounded coarse-grid plus golden-section profile WLS v1",
        "pooling_rule": (
            "max(within-chain standard error, between-chain standard error)"
        ),
        "bootstrap_method": (
            "replica-resample plus within-chain Gaussian draw and full "
            "profile refit"
        ),
        "coverage_campaign_id": "pending-production-coverage-campaign",
        "coverage_passed": False,
        "primary_fit_id": "attempt-010-primary-historical",
        "sbatch_sha256_key": "baseline_sbatch_sha256",
        "variants": [
            {
                "fit_id": "attempt-010-outer-window",
                "classification": "systematic-variant",
                "sizes": list(SIZES),
                "field_window": "outer",
                "y_t": Y_T,
                "y_i": Y_I,
                "terms": ["a1", "a2", "a3", "b1"],
            },
            {
                "fit_id": "attempt-010-lmin12",
                "classification": "systematic-variant",
                "sizes": [12, 14, 16, 18, 20],
                "field_window": "primary",
                "y_t": Y_T,
                "y_i": Y_I,
                "terms": ["a1", "a2", "a3", "b1"],
                "discard_reason": "preregistered-Lmin-variant",
            },
        ],
        "robustness_required_fit_ids": [
            "attempt-010-outer-window",
            "attempt-010-lmin12",
        ],
    }
    if analysis_overrides:
        analysis.update(analysis_overrides)
    gate = {
        "expected_cell_count": 84,
        "aspect_tolerance": 1e-12,
        "minimum_sign": 0.999999,
        "maximum_string_fill": 0.65,
        "minimum_rebin_count": 16,
        "max_covariance_condition": 1e12,
        "min_degrees_of_freedom": 4,
        "min_p_value": 0.01,
        "max_bootstrap_failed_fraction": 0.50,
        "max_crossing_chi2_per_dof": 1e6,
        "require_all_adjacent_crossings": True,
        "require_positive_crossing_slope": True,
        "reference_hc": 2.13250,
        "reference_hc_sigma": 4e-5,
        "max_reference_z": 10.0,
        "max_hc_sigma_stat": 0.005,
        "reference_q_star": 0.6149,
        "reference_q_star_sigma": 7e-4,
        "max_q_star_reference_z": 10.0,
        "max_variant_shift_paired_sigma": 10.0,
        "require_complete_bootstrap_attempts": True,
        "production_data": False,
        "production_gate": "locked",
    }
    if gate_overrides:
        gate.update(gate_overrides)
    return {
        "schema_version": "yanwang148.reproduction-run.v1",
        "run_id": "attempt-010-test",
        "run_dir": "run",
        "status": "proposal-frozen",
        "data_class": "pilot",
        "model": {"name": "honeycomb TFIM"},
        "scan_axes": {
            "L": list(SIZES),
            "h": list(FIELDS),
            "seed": list(SEEDS),
        },
        "settings": {
            "phase": "pilot",
            "lattice_name": "honeycomb",
            "J": 1.0,
            "beta_policy": "beta_h_equals_L",
            "measurement_sweeps": 12000,
            "thermalization_sweeps": 3000,
            "bin_size": 50,
            "string_length_scale": 2.5,
            "string_length_padding": 128,
            "minimum_rebin_count": 16,
            "maximum_string_fill": 0.65,
            "aspect_tolerance": 1e-12,
        },
        "cells": cells,
        "analysis": analysis,
        "acceptance_gate": gate,
        "provenance": {
            "phase": "pilot",
            "production_data": False,
            "sbatch_script": sbatch_script,
            "baseline_sbatch_sha256": SBATCH_SHA256,
        },
    }


class AnalysisFixture:
    def __init__(
        self,
        *,
        analysis_overrides=None,
        gate_overrides=None,
        poor_fit=False,
        reverse_slope=False,
        source_overrides=None,
        sbatch_script="scripts/run-honeycomb-baseline-array.sbatch",
    ):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()
        self.sbatch_script = sbatch_script
        script_path = self.root / sbatch_script
        script_path.parent.mkdir(parents=True)
        script_path.write_bytes(SBATCH_BYTES)
        self.source_plan = proposal(
            analysis_overrides=analysis_overrides,
            gate_overrides=gate_overrides,
            sbatch_script=sbatch_script,
        )
        if source_overrides:
            self.source_plan.update(source_overrides)
        self.source_path = self.run_dir / "run.json"
        self.source_bytes = deterministic_json(self.source_plan)
        self.source_path.write_bytes(self.source_bytes)
        source_hash = hashlib.sha256(self.source_bytes).hexdigest()
        provenance = dict(self.source_plan["provenance"])
        provenance.update(
            {
                "source_commit": SOURCE_COMMIT,
                "source_plan_path": "run/run.json",
                "source_plan_sha256": source_hash,
            }
        )
        self.spec = {
            key: self.source_plan[key]
            for key in (
                "schema_version",
                "run_id",
                "run_dir",
                "settings",
                "cells",
                "analysis",
                "acceptance_gate",
            )
        }
        self.spec["provenance"] = provenance
        self.spec_path = self.run_dir / "run_spec.json"
        self.spec_path.write_bytes(deterministic_json(self.spec))
        self._write_cells(
            poor_fit=poor_fit,
            reverse_slope=reverse_slope,
        )

    def _write_cells(self, *, poor_fit, reverse_slope):
        for array_index, cell in enumerate(self.spec["cells"], start=1):
            cell_id = cell["cell_id"]
            size = cell["params"]["L"]
            field = cell["params"]["h"]
            seed = cell["params"]["seed"]
            size_index = SIZES.index(size)
            field_index = FIELDS.index(field)
            seed_offset = -1.0e-5 if seed == SEEDS[0] else 1.0e-5
            primary = synthetic_spacetime_binder(
                size,
                field,
                reverse_slope=reverse_slope,
            ) + seed_offset
            if poor_fit:
                primary += (
                    0.012
                    if (size_index + field_index) % 2 == 0
                    else -0.012
                )
            diagnostic = (
                0.35
                + 0.002 * size_index
                - 0.001 * field_index
                - seed_offset
            )
            cell_dir = self.run_dir / "cells" / cell_id
            cell_dir.mkdir(parents=True)
            artifact = cell_dir / "raw-summary.txt"
            artifact.write_text(f"{cell_id} deterministic raw summary\n")
            relative_artifact = artifact.relative_to(self.root).as_posix()
            artifact_bytes = artifact.read_bytes()
            manifest = {
                "schema_version": "yanwang148.beta-cell.v2",
                "run_id": self.spec["run_id"],
                "cell_id": cell_id,
                "params": cell["params"],
                "settings": self.spec["settings"],
                "provenance": self.spec["provenance"],
                "status": "success",
                "effective_parameters": {
                    "lattice_name": "honeycomb",
                    "L": size,
                    "J": 1.0,
                    "h": field,
                    "seed": seed,
                    "beta": size / field,
                    "T": field / size,
                    "beta_policy": "beta_h_equals_L",
                    "beta_factor": 1.0 / field,
                    "beta_over_L": 1.0 / field,
                    "beta_times_h": float(size),
                    "measurement_sweeps": 12000,
                    "thermalization_sweeps": 3000,
                    "bin_size": 50,
                    "string_length": 10000 + size,
                },
                "observables": {
                    "spacetime_binder": primary,
                    "spacetime_binder_se": 2.0e-4,
                    "binder": diagnostic,
                    "binder_se": 2.0e-4,
                },
                "diagnostics": {
                    "health_passed": True,
                    "checks": {
                        "sign_passed": True,
                        "field_flip_passed": True,
                        "string_fill_passed": True,
                        "rebin_passed": True,
                        "finite_passed": True,
                        "autocorr_passed": True,
                        "periodicity_passed": True,
                        "effective_parameters_passed": True,
                        "beta_policy_passed": True,
                        "temperature_inverse_passed": True,
                    },
                    "sign_mean": 1.0,
                    "field_flip_mean": 2.0,
                    "string_fill_mean": 0.2,
                    "rebin_counts": {
                        "Mag2": 16,
                        "Mag4": 16,
                        "SpaceTimeMag2": 16,
                        "SpaceTimeMag4": 16,
                    },
                    "autocorr_times": {
                        "Mag2": 0.2,
                        "Mag4": 0.2,
                        "SpaceTimeMag2": 0.2,
                        "SpaceTimeMag4": 0.2,
                    },
                    "nonfinite_fields": [],
                },
                "artifacts": [
                    {
                        "path": relative_artifact,
                        "bytes": len(artifact_bytes),
                        "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    }
                ],
            }
            (cell_dir / "manifest.json").write_bytes(
                deterministic_json(manifest)
            )
            scheduler = {
                "schema_version": "yanwang148.scheduler-manifest.v2",
                "status": "completed",
                "provenance_passed": True,
                "source": {
                    "git_head": SOURCE_COMMIT,
                    "clean": True,
                    "dirty_entries": [],
                },
                "execution": {
                    "sbatch_script": self.sbatch_script,
                    "sbatch_sha256": SBATCH_SHA256,
                },
                "slurm": {
                    "SLURM_ARRAY_TASK_ID": str(array_index),
                    "SLURM_JOB_ID": f"test-{array_index}",
                },
            }
            (
                self.run_dir
                / f"scheduler-manifest-{array_index}.json"
            ).write_bytes(deterministic_json(scheduler))

    def manifest_path(self, cell_id="cell-0001"):
        return self.run_dir / "cells" / cell_id / "manifest.json"

    def load_manifest(self, cell_id="cell-0001"):
        return json.loads(self.manifest_path(cell_id).read_text())

    def write_manifest(self, manifest, cell_id="cell-0001"):
        self.manifest_path(cell_id).write_bytes(deterministic_json(manifest))

    def run(
        self,
        output_name,
        *,
        sealed_bootstrap_export=False,
        workers=None,
        fit_ids=None,
        central_only=False,
    ):
        output_dir = self.root / output_name
        command = [
            sys.executable,
            str(ANALYZER),
            "--run-spec",
            str(self.spec_path),
            "--out-dir",
            str(output_dir),
        ]
        if sealed_bootstrap_export:
            command.append("--sealed-bootstrap-export")
        for fit_id in fit_ids or []:
            command.extend(["--fit-id", fit_id])
        if central_only:
            command.append("--central-only")
        environment = os.environ.copy()
        if workers is not None:
            environment["YANWANG_ANALYSIS_WORKERS"] = str(workers)
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        report = json.loads((output_dir / "report.json").read_text())
        return result, output_dir, report

    def close(self):
        self.temporary.cleanup()


class HoneycombBaselineAnalysisTests(unittest.TestCase):
    def test_central_only_runs_all_frozen_fits_without_full_gate(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        result, _, report = fixture.run(
            "central-only",
            workers=4,
            central_only=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(report["central_only"])
        self.assertTrue(report["partial_analysis"])
        self.assertTrue(report["central_robustness_gate_passed"])
        self.assertFalse(report["passed_attempt_gate"])
        self.assertFalse(report["pilot_promotion_gate"]["passed"])
        self.assertEqual(len(report["fits"]), 3)
        self.assertTrue(
            all(fit["central"]["converged"] for fit in report["fits"])
        )
        self.assertTrue(
            all(
                fit["bootstrap"]["attempted_resamples"] == 0
                for fit in report["fits"]
            )
        )

    def test_primary_only_selection_parallelizes_without_claiming_full_gate(
        self,
    ):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        result, _, report = fixture.run(
            "primary-only",
            workers=4,
            fit_ids=["attempt-010-primary-historical"],
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(
            "parallel-bootstrap:strategy=sample-chunks",
            result.stderr,
        )
        self.assertEqual(
            report["fit_selection"],
            ["attempt-010-primary-historical"],
        )
        self.assertTrue(report["partial_analysis"])
        self.assertTrue(report["partial_fit_gate_passed"])
        self.assertFalse(report["passed_attempt_gate"])
        self.assertFalse(report["pilot_promotion_gate"]["passed"])
        self.assertEqual(len(report["fits"]), 1)
        self.assertEqual(
            report["fits"][0]["bootstrap"]["attempted_resamples"],
            16,
        )

    def test_packed_array_provenance_route_is_accepted(self):
        fixture = AnalysisFixture(
            sbatch_script=(
                "scripts/run-honeycomb-baseline-packed-array.sbatch"
            )
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("packed-array")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(report["technical_gate"]["passed"])

    def test_600k_packed_array_provenance_route_is_accepted(self):
        fixture = AnalysisFixture(
            sbatch_script=(
                "scripts/run-honeycomb-baseline-600k-packed-array.sbatch"
            )
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("packed-array-600k")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(report["technical_gate"]["passed"])

    def test_exact_model_recovery_uses_spacetime_estimator_and_passes_pilot(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        result, output_dir, report = fixture.run("analysis")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(report["technical_gate"]["passed"])
        self.assertTrue(report["crossing_gate_passed"])
        self.assertTrue(report["pilot_promotion_gate"]["passed"])
        self.assertTrue(report["passed_pilot_gate"])
        self.assertFalse(report["production_result"])
        self.assertEqual(len(report["crossing_fits"]), len(SIZES) - 1)
        self.assertTrue(all(row["passed"] for row in report["crossing_fits"]))

        primary = report["fits"][0]
        estimates = primary["central"]["parameters"]
        self.assertAlmostEqual(estimates["hc"], TRUE_HC, delta=5e-5)
        self.assertAlmostEqual(estimates["Q_star"], TRUE_Q_STAR, delta=5e-4)
        self.assertEqual(primary["bootstrap"]["attempted_resamples"], 16)
        self.assertEqual(
            primary["bootstrap"]["attempted_resamples"],
            primary["bootstrap"]["successful_resamples"]
            + primary["bootstrap"]["failed_resamples"],
        )
        self.assertTrue(
            all(
                row["estimator_id"] == "spacetime_binder_q"
                for row in report["pooled_rows"]
            )
        )
        fit_record = json.loads(
            (
                output_dir
                / "fits"
                / "attempt-010-primary-historical.json"
            ).read_text()
        )
        self.assertEqual(fit_record["schema_version"], "yanwang148.fit.v2")
        self.assertEqual(fit_record["estimator_id"], "spacetime_binder_q")
        self.assertFalse(fit_record["diagnostics"]["coverage_passed"])
        self.assertFalse(fit_record["accepted"])
        parameter_order = fit_record["parameters"]["parameter_order"]
        covariance = fit_record["parameters"]["covariance"]
        self.assertEqual(
            parameter_order,
            ["hc", "Q_star", "a1", "a2", "a3", "b1"],
        )
        self.assertEqual(len(covariance), len(parameter_order))
        self.assertTrue(
            all(len(row) == len(parameter_order) for row in covariance)
        )
        self.assertIn(
            "pending-production-coverage-campaign",
            fit_record["rejection_reason"],
        )

    def test_wrong_estimator_is_a_technical_failure(self):
        fixture = AnalysisFixture(
            analysis_overrides={"estimator_id": "equal_time_binder_q"}
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("wrong-estimator")
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "analysis.estimator_id:must-be-spacetime",
            report["technical_gate"]["errors"],
        )

    def test_sbatch_hash_key_cannot_be_redirected(self):
        fixture = AnalysisFixture(
            analysis_overrides={
                "sbatch_sha256_key": "preflight_sbatch_sha256"
            }
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("wrong-sbatch-key")
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "analysis.sbatch_sha256_key:must-be-baseline-sbatch-sha256",
            report["technical_gate"]["errors"],
        )

    def test_literal_aspect_failure_is_rejected(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        manifest = fixture.load_manifest()
        manifest["effective_parameters"]["beta"] *= 1.01
        fixture.write_manifest(manifest)
        result, _, report = fixture.run("bad-aspect")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(report["technical_gate"]["passed"])
        first = next(
            row for row in report["cell_checks"]
            if row["cell_id"] == "cell-0001"
        )
        self.assertIn("manifest:literal-aspect", first["errors"])

    def test_wrong_crossing_slope_orientation_fails_scientific_gate(self):
        fixture = AnalysisFixture(reverse_slope=True)
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("wrong-slope")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["technical_gate"]["passed"])
        self.assertFalse(report["crossing_gate_passed"])
        self.assertTrue(
            all(
                row["slope"] < 0 and not row["slope_passed"]
                for row in report["crossing_fits"]
            )
        )
        self.assertFalse(report["passed_pilot_gate"])

    def test_parallel_bootstrap_chunks_are_byte_identical_to_serial_analysis(
        self,
    ):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        serial_result, serial_dir, _ = fixture.run(
            "serial-analysis",
            workers=1,
        )
        parallel_result, parallel_dir, _ = fixture.run(
            "parallel-analysis",
            workers=24,
        )
        self.assertEqual(
            serial_result.returncode,
            0,
            serial_result.stderr + serial_result.stdout,
        )
        self.assertEqual(
            parallel_result.returncode,
            0,
            parallel_result.stderr + parallel_result.stdout,
        )
        self.assertIn(
            (
                "parallel-bootstrap:strategy=sample-chunks "
                "requested_workers=24 effective_workers=24"
            ),
            parallel_result.stderr,
        )
        self.assertIn(
            (
                "parallel-crossing:requested_workers=24 "
                "effective_workers=5 size_pairs=5"
            ),
            parallel_result.stderr,
        )
        serial_files = {
            path.relative_to(serial_dir): path.read_bytes()
            for path in serial_dir.rglob("*")
            if path.is_file()
        }
        parallel_files = {
            path.relative_to(parallel_dir): path.read_bytes()
            for path in parallel_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(serial_files, parallel_files)

    def test_exact_roster_rejects_missing_declared_manifest_and_extra_manifest(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        fixture.manifest_path("cell-0084").unlink()
        extra_dir = fixture.run_dir / "cells" / "cell-extra"
        extra_dir.mkdir()
        (extra_dir / "manifest.json").write_text("{}\n")
        result, _, report = fixture.run("bad-roster")
        self.assertEqual(result.returncode, 2)
        errors = report["technical_gate"]["errors"]
        self.assertIn("cells:extra-manifests", errors)
        last = next(
            row for row in report["cell_checks"]
            if row["cell_id"] == "cell-0084"
        )
        self.assertIn("manifest:missing", last["errors"])

    def test_artifact_hash_and_zero_standard_error_fail_closed(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        manifest = fixture.load_manifest()
        manifest["observables"]["spacetime_binder_se"] = 0.0
        fixture.write_manifest(manifest)
        artifact_path = (
            fixture.run_dir
            / "cells"
            / "cell-0001"
            / "raw-summary.txt"
        )
        artifact_path.write_text("tampered\n")
        result, _, report = fixture.run("bad-cell")
        self.assertEqual(result.returncode, 2)
        first = next(
            row for row in report["cell_checks"]
            if row["cell_id"] == "cell-0001"
        )
        self.assertIn(
            "cell-0001.observables.spacetime_binder_se:nonpositive",
            first["errors"],
        )
        self.assertIn("artifact:sha256-mismatch", first["errors"])

    def test_quantitative_health_diagnostics_are_rechecked(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        manifest = fixture.load_manifest()
        manifest["diagnostics"]["sign_mean"] = 0.95
        manifest["diagnostics"]["rebin_counts"]["SpaceTimeMag4"] = 2
        manifest["diagnostics"]["autocorr_times"]["SpaceTimeMag2"] = -0.1
        fixture.write_manifest(manifest)
        result, _, report = fixture.run("bad-diagnostics")
        self.assertEqual(result.returncode, 2)
        first = next(
            row for row in report["cell_checks"]
            if row["cell_id"] == "cell-0001"
        )
        self.assertIn("manifest:minimum-sign", first["errors"])
        self.assertIn("manifest:minimum-rebin-count", first["errors"])
        self.assertIn("manifest:negative-autocorrelation", first["errors"])

    def test_poor_fit_is_scientific_failure_not_technical_failure(self):
        fixture = AnalysisFixture(poor_fit=True)
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("poor-fit")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["technical_gate"]["passed"])
        primary = report["fits"][0]
        self.assertFalse(primary["accepted"])
        self.assertIn("goodness-of-fit", primary["rejection_reasons"])
        self.assertFalse(report["passed_pilot_gate"])

    def test_covariance_condition_gate_is_enforced(self):
        fixture = AnalysisFixture(
            gate_overrides={"max_covariance_condition": 1.0}
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("condition")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["technical_gate"]["passed"])
        self.assertIn(
            "covariance-condition",
            report["fits"][0]["rejection_reasons"],
        )

    def test_required_robustness_fit_cannot_be_skipped_when_rejected(self):
        required_variant = {
            "fit_id": "required-low-dof",
            "classification": "systematic-variant",
            "sizes": [10, 12],
            "field_window": "primary",
            "y_t": Y_T,
            "y_i": Y_I,
            "terms": ["a1", "a2", "a3", "b1", "c1"],
            "discard_reason": "preregistered-leave-one-size-out",
        }
        fixture = AnalysisFixture(
            analysis_overrides={
                "variants": [required_variant],
                "robustness_required_fit_ids": ["required-low-dof"],
            }
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("required-rejected")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["technical_gate"]["passed"])
        self.assertTrue(report["fits"][0]["accepted"])
        required = report["fits"][1]
        self.assertFalse(required["accepted"])
        checks = report["pilot_promotion_gate"]["checks"]
        required_check = next(
            row for row in checks
            if row["check"] == "required-robustness-fit:required-low-dof"
        )
        self.assertFalse(required_check["passed"])
        self.assertFalse(report["passed_pilot_gate"])

    def test_identical_variant_uses_paired_bootstrap_indices(self):
        duplicate_variant = {
            "fit_id": "duplicate-primary",
            "classification": "systematic-variant",
            "sizes": list(SIZES),
            "field_window": "primary",
            "y_t": Y_T,
            "y_i": Y_I,
            "terms": ["a1", "a2", "a3", "b1"],
        }
        fixture = AnalysisFixture(
            analysis_overrides={
                "variants": [duplicate_variant],
                "robustness_required_fit_ids": ["duplicate-primary"],
            }
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("paired")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        shift = report["pilot_promotion_gate"][
            "accepted_variant_shifts"
        ][0]
        self.assertEqual(shift["delta_hc"], 0.0)
        self.assertEqual(shift["paired_delta_sigma"], 0.0)
        self.assertEqual(shift["shift_in_paired_sigma"], 0.0)
        self.assertEqual(
            shift["common_successful_resample_count"],
            len(shift["common_successful_resample_indices"]),
        )
        self.assertGreater(
            shift["common_successful_resample_count"],
            1,
        )

    def test_unsafe_fit_id_is_rejected_before_any_external_write(self):
        fixture = AnalysisFixture(
            analysis_overrides={"primary_fit_id": "../../escaped-primary"}
        )
        self.addCleanup(fixture.close)
        result, _, report = fixture.run("unsafe-fit-id")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(report["technical_gate"]["passed"])
        self.assertFalse((fixture.root / "escaped-primary.json").exists())

    def test_malformed_scheduler_shape_produces_failure_report(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        scheduler_path = fixture.run_dir / "scheduler-manifest-1.json"
        scheduler = json.loads(scheduler_path.read_text())
        scheduler["source"] = []
        scheduler_path.write_bytes(deterministic_json(scheduler))
        result, output_dir, report = fixture.run("bad-scheduler-shape")
        self.assertEqual(result.returncode, 2)
        self.assertTrue((output_dir / "report.json").is_file())
        self.assertFalse(report["technical_gate"]["passed"])
        first = next(
            row for row in report["cell_checks"]
            if row["cell_id"] == "cell-0001"
        )
        self.assertIn("scheduler:source-shape", first["errors"])

    def test_scheduler_manifests_are_bound_into_fit_input_digest(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        first_result, first_dir, _ = fixture.run("scheduler-digest-a")
        self.assertEqual(first_result.returncode, 0)
        first_record = json.loads(
            (
                first_dir
                / "fits"
                / "attempt-010-primary-historical.json"
            ).read_text()
        )
        scheduler_path = fixture.run_dir / "scheduler-manifest-1.json"
        scheduler = json.loads(scheduler_path.read_text())
        scheduler["hostname"] = "changed-but-valid-node"
        scheduler_path.write_bytes(deterministic_json(scheduler))
        second_result, second_dir, _ = fixture.run("scheduler-digest-b")
        self.assertEqual(second_result.returncode, 0)
        second_record = json.loads(
            (
                second_dir
                / "fits"
                / "attempt-010-primary-historical.json"
            ).read_text()
        )
        self.assertNotEqual(
            first_record["input_manifest_sha256"],
            second_record["input_manifest_sha256"],
        )

    def test_bootstrap_and_all_outputs_are_deterministic(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        first_result, first_dir, first_report = fixture.run("repeat-a")
        second_result, second_dir, second_report = fixture.run("repeat-b")
        self.assertEqual(first_result.returncode, second_result.returncode)
        self.assertEqual(first_report, second_report)
        first_files = {
            path.relative_to(first_dir): path.read_bytes()
            for path in first_dir.rglob("*")
            if path.is_file()
        }
        second_files = {
            path.relative_to(second_dir): path.read_bytes()
            for path in second_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(first_files, second_files)

    def test_sealed_bootstrap_export_is_opt_in_index_aligned_and_deterministic(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        plain_result, plain_dir, _ = fixture.run("plain-export-off")
        first_result, first_dir, _ = fixture.run(
            "sealed-export-a",
            sealed_bootstrap_export=True,
        )
        second_result, second_dir, _ = fixture.run(
            "sealed-export-b",
            sealed_bootstrap_export=True,
        )
        self.assertEqual(plain_result.returncode, 0)
        self.assertEqual(
            first_result.returncode,
            0,
            first_result.stderr + first_result.stdout,
        )
        self.assertEqual(
            second_result.returncode,
            0,
            second_result.stderr + second_result.stdout,
        )
        self.assertFalse((plain_dir / "sealed-fit-bootstrap.json").exists())
        first_path = first_dir / "sealed-fit-bootstrap.json"
        second_path = second_dir / "sealed-fit-bootstrap.json"
        self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
        sealed = json.loads(first_path.read_text())
        self.assertEqual(
            sealed["schema_version"],
            "yanwang148.sealed-lattice-fit.v1",
        )
        self.assertEqual(sealed["configured_bootstrap_resamples"], 16)
        self.assertEqual(
            sealed["declared_variant_ids"],
            [row["fit_id"] for row in proposal()["analysis"]["variants"]],
        )
        self.assertEqual(
            [row["fit_id"] for row in sealed["variants"]],
            sealed["declared_variant_ids"],
        )
        for row in [sealed["primary"], *sealed["variants"]]:
            self.assertEqual(row["configured_resamples"], 16)
            if row["accepted"]:
                self.assertEqual(len(row["draws"]), 16)
                self.assertEqual(
                    row["successful_resamples"]
                    + row["failed_resamples"],
                    16,
                )
                self.assertEqual(
                    row["failed_resamples"],
                    sum(value is None for value in row["draws"]),
                )
            else:
                self.assertIsNone(row["value"])
                self.assertEqual(row["draws"], [])
        serialized = json.dumps(sealed, sort_keys=True).lower()
        self.assertNotIn("sqrt5", serialized)
        self.assertNotIn("sqrt_5", serialized)
        self.assertNotIn("ratio", serialized)

    def test_nonempty_output_directory_is_never_reused(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        first_result, output_dir, _ = fixture.run("single-output")
        self.assertEqual(first_result.returncode, 0)
        before = {
            path.relative_to(output_dir): path.read_bytes()
            for path in output_dir.rglob("*")
            if path.is_file()
        }
        second_result = subprocess.run(
            [
                sys.executable,
                str(ANALYZER),
                "--run-spec",
                str(fixture.spec_path),
                "--out-dir",
                str(output_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        after = {
            path.relative_to(output_dir): path.read_bytes()
            for path in output_dir.rglob("*")
            if path.is_file()
        }
        self.assertEqual(second_result.returncode, 2)
        self.assertEqual(before, after)

    def test_source_plan_hash_and_execution_view_are_enforced(self):
        fixture = AnalysisFixture()
        self.addCleanup(fixture.close)
        fixture.source_path.write_bytes(fixture.source_bytes + b" ")
        result, _, report = fixture.run("source-mismatch")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(report["technical_gate"]["passed"])
        self.assertTrue(
            any(
                "source_plan_sha256:mismatch" in error
                for error in report["technical_gate"]["errors"]
            )
        )

    def test_source_schema_and_frozen_status_are_required(self):
        cases = (
            {"schema_version": "yanwang148.other.v1"},
            {"status": "proposal"},
        )
        for index, override in enumerate(cases):
            with self.subTest(override=override):
                fixture = AnalysisFixture(source_overrides=override)
                self.addCleanup(fixture.close)
                result, _, report = fixture.run(f"source-label-{index}")
                self.assertEqual(result.returncode, 2)
                self.assertFalse(report["technical_gate"]["passed"])

    def test_analyzer_source_contains_no_equality_target_constant(self):
        source = ANALYZER.read_text().lower().replace(" ", "")
        self.assertNotIn("sqrt(5", source)
        self.assertNotIn("sqrt5", source)
        self.assertNotIn("2.236", source)
        self.assertNotIn("√5", source)


if __name__ == "__main__":
    unittest.main()
