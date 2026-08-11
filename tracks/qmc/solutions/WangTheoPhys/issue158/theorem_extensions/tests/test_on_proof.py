import math

import numpy as np
import pytest

from issue158.on_proof import (
    pair_plane_projection,
    pair_second_variation_exact,
    pair_second_variation_formula,
    rotate_in_plane,
    rotation_generator_matrix,
    transverse_parseval_sides,
)


def _unit_vector(rng: np.random.Generator, n: int) -> np.ndarray:
    vector = rng.normal(size=n)
    return vector / np.linalg.norm(vector)


def test_rotation_generator_requires_a_transverse_channel():
    with pytest.raises(ValueError, match="n >= 2"):
        rotation_generator_matrix(1, 0)
    with pytest.raises(ValueError, match="zero-based"):
        rotation_generator_matrix(3, 0)
    with pytest.raises(ValueError, match="zero-based"):
        rotation_generator_matrix(3, 3)


@pytest.mark.parametrize("n", [2, 3, 4, 8])
def test_rotation_generator_is_antisymmetric_and_tangent(n):
    rng = np.random.default_rng(158 + n)
    spin = _unit_vector(rng, n)
    for transverse in range(1, n):
        generator = rotation_generator_matrix(n, transverse)
        assert np.allclose(generator.T, -generator, atol=0.0)
        derivative = generator @ spin
        assert math.isclose(
            float(np.dot(spin, derivative)),
            0.0,
            abs_tol=2e-15,
        )
        assert derivative[0] == -spin[transverse]
        assert derivative[transverse] == spin[0]


@pytest.mark.parametrize("n", [2, 3, 4, 8])
def test_exact_pair_second_variation_matches_projection_formula(n):
    rng = np.random.default_rng(2026 + n)
    for _ in range(32):
        first = _unit_vector(rng, n)
        second = _unit_vector(rng, n)
        transverse = int(rng.integers(1, n))
        u = np.exp(1j * float(rng.uniform(-math.pi, math.pi)))
        v = np.exp(1j * float(rng.uniform(-math.pi, math.pi)))
        coupling = float(rng.uniform(0.01, 3.0))
        exact = pair_second_variation_exact(
            first, second, u, v, transverse, coupling
        )
        formula = pair_second_variation_formula(
            first, second, u, v, transverse, coupling
        )
        assert math.isclose(exact, formula, rel_tol=3e-14, abs_tol=3e-14)


def test_projected_pair_is_bounded_above_but_can_be_negative():
    first = np.array([1.0, 0.0, 0.0])
    second = np.array([-1.0, 0.0, 0.0])
    assert pair_plane_projection(first, second, 1) == -1.0
    rng = np.random.default_rng(230)
    for n in (2, 3, 7):
        for _ in range(128):
            s = _unit_vector(rng, n)
            t = _unit_vector(rng, n)
            for transverse in range(1, n):
                assert pair_plane_projection(s, t, transverse) <= 1.0 + 1e-15


def test_plane_rotation_preserves_norm_and_has_correct_derivative():
    spin = np.array([0.3, -0.4, math.sqrt(0.75)])
    epsilon = 1e-7
    rotated = rotate_in_plane(spin, epsilon, 2)
    derivative = (rotated - spin) / epsilon
    assert math.isclose(
        float(np.dot(rotated, rotated)),
        float(np.dot(spin, spin)),
        rel_tol=2e-15,
    )
    assert np.allclose(
        derivative[[0, 2]],
        np.array([-spin[2], spin[0]]),
        rtol=0.0,
        atol=7e-8,
    )


@pytest.mark.parametrize("n", [2, 3, 4, 8])
def test_transverse_parseval_budget_and_xy_reduction(n):
    rng = np.random.default_rng(1580 + n)
    raw = rng.normal(size=(5, 4, n))
    spins = raw / np.linalg.norm(raw, axis=-1, keepdims=True)
    fourier, real = transverse_parseval_sides(spins)
    assert math.isclose(fourier, real, rel_tol=3e-15)
    volume = 20
    expected = volume * float(np.sum(1.0 - spins[..., 0] ** 2))
    assert math.isclose(real, expected, rel_tol=3e-15)
    assert real <= volume**2 + 2e-13
    if n == 2:
        xy_budget = volume * float(np.sum(spins[..., 1] ** 2))
        assert math.isclose(real, xy_budget, rel_tol=3e-15)
