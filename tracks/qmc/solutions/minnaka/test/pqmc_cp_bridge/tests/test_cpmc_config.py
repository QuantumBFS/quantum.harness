#!/usr/bin/env python3
"""Frozen mixed-boundary CPMC grid contract."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cpmc_config import (  # noqa: E402
    fixed_horizon_parameters,
    load_cpmc_contract,
    production_parameters,
)


class CpmcConfigTest(unittest.TestCase):
    def fixture(self, theta: int):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        ltrot = int((2 * theta + 1) / 0.05)
        inputs = {}
        for name, data in (
            (
                "selected_projection.json",
                {
                    "schema_version": 1,
                    "theta_star": theta,
                    "ltrot_star": ltrot,
                    "nfield_star": 16 * ltrot,
                    "dt": 0.05,
                    "beta": 1.0,
                    "status": "target_reached",
                },
            ),
            ("trial_manifest.json", {"format_version": 1}),
            ("field_order.json", {"validated": True}),
            ("strata_contract.json", {"schema_version": 1}),
        ):
            path = root / name
            path.write_text(json.dumps(data), encoding="utf-8")
            inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (root / "site_map.dat").write_text(
            "".join(f"{i+1} {i} {i%4} {i//4}\n" for i in range(16)),
            encoding="utf-8",
        )
        selected = json.loads((root / "selected_projection.json").read_text())
        selected.update({
            "trial_manifest_sha256": inputs["trial_manifest.json"],
            "field_order_sha256": inputs["field_order.json"],
            "strata_contract_sha256": inputs["strata_contract.json"],
        })
        (root / "selected_projection.json").write_text(
            json.dumps(selected), encoding="utf-8"
        )
        return root

    def test_theta_10_and_20_grids(self) -> None:
        for theta, expected_ltrot, expected_eqblk in (
            (10, 420, 21),
            (20, 820, 41),
        ):
            contract = load_cpmc_contract(self.fixture(theta))
            self.assertEqual(contract.ltrot, expected_ltrot)
            fixed = fixed_horizon_parameters(
                contract, nwalkers=1000, pc_every=5, seed=17
            )
            self.assertEqual(fixed["steps"], expected_ltrot)
            production = production_parameters(contract, nwalkers=1000)
            self.assertEqual(production["N_eqblk"], expected_eqblk)
            self.assertGreaterEqual(
                production["N_eqblk"] * production["N_blksteps"],
                expected_ltrot,
            )

    def test_fixed_grid_and_intervals(self) -> None:
        contract = load_cpmc_contract(self.fixture(10))
        self.assertEqual(contract.stabilize_every, 5)
        self.assertEqual(contract.energy_every, 5)
        self.assertEqual(contract.primary_pc_every, 5)
        for nwalkers in (100, 500, 1000):
            self.assertEqual(
                fixed_horizon_parameters(
                    contract, nwalkers, 5, seed=nwalkers
                )["steps"],
                420,
            )
        for interval in (5, 20, 40):
            self.assertEqual(
                fixed_horizon_parameters(
                    contract, 1000, interval, seed=interval
                )["pc_every"],
                interval,
            )

    def test_rejects_projection_hash_map_and_invalid_intervals(self) -> None:
        root = self.fixture(10)
        selected_path = root / "selected_projection.json"
        selected = json.loads(selected_path.read_text())
        selected["nfield_star"] -= 1
        selected_path.write_text(json.dumps(selected), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_cpmc_contract(root)

        root = self.fixture(10)
        rows = (root / "site_map.dat").read_text().splitlines()
        rows[-1] = rows[0]
        (root / "site_map.dat").write_text("\n".join(rows) + "\n")
        with self.assertRaisesRegex(ValueError, "permutation"):
            load_cpmc_contract(root)

        contract = load_cpmc_contract(self.fixture(10))
        with self.assertRaises(ValueError):
            fixed_horizon_parameters(contract, 1000, 0, seed=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
