#!/usr/bin/env python3
"""Autocorrelation and workload rules for sparse path archives."""

from __future__ import annotations

import math
import random
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from estimate_archive_stride import (  # noqa: E402
    REQUIRED_SCORE_COLUMNS,
    choose_export_stride,
    estimate_stride,
    integrated_autocorrelation_time,
    required_sweeps,
    validate_score_columns,
)
from prepare_archive_run import (  # noqa: E402
    append_archive_namelist,
    prepare_archive_batch,
)
from rebase_archive_index import rebase_entries  # noqa: E402
from prepare_alf_chain import make_parameters  # noqa: E402


class ArchiveSelectionTest(unittest.TestCase):
    def test_archive_index_rebase_uses_portable_relative_paths(self) -> None:
        document = {
            "entries": [
                {
                    "ensemble": "TI", "chain": 127,
                    "path": "/remote/archive/chain_127.qhpath",
                }
            ]
        }
        rebased = rebase_entries(document)
        self.assertEqual(
            rebased["entries"][0]["path"], "TI/chain_127.qhpath"
        )

    def test_archive_namelist_and_hashes_are_frozen(self) -> None:
        base = make_parameters(
            theta=10, nbin=1, nsweep=4000, boundary="II"
        )
        updated = append_archive_namelist(
            base, stride=5, after_sweep=2000, ensemble_code=1,
            chain=3, archive_file=Path("/tmp/chain_3.qhpath"),
            selected_hash="a" * 64, trial_hash="b" * 64,
        )
        qmc = updated[updated.index("&VAR_QMC"):]
        qmc = qmc[:qmc.index("\n/")]
        self.assertIn("Archive_paths = .T.", qmc)
        self.assertIn("Archive_stride = 5", qmc)
        self.assertIn("Archive_chain_id = 3", qmc)
        self.assertNotIn("Archive_paths", updated[updated.index(
            "&VAR_Hubbard_Plain_Vanilla"
        ):])
        updated_1919 = append_archive_namelist(
            base, stride=5, after_sweep=2000, ensemble_code=1,
            chain=1919, archive_file=Path("/tmp/chain_1919.qhpath"),
            selected_hash="a" * 64, trial_hash="b" * 64,
        )
        self.assertIn("Archive_chain_id = 1919", updated_1919)
        with self.assertRaisesRegex(ValueError, "chain"):
            append_archive_namelist(
                base, stride=5, after_sweep=2000, ensemble_code=1,
                chain=2048, archive_file=Path("/tmp/chain_2048.qhpath"),
                selected_hash="a" * 64, trial_hash="b" * 64,
            )

    def test_prepare_archive_batch_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            manifest_text = json.dumps({"sha256": {}}) + "\n"
            (assets / "trial_manifest.json").write_text(manifest_text)
            selected = root / "selected.json"
            selected.write_text(json.dumps({
                "theta_star": 10, "ltrot_star": 420,
            }) + "\n")
            manifest = prepare_archive_batch(
                root / "runs", root / "archives",
                phase="pilot", ensemble="II", theta=10, batch=0,
                nsweep=4000, stride=5, after_sweep=2000,
                master_seed=12, executable=Path("/bin/true"),
                selected_projection=selected, trial_assets=assets,
            )
            self.assertEqual(manifest["archive_stride"], 5)
            self.assertEqual(
                manifest["selected_projection_sha256"],
                hashlib.sha256(selected.read_bytes()).hexdigest(),
            )
            self.assertEqual(len(manifest["archives"]), 6)
            for chain in range(6):
                text = (
                    root / "runs/II/theta_010/batch_000"
                    / f"chain_{chain}/parameters"
                ).read_text()
                self.assertIn(f"Archive_chain_id = {chain}", text)

    def test_prepare_archive_batch_supports_128_chains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": {}}) + "\n"
            )
            selected = root / "selected.json"
            selected.write_text(json.dumps({
                "theta_star": 10, "ltrot_star": 420,
            }) + "\n")
            manifest = prepare_archive_batch(
                root / "runs", root / "archives",
                phase="production", ensemble="II", theta=10, batch=0,
                nsweep=3912, stride=239, after_sweep=2000,
                master_seed=12, executable=Path("/bin/true"),
                selected_projection=selected, trial_assets=assets,
                chains=128,
            )
            self.assertEqual(len(manifest["archives"]), 128)
            self.assertEqual(manifest["archives"][-1]["chain"], 127)
            self.assertTrue(
                (root / "runs/II/theta_010/batch_000/chain_127/parameters")
                .is_file()
            )

    def test_prepare_archive_batch_uses_global_chain_offset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": {}}) + "\n"
            )
            selected = root / "selected.json"
            selected.write_text(json.dumps({
                "theta_star": 10, "ltrot_star": 420,
            }) + "\n")
            manifest = prepare_archive_batch(
                root / "runs", root / "archives",
                phase="direct_reweight", ensemble="II", theta=10, batch=9,
                nsweep=13950, stride=239, after_sweep=2000,
                master_seed=12, executable=Path("/bin/true"),
                selected_projection=selected, trial_assets=assets,
                chains=6, chain_offset=1914,
            )
            self.assertEqual(manifest["chain_offset"], 1914)
            self.assertEqual(manifest["sample_id_layout"], "chain11_sequence49")
            self.assertEqual(manifest["chains"][0]["chain"], 1914)
            self.assertEqual(manifest["chains"][0]["local_chain"], 0)
            self.assertEqual(manifest["chains"][-1]["chain"], 1919)
            self.assertTrue(
                (root / "runs/II/theta_010/batch_009/chain_1919/parameters")
                .is_file()
            )
            self.assertTrue(
                manifest["archives"][-1]["path"].endswith(
                    "chain_1919.qhpath"
                )
            )
            with self.assertRaisesRegex(ValueError, r"\[0,2048\)"):
                prepare_archive_batch(
                    root / "bad-runs", root / "bad-archives",
                    phase="direct_reweight", ensemble="II", theta=10,
                    batch=10, nsweep=13950, stride=239, after_sweep=2000,
                    master_seed=12, executable=Path("/bin/true"),
                    selected_projection=selected, trial_assets=assets,
                    chains=6, chain_offset=2043,
                )

    def test_archive_batch_accepts_shorter_numerical_nwrap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            (assets / "trial_manifest.json").write_text(
                json.dumps({"sha256": {}}) + "\n"
            )
            selected = root / "selected.json"
            selected.write_text(json.dumps({
                "theta_star": 10,
                "ltrot_star": 420,
                "nwrap": 5,
            }) + "\n")
            manifest = prepare_archive_batch(
                root / "runs",
                root / "archives",
                phase="direct_reweight",
                ensemble="II",
                theta=10,
                batch=0,
                nsweep=100,
                stride=5,
                after_sweep=20,
                master_seed=12,
                executable=Path("/bin/true"),
                selected_projection=selected,
                trial_assets=assets,
                chains=6,
                nwrap=1,
            )
            self.assertEqual(manifest["nwrap"], 1)
            parameters = (
                root / "runs/II/theta_010/batch_000/chain_0/parameters"
            ).read_text()
            self.assertRegex(parameters, r"(?m)^\s*Nwrap\s*=\s*1!")

    def test_white_noise_and_ar1_match_sweep_unit_expectations(self) -> None:
        rng = random.Random(9182)
        white = [rng.gauss(0.0, 1.0) for _ in range(50000)]
        self.assertAlmostEqual(
            integrated_autocorrelation_time(white), 0.5, delta=0.08
        )
        rho = 0.8
        values = []
        current = 0.0
        for _ in range(80000):
            current = rho * current + rng.gauss(0.0, math.sqrt(1 - rho**2))
            values.append(current)
        expected = 0.5 + rho / (1.0 - rho)
        self.assertAlmostEqual(
            integrated_autocorrelation_time(values), expected, delta=0.5
        )

    def test_stride_and_production_workload_are_exact(self) -> None:
        self.assertEqual(
            choose_export_stride({"energy": 0.5, "logQ": 8.01}), 41
        )
        self.assertEqual(choose_export_stride({"energy": 1.0}), 20)
        self.assertEqual(
            required_sweeps(
                target_records=10000, stride=41, chains=6, burn_sweeps=2000
            ),
            2000 + 41 * math.ceil(10000 / 6),
        )
        self.assertEqual(
            required_sweeps(
                target_records=1024, stride=239, chains=128,
                burn_sweeps=2000,
            ),
            3912,
        )

    def test_missing_replay_score_is_a_hard_stop(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing"):
            validate_score_columns(REQUIRED_SCORE_COLUMNS - {"logQ_final"})
        validate_score_columns(REQUIRED_SCORE_COLUMNS)

    def test_stride_estimate_converts_record_lags_to_sweeps(self) -> None:
        rows = []
        for ensemble in ("II", "TI"):
            for chain in range(6):
                for index in range(40):
                    rows.append({
                        "ensemble": ensemble,
                        "chain": chain,
                        "sweep": 2000 + 5 * (index + 1),
                        "frozen_etotal": (-1.0) ** index,
                        "field_sum": (index % 7) - 3,
                        "staggered_field_sum": (index % 5) - 2,
                        "logQ_final": -index - 0.01 * chain,
                        "minimum_detrended_prefix_logQ": -(index % 9),
                        "near_node_count": index % 3,
                    })
        result = estimate_stride(rows)
        self.assertEqual(result["tau_units"], "sweeps")
        self.assertGreaterEqual(result["stride"], 20)
        self.assertTrue(all(
            value >= 2.5 for value in result["tau"].values()
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
