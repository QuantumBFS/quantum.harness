from __future__ import annotations

import itertools

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from challenge15.torch_pfaffian import (  # noqa: E402
    bordered_pfaffian,
    pfaffian,
    pfaffian_cofactors,
    pfaffian_elimination,
)


RTOL = 2e-10
ATOL = 2e-11


def _recursive_pfaffian(matrix: np.ndarray) -> np.ndarray:
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


def _recursive_cofactors(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix)
    cofactors = np.zeros_like(matrix)
    for first, second in itertools.combinations(range(matrix.shape[0]), 2):
        retained = [
            index
            for index in range(matrix.shape[0])
            if index not in (first, second)
        ]
        cofactors[first, second] = (
            (-1) ** (first + second + 1)
            * _recursive_pfaffian(matrix[np.ix_(retained, retained)])
        )
    return cofactors


def _recursive_directional_derivative(
    matrix: np.ndarray, tangent: np.ndarray
) -> np.ndarray:
    return np.sum(_recursive_cofactors(matrix) * tangent)


def _skew_fixture(size: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    return np.asarray(raw - raw.T, dtype=np.complex128)


def _cofactor_fixture(
    first: int, second: int, leading: complex
) -> tuple[np.ndarray, np.ndarray]:
    complement = [index for index in range(4) if index not in (first, second)]
    matrix = np.zeros((4, 4), dtype=np.complex128)
    matrix[complement[0], complement[1]] = leading
    matrix[complement[1], complement[0]] = -leading
    tangent = np.zeros((4, 4), dtype=np.complex128)
    tangent[first, second] = 1.0
    tangent[second, first] = -1.0
    return matrix, tangent


def _batched_derivative_fixture() -> tuple[np.ndarray, np.ndarray]:
    matrices = [
        _skew_fixture(4, seed=301),
        np.zeros((4, 4), dtype=np.complex128),
        _cofactor_fixture(2, 3, 1.7 - 0.4j)[0],
        _skew_fixture(4, seed=304),
    ]
    tangents = [_skew_fixture(4, seed=401 + index) for index in range(4)]
    return np.stack(matrices).reshape(2, 2, 4, 4), np.stack(tangents).reshape(
        2, 2, 4, 4
    )


@pytest.mark.parametrize("size", [0, 2, 4, 6, 8])
def test_torch_pfaffian_matches_recursive_oracle(size):
    for sample in range(3):
        matrix = _skew_fixture(size, seed=100 + size + sample)
        actual = pfaffian(torch.tensor(matrix, dtype=torch.complex128))
        np.testing.assert_allclose(
            actual.detach().numpy(),
            _recursive_pfaffian(matrix),
            rtol=RTOL,
            atol=ATOL,
        )


def test_pfaffian_squared_equals_determinant():
    matrix = _skew_fixture(8, seed=4)
    value = pfaffian(torch.tensor(matrix, dtype=torch.complex128))
    np.testing.assert_allclose(
        (value * value).detach().numpy(),
        np.linalg.det(matrix),
        rtol=2e-11,
        atol=ATOL,
    )


def test_simultaneous_row_column_permutation_has_permutation_sign():
    matrix = _skew_fixture(8, seed=21)
    reference = pfaffian(torch.tensor(matrix, dtype=torch.complex128))
    for permutation in ((1, 0, 2, 3, 4, 5, 6, 7), (7, 0, 6, 1, 5, 2, 4, 3)):
        inversions = sum(
            permutation[i] > permutation[j]
            for i, j in itertools.combinations(range(len(permutation)), 2)
        )
        permuted = matrix[np.ix_(permutation, permutation)]
        np.testing.assert_allclose(
            pfaffian(torch.tensor(permuted)).detach().numpy(),
            ((-1) ** inversions * reference).detach().numpy(),
            rtol=RTOL,
            atol=ATOL,
        )


def test_rank_two_pfaffian_and_cofactor_use_empty_minor():
    matrix = torch.tensor([[0, 2 + 3j], [-2 - 3j, 0]], dtype=torch.complex128)
    tangent = torch.tensor([[0, 5 - 1j], [-5 + 1j, 0]], dtype=torch.complex128)

    value, derivative = torch.func.jvp(pfaffian, (matrix,), (tangent,))
    cofactors = pfaffian_cofactors(matrix)

    assert value.item() == pytest.approx(2 + 3j)
    assert derivative.item() == pytest.approx(5 - 1j)
    torch.testing.assert_close(
        cofactors,
        torch.tensor([[0, 1], [0, 0]], dtype=torch.complex128),
        rtol=0,
        atol=0,
    )


def test_exact_singular_value_and_jvp_are_finite():
    matrix = torch.zeros((4, 4), dtype=torch.complex128)
    tangent = torch.tensor(
        [[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1], [0, 0, -1, 0]],
        dtype=torch.complex128,
    )

    value, derivative = torch.func.jvp(pfaffian, (matrix,), (tangent,))

    assert value.item() == 0
    assert derivative.item() == 0
    assert torch.isfinite(derivative)


def test_singular_minor_jvp_uses_all_signed_minors():
    leading = 2.0 + 3.0j
    for first, second in itertools.combinations(range(4), 2):
        matrix, tangent = _cofactor_fixture(first, second, leading)
        _, derivative = torch.func.jvp(
            pfaffian,
            (torch.tensor(matrix, dtype=torch.complex128),),
            (torch.tensor(tangent, dtype=torch.complex128),),
        )
        expected = (-1) ** (first + second + 1) * leading
        np.testing.assert_allclose(
            derivative.detach().numpy(), expected, rtol=RTOL, atol=ATOL
        )


def test_frozen_jax_singular_minor_golden_value_and_jvp():
    matrix, tangent = _cofactor_fixture(2, 3, 2.0 + 3.0j)
    value, derivative = torch.func.jvp(
        pfaffian,
        (torch.tensor(matrix),),
        (torch.tensor(tangent),),
    )

    np.testing.assert_array_equal(value.detach().numpy(), 0.0 + 0.0j)
    np.testing.assert_allclose(
        derivative.detach().numpy(), 2.0 + 3.0j, rtol=2e-12, atol=2e-12
    )


def test_floating_residual_rank_deficiency_uses_finite_minor_jvp():
    rng = np.random.default_rng(74)
    factor = rng.normal(size=(4, 2)) + 1j * rng.normal(size=(4, 2))
    core = np.asarray([[0, 1 + 0.2j], [-1 - 0.2j, 0]], dtype=np.complex128)
    matrix = factor @ core @ factor.T
    raw_tangent = rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))
    tangent = raw_tangent - raw_tangent.T
    expected = sum(
        (-1) ** (first + second + 1)
        * _recursive_pfaffian(
            matrix[
                np.ix_(
                    [
                        index
                        for index in range(4)
                        if index not in (first, second)
                    ],
                    [
                        index
                        for index in range(4)
                        if index not in (first, second)
                    ],
                )
            ]
        )
        * tangent[first, second]
        for first, second in itertools.combinations(range(4), 2)
    )

    value, derivative = torch.func.jvp(
        pfaffian,
        (torch.tensor(matrix),),
        (torch.tensor(tangent),),
    )

    assert value.item() != 0
    assert torch.isfinite(derivative)
    np.testing.assert_allclose(
        derivative.detach().numpy(), expected, rtol=2e-11, atol=2e-11
    )


