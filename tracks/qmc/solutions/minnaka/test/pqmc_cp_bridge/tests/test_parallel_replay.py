#!/usr/bin/env python3
"""Lossless shard/merge tests for parallel archive replay."""

from __future__ import annotations

import csv
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prefix_file import HEADER, RECORD, records as prefix_records  # noqa: E402
from run_parallel_replay import (  # noqa: E402
    merge_prefixes,
    merge_summaries,
    run_parallel_replay,
    split_rows,
)


def write_prefix(path: Path, sample_ids: list[int]) -> None:
    records = []
    for sample_id in sample_ids:
        prefix = struct.pack(
            "<QI?3x6d",
            sample_id, 0, True,
            -1.0, 2.0, 3.0, -4.0, 0.5, 0.25,
        )
        checksum = zlib.crc32(prefix) & 0xFFFFFFFF
        records.append(RECORD.pack(
            sample_id, 0, True,
            -1.0, 2.0, 3.0, -4.0, 0.5, 0.25,
            checksum,
        ))
    path.write_bytes(
        HEADER.pack(
            b"QHPFX01\0", 1, 0x01020304,
            HEADER.size, RECORD.size, len(records),
        ) + b"".join(records)
    )


class ParallelReplayTest(unittest.TestCase):
    def test_split_is_balanced_and_lossless(self) -> None:
        rows = [
            {"sample_id": str(index), "ensemble": "II", "chain": "0"}
            for index in range(17)
        ]
        shards = split_rows(rows, 4)
        self.assertLessEqual(
            max(map(len, shards)) - min(map(len, shards)), 1
        )
        self.assertEqual(
            sorted(int(row["sample_id"]) for shard in shards for row in shard),
            list(range(17)),
        )

    def test_summary_and_prefix_merges_are_lossless(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summaries = []
            prefixes = []
            for shard, sample_ids in enumerate(([3, 1], [4, 2])):
                summary = root / f"summary_{shard}.csv"
                with summary.open("w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["sample_id", "alive"],
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    for sample_id in sample_ids:
                        writer.writerow({
                            "sample_id": sample_id,
                            "alive": 1,
                        })
                prefix = root / f"prefix_{shard}.qhpfx"
                write_prefix(prefix, sample_ids)
                summaries.append(summary)
                prefixes.append(prefix)
            summary_output = root / "summary.csv"
            prefix_output = root / "prefix.qhpfx"
            self.assertEqual(
                merge_summaries(summaries, summary_output), 4
            )
            self.assertEqual(
                merge_prefixes(prefixes, prefix_output), 4
            )
            with summary_output.open(newline="") as handle:
                ids = [
                    int(row["sample_id"]) for row in csv.DictReader(handle)
                ]
            self.assertEqual(ids, [1, 2, 3, 4])
            self.assertEqual(
                sorted(row.sample_id for row in prefix_records(prefix_output)),
                [1, 2, 3, 4],
            )

    def test_summary_only_parallel_replay_creates_no_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "samples.csv"
            manifest.write_text(
                "sample_id,ensemble,chain\n"
                "1,TI,0\n"
                "2,TI,1\n"
            )
            selected = root / "selected.json"
            selected.write_text('{"ltrot_star": 420}\n')

            def fake_run(command, **_kwargs):
                summary = Path(command[command.index("--summary-output") + 1])
                shard_manifest = Path(
                    command[command.index("--sample-manifest") + 1]
                )
                with shard_manifest.open(newline="") as handle:
                    rows = list(csv.DictReader(handle))
                summary.parent.mkdir(parents=True, exist_ok=True)
                with summary.open("w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["sample_id", "alive"],
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({
                            "sample_id": row["sample_id"],
                            "alive": 1,
                        })
                self.assertIn("--summary-only", command)
                self.assertNotIn("--prefix-output", command)
                return mock.Mock(returncode=0)

            output = root / "output"
            with mock.patch(
                "run_parallel_replay.validate_inputs",
                return_value=({}, []),
            ), mock.patch(
                "run_parallel_replay.initial_mixed_energy",
                return_value=-12.0,
            ), mock.patch(
                "run_parallel_replay.subprocess.run",
                side_effect=fake_run,
            ):
                summary, prefix = run_parallel_replay(
                    executable=Path("/x/cpmc"),
                    archive_index=root / "index.json",
                    sample_manifest=manifest,
                    selected_projection=selected,
                    trial_manifest=root / "trial_manifest.json",
                    field_order=root / "field_order.json",
                    output_dir=output,
                    stabilize_every=5,
                    workers=2,
                    summary_only=True,
                )
            self.assertEqual(prefix, None)
            self.assertTrue(summary.is_file())
            self.assertFalse(
                (output / "replay_prefix_s5.qhpfx").exists()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
