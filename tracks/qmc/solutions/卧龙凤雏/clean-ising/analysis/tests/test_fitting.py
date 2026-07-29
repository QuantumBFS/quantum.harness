import numpy as np
import pytest

from analysis.fitting import fit_c


def test_fit_recovers_half_central_charge():
    widths = np.array([4, 6, 8, 10, 12, 16], dtype=float)
    f_infinity = -0.9296953983
    central_charge = 0.5
    correction = 0.07
    per_site = (
        f_infinity
        - np.pi * central_charge / (6.0 * widths**2)
        + correction / widths**4
    )
    result = fit_c(widths, per_site * widths, l_min=6)
    assert result.c == pytest.approx(0.5, abs=1.0e-11)
    assert result.widths == (6, 8, 10, 12, 16)


def test_fit_rejects_a_window_with_fewer_than_four_widths():
    widths = np.array([4, 6, 8, 10, 12, 16], dtype=float)
    with pytest.raises(ValueError, match="four widths"):
        fit_c(widths, np.ones_like(widths), l_min=10)
