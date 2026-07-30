#!/usr/bin/env python3
"""Production-contract tests for replica execution and strict merging."""

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

from merge_direct_reweight_replicas import (  # noqa: E402
    merge_green_rows,
    merge_production,
    merge_replica_rows,
)
from run_direct_reweight_replica import (  # noqa: E402
    guard_incomplete_replica_resume,
    replica_contract,
    validate_archive_entries,
)


class DirectReweightProductionTest(unittest.TestCase):
    def test_ten_replica_contract_covers_every_global_chain_once(self) -> None:
        contracts = [replica_contract(replica) for replica in range(10)]
        self.assertEqual(contracts[0]["chain_offset"], 0)
        self.assertEqual(contracts[-1]["chain_stop"], 1920)
        self.assertEqual(contracts[0]["nsweep"], 13950)
        chains = [
            chain
            for contract in contracts
            for chain in range(
                contract["chain_offset"], contract["chain_stop"]
            )
        ]
        self.assertEqual(chains, list(range(1920)))
        stable = replica_contract(0, nwrap=1)
        self.assertEqual(stable["nwrap"], 1)

    def test_replica_contract_rejects_out_of_range_array_index(self) -> None:
        with self.assertRaisesRegex(ValueError, "replica"):
            replica_contract(10)

    def test_archive_validation_requires_exact_records_per_global_chain(self) -> None:
        entries = [
            {"ensemble": "TI", "chain": chain, "records": 50}
            for chain in range(192, 384)
        ]
        validate_archive_entries(
            entries, chain_offset=192, chains=192, paths_per_chain=50
        )
        entries[-1]["records"] = 49
        with self.assertRaisesRegex(RuntimeError, "record count"):
            validate_archive_entries(
                entries, chain_offset=192, chains=192, paths_per_chain=50
            )

    def test_merge_requires_lossless_replica_rectangles(self) -> None:
        replica_rows = []
        sample_id = 1
        for replica in range(2):
            rows = []
            for chain in range(2 * replica, 2 * replica + 2):
                for sweep in (10, 20):
                    rows.append({
                        "sample_id": str(sample_id),
                        "ensemble": "TI",
                        "chain": str(chain),
                        "sweep": str(sweep),
                    })
                    sample_id += 1
            replica_rows.append(rows)
        merged = merge_replica_rows(
            replica_rows,
            replicas=2,
            chains_per_replica=2,
            paths_per_chain=2,
        )
        self.assertEqual(len(merged), 8)
        replica_rows[1].pop()
        with self.assertRaisesRegex(RuntimeError, "row count"):
            merge_replica_rows(
                replica_rows,
                replicas=2,
                chains_per_replica=2,
                paths_per_chain=2,
            )

    def test_green_merge_reports_distribution_and_failures(self) -> None:
        rows = [
            {
                "chain": chain,
                "max_delta_g": value,
                "pass_1e-8": value <= 1.0e-8,
                "bin": 1,
                "sweep": chain + 10,
                "direction": 1,
                "slice": 2,
                "i": 3,
                "j": 4,
                "flavor": 1,
            }
            for chain, value in enumerate((1.0e-10, 2.0e-9, 2.0e-8))
        ]
        summary = merge_green_rows(rows, expected_chains=3)
        self.assertFalse(summary["alf_green_stability_pass"])
        self.assertEqual(summary["failed_chains"], [2])
        self.assertAlmostEqual(summary["maximum_delta_g"], 2.0e-8)
        self.assertAlmostEqual(summary["median_delta_g"], 2.0e-9)

    def test_incomplete_replica_with_records_is_not_silently_appended(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = root / "runs/TI/theta_010/batch_000"
            batch.mkdir(parents=True)
            (batch / "batch_state.json").write_text(
                '{"status": "running"}\n'
            )
            archive = root / (
                "archives/direct_reweight/TI/chain_0.qhpath"
            )
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"x" * 300)
            with self.assertRaisesRegex(RuntimeError, "isolate"):
                guard_incomplete_replica_resume(root, replica_id=0)

    def test_small_end_to_end_merge_writes_direct_products(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            production = Path(temporary)
            next_sample = 1
            for replica in range(2):
                root = production / "replicas" / f"replica_{replica:03d}"
                root.mkdir(parents=True)
                entries = []
                replay_rows = []
                green_rows = []
                for chain in range(replica * 2, replica * 2 + 2):
                    entries.append({
                        "path": str(root / f"chain_{chain}.qhpath"),
                        "ensemble": "TI",
                        "chain": chain,
                        "records": 2,
                    })
                    green_rows.append({
                        "chain": chain,
                        "max_delta_g": 1.0e-10,
                        "pass_1e-8": True,
                        "bin": 1,
                        "sweep": 10,
                        "direction": 1,
                        "slice": 2,
                        "i": 3,
                        "j": 4,
                        "flavor": 1,
                    })
                    for sweep, energy in ((10, -10.0), (20, -12.0)):
                        replay_rows.append({
                            "sample_id": next_sample,
                            "ensemble": "TI",
                            "chain": chain,
                            "bin": 0,
                            "sweep": sweep,
                            "sign_d_ti": 1,
                            "sign_d_alf_ti": 1,
                            "boundary_cut_log_ratio_ti": math.log(chain + 1),
                            "central_ti_etot": energy,
                            "alive": 1,
                            "identity_log_residual": 0,
                        })
                        next_sample += 1
                archive_index = root / "archive_index.json"
                archive_index.write_text(json.dumps({
                    "entries": entries,
                }) + "\n")
                replay = root / "replay.csv"
                with replay.open("w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=list(replay_rows[0]),
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    writer.writerows(replay_rows)
                green = root / "green.csv"
                with green.open("w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=list(green_rows[0]),
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    writer.writerows(green_rows)
                (root / "replica_status.json").write_text(json.dumps({
                    "status": "complete",
                    "chain_offset": replica * 2,
                    "chains": 2,
                    "paths_per_chain": 2,
                    "archive_index": str(archive_index),
                    "replay_summary": str(replay),
                    "green_stability_csv": str(green),
                    "replay_stability_pass": True,
                }) + "\n")
            summary = merge_production(
                production,
                replicas=2,
                chains_per_replica=2,
                paths_per_chain=2,
                target_error=100.0,
            )
            self.assertEqual(summary["paths"], 8)
            self.assertEqual(summary["cross_chain_bins"], 2)
            self.assertTrue(summary["green_stability_pass"])
            self.assertTrue(
                (production / "results/DIRECT_REWEIGHT_RESULTS_CN.md")
                .is_file()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
