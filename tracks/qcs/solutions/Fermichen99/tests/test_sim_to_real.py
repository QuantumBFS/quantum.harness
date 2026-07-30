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

from sim_to_real import (  # noqa: E402
    BlackBoxDevice,
    QueryRecord,
    fourier_controls,
    make_demo_problem,
    make_drift_perturbation,
    make_loss,
    make_single_qubit_problem,
    phase_aligned_unitary_distance,
    propagate_expm,
    unitarity_defect,
)
from optimizers import _closed_loop_summary  # noqa: E402


class DynamicsTests(unittest.TestCase):
    def test_demo_problem_shapes_and_hermiticity(self) -> None:
        problem = make_demo_problem()
        self.assertEqual(problem.dim, 4)
        self.assertEqual(problem.n_ctrl, 4)
        self.assertEqual(problem.n_basis, 10)
        self.assertEqual(problem.n_params, 40)
        np.testing.assert_allclose(problem.h0, problem.h0.conj().T, atol=1e-13)
        for control in np.asarray(problem.h_ctrl):
            np.testing.assert_allclose(control, control.conj().T, atol=1e-13)

    def test_single_qubit_problem_is_overparameterized(self) -> None:
        problem = make_single_qubit_problem()
        self.assertEqual(problem.dim, 2)
        self.assertEqual(problem.n_ctrl, 2)
        self.assertEqual(problem.n_params, 20)
        np.testing.assert_allclose(
            problem.target.conj().T @ problem.target,
            np.eye(2),
            atol=1e-13,
        )

    def test_fourier_controls_vanish_at_endpoints(self) -> None:
        problem = make_demo_problem(n_ctrl=2, n_basis=3)
        for time in (0.0, problem.t_final):
            amplitudes = fourier_controls(
                problem, jnp.asarray(time), problem.initial_params
            )
            np.testing.assert_allclose(amplitudes, 0.0, atol=1e-14)

    def test_product_exponential_is_unitary(self) -> None:
        problem = make_demo_problem(n_ctrl=2, n_basis=3)
        unitary = propagate_expm(problem, problem.initial_params, n_steps=16)
        self.assertLess(float(unitarity_defect(unitary)), 1e-11)

    def test_phase_aligned_distance_ignores_global_phase(self) -> None:
        identity = jnp.eye(4, dtype=jnp.complex128)
        phased = identity * jnp.exp(0.37j)
        self.assertLess(
            float(phase_aligned_unitary_distance(identity, phased)), 1e-13
        )

    def test_drift_perturbation_is_traceless_hermitian_and_normalized(self) -> None:
        problem = make_demo_problem()
        perturbation = make_drift_perturbation(problem)
        np.testing.assert_allclose(
            perturbation, perturbation.conj().T, atol=1e-13
        )
        self.assertLess(abs(complex(jnp.trace(perturbation))), 1e-12)
        self.assertAlmostEqual(
            float(jnp.linalg.norm(perturbation)),
            float(jnp.linalg.norm(problem.h0)),
            places=12,
        )

    def test_autodiff_gradient_matches_finite_difference(self) -> None:
        problem = make_demo_problem(n_ctrl=1, n_basis=2)
        loss = make_loss(problem, integrator="expm", n_steps=12)
        params = problem.initial_params
        gradient = np.asarray(jax.grad(loss)(params))
        epsilon = 1e-5
        direction = np.asarray([0.6, -0.8])
        finite_difference = (
            float(loss(params + epsilon * direction))
            - float(loss(params - epsilon * direction))
        ) / (2.0 * epsilon)
        autodiff = float(gradient @ direction)
        self.assertAlmostEqual(autodiff, finite_difference, places=7)


class BlackBoxTests(unittest.TestCase):
    def test_exact_device_counts_queries_without_shots(self) -> None:
        fidelity = lambda params: jnp.exp(-jnp.vdot(params, params))
        device = BlackBoxDevice(fidelity)
        loss = device.query(np.zeros(3))
        self.assertAlmostEqual(loss, 0.0)
        self.assertEqual(device.query_count, 1)
        self.assertEqual(device.shot_count, 0)
        self.assertAlmostEqual(device.history[0].exact_fidelity, 1.0)

    def test_finite_shot_device_counts_shots(self) -> None:
        device = BlackBoxDevice(lambda _: jnp.asarray(0.5), shots=100, seed=7)
        device.query(np.zeros(2))
        device.query(np.ones(2))
        self.assertEqual(device.query_count, 2)
        self.assertEqual(device.shot_count, 200)
        for record in device.history:
            self.assertGreaterEqual(record.reported_fidelity, 0.0)
            self.assertLessEqual(record.reported_fidelity, 1.0)

    def test_closed_loop_returns_best_reported_not_latent_params(self) -> None:
        device = BlackBoxDevice(lambda _: jnp.asarray(0.5))
        device.history.extend(
            [
                QueryRecord(1, 0.99, 0.90, np.asarray([1.0])),
                QueryRecord(2, 0.94, 0.95, np.asarray([2.0])),
            ]
        )
        result = _closed_loop_summary(
            device,
            target_infidelity=0.01,
            optimizer_success=True,
            message="test",
        )
        np.testing.assert_allclose(result.params, [1.0])
        self.assertAlmostEqual(result.best_reported_fidelity, 0.99)
        self.assertAlmostEqual(result.best_exact_fidelity, 0.95)

if __name__ == "__main__":
    unittest.main()
