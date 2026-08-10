import numpy as np
import pytest

from analysis.casimir import fit_casimir


def test_casimir_recovers_amplitude_with_l3_correction():
    widths = np.array([8, 12, 16, 20, 24, 28, 32], dtype=float)
    expected = 0.41
    gamma = (
        0.73 * widths
        - np.pi * expected / (6 * widths)
        + 1.2 / widths**3
    )
    fit = fit_casimir(
        widths, gamma, np.eye(len(widths)) * 1e-10, 8, "l3"
    )
    assert fit.casimir_amplitude == pytest.approx(expected, abs=1e-8)
    assert fit.bulk_density == pytest.approx(0.73, abs=1e-10)
    assert fit.covariance_condition <= 1.0e10
    assert fit.stable_without_smallest


def test_casimir_requires_five_widths_and_known_correction():
    widths = np.array([8, 12, 16, 20], dtype=float)
    with pytest.raises(ValueError, match="five widths"):
        fit_casimir(widths, widths, np.eye(4), 8, "none")
    with pytest.raises(ValueError, match="correction"):
        fit_casimir(
            np.array([8, 12, 16, 20, 24], dtype=float),
            np.ones(5),
            np.eye(5),
            8,
            "mystery",
        )
