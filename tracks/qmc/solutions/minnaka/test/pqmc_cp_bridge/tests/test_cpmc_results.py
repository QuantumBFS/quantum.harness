#!/usr/bin/env python3
"""Independent-run statistics for MATLAB CPMC outputs."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy.io import savemat


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cpmc_config import CpmcContract  # noqa: E402
from parse_cpmc_results import (  # noqa: E402
    RunEstimate,
    block_and_run_error,
    independent_run_estimate,
    load_cpmc_run,
)


def contract() -> CpmcContract:
    return CpmcContract(
        lx=4, ly=4, n_up=8, n_down=8, dt=0.05,
        ltrot=420, nfield=6720, stabilize_every=5,
        energy_every=5, primary_pc_every=5,
        strict_ground_state_claim_allowed=True,
        input_sha256={"selected_projection": "a" * 64},
        site_permutation=tuple(range(16)),
    )


class CpmcResultsTest(unittest.TestCase):
    def test_terminal_ratio_uses_pre_pc_weights(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.mat"
            savemat(path, {
                "schema_version": 1,
                "run_id": "fixed-001",
                "seed": 17,
                "mode": "fixed_horizon",
                "ltrot": 420,
                "contract_selected_projection_sha256": "a" * 64,
                "terminal_weights_pre_pc": np.array([1.0, 3.0]),
                "terminal_energies": np.array([-10.0, -14.0]),
                "terminal_weights_post_pc": np.ones(2),
                "strata_names": np.array(["regular"], dtype=object),
                "strata_mass": np.array([4.0]),
                "block_energies": np.array([]),
            })
            result = load_cpmc_run(path, contract())
            self.assertAlmostEqual(result.energy, -13.0)
            self.assertAlmostEqual(result.terminal_weight, 4.0)

    def test_run_offsets_dominate_pooled_block_noise(self) -> None:
        runs = [
            RunEstimate(
                run_id=f"r{index}", seed=index + 1,
                energy=-13.62 + 0.02 * (index - 2),
                terminal_weight=100.0, strata_mass={},
                blocks=tuple(
                    -13.62 + 0.02 * (index - 2) + 0.001 * ((j % 2) * 2 - 1)
                    for j in range(12)
                ),
            )
            for index in range(5)
        ]
        estimate = independent_run_estimate(runs)
        self.assertGreater(estimate.sigma_run, estimate.sigma_block)
        self.assertEqual(estimate.sigma, estimate.sigma_run)
        self.assertEqual(estimate.independent_runs, 5)

    def test_hash_mode_and_duplicate_seed_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.mat"
            savemat(path, {
                "schema_version": 1,
                "run_id": "bad",
                "seed": 3,
                "mode": "rolling_unknown",
                "ltrot": 420,
                "contract_selected_projection_sha256": "b" * 64,
                "terminal_weights_pre_pc": np.array([1.0]),
                "terminal_energies": np.array([-13.0]),
            })
            with self.assertRaises(ValueError):
                load_cpmc_run(path, contract())
        duplicate = [
            RunEstimate("a", 1, -13.0, 1.0, {}, (-13.0,) * 4),
            RunEstimate("b", 1, -14.0, 1.0, {}, (-14.0,) * 4),
        ]
        with self.assertRaisesRegex(ValueError, "seed"):
            independent_run_estimate(duplicate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
