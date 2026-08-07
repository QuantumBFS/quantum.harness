#!/usr/bin/env python3
"""Gates for consuming the frozen projection in path archives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from archive_contract import load_contracts  # noqa: E402
from path_archive import (  # noqa: E402
    ArchiveHeader,
    ArchiveReader,
    ArchiveRecord,
    write_archive,
)


class ArchiveContractTest(unittest.TestCase):
    def fixture(self, status: str = "target_reached"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        trial = root / "trial_manifest.json"
        trial.write_text(json.dumps({"format_version": 1}), encoding="utf-8")
        digest = hashlib.sha256(trial.read_bytes()).hexdigest()
        selected = {
            "schema_version": 1,
            "theta_star": 10,
            "ltrot_star": 420,
            "nfield_star": 6720,
            "dt": 0.05,
            "beta": 1.0,
            "status": status,
            "trial_manifest_sha256": digest,
        }
        selected_path = root / "selected_projection.json"
        selected_path.write_text(json.dumps(selected), encoding="utf-8")
        site_map = root / "site_map.dat"
        site_map.write_text(
            "".join(f"{i + 1} {i} {i % 4} {i // 4}\n" for i in range(16)),
            encoding="utf-8",
        )
        return selected_path, trial, site_map

    def test_exact_slices_and_field_direction(self) -> None:
        selected, trial, site_map = self.fixture()
        archive, replay = load_contracts(selected, trial, site_map)
        self.assertEqual(archive.ltrot, 420)
        self.assertEqual(archive.nfield, 6720)
        self.assertEqual(replay.right_projector_slices, 200)
        self.assertEqual(replay.measurement_window_slices, 20)
        self.assertEqual(replay.left_projector_slices, 200)
        self.assertEqual(replay.center_slice, 210)
        self.assertEqual(archive.up_exponent, "+gamma*x")
        self.assertEqual(archive.down_exponent, "-gamma*x")
        self.assertTrue(archive.strict_ground_state_claim_allowed)

    def test_fallback_is_accepted_but_claim_is_restricted(self) -> None:
        selected, trial, site_map = self.fixture("max_theta_fallback")
        archive, _replay = load_contracts(selected, trial, site_map)
        self.assertFalse(archive.strict_ground_state_claim_allowed)

    def test_rejects_inconsistent_projection_hash_map_and_status(self) -> None:
        for key, bad in (
            ("ltrot_star", 419),
            ("nfield_star", 6719),
            ("status", "unknown"),
            ("trial_manifest_sha256", "0" * 64),
        ):
            selected, trial, site_map = self.fixture()
            data = json.loads(selected.read_text())
            data[key] = bad
            selected.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(key=key), self.assertRaises(ValueError):
                load_contracts(selected, trial, site_map)
        selected, trial, site_map = self.fixture()
        rows = site_map.read_text().splitlines()
        rows[-1] = rows[0]
        site_map.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bijection"):
            load_contracts(selected, trial, site_map)

    def test_golden_archive_crc_bits_and_truncated_tail(self) -> None:
        header = ArchiveHeader(
            lx=2,
            ly=1,
            n_up=1,
            n_down=1,
            ltrot=2,
            hopping=1.0,
            interaction=4.0,
            dt=0.05,
            beta=0.1,
            theta=0.0,
            ensemble_code=2,
            selected_projection_sha256="1" * 64,
            trial_manifest_sha256="2" * 64,
        )
        record = ArchiveRecord(
            sample_id=(2 << 60) | (127 << 52) | 9,
            chain_id=127,
            bin_id=4,
            sweep_id=17,
            frozen_sign=1,
            central_ekin=-2.0,
            central_epot=0.5,
            central_etot=-1.5,
            central_npart=2.0,
            endpoint_sign=1,
            endpoint_logabs_d=-7.0,
            endpoint_ekin=-1.9,
            endpoint_epot=0.4,
            endpoint_etot=-1.5,
            fields=(-1, +1, +1, -1),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "golden.bin"
            write_archive(path, header, [record])
            raw = path.read_bytes()
            self.assertEqual(raw[256 + 108], 0b00000110)
            reader = ArchiveReader(
                path,
                expected={
                    "ensemble_code": 2,
                    "ltrot": 2,
                    "selected_projection_sha256": "1" * 64,
                },
            )
            scan = reader.scan()
            self.assertEqual(scan.complete_records, 1)
            self.assertFalse(scan.truncated_tail)
            self.assertEqual(list(reader.records())[0].fields, record.fields)

            corrupted = bytearray(raw)
            corrupted[256 + 108] ^= 1
            bad = Path(temporary) / "bad.bin"
            bad.write_bytes(corrupted)
            with self.assertRaisesRegex(ValueError, "CRC"):
                ArchiveReader(bad).scan()

            truncated = Path(temporary) / "truncated.bin"
            truncated.write_bytes(raw + raw[256:300])
            trunc_scan = ArchiveReader(truncated).scan()
            self.assertEqual(trunc_scan.complete_records, 1)
            self.assertTrue(trunc_scan.truncated_tail)

            with self.assertRaisesRegex(ValueError, "ensemble"):
                ArchiveReader(path, expected={"ensemble_code": 1})

    def test_global_chain_id_boundaries(self) -> None:
        header = ArchiveHeader(
            lx=2,
            ly=1,
            n_up=1,
            n_down=1,
            ltrot=1,
            hopping=1.0,
            interaction=4.0,
            dt=0.05,
            beta=0.05,
            theta=0.0,
            ensemble_code=2,
            selected_projection_sha256="1" * 64,
            trial_manifest_sha256="2" * 64,
        )

        def record(chain: int) -> ArchiveRecord:
            return ArchiveRecord(
                sample_id=(2 << 60) | (chain << 49) | 1,
                chain_id=chain,
                bin_id=0,
                sweep_id=1,
                frozen_sign=1,
                central_ekin=-2.0,
                central_epot=0.5,
                central_etot=-1.5,
                central_npart=2.0,
                endpoint_sign=1,
                endpoint_logabs_d=-7.0,
                endpoint_ekin=-1.9,
                endpoint_epot=0.4,
                endpoint_etot=-1.5,
                fields=(-1, +1),
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for chain in (255, 256, 1919):
                with self.subTest(chain=chain):
                    path = root / f"chain_{chain}.qhpath"
                    write_archive(path, header, [record(chain)])
                    decoded = list(ArchiveReader(path).records())
                    self.assertEqual(decoded[0].chain_id, chain)
                    self.assertEqual(decoded[0].sample_id, record(chain).sample_id)

            with self.assertRaisesRegex(ValueError, r"\[0,2048\)"):
                write_archive(root / "chain_2048.qhpath", header, [record(2048)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
