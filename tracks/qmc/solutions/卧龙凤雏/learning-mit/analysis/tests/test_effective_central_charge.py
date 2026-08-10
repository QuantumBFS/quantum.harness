import numpy as np
import pytest

from analysis.effective_central_charge import (
    chord_log,
    extrapolate_c_eff,
    fit_width_c_eff,
)


def _synthetic_width_rows(width: int, c_eff: float) -> np.ndarray:
    intervals = np.arange(1, width, dtype=float)
    x = np.log((width / np.pi) * np.sin(np.pi * intervals / width))
    entropy = (
        0.3
        + (c_eff / 3.0) * x
        + (0.4 / width**2) * np.cos(2.0 * np.pi * intervals / width)
    )
    return np.column_stack(
        [intervals, np.full_like(intervals, width), entropy, np.full_like(intervals, 0.01)]
    )


def test_chord_log_and_two_stage_fit_recover_known_effective_central_charge():
    assert np.allclose(
        chord_log(np.array([2.0]), 8.0),
        np.log((8.0 / np.pi) * np.sin(np.pi * 2.0 / 8.0)),
    )
    by_width = {}
    for width in (8, 12, 16, 20, 24, 28, 32):
        finite_size_value = 0.72 + 0.8 / width**2
        estimate, covariance, _ = fit_width_c_eff(
            _synthetic_width_rows(width, finite_size_value)
        )
        assert estimate == pytest.approx(finite_size_value, abs=2e-8)
        by_width[width] = (estimate, max(float(covariance[1, 1]) ** 0.5, 1e-6))

    fit = extrapolate_c_eff(0.22, by_width, {"log": 0.8, "constant": 0.2})
    assert fit.extrapolated == pytest.approx(0.72, abs=2e-3)
    assert fit.stable_without_smallest
    assert fit.model_weights == {"log": 0.8, "constant": 0.2}
    assert fit.interval[0] <= fit.extrapolated <= fit.interval[1]


@pytest.mark.parametrize(
    "rows, message",
    [
        (
            np.array(
                [
                    [2.0, 8.0, np.nan, 0.1],
                    [3.0, 8.0, 0.2, 0.1],
                    [4.0, 8.0, 0.2, 0.1],
                    [5.0, 8.0, 0.2, 0.1],
                ]
            ),
            "finite",
        ),
        (
            np.array(
                [
                    [2.0, 8.0, 0.2, 0.0],
                    [3.0, 8.0, 0.2, 0.1],
                    [4.0, 8.0, 0.2, 0.1],
                    [5.0, 8.0, 0.2, 0.1],
                ]
            ),
            "uncertainties",
        ),
        (
            np.array(
                [
                    [2.0, 8.0, 0.2, 0.1],
                    [3.0, 8.0, 0.2, 0.1],
                    [4.0, 9.0, 0.3, 0.1],
                    [5.0, 9.0, 0.3, 0.1],
                ]
            ),
            "one width",
        ),
    ],
)
def test_width_fit_rejects_invalid_rows(rows, message):
    with pytest.raises(ValueError, match=message):
        fit_width_c_eff(rows)


def test_extrapolation_requires_four_distinct_finite_widths():
    with pytest.raises(ValueError, match="at least four"):
        extrapolate_c_eff(
            0.22,
            {8: (0.5, 0.1), 12: (0.6, 0.1), 16: (0.7, 0.1)},
            {"log": 1.0},
        )
    with pytest.raises(ValueError, match="finite"):
        extrapolate_c_eff(
            0.22,
            {8: (0.5, 0.1), 12: (0.6, 0.1), 16: (0.7, 0.1), 20: (np.nan, 0.1)},
            {"log": 1.0},
        )


def test_extrapolation_rejects_an_unidentifiable_size_window():
    nearly_equal_large_widths = {
        1_000_000 + offset: (0.7, 0.01) for offset in range(4)
    }
    with pytest.raises(ValueError, match="condition"):
        extrapolate_c_eff(0.22, nearly_equal_large_widths, {"log": 1.0})
