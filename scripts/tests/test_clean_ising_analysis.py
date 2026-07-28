"""Tests for clean-Ising Lyapunov and central-charge analysis."""

import importlib.util
import math
import sys
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


if __name__ == "__main__":
    unittest.main()
