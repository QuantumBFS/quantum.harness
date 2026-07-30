import itertools

import jax
import jax.numpy as jnp
import numpy as np
import pytest

import challenge15
from challenge15.pfaffian import bordered_pfaffian, pfaffian

jax.config.update("jax_enable_x64", True)


def test_pfaffian_interfaces_are_exported_from_package():
    assert challenge15.pfaffian is pfaffian
    assert challenge15.bordered_pfaffian is bordered_pfaffian


def _recursive_pfaffian(matrix):
    matrix = np.asarray(matrix)
    if matrix.shape == (0, 0):
        return np.array(1.0, dtype=matrix.dtype)
    return sum(
        (-1) ** (column + 1)
        * matrix[0, column]
        * _recursive_pfaffian(
            np.delete(np.delete(matrix, (0, column), axis=0), (0, column), axis=1)
        )
        for column in range(1, matrix.shape[0])
    )


@pytest.mark.parametrize("size", range(0, 11, 2))
def test_pfaffian_matches_independent_recursive_oracle(size):
    rng = np.random.default_rng(100 + size)
    for _ in range(3):
        raw = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
        matrix = raw - raw.T
        np.testing.assert_allclose(
            np.asarray(pfaffian(jnp.asarray(matrix))),
            _recursive_pfaffian(matrix),
            rtol=3e-12,
            atol=3e-12,
        )


def test_pfaffian_squared_equals_determinant():
    rng = np.random.default_rng(4)
    raw = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
    matrix = raw - raw.T
    value = np.asarray(pfaffian(jnp.asarray(matrix)))
    np.testing.assert_allclose(value * value, np.linalg.det(matrix), rtol=2e-11)


def test_simultaneous_row_column_permutation_has_permutation_sign():
    rng = np.random.default_rng(21)
    raw = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
    matrix = raw - raw.T
    reference = pfaffian(jnp.asarray(matrix))
    for permutation in ((1, 0, 2, 3, 4, 5, 6, 7), (7, 0, 6, 1, 5, 2, 4, 3)):
        inversions = sum(
            permutation[i] > permutation[j]
            for i, j in itertools.combinations(range(len(permutation)), 2)
        )
        permuted = matrix[np.ix_(permutation, permutation)]
        np.testing.assert_allclose(
            pfaffian(jnp.asarray(permuted)),
            (-1) ** inversions * reference,
            rtol=2e-12,
            atol=2e-12,
        )


