#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cross_reweight import cross_reweight_ii_to_ti  # noqa: E402
from energy_decomposition import (  # noqa: E402
    cp_symmetric_ti,
    decompose_frequency_within,
    ii_strata_estimates,
    ti_sign_reweighted,
)


class EnergyDecompositionTest(unittest.TestCase):
    def test_path_strata_close_direct_estimators(self) -> None:
        labels = [
            "dead_support", "alive_low_final_q",
            "alive_deep_prefix_not_low_q", "alive_regular_static",
        ]
        rows = []
        for index, label in enumerate(labels):
            rows.append({
                "primary_static_stratum": label,
                "central_ii_etot": -10.0 - index,
                "central_ti_etot": -11.0 - index,
                "sign_d_ti": 1,
                "sign_d_alf_ti": 1,
            })
        ii = ii_strata_estimates(rows)
        ti = ti_sign_reweighted(rows)
        self.assertAlmostEqual(ii["closure_residual"], 0.0)
        self.assertAlmostEqual(ti["closure_residual"], 0.0)
        self.assertEqual(
            ii["strata"]["ambiguous_support"]["probability"], 0.0
        )

    def test_frequency_within_identity(self) -> None:
        ti = {
            "a": {"probability": 0.4, "energy": -10.0},
            "b": {"probability": 0.6, "energy": -12.0},
        }
        cp = {
            "a": {"probability": 0.7, "energy": -9.5},
            "b": {"probability": 0.3, "energy": -11.0},
        }
        result = decompose_frequency_within(ti, cp)
        self.assertAlmostEqual(result["closure_residual"], 0.0)

    def test_cross_reweight_reports_ess_and_tail(self) -> None:
        rows = [
            {
                "logabs_d_ii": 100.0,
                "logabs_d_alf_ii": 0.0,
                "logabs_d_ti": value,
                "sign_d_ii": 1,
                "sign_d_alf_ii": 1,
                "sign_d_ti": 1,
                "central_ti_etot": -10.0 - value,
            }
            for value in (0.0, 0.1, 0.2, 0.3)
        ]
        result = cross_reweight_ii_to_ti(rows)
        self.assertGreater(result.ess, 3.0)
        self.assertGreater(result.maximum_normalized_weight, 0.25)

    def test_cp_symmetric_ti_uses_boundary_cut_reweighting(self) -> None:
        rows = [
            {
                "primary_static_stratum": "alive_regular_static",
                "central_ti_etot": -10.0,
                "logabs_d_ti": 0.0,
                "logabs_d_alf_ti": 0.0,
                "sign_d_ti": 1,
                "sign_d_alf_ti": 1,
            },
            {
                "primary_static_stratum": "alive_regular_static",
                "central_ti_etot": -14.0,
                "logabs_d_ti": 1.0,
                "logabs_d_alf_ti": 0.0,
                "sign_d_ti": 1,
                "sign_d_alf_ti": 1,
            },
        ]
        result = cp_symmetric_ti(rows)
        expected = (-10.0 - 14.0 * 2.718281828459045) / (
            1.0 + 2.718281828459045
        )
        self.assertAlmostEqual(result["direct_energy"], expected)
        self.assertLess(result["ess"], 2.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
