import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.kernels import unrolled_state
from vqetape.optimizers import (
    active_parameter_mask,
    pure_state_qgt,
    run_adam,
    run_lbfgs,
    run_natural_gradient,
)
from vqetape.spec import TFIMVQESpec


def _quadratic(target):
    target = np.asarray(target, dtype=np.float64)

    def evaluate(parameters):
        difference = parameters - target
        return (
            0.5 * float(np.vdot(difference, difference)),
            difference,
        )

    return evaluate


def _stop_below(threshold):
    records = []

    def observer(
        evaluation,
        optimizer_step,
        parameters,
        value,
        gradient,
        metric_condition,
    ):
        records.append(
            (
                evaluation,
                optimizer_step,
                float(value),
                metric_condition,
            )
        )
        return value <= threshold

    return observer, records


def test_adam_converges_on_quadratic_and_counts_evaluations():
    observer, records = _stop_below(1e-8)
    outcome = run_adam(
        np.asarray([2.0, -1.0]),
        _quadratic([0.3, 0.7]),
        observer,
        max_steps=300,
        learning_rate=0.1,
    )

    assert outcome.target_reached
    assert outcome.evaluations == len(records)
    assert outcome.evaluations == outcome.steps + 1
    np.testing.assert_allclose(
        outcome.parameters,
        [0.3, 0.7],
        atol=3e-4,
    )


def test_lbfgs_converges_on_quadratic():
    pytest.importorskip("scipy")
    observer, records = _stop_below(1e-12)
    outcome = run_lbfgs(
        np.asarray([3.0, -2.0]),
        _quadratic([0.2, 0.4]),
        observer,
        max_steps=30,
    )

    assert outcome.target_reached
    assert outcome.evaluations == len(records)
    np.testing.assert_allclose(
        outcome.parameters,
        [0.2, 0.4],
        atol=1e-6,
    )


def test_natural_gradient_uses_metric_and_converges():
    observer, records = _stop_below(1e-8)
    outcome = run_natural_gradient(
        np.asarray([2.0, -1.0]),
        _quadratic([0.3, 0.7]),
        lambda _: np.diag([2.0, 0.5]),
        observer,
        max_steps=100,
        learning_rate=0.2,
        damping=1e-3,
    )

    assert outcome.target_reached
    assert all(
        condition is not None
        for _, _, _, condition in records[1:]
    )


def test_active_mask_freezes_last_rzz_parameter():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    mask = active_parameter_mask(spec)

    assert mask.shape == spec.parameter_shape
    assert np.all(mask[:, 0, -1] == 0)
    assert np.all(mask[:, 0, :-1] == 1)
    assert np.all(mask[:, 1, :] == 1)


def test_pure_state_qgt_matches_finite_difference():
    with jax.enable_x64():
        spec = TFIMVQESpec(
            nqubits=2,
            depth=1,
            dtype="complex128",
        )
        theta = jnp.asarray(
            [[[0.2, 0.0], [0.1, -0.3]]],
            dtype=jnp.float64,
        )
        actual = pure_state_qgt(theta, spec)
        flat = np.asarray(theta).reshape(-1)
        step = 1e-5
        derivatives = []
        for index in range(flat.size):
            plus = flat.copy()
            minus = flat.copy()
            plus[index] += step
            minus[index] -= step
            derivatives.append(
                (
                    np.asarray(
                        unrolled_state(
                            jnp.asarray(plus).reshape(theta.shape),
                            spec,
                        )
                    )
                    - np.asarray(
                        unrolled_state(
                            jnp.asarray(minus).reshape(theta.shape),
                            spec,
                        )
                    )
                )
                / (2 * step)
            )
        jacobian = np.stack(derivatives, axis=1)
        state = np.asarray(unrolled_state(theta, spec))
        connection = jacobian.conj().T @ state
        expected = np.real(
            jacobian.conj().T @ jacobian
            - np.outer(connection, connection.conj())
        )

        np.testing.assert_allclose(
            actual,
            expected,
            rtol=1e-6,
            atol=1e-7,
        )
