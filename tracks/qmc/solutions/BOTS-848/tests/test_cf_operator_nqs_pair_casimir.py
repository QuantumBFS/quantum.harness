from __future__ import annotations

import math

import numpy as np
import pytest

import scalable_v1.routes.cf_operator_nqs.pair_casimir as pair_casimir_module
from scalable_v1.routes.cf_operator_nqs.pair_casimir import (
    pair_casimir_decomposition,
)
from scalable_v1.routes.cf_operator_nqs.projected_density import (
    projected_density_tensor,
)


def _direct_pair_fixture(
    two_q: int, ell: int
) -> tuple[complex, np.ndarray, np.ndarray]:
    dimension = two_q + 1
    j = 0.5 * two_q
    jz = np.diag(np.arange(dimension, dtype=float) - j).astype(np.complex128)
    jplus = np.zeros((dimension, dimension), dtype=np.complex128)
    for orbital in range(two_q):
        jplus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    jminus = jplus.T.conj()
    pair_dot = (
        np.kron(jz, jz)
        + 0.5 * np.kron(jplus, jminus)
        + 0.5 * np.kron(jminus, jplus)
    )
    tensors = {
        m: projected_density_tensor(two_q=two_q, ell=ell, m=m)
        for m in range(-ell, ell + 1)
    }
    self_matrix = sum(
        ((-1) ** m) * tensors[m] @ tensors[-m]
        for m in range(-ell, ell + 1)
    )
    cross = sum(
        ((-1) ** m)
        * (
            np.kron(tensors[m], tensors[-m])
            + np.kron(tensors[-m], tensors[m])
        )
        for m in range(-ell, ell + 1)
    )
    return complex(np.trace(self_matrix) / dimension), cross, pair_dot


@pytest.mark.parametrize(
    ("two_q", "ell"),
    ((3, 2), (9, 2), (15, 3), (15, 4), (21, 2), (21, 3), (21, 4)),
)
def test_pair_casimir_reconstructs_projected_density_scalar(
    two_q: int, ell: int
) -> None:
    decomposition = pair_casimir_decomposition(two_q=two_q, ell=ell)
    expected_self, expected_cross, pair_dot = _direct_pair_fixture(two_q, ell)

    np.testing.assert_allclose(
        decomposition.self_scalar,
        expected_self,
        rtol=0.0,
        atol=1.0e-11,
    )
    reconstructed = decomposition.evaluate_matrix(pair_dot)
    residual = np.linalg.norm(reconstructed - expected_cross) / np.linalg.norm(
        expected_cross
    )
    assert residual <= 1.0e-10
    assert decomposition.reconstruction_residual <= 1.0e-10
    assert decomposition.degree == ell
    assert decomposition.scale > 0.0


def test_pair_casimir_coefficients_are_cached_and_immutable() -> None:
    first = pair_casimir_decomposition(two_q=15, ell=4)
    second = pair_casimir_decomposition(two_q=np.int64(15), ell=np.int32(4))

    assert first is second
    assert not first.coefficients.flags.writeable
    with pytest.raises(ValueError):
        first.coefficients[0] = 0.0


def test_pair_casimir_scalar_evaluation_matches_one_dimensional_matrix() -> None:
    decomposition = pair_casimir_decomposition(two_q=3, ell=2)
    x = -1.25

    scalar = decomposition.evaluate_scalar(x)
    matrix = decomposition.evaluate_matrix(np.asarray([[x]], dtype=np.complex128))

    np.testing.assert_allclose(matrix[0, 0], scalar, rtol=0.0, atol=1.0e-15)


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    (
        ({"two_q": True, "ell": 2}, TypeError, "two_q"),
        ({"two_q": 3.0, "ell": 2}, TypeError, "two_q"),
        ({"two_q": 0, "ell": 2}, ValueError, "flux"),
        ({"two_q": 3, "ell": True}, TypeError, "ell"),
        ({"two_q": 3, "ell": 1}, ValueError, "rank"),
        ({"two_q": 3, "ell": 4}, ValueError, "rank"),
    ),
)
def test_pair_casimir_rejects_invalid_inputs(
    kwargs: dict[str, object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        pair_casimir_decomposition(**kwargs)  # type: ignore[arg-type]


def test_pair_casimir_rejects_fit_above_residual_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def zero_fit(
        design: np.ndarray,
        target: np.ndarray,
        *,
        rcond: object,
    ) -> tuple[np.ndarray, np.ndarray, int, np.ndarray]:
        del target, rcond
        return (
            np.zeros(design.shape[1], dtype=np.complex128),
            np.empty(0, dtype=float),
            design.shape[1],
            np.ones(design.shape[1], dtype=float),
        )

    monkeypatch.setattr(pair_casimir_module.np.linalg, "lstsq", zero_fit)

    with pytest.raises(ValueError, match="reconstruction failed"):
        pair_casimir_decomposition(two_q=5, ell=2)
