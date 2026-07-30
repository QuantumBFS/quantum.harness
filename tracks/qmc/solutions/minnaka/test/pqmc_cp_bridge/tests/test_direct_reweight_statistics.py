#!/usr/bin/env python3
"""Tests for the direct, ratio-of-sums path-reweighting estimator."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from direct_reweight_statistics import (  # noqa: E402
    compute_direct_reweight,
    write_products,
)


def row(
    sample_id: int,
    chain: int,
    sweep: int,
    log_weight: float,
    energy: float,
    *,
    sign_cp: int = 1,
    sign_alf: int = 1,
) -> dict[str, str]:
    return {
        "sample_id": str(sample_id),
        "ensemble": "TI",
        "chain": str(chain),
        "bin": "0",
        "sweep": str(sweep),
        "sign_d_ti": str(sign_cp),
        "sign_d_alf_ti": str(sign_alf),
        "boundary_cut_log_ratio_ti": f"{log_weight:.17g}",
        "central_ti_etot": f"{energy:.17g}",
        "alive": "1",
        "identity_log_residual": "0",
    }


class DirectReweightStatisticsTest(unittest.TestCase):
    def test_ratio_of_sums_precedes_cross_chain_bin_average(self) -> None:
        rows = [
            row(4, 1, 20, 0.0, 50.0),
            row(1, 0, 10, 0.0, 10.0),
            row(3, 1, 10, math.log(3.0), 20.0),
            row(2, 0, 20, 0.0, 30.0),
        ]
        result, raw, bins, loo = compute_direct_reweight(
            rows, expected_chains=2, paths_per_chain=2,
            target_error=12.0, green_stability_pass=True,
        )
        self.assertEqual(
            [(item["chain"], item["slot"]) for item in raw],
            [(0, 1), (0, 2), (1, 1), (1, 2)],
        )
        self.assertAlmostEqual(bins[0]["energy"], 17.5)
        self.assertAlmostEqual(bins[1]["energy"], 40.0)
        self.assertAlmostEqual(
            result["energy_cross_chain_bin_mean"], 28.75
        )
        self.assertAlmostEqual(
            result["energy_error_cross_chain_bins"], 11.25
        )
        self.assertAlmostEqual(result["energy_global_ratio"], 25.0)
        self.assertAlmostEqual(
            result["aggregation_consistency_difference"], 3.75
        )
        self.assertAlmostEqual(
            result["leave_one_chain_jackknife_error"], 3.75
        )
        self.assertEqual(
            [item["energy"] for item in loo], [27.5, 20.0]
        )
        self.assertAlmostEqual(result["effective_sample_size"], 3.0)
        self.assertAlmostEqual(result["maximum_normalized_weight"], 0.5)
        self.assertAlmostEqual(result["top_one_percent_weight_share"], 0.5)
        self.assertTrue(
            result["direct_reweight_statistical_precision_pass"]
        )
        self.assertTrue(result["green_stability_pass"])

    def test_requires_complete_contiguous_chain_by_slot_rectangle(self) -> None:
        rows = [
            row(1, 0, 10, 0.0, 1.0),
            row(2, 0, 20, 0.0, 1.0),
            row(3, 2, 10, 0.0, 1.0),
            row(4, 2, 20, 0.0, 1.0),
        ]
        with self.assertRaisesRegex(ValueError, "chain IDs"):
            compute_direct_reweight(
                rows, expected_chains=2, paths_per_chain=2
            )

    def test_nonpositive_weight_is_included_but_fails_precision_gate(self) -> None:
        rows = [
            row(1, 0, 10, 0.0, 2.0),
            row(2, 0, 20, 0.0, 4.0),
            row(3, 1, 10, -math.log(2.0), 6.0, sign_cp=-1),
            row(4, 1, 20, -2.0, 8.0),
        ]
        result, _raw, _bins, _loo = compute_direct_reweight(
            rows, expected_chains=2, paths_per_chain=2,
            target_error=100.0,
        )
        self.assertEqual(
            result["nonpositive_or_nonfinite_weight_count"], 1
        )
        self.assertAlmostEqual(result["mean_weight_sign"], 0.5)
        self.assertFalse(
            result["direct_reweight_statistical_precision_pass"]
        )

    def test_products_preserve_raw_bins_jackknife_and_json(self) -> None:
        rows = [
            row(1, 0, 10, 0.0, 10.0),
            row(2, 0, 20, 0.0, 30.0),
            row(3, 1, 10, math.log(3.0), 20.0),
            row(4, 1, 20, 0.0, 50.0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            summary = write_products(
                rows, output,
                expected_chains=2,
                paths_per_chain=2,
                target_error=12.0,
                green_stability_pass=False,
            )
            self.assertEqual(summary["paths"], 4)
            self.assertFalse(summary["green_stability_pass"])
            for name, expected_rows in (
                ("raw_path_statistics.csv", 4),
                ("cross_chain_bins.csv", 2),
                ("leave_one_chain_jackknife.csv", 2),
            ):
                with (output / name).open(newline="") as handle:
                    self.assertEqual(
                        len(list(csv.DictReader(handle))), expected_rows
                    )
            loaded = json.loads(
                (output / "direct_reweight_summary.json").read_text()
            )
            self.assertEqual(loaded["estimator"], "direct_ratio_of_sums")


if __name__ == "__main__":
    unittest.main(verbosity=2)
