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
    assert alpha.window_relative_spread == pytest.approx(0.0, abs=1e-12)
    assert alpha.stable


def test_anisotropy_rejects_a_window_spread_above_25_percent():
    spatial = fit_spatial_dimension(
        {
            16: [
                np.column_stack(
                    [
                        np.arange(2, 8, dtype=float),
                        np.arange(2, 8, dtype=float) ** -0.8,
                    ]
                )
            ]
        },
        (16,),
        (1 / 8, 3 / 8),
    )
    lyapunov = {
        16: [
            np.array([0.60, 0.40, -0.5]),
            np.array([0.52, 0.48, -0.5]),
            np.array([0.80, 0.20, -0.5]),
        ]
    }
    alpha = calibrate_alpha(spatial, lyapunov, (None, None))
    assert alpha.window_relative_spread > 0.25
    assert not alpha.stable