def test_log_pfaffian_gradient_matches_finite_difference():
    matrix = jnp.asarray(
        [
            [0, 2 + 1j, 3, 0],
            [-2 - 1j, 0, 0, 4],
            [-3, 0, 0, 5j],
            [0, -4, -5j, 0],
        ],
        dtype=jnp.complex128,
    )
    tangent = jnp.asarray(
        [[0, 1 + 0.3j, 0, 0], [-1 - 0.3j, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
        dtype=jnp.complex128,
    )
    automatic = jax.jvp(lambda x: jnp.log(pfaffian(x)), (matrix,), (tangent,))[1]
    eps = 1e-6
    finite = (
        jnp.log(pfaffian(matrix + eps * tangent))
        - jnp.log(pfaffian(matrix - eps * tangent))
    ) / (2 * eps)
    np.testing.assert_allclose(automatic, finite, rtol=2e-7, atol=2e-8)


def test_complex_jvp_uses_holomorphic_pfaffian_differential():
    matrix = jnp.asarray(
        [[0, 1 + 2j, 3, 4j], [-1 - 2j, 0, 5, 6], [-3, -5, 0, 7j], [-4j, -6, -7j, 0]],
        dtype=jnp.complex128,
    )
    tangent = 1j * matrix
    value, derivative = jax.jvp(pfaffian, (matrix,), (tangent,))
    np.testing.assert_allclose(derivative, 2j * value, rtol=2e-12, atol=2e-12)


@pytest.mark.parametrize(
    "matrix,message",
    [
        (jnp.zeros((2, 3)), "square"),
        (jnp.zeros((3, 3)), "even"),
        (jnp.asarray([[0.0, 1.0], [-1.0 + 2e-12, 0.0]]), "skew"),
    ],
)
def test_pfaffian_rejects_invalid_input(matrix, message):
    with pytest.raises(ValueError, match=message):
        pfaffian(matrix)


def test_compiled_public_pfaffian_rejects_invalid_skew_input():
    invalid = jnp.asarray([[0.0, 1.0], [-1.0 + 2e-12, 0.0]])
    compiled = jax.jit(pfaffian)
    with pytest.raises(Exception, match="skew-symmetric"):
        compiled(invalid)


def test_compiled_public_pfaffian_accepts_valid_input():
    matrix = jnp.asarray([[0.0, 2.0 + 3.0j], [-2.0 - 3.0j, 0.0]])
    np.testing.assert_allclose(jax.jit(pfaffian)(matrix), 2.0 + 3.0j)


def test_rank_two_pfaffian_jvp_handles_empty_minor_indices():
    matrix = jnp.asarray([[0.0, 2.0], [-2.0, 0.0]], dtype=jnp.float64)
    tangent = jnp.asarray([[0.0, 3.0], [-3.0, 0.0]], dtype=jnp.float64)

    value, derivative = jax.jvp(pfaffian, (matrix,), (tangent,))

    assert value == pytest.approx(2.0)
    assert derivative == pytest.approx(3.0)


def test_exact_singular_value_and_jvp_are_finite():
    matrix = jnp.zeros((4, 4), dtype=jnp.complex128)
    tangent = jnp.asarray(
        [[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1], [0, 0, -1, 0]],
        dtype=jnp.complex128,
    )
    value, derivative = jax.jvp(pfaffian, (matrix,), (tangent,))
    assert value == 0
    assert derivative == 0
    assert jnp.isfinite(derivative)


def test_singular_minor_jvp_matches_finite_difference():
    leading = 2.0 + 3.0j
    matrix = jnp.asarray(
        [[0, leading, 0, 0], [-leading, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
        dtype=jnp.complex128,
    )
    tangent = jnp.asarray(
        [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1], [0, 0, -1, 0]],
        dtype=jnp.complex128,
    )
    value, automatic = jax.jvp(pfaffian, (matrix,), (tangent,))
    eps = 1e-6
    finite = (
        pfaffian(matrix + eps * tangent) - pfaffian(matrix - eps * tangent)
    ) / (2 * eps)
    assert value == 0
    np.testing.assert_allclose(automatic, leading, rtol=2e-12, atol=2e-12)
    np.testing.assert_allclose(automatic, finite, rtol=2e-10, atol=2e-10)


def test_singular_minor_jvp_tracks_every_cofactor_sign():
    leading = 1.7 - 0.4j
    for first, second in itertools.combinations(range(4), 2):
        complement = [index for index in range(4) if index not in (first, second)]
        matrix = np.zeros((4, 4), dtype=np.complex128)
        matrix[complement[0], complement[1]] = leading
        matrix[complement[1], complement[0]] = -leading
        tangent = np.zeros((4, 4), dtype=np.complex128)
        tangent[first, second] = 1.0
        tangent[second, first] = -1.0
        _, derivative = jax.jvp(
            pfaffian,
            (jnp.asarray(matrix),),
            (jnp.asarray(tangent),),
        )
        expected = (-1) ** (first + second + 1) * leading
        np.testing.assert_allclose(derivative, expected, rtol=2e-12, atol=2e-12)


def test_floating_residual_singular_construction_uses_finite_minor_jvp():
    rng = np.random.default_rng(74)
    factor = rng.normal(size=(4, 2)) + 1j * rng.normal(size=(4, 2))
    core = np.asarray([[0, 1 + 0.2j], [-1 - 0.2j, 0]], dtype=np.complex128)
    matrix = factor @ core @ factor.T
    raw_tangent = rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))
    tangent = raw_tangent - raw_tangent.T

    expected = 0.0j
    for first, second in itertools.combinations(range(4), 2):
        retained = [
            index for index in range(4) if index not in (first, second)
        ]
        expected += (
            (-1) ** (first + second + 1)
            * _recursive_pfaffian(matrix[np.ix_(retained, retained)])
            * tangent[first, second]
        )

    value, automatic = jax.jvp(
        pfaffian,
        (jnp.asarray(matrix),),
        (jnp.asarray(tangent),),
    )
    eps = 1e-5
    finite = (
        pfaffian(jnp.asarray(matrix + eps * tangent))
        - pfaffian(jnp.asarray(matrix - eps * tangent))
    ) / (2 * eps)
    assert value != 0
    assert jnp.isfinite(automatic)
    np.testing.assert_allclose(automatic, expected, rtol=2e-11, atol=2e-11)
    np.testing.assert_allclose(automatic, finite, rtol=2e-9, atol=2e-9)


def test_full_rank_widely_separated_blocks_avoid_intermediate_overflow():
    phases = (0.3, -0.7, 0.2, 0.4)
    scales = (
        1e200 * np.exp(1j * phases[0]),
        1e200 * np.exp(1j * phases[1]),
        1e-200 * np.exp(1j * phases[2]),
        1e-200 * np.exp(1j * phases[3]),
    )
    matrix = np.zeros((8, 8), dtype=np.complex128)
    for block, scale in enumerate(scales):
        matrix[2 * block, 2 * block + 1] = scale
        matrix[2 * block + 1, 2 * block] = -scale
    value = pfaffian(jnp.asarray(matrix))
    assert jnp.isfinite(value)
    np.testing.assert_allclose(value, np.exp(1j * sum(phases)), rtol=2e-12, atol=2e-12)


def test_large_dense_rank_deficient_schur_cancellation_stays_finite():
    magnitude = 1e200
    matrix = jnp.asarray(
        [
            [0, magnitude, magnitude, magnitude],
            [-magnitude, 0, magnitude, 2 * magnitude],
            [-magnitude, -magnitude, 0, magnitude],
            [-magnitude, -2 * magnitude, -magnitude, 0],
        ],
        dtype=jnp.complex128,
    )
    tangent = jnp.zeros((4, 4), dtype=jnp.complex128)
    tangent = tangent.at[0, 1].set(1 / magnitude)
    tangent = tangent.at[1, 0].set(-1 / magnitude)

    value, derivative = jax.jvp(pfaffian, (matrix,), (tangent,))

    assert jnp.isfinite(value)
    np.testing.assert_allclose(value, 0.0, atol=1e-12)
    assert jnp.isfinite(derivative)
    np.testing.assert_allclose(derivative, 1.0, rtol=2e-12, atol=2e-12)


def test_bordered_pfaffian_uses_border_as_last_column():
    matrix = jnp.asarray(
        [[0, 2, 3], [-2, 0, 5], [-3, -5, 0]], dtype=jnp.complex128
    )
    border = jnp.asarray([7, 11, 13], dtype=jnp.complex128)
    expected = 2 * 13 - 3 * 11 + 5 * 7
    np.testing.assert_allclose(bordered_pfaffian(matrix, border), expected)
