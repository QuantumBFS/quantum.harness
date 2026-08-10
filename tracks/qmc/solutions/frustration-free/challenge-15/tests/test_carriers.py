import jax
import jax.numpy as jnp
import numpy as np
import pytest

from challenge15.carriers import (
    carrier_amplitudes,
    carrier_determinant_coefficients,
)
from challenge15.fermions import DeterminantBasis
from challenge15.monopole import raw_north_lll_polynomials
from challenge15.spec import SphereSpec


def _random_spinors(particles, seed):
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(particles, 2)) + 1j * rng.normal(size=(particles, 2))
    return spinors / np.linalg.norm(spinors, axis=-1, keepdims=True)


def _weights(spec):
    positive_channels = sum(two_m > 0 for two_m in spec.two_m_values)
    index = np.arange(1, positive_channels + 1)
    return jnp.asarray(index + 0.2j * index[::-1], dtype=jnp.complex128)


@pytest.mark.parametrize("particles", [3, 4, 5, 6])
def test_particle_exchange_negates_carrier(particles):
    spec = SphereSpec(particles)
    spinors = _random_spinors(particles, 10 + particles)
    value = carrier_amplitudes(spinors, spec, _weights(spec), border_weight=1.3 - 0.4j)
    exchanged = spinors.copy()
    exchanged[[0, 2]] = exchanged[[2, 0]]
    exchanged_value = carrier_amplitudes(
        exchanged, spec, _weights(spec), border_weight=1.3 - 0.4j
    )
    np.testing.assert_allclose(exchanged_value, -value, rtol=3e-12, atol=3e-12)


@pytest.mark.parametrize("particles", [3, 4, 5, 6])
def test_each_particle_has_exact_monopole_gauge_degree(particles):
    spec = SphereSpec(particles)
    spinors = _random_spinors(particles, 20 + particles)
    phase = np.exp(0.37j)
    value = carrier_amplitudes(spinors, spec, _weights(spec), border_weight=0.8 + 0.1j)
    transformed = spinors.copy()
    transformed[1] *= phase
    transformed_value = carrier_amplitudes(
        transformed, spec, _weights(spec), border_weight=0.8 + 0.1j
    )
    np.testing.assert_allclose(
        transformed_value,
        phase**spec.two_q * value,
        rtol=4e-12,
        atol=4e-12,
    )


@pytest.mark.parametrize("particles", [3, 4, 5, 6])
def test_each_particle_has_exact_nonunit_holomorphic_degree(particles):
    spec = SphereSpec(particles)
    spinors = _random_spinors(particles, 25 + particles)
    scale = 1.35 - 0.27j
    value = carrier_amplitudes(spinors, spec, _weights(spec), border_weight=0.8 + 0.1j)
    transformed = spinors.copy()
    transformed[1] *= scale
    transformed_value = carrier_amplitudes(
        transformed, spec, _weights(spec), border_weight=0.8 + 0.1j
    )
    np.testing.assert_allclose(
        transformed_value,
        scale**spec.two_q * value,
        rtol=5e-12,
        atol=5e-12,
    )


def test_carrier_spinor_jvp_is_complex_linear_without_conjugate_dependence():
    spec = SphereSpec(4)
    spinors = jnp.asarray(_random_spinors(4, 29))
    tangent = jnp.asarray(_random_spinors(4, 30)) * 0.2
    evaluate = lambda z: carrier_amplitudes(z, spec, _weights(spec))
    real_direction = jax.jvp(evaluate, (spinors,), (tangent,))[1]
    imaginary_direction = jax.jvp(evaluate, (spinors,), (1j * tangent,))[1]
    np.testing.assert_allclose(
        imaginary_direction,
        1j * real_direction,
        rtol=5e-11,
        atol=5e-11,
    )


@pytest.mark.parametrize("particles", [3, 4, 5, 6])
def test_z_axis_rotation_leaves_m_zero_carrier_unchanged(particles):
    spec = SphereSpec(particles)
    spinors = _random_spinors(particles, 30 + particles)
    angle = 0.43
    z_rotation = np.diag([np.exp(0.5j * angle), np.exp(-0.5j * angle)])
    rotated = np.einsum("ab,ib->ia", z_rotation, spinors)
    value = carrier_amplitudes(spinors, spec, _weights(spec), border_weight=1.1)
    rotated_value = carrier_amplitudes(
        rotated, spec, _weights(spec), border_weight=1.1
    )
    np.testing.assert_allclose(rotated_value, value, rtol=4e-12, atol=4e-12)


