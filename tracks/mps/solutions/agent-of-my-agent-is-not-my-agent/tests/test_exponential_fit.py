import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lrtfim.couplings import periodic_couplings
from lrtfim.exponential_fit import (
    fit_power_law,
    periodized_exponential_couplings,
    power_law_values,
)


def test_fit_is_deterministic_and_has_valid_decays():
    first = fit_power_law(sigma=1.75, num_exponentials=8, r_fit=128)
    second = fit_power_law(sigma=1.75, num_exponentials=8, r_fit=128)

    np.testing.assert_array_equal(first.lambdas, second.lambdas)
    np.testing.assert_array_equal(first.coefficients, second.coefficients)
    assert np.all(first.lambdas > 0.0)
    assert np.all(first.lambdas < 1.0)
    assert np.all(np.diff(first.lambdas) < 0.0)


def test_fit_metrics_are_relative_kernel_errors():
    fit = fit_power_law(sigma=1.75, num_exponentials=8, r_fit=128)
    distances = np.arange(1, 129)
    exact = power_law_values(distances, sigma=1.75)
    reconstructed = fit.evaluate(distances)
    relative = np.abs(reconstructed - exact) / exact

    assert fit.max_relative_error == pytest.approx(np.max(relative))
    assert fit.rms_relative_error == pytest.approx(
        np.sqrt(np.mean(relative**2))
    )


def test_correlation_length_bound_is_enforced_deterministically():
    alpha = 0.5
    r_fit = 128
    first = fit_power_law(
        sigma=1.75,
        num_exponentials=8,
        r_fit=r_fit,
        min_rate_scale=alpha,
    )
    second = fit_power_law(
        sigma=1.75,
        num_exponentials=8,
        r_fit=r_fit,
        min_rate_scale=alpha,
    )
    rates = -np.log(first.lambdas)

    assert np.min(rates) * r_fit >= alpha * (1.0 - 1.0e-12)
    np.testing.assert_array_equal(first.lambdas, second.lambdas)
    np.testing.assert_array_equal(first.coefficients, second.coefficients)


@pytest.mark.parametrize("alpha", [0.0, -0.5, np.inf])
def test_fit_rejects_invalid_min_rate_scale(alpha):
    with pytest.raises(ValueError):
        fit_power_law(
            sigma=1.75,
            num_exponentials=8,
            r_fit=128,
            min_rate_scale=alpha,
        )


def test_periodization_matches_the_analytical_formula_and_is_symmetric():
    fit = fit_power_law(sigma=1.75, num_exponentials=8, r_fit=128)
    length = 32
    values = periodized_exponential_couplings(length, fit)
    r = 7
    expected = np.sum(
        fit.coefficients
        * (fit.lambdas**r + fit.lambdas ** (length - r))
        / (1.0 - fit.lambdas**length)
    )

    assert values[r - 1] == pytest.approx(expected)
    np.testing.assert_allclose(values, values[::-1], rtol=2e-14, atol=2e-14)


def test_fitted_kernel_error_decreases_across_requested_k_values():
    errors = []
    for k in (8, 12, 16):
        fit = fit_power_law(sigma=1.75, num_exponentials=k, r_fit=256)
        errors.append(fit.rms_relative_error)

    assert errors[1] < errors[0]
    assert errors[2] < errors[1]


@pytest.mark.parametrize(
    ("sigma", "num_exponentials", "r_fit"),
    [(0.0, 8, 128), (1.75, 0, 128), (1.75, 8, 0)],
)
def test_fit_rejects_invalid_parameters(sigma, num_exponentials, r_fit):
    with pytest.raises(ValueError):
        fit_power_law(
            sigma=sigma,
            num_exponentials=num_exponentials,
            r_fit=r_fit,
        )
