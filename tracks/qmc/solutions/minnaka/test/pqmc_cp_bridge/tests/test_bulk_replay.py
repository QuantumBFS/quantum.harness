#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "test/pqmc_cp_bridge/scripts/run_bulk_replay.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("run_bulk_replay", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
from path_archive import ArchiveHeader, ArchiveRecord, write_archive
from prefix_file import records as prefix_records


class BulkReplayTest(unittest.TestCase):
    def test_command_contains_frozen_roles_and_outputs(self) -> None:
        command = module.replay_command(
            Path("/x/cpmc"), Path("/x/index.json"), Path("/x/samples.csv"),
            Path("/x/selected.json"), Path("/x/trial_manifest.json"),
            Path("/x/field_order.json"), Path("/x/summary.csv"),
            Path("/x/prefix.bin"), -12.0, 5,
        )
        self.assertEqual(command[1], "replay-archive")
        self.assertIn("--trial-manifest", command)
        self.assertIn("--selected-projection", command)
        self.assertEqual(command[-2:], ["--stabilize-every", "5"])

    def test_summary_only_command_omits_prefix_output(self) -> None:
        command = module.replay_command(
            Path("/x/cpmc"), Path("/x/index.json"), Path("/x/samples.csv"),
            Path("/x/selected.json"), Path("/x/trial_manifest.json"),
            Path("/x/field_order.json"), Path("/x/summary.csv"),
            None, -12.0, 5, summary_only=True,
        )
        self.assertIn("--summary-only", command)
        self.assertNotIn("--prefix-output", command)

    def test_consistency_marks_changed_path(self) -> None:
        columns = [
            "sample_id", "logabs_d_ii", "logabs_d_ti",
            "logabs_d_alf_ii", "logabs_d_alf_ti",
            "boundary_cut_log_ratio_ii", "boundary_cut_log_ratio_ti",
            "central_ii_etot", "central_ti_etot", "endpoint_i_etot",
            "endpoint_t_etot", "identity_log_residual", "alive",
            "first_rejection_kind", "first_rejection_slice",
            "first_rejection_site",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / f"{index}.csv" for index in range(2)]
            for index, path in enumerate(paths):
                with path.open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    writer.writerow({
                        "sample_id": 7,
                        "logabs_d_ii": 1.0 + index * 1e-6,
                        "logabs_d_ti": 2.0,
                        "logabs_d_alf_ii": 1.5,
                        "logabs_d_alf_ti": 2.5,
                        "boundary_cut_log_ratio_ii": -0.5,
                        "boundary_cut_log_ratio_ti": -0.5,
                        "central_ii_etot": 3.0,
                        "central_ti_etot": 4.0,
                        "endpoint_i_etot": 5.0,
                        "endpoint_t_etot": 6.0,
                        "identity_log_residual": 0.0,
                        "alive": 1,
                        "first_rejection_kind": "none",
                        "first_rejection_slice": "",
                        "first_rejection_site": "",
                    })
            result = module.compare_summaries(paths)
            self.assertFalse(result["passed"])
            self.assertEqual(result["numerically_ambiguous"], [7])

    def test_endpoint_energy_difference_is_diagnostic(self) -> None:
        columns = [
            "sample_id", "logabs_d_ii", "logabs_d_ti",
            "logabs_d_alf_ii", "logabs_d_alf_ti",
            "boundary_cut_log_ratio_ii", "boundary_cut_log_ratio_ti",
            "central_ii_etot", "central_ti_etot", "endpoint_i_etot",
            "endpoint_t_etot", "identity_log_residual", "alive",
            "first_rejection_kind", "first_rejection_slice",
            "first_rejection_site",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / f"{index}.csv" for index in range(2)]
            for index, path in enumerate(paths):
                with path.open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    writer.writerow({
                        "sample_id": 9,
                        "logabs_d_ii": 1.0,
                        "logabs_d_ti": 2.0,
                        "logabs_d_alf_ii": 1.5,
                        "logabs_d_alf_ti": 2.5,
                        "boundary_cut_log_ratio_ii": -0.5,
                        "boundary_cut_log_ratio_ti": -0.5,
                        "central_ii_etot": 3.0,
                        "central_ti_etot": 4.0,
                        "endpoint_i_etot": 5.0 + index,
                        "endpoint_t_etot": 6.0 - index,
                        "identity_log_residual": 0.0,
                        "alive": 1,
                        "first_rejection_kind": "none",
                        "first_rejection_slice": "",
                        "first_rejection_site": "",
                    })
            result = module.compare_summaries(paths)
            self.assertTrue(result["passed"])
            self.assertAlmostEqual(
                result["max_endpoint_energy_difference"], 1.0
            )

    @unittest.skipUnless(
        (ROOT / "test/cpmc_path_audit/build/cpmc_audit").exists(),
        "C++ replay executable has not been built",
    )
    def test_real_cli_filters_golden_archive(self) -> None:
        executable = ROOT / "test/cpmc_path_audit/build/cpmc_audit"
        trial_manifest = (
            ROOT / "test/pqmc_cp_bridge/assets/trials/trial_manifest.json"
        )
        field_order = ROOT / "test/pqmc_cp_bridge/contracts/field_order.json"
        chain_id = 256
        sample_id = (1 << 60) | (chain_id << 49) | 1
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive = directory / "golden.qhpath"
            header = ArchiveHeader(
                lx=4, ly=4, n_up=8, n_down=8, ltrot=4,
                hopping=1.0, interaction=4.0, dt=0.05,
                beta=0.1, theta=0.05, ensemble_code=1,
                selected_projection_sha256="0" * 64,
                trial_manifest_sha256="1" * 64,
            )
            record = ArchiveRecord(
                sample_id=sample_id, chain_id=chain_id,
                bin_id=2, sweep_id=9,
                frozen_sign=1, central_ekin=0.0, central_epot=0.0,
                central_etot=0.0, central_npart=16.0,
                endpoint_sign=1, endpoint_logabs_d=0.0,
                endpoint_ekin=0.0, endpoint_epot=0.0,
                endpoint_etot=0.0,
                fields=tuple(1 if index % 2 else -1 for index in range(64)),
            )
            write_archive(archive, header, [record])
            index = directory / "index.json"
            index.write_text(json.dumps({
                "sample_id_layout": "chain11_sequence49",
                "entries": [{
                    "path": str(archive), "ensemble": "II",
                    "chain": chain_id,
                }]
            }) + "\n")
            samples = directory / "samples.csv"
            samples.write_text(
                "sample_id,ensemble,chain\n"
                f"{sample_id},II,{chain_id}\n"
            )
            selected = directory / "selected.json"
            selected.write_text(json.dumps({
                "theta_star": 0.05, "ltrot_star": 4,
                "dt": 0.05, "beta": 0.1,
            }) + "\n")
            summary = directory / "summary.csv"
            prefix = directory / "prefix.qhpfx"
            subprocess.run(module.replay_command(
                executable, index, samples, selected, trial_manifest,
                field_order, summary, prefix, -12.0, 1,
            ), check=True)
            with summary.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([int(row["sample_id"]) for row in rows], [sample_id])
            self.assertEqual(prefix.stat().st_size, 64 + 4 * 72)
            decoded = list(prefix_records(prefix))
            self.assertEqual(len(decoded), 4)
            self.assertEqual({row.sample_id for row in decoded}, {sample_id})

            summary_only = directory / "summary_only.csv"
            absent_prefix = directory / "summary_only_prefix.qhpfx"
            subprocess.run(module.replay_command(
                executable, index, samples, selected, trial_manifest,
                field_order, summary_only, None, -12.0, 1,
                summary_only=True,
            ), check=True)
            self.assertFalse(absent_prefix.exists())
            self.assertEqual(
                summary_only.read_text(),
                summary.read_text(),
            )


if __name__ == "__main__":
    unittest.main()