def test_complex_jvp_uses_holomorphic_pfaffian_differential():
    matrix = torch.tensor(_skew_fixture(6, seed=55))
    value, derivative = torch.func.jvp(pfaffian, (matrix,), (1j * matrix,))
    torch.testing.assert_close(derivative, 3j * value, rtol=RTOL, atol=ATOL)


def test_backward_uses_conjugate_all_minor_jacobian_for_real_and_imaginary_parts():
    matrix_array = _skew_fixture(6, seed=81)
    matrix = torch.tensor(matrix_array, requires_grad=True)
    expected = torch.tensor(_recursive_cofactors(matrix_array).conj())

    real_gradient = torch.autograd.grad(pfaffian(matrix).real, matrix)[0]
    imaginary_gradient = torch.autograd.grad(pfaffian(matrix).imag, matrix)[0]

    torch.testing.assert_close(real_gradient, expected, rtol=RTOL, atol=ATOL)
    torch.testing.assert_close(
        imaginary_gradient, 1j * expected, rtol=RTOL, atol=ATOL
    )


def test_batched_reverse_mode_matches_independent_recursive_minors():
    matrix_array, _ = _batched_derivative_fixture()
    matrix = torch.tensor(matrix_array, requires_grad=True)
    expected = np.stack(
        [
            _recursive_cofactors(item).conj()
            for item in matrix_array.reshape(-1, 4, 4)
        ]
    ).reshape(matrix_array.shape)

    gradient = torch.autograd.grad(pfaffian(matrix).real.sum(), matrix)[0]

    np.testing.assert_allclose(
        gradient.detach().numpy(), expected, rtol=RTOL, atol=ATOL
    )
    assert np.count_nonzero(expected[0, 1]) == 0
    assert np.count_nonzero(expected[1, 0]) == 1


