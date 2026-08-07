from __future__ import annotations

from math import factorial

import numpy as np
import pytest

from src.fcs_time_series import fit_cumulants, validate_fcs_time_series


GAMMA = np.asarray([-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6])


def _logz(cumulants: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            sum((1j * GAMMA) ** n * row[n - 1] / factorial(n) for n in range(1, 7))
            for row in cumulants
        ]
    )


def test_recovers_known_weakly_non_gaussian_cumulants() -> None:
    t = np.arange(4.0)
    truth = np.column_stack(
        [
            0.02 * t,
            0.4 + 0.1 * t,
            0.01 * t,
            0.03 + 0.002 * t,
            np.zeros_like(t),
            np.zeros_like(t),
        ]
    )
    validated = validate_fcs_time_series(
        t,
        GAMMA,
        _logz(truth),
        normalization_tol=1e-12,
        conjugacy_tol=1e-12,
        cumulant_stability_tol=0.05,
    )
    np.testing.assert_allclose(validated.cumulants, truth[:, :4], rtol=1e-10, atol=1e-10)
    assert np.max(np.abs(validated.logz[:, GAMMA == 0.0])) == 0.0
    np.testing.assert_allclose(
        validated.logz[:, GAMMA < 0],
        np.conj(validated.logz[:, GAMMA > 0][:, ::-1]),
        atol=1e-12,
    )


def test_fit_cumulants_handles_gaussian_characteristic_function() -> None:
    t = np.arange(3.0)
    truth = np.column_stack(
        [0.1 * t, 0.5 + t, np.zeros_like(t), np.zeros_like(t)]
    )
    estimated = fit_cumulants(GAMMA, _logz(np.pad(truth, ((0, 0), (0, 2)))), order=4)
    np.testing.assert_allclose(estimated, truth, atol=1e-10)


@pytest.mark.parametrize(
    ("gamma", "message"),
    [
        (np.asarray([-0.6, -0.2, 0.2, 0.4, 0.6, 0.8, 1.0]), "zero"),
        (np.asarray([-0.6, -0.4, -0.2, 0.0, 0.2, 0.5, 0.6]), "symmetric"),
    ],
)
def test_rejects_invalid_gamma_grid(gamma: np.ndarray, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_fcs_time_series(np.arange(2.0), gamma, np.zeros((2, 7), complex))


def test_rejects_conjugacy_violation() -> None:
    values = np.zeros((2, 7), dtype=complex)
    values[:, 0] = 0.2 + 0.1j
    with pytest.raises(ValueError, match="conjugacy"):
        validate_fcs_time_series(np.arange(2.0), GAMMA, values)


def test_rejects_negative_variance() -> None:
    truth = np.zeros((2, 6))
    truth[:, 1] = -0.5
    with pytest.raises(ValueError, match="second cumulant"):
        validate_fcs_time_series(
            np.arange(2.0),
            GAMMA,
            _logz(truth),
            cumulant_stability_tol=0.1,
        )


def test_rejects_unstable_fourth_order_truncation() -> None:
    truth = np.zeros((2, 6))
    truth[:, 1] = 0.5
    truth[:, 5] = 100.0
    with pytest.raises(ValueError, match="unstable"):
        validate_fcs_time_series(
            np.arange(2.0),
            GAMMA,
            _logz(truth),
            cumulant_stability_tol=0.01,
        )
