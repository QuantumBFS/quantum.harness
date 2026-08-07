#!/usr/bin/env python3
"""Validation gates for ALF frozen records and C++ archive replay."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from path_archive import ArchiveRecord  # noqa: E402
import verify_archive_replay  # noqa: E402

validate_rows = verify_archive_replay.validate_rows


def source(sample_id: int, *, ensemble: str) -> tuple[str, ArchiveRecord]:
    return ensemble, ArchiveRecord(
        sample_id=sample_id,
        chain_id=0,
        bin_id=1,
        sweep_id=9,
        frozen_sign=1,
        central_ekin=-17.0,
        central_epot=3.4,
        central_etot=-13.6,
        central_npart=16.0,
        endpoint_sign=1,
        endpoint_logabs_d=-7.0,
        endpoint_ekin=-17.1,
        endpoint_epot=3.5,
        endpoint_etot=-13.6,
        fields=(1,) * 16,
    )


def row(sample_id: int, *, ensemble: str) -> dict[str, str]:
    return {
        "sample_id": str(sample_id),
        "ensemble": ensemble,
        "chain": "0",
        "sign_d_ii": "1",
        "logabs_d_ii": "-7",
        "sign_d_ti": "1",
        "logabs_d_ti": "-7",
        "sign_d_alf_ii": "1",
        "logabs_d_alf_ii": "-7",
        "sign_d_alf_ti": "1",
        "logabs_d_alf_ti": "-7",
        "alive": "1",
        "identity_log_residual": "1e-12",
        "central_ii_ekin": "-17",
        "central_ii_epot": "3.4",
        "central_ii_etot": "-13.6",
        "central_ti_ekin": "-17",
        "central_ti_epot": "3.4",
        "central_ti_etot": "-13.6",
        "endpoint_i_etot": "-13.6",
        "endpoint_t_etot": "-13.6",
        "alf_frozen_etot": "-13.6",
        "alf_endpoint_etot": "-13.6",
    }


class VerifyArchiveReplayTest(unittest.TestCase):
    def test_matching_ii_and_ti_rows_pass_all_gates(self) -> None:
        records = {
            11: source(11, ensemble="II"),
            22: source(22, ensemble="TI"),
        }
        result = validate_rows(
            [row(11, ensemble="II"), row(22, ensemble="TI")],
            records,
        )
        self.assertTrue(result["passed"])
        self.assertLess(result["max_energy_residual"], 1.0e-8)
        self.assertLess(result["max_endpoint_logd_residual"], 1.0e-8)

    def test_wrong_boundary_determinant_and_energy_are_identified(self) -> None:
        bad = row(22, ensemble="TI")
        bad["logabs_d_alf_ti"] = "-6.9"
        bad["central_ti_etot"] = "-13.4"
        result = validate_rows(
            [bad],
            {22: source(22, ensemble="TI")},
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["failed_sample_ids"], [22])

    def test_endpoint_energy_is_diagnostic_not_a_validation_gate(self) -> None:
        diagnostic = row(22, ensemble="TI")
        diagnostic["endpoint_t_etot"] = "-12.8"
        diagnostic["alf_endpoint_etot"] = "-13.1"
        result = validate_rows(
            [diagnostic],
            {22: source(22, ensemble="TI")},
        )
        self.assertTrue(result["passed"])
        self.assertAlmostEqual(
            result["max_endpoint_energy_residual"], 0.8
        )

    def test_rare_central_energy_outlier_is_marked_not_systemic(self) -> None:
        records = {
            sample_id: source(sample_id, ensemble="TI")
            for sample_id in range(100, 200)
        }
        rows = [
            row(sample_id, ensemble="TI")
            for sample_id in range(100, 200)
        ]
        rows[0]["central_ti_etot"] = "-13.599"
        result = validate_rows(rows, records)
        self.assertTrue(result["passed"])
        self.assertEqual(result["numerically_ambiguous_sample_ids"], [100])
        self.assertTrue(result["replay_numerical_pass"])

    def test_ti_logd_accepts_alf_boundary_normalization_shift(self) -> None:
        normalized = row(22, ensemble="TI")
        normalized["logabs_d_alf_ti"] = "-9.491"
        normalized["_alf_to_raw_log_shift"] = "-2.491"
        result = validate_rows(
            [normalized],
            {22: source(22, ensemble="TI")},
        )
        self.assertTrue(result["passed"])
        self.assertLess(result["max_path_logd_residual"], 1.0e-12)

    def test_cp_symmetric_weight_is_not_used_to_validate_alf_cut(self) -> None:
        different_cut = row(22, ensemble="TI")
        different_cut["logabs_d_ti"] = "-6.75"
        result = validate_rows(
            [different_cut],
            {22: source(22, ensemble="TI")},
        )
        self.assertTrue(result["passed"])

    def test_trial_manifest_supplies_alf_to_raw_log_shifts(self) -> None:
        helper = getattr(verify_archive_replay, "trial_log_shifts", None)
        self.assertIsNotNone(helper)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trial_manifest.json"
            path.write_text(json.dumps({
                "spin_overlap_determinants": {
                    "up": 0.25,
                    "down": 0.5,
                },
            }))
            shifts = helper(path)
        self.assertAlmostEqual(shifts["II"], 0.0)
        self.assertAlmostEqual(shifts["TI"], -2.0794415416798357)

    def test_alive_identity_gate_is_strict(self) -> None:
        bad = row(11, ensemble="II")
        bad["identity_log_residual"] = "2e-9"
        result = validate_rows(
            [bad],
            {11: source(11, ensemble="II")},
        )
        self.assertFalse(result["passed"])
        self.assertGreater(result["max_alive_identity_residual"], 1.0e-9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