def test_batched_torch_func_jvp_matches_independent_recursive_polynomial():
    matrix_array, tangent_array = _batched_derivative_fixture()
    expected = np.asarray(
        [
            _recursive_directional_derivative(matrix, tangent)
            for matrix, tangent in zip(
                matrix_array.reshape(-1, 4, 4),
                tangent_array.reshape(-1, 4, 4),
                strict=True,
            )
        ]
    ).reshape(matrix_array.shape[:-2])

    _, derivative = torch.func.jvp(
        pfaffian,
        (torch.tensor(matrix_array),),
        (torch.tensor(tangent_array),),
    )

    np.testing.assert_allclose(
        derivative.detach().numpy(), expected, rtol=RTOL, atol=ATOL
    )
    assert expected[0, 1] == 0
    assert expected[1, 0] != 0


def test_singular_backward_uses_nonzero_minor():
    matrix_array, _ = _cofactor_fixture(2, 3, 1.7 - 0.4j)
    matrix = torch.tensor(matrix_array, requires_grad=True)

    gradient = torch.autograd.grad(pfaffian(matrix).real, matrix)[0]

    assert pfaffian(matrix).item() == 0
    assert gradient[2, 3].item() == pytest.approx((1.7 - 0.4j).conjugate())
    assert torch.count_nonzero(gradient).item() == 1


def test_pfaffian_second_derivative_is_explicitly_unsupported():
    matrix = torch.tensor(_skew_fixture(4, seed=91), requires_grad=True)
    first = torch.autograd.grad(pfaffian(matrix).real, matrix, create_graph=True)[0]

    with pytest.raises(RuntimeError, match="once_differentiable"):
        torch.autograd.grad(first.real.sum(), matrix)


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

    value = pfaffian(torch.tensor(matrix))

    assert torch.isfinite(value)
    np.testing.assert_allclose(
        value.detach().numpy(), np.exp(1j * sum(phases)), rtol=2e-12, atol=2e-12
    )


def test_large_dense_rank_deficient_schur_cancellation_stays_finite():
    magnitude = 1e200
    matrix = torch.tensor(
        [
            [0, magnitude, magnitude, magnitude],
            [-magnitude, 0, magnitude, 2 * magnitude],
            [-magnitude, -magnitude, 0, magnitude],
            [-magnitude, -2 * magnitude, -magnitude, 0],
        ],
        dtype=torch.complex128,
    )
    tangent = torch.zeros((4, 4), dtype=torch.complex128)
    tangent[0, 1] = 1 / magnitude
    tangent[1, 0] = -1 / magnitude

    value, derivative = torch.func.jvp(pfaffian, (matrix,), (tangent,))

    assert torch.isfinite(value)
    np.testing.assert_allclose(value.detach().numpy(), 0.0, atol=1e-12)
    assert torch.isfinite(derivative)
    np.testing.assert_allclose(
        derivative.detach().numpy(), 1.0, rtol=2e-12, atol=2e-12
    )


def test_pfaffian_cofactors_store_only_strict_upper_triangle():
    matrix = torch.tensor(_skew_fixture(6, seed=15))
    cofactors = pfaffian_cofactors(matrix)

    torch.testing.assert_close(
        torch.tril(cofactors), torch.zeros_like(cofactors), rtol=0, atol=0
    )
    for first, second in itertools.combinations(range(6), 2):
        retained = [index for index in range(6) if index not in (first, second)]
        expected = (-1) ** (first + second + 1) * _recursive_pfaffian(
            matrix.detach().numpy()[np.ix_(retained, retained)]
        )
        np.testing.assert_allclose(
            cofactors[first, second].detach().numpy(),
            expected,
            rtol=RTOL,
            atol=ATOL,
        )


def test_bordered_pfaffian_uses_border_as_last_column():
    matrix = torch.tensor(
        [[0, 2, 3], [-2, 0, 5], [-3, -5, 0]], dtype=torch.complex128
    )
    border = torch.tensor([7, 11, 13], dtype=torch.complex128)

    value = bordered_pfaffian(matrix, border)

    np.testing.assert_allclose(value.detach().numpy(), 2 * 13 - 3 * 11 + 5 * 7)


