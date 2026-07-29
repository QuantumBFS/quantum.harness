"""Tests for clean-Ising Lyapunov and central-charge analysis."""

import importlib.util
import csv
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE.parent / "clean_ising_analysis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("clean_ising_analysis", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["clean_ising_analysis"] = module
    spec.loader.exec_module(module)
    return module


def _dense_transfer(L, kx, ktau):
    states = np.arange(1 << L, dtype=np.uint64)
    bits = ((states[:, None] >> np.arange(L, dtype=np.uint64)) & 1).astype(float)
    spins = 2.0 * bits - 1.0
    horizontal = np.sum(spins * np.roll(spins, -1, axis=1), axis=1)
    vertical = spins @ spins.T
    return np.exp(
        0.5 * kx * (horizontal[:, None] + horizontal[None, :])
        + ktau * vertical
    )


class CleanLyapunovTests(unittest.TestCase):
    def test_exact_ising_scaling_dimensions_preserve_degeneracies(self):
        """Catches a missing conformal tower level or wrong degeneracy."""
        module = _load_module()

        np.testing.assert_allclose(
            module.exact_ising_scaling_dimensions(),
            [1 / 8, 1, 9 / 8, 9 / 8, 2, 2, 2, 2, 17 / 8, 17 / 8, 17 / 8],
        )

    def test_scaling_dimension_rows_use_transfer_gap_normalization(self):
        """Catches a wrong factor of L, 2 pi, or excitation index."""
        module = _load_module()
        L = 8
        exact = np.asarray(
            [1 / 8, 1, 9 / 8, 9 / 8, 2, 2, 2, 2, 17 / 8, 17 / 8, 17 / 8]
        )
        row = {"L": L, "ell_1": 3.0}
        for rank, target in enumerate(exact, start=1):
            row[f"ell_{rank + 1}"] = 3.0 - 2.0 * math.pi * target / L

        result = module.scaling_dimension_rows([row])

        self.assertEqual(len(result), 11)
        self.assertEqual([item["excitation_rank"] for item in result], list(range(1, 12)))
        np.testing.assert_allclose(
            [item["numerical_dimension"] for item in result], exact
        )
        np.testing.assert_allclose(
            [item["deviation"] for item in result], 0.0, atol=1e-15
        )

    def test_first_four_exponents_match_dense_spectrum(self):
        """Catches missed Z2 sectors, wrong ordering, logs, or residuals."""
        if not _SCRIPT.exists():
            self.fail("scripts/clean_ising_analysis.py is missing")
        module = _load_module()
        k = 0.5 * math.log(1.0 + math.sqrt(2.0))
        expected_lambda = np.linalg.eigvalsh(_dense_transfer(4, k, k))[::-1][:4]

        result = module.clean_lyapunov_spectrum(4, count=4, tol=1e-12)

        np.testing.assert_allclose(result["lambda"], expected_lambda, rtol=1e-11, atol=1e-11)
        np.testing.assert_allclose(result["ell"], np.log(expected_lambda), rtol=1e-11, atol=1e-11)
        self.assertTrue(all(value < 1e-10 for value in result["residuals"]))

    def test_first_twelve_exponents_match_dense_degenerate_spectrum(self):
        """Catches single-vector Lanczos dropping exact multiplet members."""
        module = _load_module()
        L = 8
        k = 0.5 * math.log(1.0 + math.sqrt(2.0))
        expected = np.linalg.eigvalsh(_dense_transfer(L, k, k))[::-1][:12]

        result = module.clean_lyapunov_spectrum(L, count=12, tol=1e-11)

        np.testing.assert_allclose(result["lambda"], expected, rtol=1e-10, atol=1e-8)
        self.assertTrue(all(value < 1e-9 for value in result["residuals"]))

    def test_leading_iteration_matches_log_dominant_eigenvalue(self):
        """Catches missing normalization, burn-in, or incorrect log accumulation."""
        if not _SCRIPT.exists():
            self.fail("scripts/clean_ising_analysis.py is missing")
        module = _load_module()
        k = 0.5 * math.log(1.0 + math.sqrt(2.0))
        expected = math.log(np.linalg.eigvalsh(_dense_transfer(4, k, k))[-1])

        result = module.leading_lyapunov_iteration(4, steps=100, burn_in=50)

        self.assertLess(abs(result["ell1"] - expected), 1e-10)
        self.assertEqual(result["samples"], 50)

    def test_rejects_invalid_spectrum_count(self):
        """Catches requests that cannot define a partial sparse spectrum."""
        module = _load_module()
        with self.assertRaises(ValueError):
            module.clean_lyapunov_spectrum(4, count=16)

    def test_rejects_empty_post_burn_in_window(self):
        """Catches a Lyapunov average with no retained normalization steps."""
        module = _load_module()
        with self.assertRaises(ValueError):
            module.leading_lyapunov_iteration(4, steps=10, burn_in=10)

    def test_transfer_energy_fit_recovers_known_central_charge(self):
        """Catches a wrong CFT sign, normalization, or finite-size basis."""
        module = _load_module()
        if not hasattr(module, "fit_transfer_energy"):
            self.fail("fit_transfer_energy is missing")
        sizes = np.array([8, 10, 12, 16, 20], dtype=float)
        expected_c = 0.5
        energies = (
            -0.93 * sizes
            - math.pi * expected_c / (6.0 * sizes)
            + 0.15 / sizes**3
        )

        result = module.fit_transfer_energy(sizes, energies, powers=(1, 3), lmin=8)

        self.assertAlmostEqual(result["central_charge"], expected_c, places=11)
        self.assertEqual(result["sizes"], [8, 10, 12, 16, 20])
        self.assertLess(result["residual_norm"], 1e-12)

    def test_central_charge_summary_builds_stability_envelope(self):
        """Catches omitted stability fits or a malformed deterministic envelope."""
        module = _load_module()
        if not hasattr(module, "central_charge_summary"):
            self.fail("central_charge_summary is missing")
        sizes = np.array([8, 10, 12, 16, 20], dtype=float)
        energies = -0.93 * sizes - math.pi * 0.5 / (6.0 * sizes) + 0.15 / sizes**3

        result = module.central_charge_summary(sizes, energies)

        self.assertEqual(
            set(result),
            {"primary_L8_p13", "drop_L8_p13", "all_L_p135", "reported"},
        )
        reported = result["reported"]
        self.assertLessEqual(reported["lower"], 0.5)
        self.assertGreaterEqual(reported["upper"], 0.5)
        self.assertAlmostEqual(
            reported["midpoint"],
            0.5 * (reported["lower"] + reported["upper"]),
            places=14,
        )
        self.assertAlmostEqual(
            reported["half_width"],
            0.5 * (reported["upper"] - reported["lower"]),
            places=14,
        )

    def test_analysis_artifacts_include_data_fit_and_plot(self):
        """Catches incomplete or non-machine-readable analysis output."""
        module = _load_module()
        if not hasattr(module, "write_analysis_artifacts"):
            self.fail("write_analysis_artifacts is missing")
        sizes = np.array([8, 10, 12, 16, 20], dtype=float)
        energies = -0.93 * sizes - math.pi * 0.5 / (6.0 * sizes) + 0.15 / sizes**3
        exact = np.asarray(
            [1 / 8, 1, 9 / 8, 9 / 8, 2, 2, 2, 2, 17 / 8, 17 / 8, 17 / 8]
        )
        rows = []
        for size, energy in zip(sizes, energies):
            row = {
                "L": int(size),
                "ell_1": float(-energy),
                "qr_ell1": float(-energy),
                "qr_abs_error": 0.0,
            }
            for rank, target in enumerate(exact, start=1):
                row[f"ell_{rank + 1}"] = float(
                    row["ell_1"] - 2.0 * math.pi * target / size
                )
            rows.append(row)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            summary = module.write_analysis_artifacts(rows, output_dir)

            csv_path = output_dir / "lyapunov_spectrum.csv"
            json_path = output_dir / "central_charge_fit.json"
            plot_path = output_dir / "central_charge_fit.png"
            scaling_csv_path = output_dir / "lyapunov_scaling_dimensions.csv"
            scaling_plot_path = output_dir / "lyapunov_scaling_dimensions.png"
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertGreater(plot_path.stat().st_size, 1000)
            self.assertGreater(scaling_plot_path.stat().st_size, 1000)
            with scaling_csv_path.open(encoding="utf-8") as handle:
                scaling_rows = list(csv.DictReader(handle))
            self.assertEqual(len(scaling_rows), 55)
            self.assertEqual(
                {(int(row["L"]), int(row["excitation_rank"])) for row in scaling_rows},
                {(int(L), rank) for L in sizes for rank in range(1, 12)},
            )
            with json_path.open(encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertAlmostEqual(saved["reported"]["midpoint"], 0.5, places=10)
            self.assertEqual(saved, summary)

    def test_clean_central_charge_figure_uses_requested_style(self):
        """Catches regressions to the old orange fit or default marker styling."""
        module = _load_module()
        sizes = np.asarray([8, 10, 12, 16, 20], dtype=float)
        energies = -0.93 * sizes - math.pi * 0.5 / (6.0 * sizes) + 0.15 / sizes**3
        summary = module.central_charge_summary(sizes, energies)

        figure, axis = module.make_clean_central_charge_figure(
            sizes, energies, summary
        )
        try:
            fit = axis.lines[0]
            points = axis.collections[0]
            self.assertEqual(fit.get_color(), "red")
            self.assertEqual(fit.get_linestyle(), "-")
            self.assertAlmostEqual(fit.get_alpha(), 0.78)
            np.testing.assert_allclose(points.get_sizes(), [72.0])
            self.assertAlmostEqual(points.get_alpha(), 0.78)
            self.assertEqual(axis.title.get_fontstyle(), "italic")
            self.assertTrue(
                all(label.get_fontstyle() == "italic" for label in axis.get_xticklabels())
            )
            self.assertTrue(
                all(text.get_fontstyle() == "italic" for text in axis.get_legend().get_texts())
            )
        finally:
            module.plt.close(figure)

    def test_lower_count_run_removes_stale_scaling_artifacts(self):
        """Catches a four-level rerun leaving an obsolete eleven-level plot."""
        module = _load_module()
        sizes = np.asarray([8, 10, 12, 16, 20], dtype=float)
        energies = -0.93 * sizes - math.pi * 0.5 / (6.0 * sizes) + 0.15 / sizes**3
        exact = np.asarray(
            [1 / 8, 1, 9 / 8, 9 / 8, 2, 2, 2, 2, 17 / 8, 17 / 8, 17 / 8]
        )
        full_rows = []
        reduced_rows = []
        for size, energy in zip(sizes, energies):
            full = {"L": int(size), "ell_1": float(-energy)}
            for rank, target in enumerate(exact, start=1):
                full[f"ell_{rank + 1}"] = float(
                    full["ell_1"] - 2.0 * math.pi * target / size
                )
            full_rows.append(full)
            reduced_rows.append({"L": int(size), "ell_1": float(-energy)})

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            module.write_analysis_artifacts(full_rows, output_dir)
            scaling_paths = (
                output_dir / "lyapunov_scaling_dimensions.csv",
                output_dir / "lyapunov_scaling_dimensions.png",
            )
            self.assertTrue(all(path.exists() for path in scaling_paths))

            module.write_analysis_artifacts(reduced_rows, output_dir)

            self.assertTrue(all(not path.exists() for path in scaling_paths))

    def test_scaling_dimension_figure_has_exact_segments_and_deviation_panel(self):
        """Catches missing CFT levels, size series, or the deviation reference."""
        module = _load_module()
        exact = np.asarray(
            [1 / 8, 1, 9 / 8, 9 / 8, 2, 2, 2, 2, 17 / 8, 17 / 8, 17 / 8]
        )
        rows = []
        for L in (8, 10, 12, 16, 20):
            for rank, target in enumerate(exact, start=1):
                rows.append(
                    {
                        "L": L,
                        "excitation_rank": rank,
                        "numerical_dimension": float(target + 1.0 / L**2),
                        "exact_dimension": float(target),
                        "deviation": float(1.0 / L**2),
                    }
                )

        figure, (upper, lower) = module.make_scaling_dimension_figure(rows)
        try:
            self.assertEqual(len(upper.collections), 5)
            self.assertEqual(len(upper.lines), 11)
            self.assertTrue(all(line.get_color() == "red" for line in upper.lines))
            self.assertTrue(all(line.get_linestyle() == "-" for line in upper.lines))
            self.assertTrue(all(line.get_alpha() == 0.78 for line in upper.lines))
            self.assertEqual(len(lower.collections), 5)
            self.assertEqual(lower.lines[0].get_color(), "red")
            self.assertEqual(lower.lines[0].get_linestyle(), "-")
            self.assertAlmostEqual(lower.lines[0].get_alpha(), 0.78)
            self.assertEqual(upper.title.get_fontstyle(), "italic")
            self.assertEqual(lower.xaxis.label.get_fontstyle(), "italic")
            self.assertEqual(
                lower.yaxis.label.get_text(),
                r"$x_a(L)-x_a^{\mathit{CFT}}$",
            )
        finally:
            module.plt.close(figure)


if __name__ == "__main__":
    unittest.main()
