import jax
import jax.numpy as jnp
import numpy as np
import pytest

from challenge15.monopole import (
    north_lll_orbitals,
    normalized_spinors,
    raw_north_lll_polynomials,
    rotate_spinors,
    south_lll_orbitals,
)
from challenge15.spec import SphereSpec


def _expected_transition_from_overlap(spinors, two_q):
    overlap = spinors[..., 0] * np.conjugate(spinors[..., 1])
    spinor_phase = np.where(
        np.abs(overlap) > 1e-15,
        overlap / np.abs(overlap),
        np.ones_like(overlap),
    )
    return spinor_phase**two_q


def test_lll_orbitals_are_normalized_by_sphere_quadrature():
    spec = SphereSpec(4)
    x, wx = np.polynomial.legendre.leggauss(80)
    phi = np.linspace(0.0, 2.0 * np.pi, 161, endpoint=False)
    theta = np.arccos(x)
    spinors = normalized_spinors(theta[:, None], phi[None, :])
    values = north_lll_orbitals(spinors, spec)
    norms = np.einsum("x,xpm,xpm->m", wx, values.conj(), values)
    norms *= 2.0 * np.pi / phi.size
    np.testing.assert_allclose(norms, np.ones(spec.orbital_count), atol=2e-12)


def test_chart_change_matches_exp_i_two_q_phi_for_north_chart_points():
    spec = SphereSpec(4)
    phi = np.array([0.2, 0.7, -1.1])
    spinors = normalized_spinors(np.array([0.4, 1.1, 2.2]), phi)
    north = north_lll_orbitals(spinors, spec)
    south, phase = south_lll_orbitals(spinors, spec, return_transition=True)
    expected = np.exp(1j * spec.two_q * phi)
    np.testing.assert_allclose(phase, expected, atol=1e-13)
    np.testing.assert_allclose(south, phase[:, None] * north, atol=1e-13)


def test_chart_transition_uses_gauge_invariant_overlap_after_su2_rotation():
    spec = SphereSpec(4)
    spinors = normalized_spinors(np.array([0.6, 1.2]), np.array([0.4, -0.9]))
    a = 0.7 * np.exp(0.3j)
    b = np.sqrt(1.0 - 0.7**2) * np.exp(-0.4j)
    raw_rotation = 2.5 * np.array(
        [
            [a, -np.conjugate(b)],
            [b, np.conjugate(a)],
        ],
        dtype=np.complex128,
    )
    rotated = rotate_spinors(spinors, raw_rotation)
    _, phase = south_lll_orbitals(rotated, spec, return_transition=True)
    expected = _expected_transition_from_overlap(np.asarray(rotated), spec.two_q)
    np.testing.assert_allclose(phase, expected, atol=1e-13)


def test_chart_transition_is_invariant_under_nonunit_complex_spinor_scaling():
    spec = SphereSpec(4)
    spinors = np.asarray(
        normalized_spinors(np.array([0.6, 1.2]), np.array([0.4, -0.9]))
    )
    scales = np.asarray([1.7 - 0.2j, -0.4 + 1.3j])
    south, transition = south_lll_orbitals(spinors, spec, return_transition=True)
    scaled_south, scaled_transition = south_lll_orbitals(
        scales[:, None] * spinors, spec, return_transition=True
    )
    np.testing.assert_allclose(scaled_transition, transition, atol=1e-13)
    gauge_scales = scales / np.abs(scales)
    np.testing.assert_allclose(
        scaled_south,
        gauge_scales[:, None] ** spec.two_q * south,
        rtol=5e-13,
        atol=5e-13,
    )


def test_chart_transition_uses_unit_phase_outside_overlap_at_poles():
    spec = SphereSpec(4)
    spinors = normalized_spinors(np.array([0.0, np.pi]), np.array([0.3, -0.8]))
    _, phase = south_lll_orbitals(spinors, spec, return_transition=True)
    np.testing.assert_allclose(phase, np.ones(2, dtype=np.complex128), atol=1e-13)


def test_rotate_spinors_normalizes_su2_matrix_and_preserves_spinor_norm():
    spinors = normalized_spinors(np.array([0.4, 1.2]), np.array([0.3, -0.5]))
    raw_rotation = 3.0 * np.array(
        [
            [np.exp(0.2j), 0.0],
            [0.0, np.exp(-0.2j)],
        ],
        dtype=np.complex128,
    )
    rotated = rotate_spinors(spinors, raw_rotation)
    np.testing.assert_allclose(np.sum(np.abs(rotated) ** 2, axis=-1), 1.0, atol=1e-13)


def test_lll_orbitals_preserve_nonunit_holomorphic_homogeneity():
    spec = SphereSpec(4)
    spinors = np.asarray(
        normalized_spinors(np.array([0.5, 1.3]), np.array([0.2, -0.8]))
    )
    scale = 1.4 - 0.35j
    reference = raw_north_lll_polynomials(spinors, spec)
    scaled = raw_north_lll_polynomials(scale * spinors, spec)
    np.testing.assert_allclose(
        scaled,
        scale**spec.two_q * reference,
        rtol=3e-13,
        atol=3e-13,
    )


def test_lll_orbital_jvp_is_complex_linear_without_conjugate_dependence():
    spec = SphereSpec(3)
    spinor = jnp.asarray([0.8 + 0.2j, -0.4 + 0.7j], dtype=jnp.complex128)
    tangent = jnp.asarray([0.3 - 0.1j, 0.2 + 0.5j], dtype=jnp.complex128)
    evaluate = lambda z: raw_north_lll_polynomials(z, spec)
    real_direction = jax.jvp(evaluate, (spinor,), (tangent,))[1]
    imaginary_direction = jax.jvp(evaluate, (spinor,), (1j * tangent,))[1]
    np.testing.assert_allclose(
        imaginary_direction,
        1j * real_direction,
        rtol=3e-13,
        atol=3e-13,
    )


def test_orbital_evaluation_rejects_zero_spinors_without_normalizing_nonzero_inputs():
    with pytest.raises(ValueError, match="nonzero"):
        raw_north_lll_polynomials(np.zeros((2,), dtype=np.complex128), SphereSpec(3))


def test_public_lll_orbitals_normalize_nonzero_supplied_spinors():
    spec = SphereSpec(4)
    spinors = np.asarray(
        normalized_spinors(np.array([0.5, 1.3]), np.array([0.2, -0.8]))
    )
    scales = np.asarray([2.4, 0.3])
    np.testing.assert_allclose(
        north_lll_orbitals(scales[:, None] * spinors, spec),
        north_lll_orbitals(spinors, spec),
        rtol=3e-13,
        atol=3e-13,
    )


def test_rotate_spinors_still_normalizes_physical_input_points():
    raw_spinors = 2.7 * np.asarray(
        normalized_spinors(np.array([0.4, 1.1]), np.array([0.2, -0.5]))
    )
    rotated = rotate_spinors(raw_spinors, np.eye(2, dtype=np.complex128))
    np.testing.assert_allclose(np.sum(np.abs(rotated) ** 2, axis=-1), 1.0, atol=1e-13)
