#!/usr/bin/env python3
"""Tests for ALF-compatible bin analysis."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import analyze  # noqa: E402


class JackknifeTest(unittest.TestCase):
    def test_ratio_matches_alf_error_convention_for_unit_sign(self) -> None:
        values = [1.0, 2.0, 4.0, 8.0]
        mean, error = analyze.jackknife_ratio(values, [1.0] * len(values))
        expected_mean = sum(values) / len(values)
        expected_error = math.sqrt(
            sum((value - expected_mean) ** 2 for value in values)
        ) / (len(values) - 1)
        self.assertAlmostEqual(mean, expected_mean)
        self.assertAlmostEqual(error, expected_error)

    def test_mean_sign_jackknife(self) -> None:
        mean, error = analyze.jackknife_mean([1.0, 1.0, 1.0, 1.0])
        self.assertEqual(mean, 1.0)
        self.assertEqual(error, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
