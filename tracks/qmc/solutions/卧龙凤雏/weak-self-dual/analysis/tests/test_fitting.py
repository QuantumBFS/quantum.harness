import numpy as np
import pytest

from analysis.fitting import evaluate_fit, fit_gamma


def test_primary_fit_recovers_hand_constructed_central_charge():
    widths = np.arange(6, 32, 2, dtype=float)
    gamma = 0.73 * widths - np.pi * 0.447 / (6.0 * widths) + 1.2 / widths**3
    fit = fit_gamma(widths, gamma, np.full_like(widths, 1e-4), 6, "l3")
    assert fit.central_charge == pytest.approx(0.447, abs=1e-10)
    np.testing.assert_allclose(evaluate_fit(fit, widths), gamma, atol=1e-12)


def test_no_correction_model_recovers_two_parameter_data():
    widths = np.arange(6, 20, 2, dtype=float)
    gamma = 0.6 * widths - np.pi * 0.447 / (6.0 * widths)
    fit = fit_gamma(widths, gamma, np.ones_like(widths), 6, "none")
    assert fit.central_charge == pytest.approx(0.447, abs=1e-11)


def test_fit_rejects_too_few_widths():
    with pytest.raises(ValueError, match="at least three"):
        fit_gamma(
            np.array([6.0, 8.0]),
            np.array([1.0, 2.0]),
            np.ones(2),
            6,
            "l3",
        )