def test_elimination_cofactors_pfaffian_and_border_support_leading_batch_axes():
    matrices = np.stack([_skew_fixture(4, seed=120 + index) for index in range(6)])
    matrices = matrices.reshape(2, 3, 4, 4)
    tensor = torch.tensor(matrices)
    expected = np.asarray(
        [_recursive_pfaffian(matrix) for matrix in matrices.reshape(-1, 4, 4)]
    ).reshape(2, 3)

    torch.testing.assert_close(
        pfaffian_elimination(tensor),
        torch.tensor(expected),
        rtol=RTOL,
        atol=ATOL,
    )
    torch.testing.assert_close(
        pfaffian(tensor), torch.tensor(expected), rtol=RTOL, atol=ATOL
    )
    assert pfaffian_cofactors(tensor).shape == (2, 3, 4, 4)

    odd = tensor[..., :3, :3]
    border = tensor[..., :3, 3]
    augmented = torch.cat(
        (
            torch.cat((odd, border[..., None]), dim=-1),
            torch.cat(
                (
                    -border[..., None, :],
                    torch.zeros((2, 3, 1, 1), dtype=torch.complex128),
                ),
                dim=-1,
            ),
        ),
        dim=-2,
    )
    torch.testing.assert_close(
        bordered_pfaffian(odd, border),
        pfaffian(augmented),
        rtol=RTOL,
        atol=ATOL,
    )


@pytest.mark.parametrize(
    ("matrix", "message"),
    [
        (torch.zeros((2, 3), dtype=torch.complex128), "square"),
        (torch.zeros((3, 3), dtype=torch.complex128), "even"),
        (torch.zeros((2, 2), dtype=torch.complex64), "complex128"),
        (
            torch.tensor(
                [[0, 1], [-1 + 2e-12, 0]], dtype=torch.complex128
            ),
            "skew",
        ),
    ],
)
def test_pfaffian_rejects_invalid_public_input(matrix, message):
    with pytest.raises((TypeError, ValueError), match=message):
        pfaffian(matrix)


def test_public_skew_tolerance_is_exactly_one_e_minus_twelve():
    accepted = torch.tensor(
        [[0, 1], [-1 + 1e-12, 0]], dtype=torch.complex128
    )
    rejected = torch.tensor(
        [[0, 1], [-1 + 1.0001e-12, 0]], dtype=torch.complex128
    )

    pfaffian(accepted)
    with pytest.raises(ValueError, match="1e-12"):
        pfaffian(rejected)


@pytest.mark.parametrize("function", [pfaffian_elimination, pfaffian_cofactors])
@pytest.mark.parametrize(
    ("matrix", "message"),
    [
        (np.zeros((2, 2), dtype=np.complex128), "Tensor"),
        (torch.zeros((2, 3), dtype=torch.complex128), "square"),
        (torch.zeros((3, 3), dtype=torch.complex128), "even"),
        (torch.zeros((2, 2), dtype=torch.complex64), "complex128"),
        (
            torch.tensor([[0, 1], [-1 + 2e-12, 0]], dtype=torch.complex128),
            "skew",
        ),
    ],
)
def test_public_elimination_and_cofactors_reject_invalid_input(
    function, matrix, message
):
    with pytest.raises((TypeError, ValueError), match=message):
        function(matrix)


@pytest.mark.parametrize("function", [pfaffian_elimination, pfaffian_cofactors])
def test_public_elimination_and_cofactors_use_exact_skew_tolerance(function):
    accepted = torch.tensor(
        [[0, 1], [-1 + 1e-12, 0]], dtype=torch.complex128
    )
    rejected = torch.tensor(
        [[0, 1], [-1 + 1.0001e-12, 0]], dtype=torch.complex128
    )

    function(accepted)
    with pytest.raises(ValueError, match="1e-12"):
        function(rejected)


@pytest.mark.parametrize(
    ("matrix", "border", "message"),
    [
        (
            torch.zeros((2, 2), dtype=torch.complex128),
            torch.zeros((2,), dtype=torch.complex128),
            "odd",
        ),
        (
            torch.zeros((3, 3), dtype=torch.complex128),
            torch.zeros((2,), dtype=torch.complex128),
            "one entry",
        ),
        (
            torch.zeros((2, 3, 3), dtype=torch.complex128),
            torch.zeros((3,), dtype=torch.complex128),
            "leading batch",
        ),
        (
            torch.zeros((3, 3), dtype=torch.complex128),
            torch.zeros((3,), dtype=torch.complex64),
            "complex128",
        ),
    ],
)
def test_bordered_pfaffian_rejects_invalid_public_input(matrix, border, message):
    with pytest.raises((TypeError, ValueError), match=message):
        bordered_pfaffian(matrix, border)


def test_public_pfaffians_require_tensor_inputs():
    with pytest.raises(TypeError, match="Tensor"):
        pfaffian(np.zeros((2, 2), dtype=np.complex128))
    with pytest.raises(TypeError, match="Tensor"):
        bordered_pfaffian(
            np.zeros((3, 3), dtype=np.complex128),
            np.zeros((3,), dtype=np.complex128),
        )
