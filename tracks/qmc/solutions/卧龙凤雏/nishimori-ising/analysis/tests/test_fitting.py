import numpy as np
import pytest

from analysis.fitting import fit_free_energy


def test_three_term_finite_size_fit_recovers_known_central_charge():
    widths = np.array([4, 6, 8, 10, 12, 14], dtype=float)
    phi_infinity = 1.337
    central_charge = 0.464
    correction = -0.73
    phi = (
        phi_infinity
        + np.pi * central_charge / (6.0 * widths**2)
        + correction / widths**4
    )

    fit = fit_free_energy(widths, phi, minimum_width=4)
    assert fit.phi_infinity == pytest.approx(phi_infinity, abs=1.0e-12)
    assert fit.central_charge == pytest.approx(central_charge, abs=1.0e-12)
    assert fit.l4_amplitude == pytest.approx(correction, abs=1.0e-11)
    assert fit.residual_rms < 1.0e-13


def test_fit_requires_three_distinct_widths():
    with pytest.raises(ValueError, match="at least three"):
        fit_free_energy(
            np.array([4.0, 6.0]),
            np.array([1.0, 1.0]),
            minimum_width=4,
        )
