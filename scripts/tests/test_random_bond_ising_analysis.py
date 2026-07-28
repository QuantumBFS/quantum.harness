"""Tests for Nishimori-point free-energy and central-charge analysis."""

import importlib.util
import math
import sys
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


class CentralChargeFitTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
