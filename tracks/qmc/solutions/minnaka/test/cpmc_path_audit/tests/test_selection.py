import math
import pathlib
import struct
import sys
import tempfile
import unittest

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pattern_analysis.path_records import (  # noqa: E402
    HEADER_STRUCT,
    MAGIC,
    PATH_DTYPE_V2,
    logsumexp_field,
    open_path_records,
)
from pattern_analysis.selection import (  # noqa: E402
    build_trial_selection,
    exact_worst_fraction,
    nearest_unused_matches,
    weight_bin,
)


def synthetic_records(config_id, log_d, log_q):
    records = np.zeros(
        len(config_id),
        dtype=[
            ("config_id", "<u8"),
            ("log_d", "<f8"),
            ("log_q", "<f8"),
            ("alive", "u1"),
        ],
    )
    records["config_id"] = config_id
    records["log_d"] = log_d
    records["log_q"] = log_q
    records["alive"] = 1
    return records


class PathRecordTest(unittest.TestCase):
    def test_open_path_records_uses_fixed_64_byte_stride(self):
        record_struct = struct.Struct("<Q5d2IbBfBB")
        header = HEADER_STRUCT.pack(
            MAGIC,
            2,
            128,
            64,
            0x01020304,
            2,
            2,
            2,
            2,
            1,
            1,
            1,
            1,
            1.0,
            8.0,
            0.1,
            2,
            2,
        )
        rows = [
            record_struct.pack(
                4, 1.0, -2.0, 3.0, -4.0, 0.2, 5, 6, 1, 1, 0.5, 1, 0
            ),
            record_struct.pack(
                9, 7.0, -8.0, 9.0, -10.0, 0.1, 11, 12, 1, 1, 1.5, 2, 0
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "paths.bin"
            path.write_bytes(header + b"".join(rows))
            metadata, records = open_path_records(path)

            self.assertEqual(metadata.trial, "rhf_x")
            self.assertEqual(metadata.slices, 1)
            self.assertEqual(records.dtype.itemsize, 64)
            np.testing.assert_array_equal(records["config_id"], [4, 9])
            np.testing.assert_allclose(records["log_d"], [1.0, 7.0])

    def test_logsumexp_field_is_stable_across_chunks(self):
        records = np.zeros(3, dtype=PATH_DTYPE_V2)
        records["log_d"] = [1000.0, 1000.0 + math.log(2.0), -1000.0]

        total = logsumexp_field(records, "log_d", chunk_size=1)

        self.assertAlmostEqual(total, 1000.0 + math.log(3.0), places=12)


class ExactSelectionTest(unittest.TestCase):
    def test_exact_worst_fraction_resolves_cutoff_ties_by_config_id(self):
        records = synthetic_records(
            config_id=[0, 1, 2, 3, 4],
            log_d=[0.0] * 5,
            log_q=[0.0, -2.0, -2.0, -2.0, -1.0],
        )
        selected = exact_worst_fraction(
            records, log_total_d=math.log(5.0), fraction=0.4
        )

        np.testing.assert_array_equal(selected.config_ids, [1, 2])
        self.assertEqual(selected.cutoff_tie_count, 3)
        self.assertEqual(selected.cutoff_score, selected.scores[0])

    def test_weight_bins_use_mutually_exclusive_matching_layers(self):
        self.assertEqual(weight_bin(math.log(0.75)), "near_average")
        self.assertEqual(weight_bin(math.log(1.5)), "important")
        self.assertEqual(weight_bin(math.log(2.0)), "strongly_important")
        self.assertIsNone(weight_bin(math.log(0.49)))

    def test_build_trial_selection_separates_all_replay_roles(self):
        d_values = [1.0, 1.0, 1.0, 1.0, 1.0, 8.0, 8.0, 0.1]
        log_q = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -10.0, -20.0]
        records = []
        record_struct = struct.Struct("<Q5d2IbBfBB")
        for config_id, (d_value, q_value) in enumerate(
            zip(d_values, log_q)
        ):
            records.append(
                record_struct.pack(
                    config_id,
                    math.log(d_value),
                    q_value,
                    0.0,
                    0.0,
                    1.0,
                    0,
                    0,
                    1,
                    1,
                    0.0,
                    0,
                    0,
                )
            )
        header = HEADER_STRUCT.pack(
            MAGIC,
            2,
            128,
            64,
            0x01020304,
            2,
            2,
            2,
            2,
            1,
            1,
            1,
            1,
            1.0,
            8.0,
            0.1,
            8,
            8,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "paths.bin"
            path.write_bytes(header + b"".join(records))

            table = build_trial_selection(path, fraction=0.25)

        worst = table[table["role"].isin(["case", "worst_low"])]
        self.assertEqual(set(worst["config_id"]), {6, 7})
        self.assertEqual(
            table.loc[table.role == "case", "config_id"].tolist(), [6]
        )
        self.assertEqual(
            table.loc[table.role == "control", "config_id"].tolist(), [5]
        )
        self.assertEqual(
            table.loc[
                table.role == "low_weight_reference", "config_id"
            ].tolist(),
            [7],
        )
        self.assertEqual(table.loc[table.role == "case", "case_id"].iloc[0], 6)
        self.assertEqual(
            table.loc[table.role == "control", "case_id"].iloc[0], 6
        )


class MatchingTest(unittest.TestCase):
    def test_nearest_unused_matching_is_deterministic(self):
        matched = nearest_unused_matches(
            case_log_d=np.array([0.01, 0.03, 1.009]),
            case_ids=np.array([9, 8, 7], dtype=np.uint64),
            control_log_d=np.array([0.00, 0.04, 1.00, 1.02]),
            control_ids=np.array([11, 10, 13, 12], dtype=np.uint64),
        )

        np.testing.assert_array_equal(matched, [11, 10, 13])
        self.assertEqual(len(set(matched.tolist())), len(matched))

    def test_nearest_unused_matching_rejects_small_control_pool(self):
        with self.assertRaisesRegex(ValueError, "insufficient unique controls"):
            nearest_unused_matches(
                case_log_d=np.array([0.0, 1.0]),
                case_ids=np.array([0, 1], dtype=np.uint64),
                control_log_d=np.array([0.5]),
                control_ids=np.array([2], dtype=np.uint64),
            )


if __name__ == "__main__":
    unittest.main()
