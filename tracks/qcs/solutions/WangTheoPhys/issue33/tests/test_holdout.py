import jax
import jax.numpy as jnp
import numpy as np

from vqetape.holdout import (
    LongitudinalIsingSpec,
    dense_longitudinal_hamiltonian,
    global_x_commutator_norm,
    holdout_z2_applicability,
    longitudinal_ansatz_state,
    longitudinal_energy,
    longitudinal_ground_energy,
    longitudinal_hamiltonian_action,
)


def test_holdout_state_is_normalized_and_padding_is_inactive():
    with jax.enable_x64():
        spec = LongitudinalIsingSpec(
            nqubits=4,
            depth=2,
        )
        parameters = jnp.linspace(
            -0.2,
            0.3,
            np.prod(spec.parameter_shape),
        ).reshape(spec.parameter_shape)
        state = longitudinal_ansatz_state(parameters, spec)
        gradient = jax.grad(
            lambda values: longitudinal_energy(
                values,
                spec,
            )
        )(parameters)

        np.testing.assert_allclose(
            jnp.vdot(state, state),
            1.0,
            atol=1e-12,
        )
        np.testing.assert_array_equal(
            gradient[:, 0, -1],
            np.zeros(spec.depth),
        )


def test_action_and_energy_match_dense_hamiltonian():
    with jax.enable_x64():
        spec = LongitudinalIsingSpec(
            nqubits=3,
            depth=1,
        )
        parameters = jnp.asarray(
            np.linspace(-0.2, 0.25, 9).reshape(1, 3, 3)
        )
        state = longitudinal_ansatz_state(parameters, spec)
        dense = dense_longitudinal_hamiltonian(spec)

        np.testing.assert_allclose(
            longitudinal_hamiltonian_action(
                state,
                spec,
            ),
            dense @ np.asarray(state),
            rtol=1e-12,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            longitudinal_energy(parameters, spec),
            np.vdot(state, dense @ np.asarray(state)).real,
            rtol=1e-12,
            atol=1e-12,
        )
        assert longitudinal_ground_energy(spec) == np.min(
            np.linalg.eigvalsh(dense)
        )


def test_holdout_gradient_matches_central_difference():
    with jax.enable_x64():
        spec = LongitudinalIsingSpec(
            nqubits=3,
            depth=1,
        )
        parameters = jnp.asarray(
            np.linspace(-0.3, 0.2, 9).reshape(1, 3, 3)
        )
        gradient = jax.grad(
            lambda values: longitudinal_energy(
                values,
                spec,
            )
        )(parameters)
        index = (0, 1, 1)
        delta = jnp.zeros_like(parameters).at[index].set(
            1e-5
        )
        finite = (
            longitudinal_energy(parameters + delta, spec)
            - longitudinal_energy(parameters - delta, spec)
        ) / 2e-5

        np.testing.assert_allclose(
            gradient[index],
            finite,
            rtol=1e-8,
            atol=1e-9,
        )


def test_longitudinal_field_breaks_global_x_charge():
    broken = LongitudinalIsingSpec(
        nqubits=4,
        depth=1,
        longitudinal_field=0.35,
    )
    tfim = LongitudinalIsingSpec(
        nqubits=4,
        depth=1,
        longitudinal_field=0.0,
    )

    assert global_x_commutator_norm(broken) > 1
    np.testing.assert_allclose(
        global_x_commutator_norm(tfim),
        0.0,
        atol=1e-12,
    )
    applicability = holdout_z2_applicability(broken)
    assert not applicability["applicable"]
    assert any(
        "longitudinal" in reason
        for reason in applicability["reasons"]
    )
