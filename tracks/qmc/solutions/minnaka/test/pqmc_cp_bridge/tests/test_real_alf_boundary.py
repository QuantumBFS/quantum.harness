#!/usr/bin/env python3
"""End-to-end checks for shared ALF/free and C++/UHF trial assets."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSETS = ROOT / "assets" / "trials"
CPMC_AUDIT = REPO / "test" / "cpmc_path_audit" / "build" / "cpmc_audit"
sys.path.insert(0, str(ROOT / "scripts"))

from bootstrap_trials import read_orbitals, validate_manifest  # noqa: E402


class RealAlfBoundaryTest(unittest.TestCase):
    def test_export_uhf_requires_explicit_inputs(self) -> None:
        completed = subprocess.run(
            [str(CPMC_AUDIT), "export-uhf"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("missing required option", completed.stdout)

    def test_bootstrap_assets_are_complete(self) -> None:
        manifest = validate_manifest(ASSETS / "trial_manifest.json")
        self.assertEqual(manifest["format_version"], 1)
        self.assertEqual(manifest["uhf_u"], 4.0)
        self.assertTrue(manifest["scf_converged"])
        self.assertLess(manifest["scf_residual"], 1.0e-12)
        self.assertGreater(manifest["staggered_magnetization"], 0.0)
        for spin in ("up", "down"):
            self.assertGreater(
                manifest["spin_overlap_determinants"][spin], 1.0e-10
            )
            self.assertLess(
                manifest["orthonormality_residuals"][f"I_{spin}"],
                1.0e-11,
            )
            self.assertLess(
                manifest["orthonormality_residuals"][f"T_{spin}"],
                1.0e-11,
            )
        for value in manifest["particle_hole_residuals"].values():
            self.assertLess(value, 1.0e-10)
        self.assertEqual(set(manifest["sha256"]), {
            "trial_I_up.dat",
            "trial_I_down.dat",
            "trial_T_up.dat",
            "trial_T_down.dat",
            "site_map.dat",
            "uhf_metadata.json",
        })

    def test_orbital_files_are_16_by_8_and_finite(self) -> None:
        for name in (
            "trial_I_up.dat",
            "trial_I_down.dat",
            "trial_T_up.dat",
            "trial_T_down.dat",
        ):
            matrix = read_orbitals(ASSETS / name)
            self.assertEqual((len(matrix), len(matrix[0])), (16, 8))
            self.assertTrue(
                all(math.isfinite(value) for row in matrix for value in row)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
