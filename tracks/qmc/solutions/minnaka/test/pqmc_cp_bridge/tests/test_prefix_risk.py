#!/usr/bin/env python3
"""Uniform path selection and preregistered prefix-risk strata."""

from __future__ import annotations

import random
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_prefix_risk import (  # noqa: E402
    ambiguous_sample_ids,
    assign_static_strata,
    chain_partitions,
    prefix_barrier,
    prefix_reference,
    quantile,
)
from select_replay_samples import (  # noqa: E402
    stratified_sample,
    write_sample_manifest,
)
from select_full_traces import select_cases_and_controls  # noqa: E402
from run_parallel_traces import (  # noqa: E402
    merge_csv_outputs,
    split_trace_rows,
)


class PrefixRiskTest(unittest.TestCase):
    def test_ambiguous_ids_accept_replay_validation_wrapper(self) -> None:
        self.assertEqual(
            ambiguous_sample_ids({
                "numerically_ambiguous_sample_ids": [11, 3],
                "stabilization": {
                    "numerically_ambiguous": [7, 3],
                }
            }),
            {3, 7, 11},
        )

    def test_sample_manifest_uses_portable_lf_line_endings(self) -> None:
        rows = [{
            "sample_id": 17,
            "ensemble": 1,
            "chain": 0,
            "bin": 2,
            "sweep": 20,
        }]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.csv"
            write_sample_manifest(path, rows, [17])
            payload = path.read_bytes()
        self.assertNotIn(b"\r", payload)
        self.assertEqual(
            payload,
            b"sample_id,ensemble,chain\n17,II,0\n",
        )

    def test_quantile_uses_linear_order_statistic(self) -> None:
        self.assertAlmostEqual(quantile([0, 10, 20], 0.25), 5.0)
        self.assertAlmostEqual(quantile([20, 0, 10], 0.75), 15.0)

    def test_uniform_selection_has_exact_per_chain_counts(self) -> None:
        index = [
            {
                "sample_id": ensemble * 100000 + chain * 10000 + item,
                "ensemble": ensemble,
                "chain": chain,
                "bin": item // 25,
                "sweep": item * 20,
            }
            for ensemble in (1, 2)
            for chain in range(6)
            for item in range(1000)
        ]
        selected = stratified_sample(index, per_chain=500, seed=7721)
        self.assertEqual(len(selected), 6000)
        self.assertEqual(selected, stratified_sample(index, 500, 7721))
        chosen = set(selected)
        for ensemble in (1, 2):
            for chain in range(6):
                count = sum(
                    row["sample_id"] in chosen
                    for row in index
                    if row["ensemble"] == ensemble and row["chain"] == chain
                )
                self.assertEqual(count, 500)

    def test_uniform_selection_infers_128_chain_contract(self) -> None:
        index = [
            {
                "sample_id": ensemble * 10**12 + chain * 100 + item,
                "ensemble": ensemble,
                "chain": chain,
                "bin": 0,
                "sweep": item * 239,
            }
            for ensemble in (1, 2)
            for chain in range(128)
            for item in range(8)
        ]
        selected = stratified_sample(index, per_chain=4, seed=7721)
        self.assertEqual(len(selected), 2 * 128 * 4)

    def test_chain_partitions_use_half_for_training(self) -> None:
        rows = [
            {"ensemble": ensemble, "chain": chain}
            for ensemble in ("II", "TI")
            for chain in range(128)
        ]
        training, held_out = chain_partitions(rows)
        self.assertEqual(training, list(range(64)))
        self.assertEqual(held_out, list(range(64, 128)))

    def test_prefix_barrier_removes_shared_linear_trend(self) -> None:
        paths = [
            {
                "chain": chain,
                "alive": True,
                "logq": [
                    -0.3 * step + 0.01 * chain + 0.02 * ((step + chain) % 3)
                    for step in range(12)
                ],
            }
            for chain in range(3)
            for _ in range(5)
        ]
        reference = prefix_reference(paths)
        target = [-0.3 * step - (0.4 if step == 7 else 0.0)
                  for step in range(12)]
        barrier, location = prefix_barrier(target, reference)
        trend = [0.17 * step for step in range(12)]
        shifted_reference = [
            value + trend[index] for index, value in enumerate(reference)
        ]
        shifted_target = [
            value + trend[index] for index, value in enumerate(target)
        ]
        shifted = prefix_barrier(shifted_target, shifted_reference)
        self.assertAlmostEqual(shifted[0], barrier)
        self.assertEqual(shifted[1], location)
        self.assertEqual(location, 7)

    def test_static_strata_are_mutually_exclusive(self) -> None:
        thresholds = {"q01": -120.0, "b99": 8.0, "n99": 4}
        cases = [
            ({"alive": False}, "dead_support"),
            (
                {
                    "alive": True, "log_q_prop": -130.0,
                    "prefix_barrier": 2.0, "near_node_count": 1,
                },
                "alive_low_final_q",
            ),
            (
                {
                    "alive": True, "log_q_prop": -100.0,
                    "prefix_barrier": 9.0, "near_node_count": 1,
                },
                "alive_deep_prefix_not_low_q",
            ),
            (
                {
                    "alive": True, "log_q_prop": -100.0,
                    "prefix_barrier": 2.0, "near_node_count": 1,
                },
                "alive_regular_static",
            ),
        ]
        for summary, expected in cases:
            labels = assign_static_strata(summary, thresholds)
            self.assertEqual(labels["primary_static_stratum"], expected)
            self.assertIn("support", labels)
            self.assertIn("proposal_risk", labels)
            self.assertIn("prefix_risk", labels)
            self.assertIn("near_node_risk", labels)
        zero_node = assign_static_strata(
            {
                "alive": True,
                "log_q_prop": -100.0,
                "prefix_barrier": 2.0,
                "near_node_count": 0,
            },
            {"q01": -120.0, "b99": 8.0, "n99": 0},
        )
        self.assertEqual(zero_node["near_node_risk"], "regular")

    def test_trace_controls_match_ensemble_split_and_energy_decile(self) -> None:
        rows = []
        for ensemble in ("II", "TI"):
            for chain in range(6):
                for item in range(30):
                    sample_id = (
                        (1 if ensemble == "II" else 2) * 100000
                        + chain * 1000 + item
                    )
                    rows.append({
                        "sample_id": sample_id,
                        "ensemble": ensemble,
                        "chain": chain,
                        "alive": "1",
                        "numerically_ambiguous": "0",
                        "alf_frozen_etot": -14.0 + 0.01 * item,
                        "log_q_prop": -100.0 - item,
                        "prefix_barrier": float(item),
                        "proposal_risk": (
                            "lowest_1pct" if item == 29 else "regular"
                        ),
                        "prefix_risk": (
                            "highest_1pct" if item == 28 else "regular"
                        ),
                        "primary_static_stratum": (
                            "alive_low_final_q" if item == 29
                            else "alive_deep_prefix_not_low_q"
                            if item == 28 else "alive_regular_static"
                        ),
                    })
        first = select_cases_and_controls(rows, seed=77)
        second = select_cases_and_controls(rows, seed=77)
        self.assertEqual(first, second)
        cases = {
            row["case_id"]: row for row in first if row["role"] == "case"
        }
        controls = [
            row for row in first if row["role"] == "control"
        ]
        self.assertTrue(controls)
        for control in controls:
            case = cases[control["case_id"]]
            self.assertEqual(control["ensemble"], case["ensemble"])
            self.assertEqual(control["chain_split"], case["chain_split"])
            self.assertEqual(control["energy_decile"], case["energy_decile"])

    def test_trace_selection_caps_each_risk_category(self) -> None:
        rows = []
        for ensemble in ("II", "TI"):
            for chain in range(6):
                for item in range(30):
                    rows.append({
                        "sample_id": (
                            (1 if ensemble == "II" else 2) * 100000
                            + chain * 1000 + item
                        ),
                        "ensemble": ensemble,
                        "chain": chain,
                        "alive": "1",
                        "numerically_ambiguous": "0",
                        "alf_frozen_etot": -14.0 + 0.01 * item,
                        "log_q_prop": -100.0 - item,
                        "prefix_barrier": float(item),
                        "proposal_risk": "lowest_1pct",
                        "prefix_risk": "highest_1pct",
                        "primary_static_stratum": "alive_low_final_q",
                    })
        selected = select_cases_and_controls(
            rows, seed=77, category_cap=5
        )
        cases = [row for row in selected if row["role"] == "case"]
        self.assertLessEqual(len(cases), 10)

    def test_parallel_trace_csv_merge_is_lossless(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shards = []
            for index, rows in enumerate((("a,1\n",), ("b,2\n",))):
                path = root / f"{index}.csv"
                path.write_text("path_id,value\n" + "".join(rows))
                shards.append(path)
            output = root / "merged.csv"
            self.assertEqual(merge_csv_outputs(shards, output), 2)
            self.assertEqual(
                output.read_text(),
                "path_id,value\na,1\nb,2\n",
            )

    def test_trace_shards_are_balanced_and_lossless(self) -> None:
        rows = [{"path_id": f"path-{index}"} for index in range(20)]
        shards = split_trace_rows(rows, 64)
        self.assertEqual(len(shards), 20)
        self.assertEqual(
            sorted(row["path_id"] for shard in shards for row in shard),
            sorted(row["path_id"] for row in rows),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
