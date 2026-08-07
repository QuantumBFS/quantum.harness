#!/usr/bin/env python3
"""Provenance tests for an untouched official CPMC-Lab source tree."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCE = Path(
    "/home/minnaka/code/QuanHarness/.external/cpmc-lab/"
    "CPMC_Lab_20160129"
)
SCRIPT = ROOT / "matlab" / "apply_cpmc_patch.sh"


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "little"))
        digest.update(content)
    return digest.hexdigest()


class CpmcPatchTest(unittest.TestCase):
    def test_patch_exposes_mixed_roles_and_path_diagnostics(self) -> None:
        patch = (
            ROOT / "patches/cpmc-lab-mixed-diagnostics.patch"
        ).read_text()
        for required in (
            "CPMC_Bridge.m",
            "opts.Phi_init",
            "opts.Phi_trial",
            "rng(opts.rng_seed,'twister')",
            "terminal_weights_pre_pc",
            "path_bits_uint64",
            "pc_parent_index",
            "pc_genealogical_ess",
            "state.logW_path-state.eref_sum",
        ):
            self.assertIn(required, patch)

    def test_copy_patch_reuse_and_source_immutability(self) -> None:
        before = tree_hash(SOURCE)
        self.assertEqual(
            before,
            "6bd0c736649b78647ec8c8d3908d128e4a438a806b6690bee6d066a9f4b710f9",
        )
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "package"
            command = [
                str(SCRIPT),
                "--source", str(SOURCE),
                "--destination", str(destination),
            ]
            subprocess.run(command, check=True, text=True, capture_output=True)
            self.assertTrue((destination / "CPMC_Lab.m").is_file())
            self.assertTrue((destination / "CPMC_BRIDGE_PATCH.txt").is_file())
            manifest = json.loads(
                (destination.parent / "package_manifest.json").read_text()
            )
            self.assertEqual(manifest["source_tree_sha256"], before)
            first = tree_hash(destination)
            subprocess.run(command, check=True, text=True, capture_output=True)
            self.assertEqual(tree_hash(destination), first)

            (destination / "unknown.txt").write_text("mutation\n")
            failed = subprocess.run(
                command, check=False, text=True, capture_output=True
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("does not match", failed.stderr)
        self.assertEqual(tree_hash(SOURCE), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
