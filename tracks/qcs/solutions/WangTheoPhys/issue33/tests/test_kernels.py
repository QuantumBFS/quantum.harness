import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.kernels import (
    initial_state,
    rzz_matrix,
    rzz_schmidt_factors,
    unrolled_energy,
)
from vqetape.spec import TFIMVQESpec


def test_initial_states_are_normalized():
    for name in ("zero", "plus"):
        spec = TFIMVQESpec(nqubits=4, depth=1, initial_state=name)
        state = initial_state(spec)
        np.testing.assert_allclose(
            np.asarray(jnp.vdot(state, state)),
            1.0,
            atol=1e-6,
        )


def test_plus_state_tfim_energy_at_zero_parameters():
    spec = TFIMVQESpec(nqubits=4, depth=1, initial_state="plus")
    theta = jnp.zeros(spec.parameter_shape)
    energy = unrolled_energy(theta, spec)
    np.testing.assert_allclose(np.asarray(energy), -4.0, atol=1e-6)


def test_padding_rzz_parameter_has_zero_gradient():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    theta = (
        jnp.arange(np.prod(spec.parameter_shape), dtype=jnp.float32).reshape(
            spec.parameter_shape
        )
        / 20
    )
    gradient = jax.grad(lambda value: unrolled_energy(value, spec))(theta)
    np.testing.assert_array_equal(
        np.asarray(gradient[:, 0, -1]),
        np.zeros(spec.depth),
    )


def test_gradient_matches_central_difference():
    with jax.enable_x64():
        spec = TFIMVQESpec(nqubits=3, depth=2, dtype="complex128")
        theta = jnp.linspace(
            -0.2,
            0.3,
            np.prod(spec.parameter_shape),
            dtype=jnp.float64,
        ).reshape(spec.parameter_shape)
        gradient = jax.grad(lambda value: unrolled_energy(value, spec))(theta)
        index = (1, 1, 2)
        step = 1e-5
        delta = jnp.zeros_like(theta).at[index].set(step)
        finite_difference = (
            unrolled_energy(theta + delta, spec)
            - unrolled_energy(theta - delta, spec)
        ) / (2 * step)
        np.testing.assert_allclose(
            np.asarray(gradient[index]),
            np.asarray(finite_difference),
            rtol=1e-6,
            atol=1e-7,
        )


@pytest.mark.parametrize("angle", [0.0, 1e-6, -0.7, np.pi - 1e-5])
def test_rzz_schmidt_factors_reconstruct_dense_gate(angle):
    value = jnp.asarray(angle, dtype=jnp.float32)
    left, right = rzz_schmidt_factors(value, jnp.complex64)
    reconstructed = jnp.einsum("oia,pja->opij", left, right)
    expected = rzz_matrix(value, jnp.complex64).reshape(2, 2, 2, 2)
    np.testing.assert_allclose(
        np.asarray(reconstructed),
        np.asarray(expected),
        rtol=1e-6,
        atol=1e-6,
    )
    assert left.shape == (2, 2, 2)
    assert right.shape == (2, 2, 2)


def test_rzz_schmidt_factors_support_complex128():
    with jax.enable_x64():
        value = jnp.asarray(0.37, dtype=jnp.float64)
        left, right = rzz_schmidt_factors(value, jnp.complex128)
        reconstructed = jnp.einsum("oia,pja->opij", left, right)
        expected = rzz_matrix(value, jnp.complex128).reshape(2, 2, 2, 2)
        np.testing.assert_allclose(
            np.asarray(reconstructed),
            np.asarray(expected),
            rtol=1e-12,
            atol=1e-12,
        )
