import jax
import jax.numpy as jnp
import numpy as np

from vqetape.ansatz import (
    apply_ansatz_generator,
    fixed_rzz_rx_structure,
    local_operator_pool,
    ordered_ansatz_energy,
    ordered_ansatz_state,
)
from vqetape.ansatz_signals import candidate_signal, pool_signals
from vqetape.spec import TFIMVQESpec


def _state_and_parameters():
    spec = TFIMVQESpec(
        nqubits=3,
        depth=1,
        dtype="complex128",
    )
    structure = fixed_rzz_rx_structure(3, 1)
    parameters = jnp.asarray(
        [0.21, -0.13, 0.08, -0.19, 0.17],
        dtype=jnp.float64,
    )
    state = ordered_ansatz_state(
        parameters,
        structure,
        spec,
    )
    return spec, structure, parameters, state


def test_candidate_gradient_matches_appended_autodiff():
    with jax.enable_x64():
        spec, structure, parameters, state = (
            _state_and_parameters()
        )
        for operator in local_operator_pool(3):
            signal = candidate_signal(
                state,
                operator,
                spec,
            )
            extended = structure.append(operator)

            def inserted_energy(angle):
                values = jnp.concatenate(
                    (parameters, jnp.asarray([angle]))
                )
                return ordered_ansatz_energy(
                    values,
                    extended,
                    spec,
                )

            automatic = jax.grad(inserted_energy)(
                jnp.asarray(0.0, dtype=jnp.float64)
            )
            step = 1e-5
            finite = (
                inserted_energy(step)
                - inserted_energy(-step)
            ) / (2 * step)
            np.testing.assert_allclose(
                signal.gradient,
                automatic,
                rtol=1e-10,
                atol=1e-11,
            )
            np.testing.assert_allclose(
                signal.gradient,
                finite,
                rtol=1e-7,
                atol=1e-9,
            )


def test_candidate_metric_matches_state_jacobian():
    with jax.enable_x64():
        spec, structure, parameters, state = (
            _state_and_parameters()
        )
        for operator in local_operator_pool(3):
            signal = candidate_signal(
                state,
                operator,
                spec,
            )
            extended = structure.append(operator)

            def inserted_state(angle):
                return ordered_ansatz_state(
                    jnp.concatenate(
                        (
                            parameters,
                            jnp.asarray([angle]),
                        )
                    ),
                    extended,
                    spec,
                )

            derivative = jax.jacfwd(inserted_state)(
                jnp.asarray(0.0, dtype=jnp.float64)
            )
            expected = jnp.real(
                jnp.vdot(derivative, derivative)
                - jnp.vdot(derivative, state)
                * jnp.vdot(state, derivative)
            )
            np.testing.assert_allclose(
                signal.metric,
                expected,
                rtol=1e-10,
                atol=1e-11,
            )


def test_pool_signals_preserve_full_pool_order():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    state = jnp.asarray(
        np.ones(8) / np.sqrt(8),
        dtype=jnp.complex64,
    )
    pool = local_operator_pool(3)
    signals = pool_signals(state, pool, spec)

    assert tuple(item.operator for item in signals) == pool
    assert all(item.normalized_signal >= 0 for item in signals)


def test_pauli_generators_are_involutions():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    state = jnp.asarray(
        np.arange(8) + 1j * np.arange(8)[::-1],
        dtype=jnp.complex64,
    )
    for operator in local_operator_pool(3):
        twice = apply_ansatz_generator(
            apply_ansatz_generator(
                state,
                operator,
                spec,
            ),
            operator,
            spec,
        )
        np.testing.assert_array_equal(twice, state)