@pytest.mark.parametrize("particles", [3, 5])
def test_odd_coefficients_use_unique_m_zero_border(particles):
    spec = SphereSpec(particles)
    basis = DeterminantBasis.with_two_m(spec, 0)
    coefficients = np.asarray(
        carrier_determinant_coefficients(
            spec, _weights(spec), border_weight=1.7 - 0.2j
        )
    )
    zero_orbital = spec.two_m_values.index(0)
    for state, coefficient in zip(basis.states, coefficients, strict=True):
        if not state & (1 << zero_orbital):
            assert coefficient == 0
    assert np.any(np.abs(coefficients) > 0)
    zero_border = carrier_determinant_coefficients(
        spec, _weights(spec), border_weight=0.0
    )
    np.testing.assert_array_equal(zero_border, np.zeros_like(zero_border))


@pytest.mark.parametrize("particles", [3, 4, 5, 6])
def test_analytic_determinant_coefficients_match_coordinates(particles):
    spec = SphereSpec(particles)
    spinors = _random_spinors(particles, 40 + particles)
    pair_weights = _weights(spec)
    border_weight = 0.9 - 0.3j
    direct = carrier_amplitudes(
        spinors, spec, pair_weights, border_weight=border_weight
    )

    basis = DeterminantBasis.with_two_m(spec, 0)
    coefficients = np.asarray(
        carrier_determinant_coefficients(
            spec, pair_weights, border_weight=border_weight
        )
    )
    orbitals = np.asarray(raw_north_lll_polynomials(spinors, spec))
    reconstructed = 0.0j
    for state, coefficient in zip(basis.states, coefficients, strict=True):
        occupied = [
            orbital
            for orbital in range(spec.orbital_count)
            if state & (1 << orbital)
        ]
        reconstructed += coefficient * np.linalg.det(orbitals[:, occupied])
    np.testing.assert_allclose(reconstructed, direct, rtol=2e-11, atol=2e-11)


def test_pair_weights_must_cover_each_positive_m_channel():
    spec = SphereSpec(4)
    with pytest.raises(ValueError, match="positive-m channel"):
        carrier_amplitudes(_random_spinors(4, 51), spec, jnp.ones(3))


def test_carrier_bank_matches_independent_single_carriers():
    spec = SphereSpec(3)
    spinors = _random_spinors(3, 61)
    first = _weights(spec)
    weights = jnp.stack((first, (0.4 + 0.2j) * first))
    borders = jnp.asarray([1.1 - 0.3j, -0.7 + 0.5j])

    amplitudes = carrier_amplitudes(
        spinors, spec, weights, border_weight=borders
    )
    expected_amplitudes = jnp.stack(
        [
            carrier_amplitudes(spinors, spec, weight, border_weight=border)
            for weight, border in zip(weights, borders, strict=True)
        ]
    )
    np.testing.assert_allclose(amplitudes, expected_amplitudes)

    coefficients = carrier_determinant_coefficients(
        spec, weights, border_weight=borders
    )
    expected_coefficients = jnp.stack(
        [
            carrier_determinant_coefficients(
                spec, weight, border_weight=border
            )
            for weight, border in zip(weights, borders, strict=True)
        ]
    )
    np.testing.assert_allclose(coefficients, expected_coefficients)


def test_carrier_is_jittable_and_complex_differentiable():
    spec = SphereSpec(4)
    spinors = jnp.asarray(_random_spinors(4, 71))
    weights = _weights(spec)
    eager = carrier_amplitudes(spinors, spec, weights)
    compiled = jax.jit(lambda z, g: carrier_amplitudes(z, spec, g))
    np.testing.assert_allclose(compiled(spinors, weights), eager)
    _, tangent = jax.jvp(
        lambda g: carrier_amplitudes(spinors, spec, g),
        (weights,),
        (1j * weights,),
    )
    np.testing.assert_allclose(tangent, 2j * eager, rtol=2e-12, atol=2e-12)
