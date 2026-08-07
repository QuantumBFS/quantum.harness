from __future__ import annotations

import numpy as np
import pytest
from scipy.linalg import expm


def _random_u_pq_generator(
    rng: np.random.Generator,
    *,
    p: int,
    q: int,
) -> np.ndarray:
    size = p + q
    raw = (
        rng.standard_normal((size, size))
        + 1j * rng.standard_normal((size, size))
    ) / np.sqrt(2.0 * size)
    antihermitian = 0.5 * (raw - raw.conj().T)
    eta = np.diag([1.0] * p + [-1.0] * q)
    return eta @ antihermitian


@pytest.mark.parametrize("n", [1, 2, 3])
def test_u_nn_product_obeys_exact_phase_identity(n: int) -> None:
    rng = np.random.default_rng(1000 + n)
    size = 2 * n
    eta = np.diag([1.0] * n + [-1.0] * n)
    product = np.eye(size, dtype=complex)

    for _ in range(7):
        generator = _random_u_pq_generator(rng, p=n, q=n)
        product = product @ expm(generator)

    weight = np.linalg.det(np.eye(size) + product)
    determinant = np.linalg.det(product)

    assert np.allclose(
        product.conj().T @ eta @ product,
        eta,
        rtol=1e-10,
        atol=1e-10,
    )
    assert abs(weight) > 1e-10
    assert np.allclose(
        weight.conjugate(),
        weight / determinant,
        rtol=1e-10,
        atol=1e-10,
    )


def test_u_11_central_phase_sweeps_the_circle() -> None:
    for angle in [-2.4, -0.7, 0.3, 1.8]:
        matrix = np.exp(1j * angle) * np.eye(2)
        weight = np.linalg.det(np.eye(2) + matrix)
        expected = np.exp(1j * angle) * (
            2.0 * np.cos(angle / 2.0)
        ) ** 2

        assert np.allclose(weight, expected, rtol=1e-12, atol=1e-12)
