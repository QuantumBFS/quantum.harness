from __future__ import annotations

import sys
import unittest
from pathlib import Path

import jax.numpy as jnp
import numpy as np

SOLUTION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION_DIR))

from landscapes import stacked_jacobian_subspace  # noqa: E402
from optimizers import (  # noqa: E402
    one_sided_wilson_upper,
    optimize_cma_es,
    optimize_coordinate_scans,
)
from sim_to_real import BlackBoxDevice  # noqa: E402


class RobustSubspaceTests(unittest.TestCase):
    def test_stacked_jacobian_recovers_model_direction_union(self) -> None:
        jacobians = np.asarray(
            [
                [[3.0, 0.0, 0.0]],
                [[0.0, 2.0, 0.0]],
            ]
        )
        singular_values, basis = stacked_jacobian_subspace(
            jacobians,
            2,
            normalize_blocks=False,
        )
        np.testing.assert_allclose(singular_values[:2], [3.0, 2.0])
        np.testing.assert_allclose(
            basis @ basis.T,
            np.diag([1.0, 1.0, 0.0]),
        )

    def test_block_normalization_equalizes_model_scale(self) -> None:
        jacobians = np.asarray(
            [
                [[100.0, 0.0]],
                [[0.0, 1.0]],
            ]
        )
        singular_values, _ = stacked_jacobian_subspace(jacobians, 2)
        np.testing.assert_allclose(singular_values[:2], [1.0, 1.0])


class ClosedLoopOptimizerTests(unittest.TestCase):
    def test_wilson_bound_exceeds_observed_failure_rate(self) -> None:
        bound = one_sided_wilson_upper(50, 100_000)
        self.assertGreater(bound, 50 / 100_000)
        self.assertLess(bound, 1e-3)

    def test_coordinate_scan_reaches_quadratic_target(self) -> None:
        optimum = np.asarray([0.3, -0.2])

        def fidelity(params: jnp.ndarray) -> jnp.ndarray:
            error = jnp.sum((params - optimum) ** 2)
            return jnp.clip(1.0 - error, 0.0, 1.0)

        device = BlackBoxDevice(fidelity)
        result = optimize_coordinate_scans(
            device,
            np.zeros(2),
            max_queries=100,
            target_infidelity=1e-8,
            max_cycles=3,
            initial_step=0.4,
            certification_repeats=1,
        )
        self.assertIsNotNone(result.certified_query_to_target)
        self.assertLessEqual(1.0 - result.best_exact_fidelity, 1e-8)
        self.assertLessEqual(result.query_count, 100)

    def test_noisy_coordinate_scan_uses_reported_certificate(self) -> None:
        device = BlackBoxDevice(
            lambda _: jnp.asarray(0.9998),
            shots=100_000,
            seed=4,
        )
        result = optimize_coordinate_scans(
            device,
            np.zeros(1),
            max_queries=50,
            target_infidelity=1e-3,
            max_cycles=1,
            initial_step=0.1,
            certification_repeats=7,
        )
        self.assertIsNotNone(result.certified_query_to_target)
        self.assertTrue(result.optimizer_success)

    def test_cma_es_reaches_rotated_quadratic_target(self) -> None:
        optimum = np.asarray([0.35, -0.2])
        rotation = np.asarray(
            [
                [np.sqrt(0.5), -np.sqrt(0.5)],
                [np.sqrt(0.5), np.sqrt(0.5)],
            ]
        )
        curvature = np.diag([1.0, 20.0])

        def fidelity(params: jnp.ndarray) -> jnp.ndarray:
            delta = rotation.T @ (params - optimum)
            error = delta @ curvature @ delta
            return jnp.clip(1.0 - error, 0.0, 1.0)

        device = BlackBoxDevice(fidelity)
        result = optimize_cma_es(
            device,
            np.zeros(2),
            max_queries=500,
            target_infidelity=1e-6,
            initial_sigma=0.3,
            seed=11,
        )
        self.assertLessEqual(result.query_count, 500)
        self.assertLessEqual(1.0 - result.best_exact_fidelity, 1e-6)


if __name__ == "__main__":
    unittest.main()
