from __future__ import annotations

import sys
import unittest
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np

SOLUTION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION_DIR))

from landscapes import subspace_metrics  # noqa: E402
from sim_to_real import BlackBoxDevice  # noqa: E402
from subspace_tracking import (  # noqa: E402
    _wilson_upper_bound,
    cross_block_query_cost,
    estimate_cross_block_rotation,
)


class SubspaceTrackingTests(unittest.TestCase):
    def test_wilson_upper_bound_is_conservative(self) -> None:
        upper = _wilson_upper_bound(8e-4, 65536 * 4, z_score=1.64)
        self.assertGreater(upper, 8e-4)
        self.assertLess(upper, 1e-3)

    def test_cross_block_update_recovers_rotated_rank_two_space(self) -> None:
        angle = 0.43
        true_basis = np.asarray(
            [
                [np.cos(angle), 0.0],
                [0.0, 1.0],
                [np.sin(angle), 0.0],
                [0.0, 0.0],
            ]
        )
        hessian = true_basis @ np.diag([0.8, 0.3]) @ true_basis.T

        def fidelity(params):
            loss = 0.5 * params @ jnp.asarray(hessian) @ params
            return 1.0 - loss

        device = BlackBoxDevice(fidelity)
        initial_basis = np.eye(4)[:, :2]
        update = estimate_cross_block_rotation(
            device,
            np.zeros(4),
            initial_basis,
            np.asarray([0.8, 0.3]),
            scout_count=2,
            finite_difference_step=0.2,
            center_repeats=1,
            diagonal_blend=1.0,
            cross_shrink=1.0,
            seed=11,
        )
        metrics = subspace_metrics(update.basis, true_basis)
        self.assertGreater(metrics.minimum_overlap, 0.999)
        self.assertEqual(
            update.queries,
            cross_block_query_cost(2, 2, center_repeats=1),
        )


if __name__ == "__main__":
    unittest.main()
