#!/usr/bin/env python3
"""Validate ALF archive ordering against independent NumPy propagation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
BRIDGE_ROOT = HERE.parent
REPO_ROOT = BRIDGE_ROOT.parents[1]
SCRIPTS = BRIDGE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from path_archive import ArchiveReader  # noqa: E402
from validate_field_order import validate_record  # noqa: E402


def load_alf_test_module():
    path = REPO_ROOT / "test" / "alf_hirsch_binary" / "tests" / \
        "test_binary_hirsch.py"
    spec = importlib.util.spec_from_file_location("alf_archive_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RealArchiveDirectionTest(unittest.TestCase):
    def test_exactly_one_time_site_direction_matches(self) -> None:
        alf = load_alf_test_module()
        executable = (
            REPO_ROOT / "test" / "alf_hirsch_binary" /
            "ALF" / "Prog" / "ALF.out"
        )
        if not executable.is_file():
            self.skipTest(
                "optional ALF integration test requires "
                "test/alf_hirsch_binary/scripts/build.sh"
            )
        with tempfile.TemporaryDirectory(prefix="alf-order-") as tmp:
            run_dir = Path(tmp)
            completed = alf.run_alf(
                executable,
                run_dir,
                alf.make_smoke_parameters(
                    archive_paths=True,
                    export_trial_orbitals=True,
                    theta=0.05,
                    beta=0.1,
                ),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            record = list(
                ArchiveReader(run_dir / "paths.qhpath").records()
            )[-1]
            result = validate_record(
                record=record,
                up_path=run_dir / "trial_I_up.dat",
                down_path=run_dir / "trial_I_down.dat",
                site_map_path=run_dir / "site_map.dat",
                lx=4,
                ly=4,
                hopping=1.0,
                interaction=4.0,
                dt=0.05,
                stabilization_interval=10,
                tolerance=2.0e-3,
            )
            self.assertEqual(result["matching_candidates"], [
                "time_forward_site_forward"
            ], result)
            self.assertLess(result["endpoint_logabs_residual"], 1.0e-3)
            self.assertLess(result["endpoint_energy_residual"], 1.0e-3)
            self.assertLess(result["central_energy_residual"], 1.0e-3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
