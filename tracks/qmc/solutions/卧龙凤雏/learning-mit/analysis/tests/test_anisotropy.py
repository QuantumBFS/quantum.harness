import numpy as np
import pytest

from analysis.anisotropy import calibrate_alpha, fit_spatial_dimension


def test_spatial_power_law_and_temporal_gap_recover_alpha():
    expected_delta = 0.37
    expected_alpha = 1.25
    correlations = {}
    lyapunov = {}
    for width in (16, 24, 32):
        distance = np.arange(2, width // 2, dtype=float)
        chord = width / np.pi * np.sin(np.pi * distance / width)
        values = 0.8 * chord ** (-2 * expected_delta)
        correlations[width] = [
            np.column_stack([distance, values * (1 + shift)])
            for shift in (-0.002, 0.0, 0.002)
        ]
        gap = expected_alpha * 2 * np.pi * expected_delta / width
        lyapunov[width] = [
            np.array([0.5 + gap / 2, 0.5 - gap / 2, -0.5])
            for _ in range(4)
        ]

    spatial = fit_spatial_dimension(correlations, (16, 24, 32), (1 / 8, 3 / 8))
    alpha = calibrate_alpha(spatial, lyapunov, (None, None))
    assert spatial.delta == pytest.approx(expected_delta, abs=1e-8)
    assert alpha.alpha == pytest.approx(expected_alpha, abs=1e-8)
    assert alpha.alpha > 0
