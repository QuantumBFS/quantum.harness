"""Tests for Nishimori-point free-energy and central-charge analysis."""

import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE.parent / "random_bond_ising_analysis.py"


def _load_module():
    if not _SCRIPT.exists():
        raise AssertionError(f"missing production module: {_SCRIPT}")
    spec = importlib.util.spec_from_file_location("random_bond_ising_analysis", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["random_bond_ising_analysis"] = module
    spec.loader.exec_module(module)
    return module


def _synthetic_strip_results(expected_c=0.464):
    sizes = np.array([8, 10, 12, 16, 20], dtype=float)
    results = []
    for L in sizes:
        free_energy = -1.27 - math.pi * expected_c / (6.0 * L**2) + 0.8 / L**4
        lyapunov = -L * free_energy
        blocks = lyapunov + np.array([-0.004, -0.002, 0.002, 0.004])
        lyapunov_se = np.std(blocks, ddof=1) / math.sqrt(len(blocks))
        results.append(
            {
                "L": int(L),
                "p": 0.1092212,
                "coupling": 1.0,
                "seed": int(L),
                "burn_in": 50 * int(L),
                "retained_rows": 400 * int(L),
                "block_length": 100 * int(L),
                "block_log_norm_means": blocks,
                "lyapunov": float(np.mean(blocks)),
                "lyapunov_se": float(lyapunov_se),
                "free_energy": float(-np.mean(blocks) / L),
                "free_energy_se": float(lyapunov_se / L),
                "runtime_seconds": 1.0,
                "rows_per_second": 1000.0,
            }
        )
    return results


def _synthetic_sample_records(expected_c=0.464):
    sizes = (4, 5, 6, 8, 9, 10, 12)
    offsets = (-6e-5, -2e-5, 2e-5, 6e-5)
    records = []
    for L in sizes:
        center = -1.27 - math.pi * expected_c / (6.0 * L**2) + 0.8 / L**4
        for sample_index, offset in enumerate(offsets):
            records.append(
                {
                    "L": L,
                    "p": 0.1092212,
                    "coupling": 1.0493604763,
                    "sample_index": sample_index,
                    "seed": 1000 * L + sample_index,
                    "burn_in": 1000,
                    "retained_rows": 100000,
                    "block_length": 1000,
                    "free_energy": center + offset,
                    "runtime_seconds": 1.0,
                    "antiferromagnetic_bonds": round(0.1092212 * 2 * L * 100000),
                    "total_retained_bonds": 2 * L * 100000,
                    "disorder_ensemble": "fixed_count",
                }
            )
    return records


class CentralChargeFitTests(unittest.TestCase):
    def test_charge_annotation_is_valid_mathtext(self):
        """Catches doubled raw-string slashes that render as literal TeX."""
        module = _load_module()

        annotation = module.format_charge_annotation(
            {"central_charge": 0.458463, "bootstrap_se": 0.005165}
        )

        self.assertEqual(
            annotation,
            "$c_{\\mathit{eff}}=0.4585$\nbootstrap SE $=0.00517$",
        )

    def test_ensemble_aggregation_uses_independent_sample_error(self):
        """Catches block statistics being mistaken for independent samples."""
        module = _load_module()
        records = _synthetic_sample_records()

        widths = module.aggregate_sample_records(records)

        self.assertEqual([item["L"] for item in widths], [4, 5, 6, 8, 9, 10, 12])
        first_values = np.asarray(
            [item["free_energy"] for item in records if item["L"] == 4]
        )
        self.assertEqual(widths[0]["sample_count"], 4)
        self.assertAlmostEqual(widths[0]["free_energy"], np.mean(first_values))
        self.assertAlmostEqual(
            widths[0]["free_energy_se"],
            np.std(first_values, ddof=1) / math.sqrt(len(first_values)),
        )

    def test_ensemble_aggregation_rejects_duplicates_and_singletons(self):
        """Catches invalid resume records entering disorder averages."""
        module = _load_module()
        records = _synthetic_sample_records()
        with self.assertRaises(ValueError):
            module.aggregate_sample_records(records + [dict(records[0])])
        with self.assertRaises(ValueError):
            module.aggregate_sample_records([dict(records[0])])

    def test_ensemble_fit_family_recovers_synthetic_charge(self):
        """Catches wrong fit windows or bootstrapping the wrong sampling unit."""
        module = _load_module()
        widths = module.aggregate_sample_records(_synthetic_sample_records())

        summary = module.central_charge_ensemble_summary(
            widths, bootstrap_samples=40, seed=77
        )

        expected_keys = {
            *(f"l2_Lmin{lmin}" for lmin in (4, 5, 6, 8)),
            *(f"l4_Lmin{lmin}" for lmin in (4, 5, 6, 8)),
            "reported",
        }
        self.assertEqual(set(summary), expected_keys)
        self.assertAlmostEqual(
            summary["l4_Lmin4"]["central_charge"], 0.464, places=9
        )
        self.assertEqual(summary["reported"]["primary_fit"], "l4_Lmin4")
        self.assertGreaterEqual(summary["reported"]["bootstrap_se"], 0.0)
        self.assertLessEqual(
            summary["reported"]["fit_envelope_lower"],
            summary["reported"]["fit_envelope_upper"],
        )

    def test_weighted_fit_recovers_synthetic_central_charge(self):
        """Catches a wrong cylinder sign, factor of six, or correction basis."""
        module = _load_module()
        self.assertTrue(hasattr(module, "fit_central_charge"))
        sizes = np.array([8, 10, 12, 16, 20], dtype=float)
        expected_c = 0.464
        values = -1.27 - math.pi * expected_c / (6.0 * sizes**2) + 0.8 / sizes**4
        errors = np.full(sizes.shape, 1e-5)

        result = module.fit_central_charge(
            sizes, values, errors, include_l4=True, lmin=8
        )

        self.assertAlmostEqual(result["central_charge"], expected_c, places=10)
        self.assertEqual(result["sizes"], [8, 10, 12, 16, 20])

    def test_fit_rejects_nonpositive_errors(self):
        """Catches invalid weights entering the least-squares covariance."""
        module = _load_module()
        with self.assertRaises(ValueError):
            module.fit_central_charge([8, 10, 12], [1.0, 1.0, 1.0], [0.1, 0.0, 0.1])

    def test_required_rows_scales_as_inverse_error_squared(self):
        """Catches a linear instead of variance-based runtime projection."""
        module = _load_module()
        result = {
            "retained_rows": 1000,
            "block_length": 100,
            "free_energy_se": 4e-4,
            "runtime_seconds": 5.0,
            "burn_in": 100,
        }

        projection = module.estimate_required_rows(result, 1e-4)

        self.assertEqual(projection["required_retained_rows"], 16000)
        self.assertGreater(projection["projected_runtime_seconds"], 5.0)

    def test_summary_separates_bootstrap_and_fit_envelope(self):
        """Catches conflation of sampling noise with finite-size fit choice."""
        module = _load_module()

        result = module.central_charge_summary(
            _synthetic_strip_results(), bootstrap_samples=40, seed=7
        )

        self.assertEqual(
            set(result),
            {"primary_L8_l24", "all_L_l2", "drop_L8_l24", "reported"},
        )
        self.assertAlmostEqual(
            result["primary_L8_l24"]["central_charge"], 0.464, places=10
        )
        self.assertGreaterEqual(result["reported"]["bootstrap_se"], 0.0)
        self.assertLessEqual(
            result["reported"]["fit_envelope_lower"],
            result["reported"]["fit_envelope_upper"],
        )

    def test_two_block_bootstrap_has_finite_sample_variance_correction(self):
        """Catches the factor-of-two variance bias of a raw two-block bootstrap."""
        module = _load_module()
        results = _synthetic_strip_results()
        for item in results:
            center = item["lyapunov"]
            blocks = np.array([center - 0.004, center + 0.004])
            lyapunov_se = np.std(blocks, ddof=1) / math.sqrt(len(blocks))
            item["block_log_norm_means"] = blocks
            item["lyapunov_se"] = float(lyapunov_se)
            item["free_energy_se"] = float(lyapunov_se / item["L"])

        result = module.central_charge_summary(
            results, bootstrap_samples=10000, seed=7
        )

        bootstrap_se = result["reported"]["bootstrap_se"]
        linear_se = result["primary_L8_l24"]["central_charge_linear_se"]
        self.assertAlmostEqual(bootstrap_se / linear_se, 1.0, delta=0.04)


class ArtifactWorkflowTests(unittest.TestCase):
    def test_ensemble_figure_uses_requested_style(self):
        """Catches regressions to orange fits or undersized opaque markers."""
        module = _load_module()
        widths = module.aggregate_sample_records(_synthetic_sample_records())
        summary = module.central_charge_ensemble_summary(
            widths, bootstrap_samples=20, seed=7
        )

        figure, axis = module.make_ensemble_central_charge_figure(widths, summary)
        try:
            data_line = axis.lines[0]
            fit_line = axis.lines[-1]
            self.assertAlmostEqual(data_line.get_markersize(), math.sqrt(72.0))
            self.assertAlmostEqual(data_line.get_alpha(), 0.78)
            self.assertEqual(fit_line.get_color(), "red")
            self.assertEqual(fit_line.get_linestyle(), "-")
            self.assertAlmostEqual(fit_line.get_alpha(), 0.78)
            self.assertEqual(axis.title.get_fontstyle(), "italic")
            self.assertTrue(
                all(label.get_fontstyle() == "italic" for label in axis.get_xticklabels())
            )
            self.assertTrue(
                all(text.get_fontstyle() == "italic" for text in axis.get_legend().get_texts())
            )
        finally:
            module.plt.close(figure)

    def test_ensemble_plot_regeneration_preserves_source_artifacts(self):
        """Catches accidental rewriting of completed disorder data or fit JSON."""
        module = _load_module()
        records = _synthetic_sample_records()
        widths = module.aggregate_sample_records(records)
        summary = module.central_charge_ensemble_summary(
            widths, bootstrap_samples=20, seed=7
        )
        config = {"preliminary": True, "actual_counts": {"4": 4}}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            module.write_ensemble_artifacts(
                records, widths, summary, config, output_dir
            )
            protected_names = (
                "samples.csv",
                "width_summary.csv",
                "central_charge_fit.json",
                "run_config.json",
            )
            before = {
                name: (output_dir / name).read_bytes() for name in protected_names
            }
            plot_path = output_dir / "central_charge_fit.png"
            plot_path.unlink()

            returned = module.regenerate_ensemble_plot_from_artifacts(output_dir)

            self.assertEqual(returned, plot_path)
            self.assertGreater(plot_path.stat().st_size, 1000)
            after = {
                name: (output_dir / name).read_bytes() for name in protected_names
            }
            self.assertEqual(after, before)

    def test_ensemble_artifacts_include_samples_widths_fit_and_config(self):
        """Catches a two-hour run without reproducible machine-readable outputs."""
        module = _load_module()
        records = _synthetic_sample_records()
        widths = module.aggregate_sample_records(records)
        summary = module.central_charge_ensemble_summary(
            widths, bootstrap_samples=20, seed=7
        )
        config = {
            "sizes": [4, 5, 6, 8, 9, 10, 12],
            "sample_counts": {"4": 192},
            "actual_counts": {"4": 4},
            "preliminary": True,
        }

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            module.write_ensemble_artifacts(
                records, widths, summary, config, output_dir
            )

            for name in (
                "samples.csv",
                "width_summary.csv",
                "central_charge_fit.json",
                "run_config.json",
                "central_charge_fit.png",
            ):
                path = output_dir / name
                self.assertTrue(path.exists(), name)
                self.assertGreater(path.stat().st_size, 0)
            with (output_dir / "run_config.json").open() as handle:
                self.assertEqual(json.load(handle)["actual_counts"], {"4": 4})

    def test_artifacts_include_blocks_widths_fit_projection_and_plot(self):
        """Catches incomplete or non-machine-readable RBIM output."""
        module = _load_module()
        self.assertTrue(
            hasattr(module, "write_analysis_artifacts"),
            "write_analysis_artifacts is missing",
        )
        results = _synthetic_strip_results()
        summary = module.central_charge_summary(
            results, bootstrap_samples=20, seed=7
        )
        projections = [
            module.estimate_required_rows(item, 1e-4) for item in results
        ]
        runtime = {
            "production_launched": False,
            "projected_total_seconds": 1000.0,
            "target_free_energy_se": 1e-4,
        }

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            module.write_analysis_artifacts(
                results, summary, projections, runtime, output_dir
            )

            for name in (
                "blocks.csv",
                "width_summary.csv",
                "central_charge_fit.json",
                "runtime_projection.json",
                "central_charge_fit.png",
            ):
                path = output_dir / name
                self.assertTrue(path.exists(), name)
                self.assertGreater(path.stat().st_size, 0)
            with (output_dir / "runtime_projection.json").open() as handle:
                saved_runtime = json.load(handle)
            self.assertFalse(saved_runtime["production_launched"])

    def test_workflow_cost_gate_keeps_pilot_when_budget_is_zero(self):
        """Catches an unbounded production rerun after the measured pilot."""
        module = _load_module()
        self.assertTrue(hasattr(module, "run_workflow"), "run_workflow is missing")
        synthetic = {item["L"]: item for item in _synthetic_strip_results()}
        calls = []

        def fake_runner(**kwargs):
            calls.append(dict(kwargs))
            result = dict(synthetic[kwargs["L"]])
            result["seed"] = kwargs["seed"]
            return result

        with tempfile.TemporaryDirectory() as temporary:
            selected, summary, runtime = module.run_workflow(
                sizes=[8, 10, 12, 16, 20],
                p=0.1092212,
                seed=122,
                pilot_blocks=2,
                target_se=1e-4,
                max_local_seconds=0.0,
                bootstrap_samples=20,
                output_dir=Path(temporary),
                strip_runner=fake_runner,
            )

        self.assertEqual(len(calls), 5)
        self.assertEqual([item["L"] for item in selected], [8, 10, 12, 16, 20])
        self.assertFalse(runtime["production_launched"])
        self.assertIs(runtime.get("preliminary"), True)
        self.assertEqual(runtime.get("pilot_runtime_seconds"), 5.0)
        self.assertEqual(
            runtime.get("projected_production_seconds"),
            runtime["projected_total_seconds"],
        )
        self.assertTrue(math.isfinite(summary["reported"]["central_charge"]))

    def test_workflow_rejects_invalid_configuration_before_pilot(self):
        """Catches expensive strip runs starting before cheap input validation."""
        module = _load_module()
        defaults = {
            "sizes": [8, 10, 12, 16, 20],
            "p": 0.1092212,
            "seed": 122,
            "pilot_blocks": 2,
            "target_se": 1e-4,
            "max_local_seconds": 600.0,
            "bootstrap_samples": 20,
            "output_dir": Path("unused"),
        }
        invalid = (
            {"sizes": [8, 10, 12, 16]},
            {"sizes": [8, 10, 12, 16, 16]},
            {"sizes": [2, 4, 8, 10, 12]},
            {"p": 0.5},
            {"target_se": 0.0},
            {"max_local_seconds": -1.0},
            {"bootstrap_samples": 1},
        )

        def forbidden_runner(**kwargs):
            raise AssertionError(f"pilot started with invalid configuration: {kwargs}")

        for override in invalid:
            with self.subTest(override=override):
                arguments = dict(defaults)
                arguments.update(override)
                with self.assertRaises(ValueError):
                    module.run_workflow(strip_runner=forbidden_runner, **arguments)


if __name__ == "__main__":
    unittest.main()
