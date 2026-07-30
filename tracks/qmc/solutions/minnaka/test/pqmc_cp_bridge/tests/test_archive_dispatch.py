#!/usr/bin/env python3
"""Tests for bounded per-ensemble archive dispatch."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_archive_pilot import _merge_if_complete, _partial_index  # noqa: E402
from run_archive_production import (  # noqa: E402
    _merge_if_complete as merge_production,
    _partial_index as production_index,
    production_nsweep,
    segment_nsweep,
)
from archive_runs import validate_archive_request  # noqa: E402


class ArchiveDispatchTest(unittest.TestCase):
    def test_existing_batch_must_match_requested_chain_contract(self) -> None:
        manifest = {
            "archive_phase": "production",
            "ensemble": "TI",
            "theta": 10,
            "chain_count": 6,
            "nsweep": 3912,
            "archive_stride": 239,
            "archive_after_sweep": 2000,
            "chain_offset": 0,
            "sample_id_layout": "chain11_sequence49",
        }
        with self.assertRaisesRegex(RuntimeError, "chain_count"):
            validate_archive_request(
                manifest,
                phase="production",
                ensemble="TI",
                theta=10,
                chains=128,
                nsweep=3912,
                stride=239,
                after_sweep=2000,
                chain_offset=0,
            )

    def test_existing_batch_must_match_global_chain_offset(self) -> None:
        manifest = {
            "archive_phase": "direct_reweight",
            "ensemble": "TI",
            "theta": 10,
            "chain_count": 192,
            "nsweep": 13950,
            "archive_stride": 239,
            "archive_after_sweep": 2000,
            "chain_offset": 0,
            "sample_id_layout": "chain11_sequence49",
        }
        with self.assertRaisesRegex(RuntimeError, "chain_offset"):
            validate_archive_request(
                manifest,
                phase="direct_reweight",
                ensemble="TI",
                theta=10,
                chains=192,
                nsweep=13950,
                stride=239,
                after_sweep=2000,
                chain_offset=192,
            )

    def test_waits_until_both_ensembles_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            partial = _partial_index(root, "II")
            partial.parent.mkdir(parents=True)
            partial.write_text(json.dumps({
                "entries": [{
                    "ensemble": "II", "chain": 0, "records": 400,
                }],
            }))
            self.assertIsNone(_merge_if_complete(root, theta=10))

    def test_merges_ensemble_indexes_and_record_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for ensemble in ("II", "TI"):
                partial = _partial_index(root, ensemble)
                partial.parent.mkdir(parents=True, exist_ok=True)
                partial.write_text(json.dumps({
                    "entries": [{
                        "ensemble": ensemble,
                        "chain": chain,
                        "records": 400,
                        "path": f"{ensemble}-{chain}.bin",
                    } for chain in range(6)],
                }))
            result = _merge_if_complete(root, theta=10)
            self.assertEqual(result, root / "pilot/archive_index.json")
            merged = json.loads(result.read_text())
            self.assertEqual(len(merged["entries"]), 12)
            self.assertEqual(merged["records"], 4800)
            self.assertEqual(merged["theta"], 10)

    def test_production_segment_never_exceeds_sweep_budget(self) -> None:
        self.assertEqual(segment_nsweep(5), 5000)
        self.assertEqual(segment_nsweep(32), 4976)
        with self.assertRaises(ValueError):
            segment_nsweep(3001)
        with self.assertRaises(ValueError):
            segment_nsweep(0)
        self.assertEqual(
            production_nsweep(
                stride=239, target_records=1024, chains=128,
                burn=2000, max_sweeps=4500,
            ),
            3912,
        )

    def test_production_merge_waits_for_both_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for ensemble, records in (("II", 10020), ("TI", 9990)):
                partial = production_index(root, ensemble)
                partial.parent.mkdir(parents=True, exist_ok=True)
                partial.write_text(json.dumps({
                    "ensemble": ensemble,
                    "records": records,
                    "segments": 5,
                    "entries": [{
                        "ensemble": ensemble,
                        "chain": chain,
                        "records": records // 6,
                        "path": f"{ensemble}-{chain}.bin",
                    } for chain in range(6)],
                }))
            self.assertIsNone(merge_production(
                root, theta=10, stride=5, burn=2000, target=10000,
            ))
            ti_path = production_index(root, "TI")
            ti = json.loads(ti_path.read_text())
            ti["records"] = 10002
            ti_path.write_text(json.dumps(ti))
            result = merge_production(
                root, theta=10, stride=5, burn=2000, target=10000,
            )
            self.assertIsNotNone(result)
            index, counts = result
            self.assertEqual(counts, {"II": 10020, "TI": 10002})
            self.assertEqual(len(json.loads(index.read_text())["entries"]), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
