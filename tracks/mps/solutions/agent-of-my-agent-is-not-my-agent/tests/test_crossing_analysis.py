import numpy as np
import pytest

from lrtfim.crossing_analysis import (
    crossing_chi_status,
    fit_crossing_drift,
    linear_crossing,
)


def test_linear_crossing_uses_neighboring_points():
    gamma = np.array([1.55, 1.56, 1.57])
    crossing = linear_crossing(
        gamma,
        np.array([0.48, 0.50, 0.52]),
        np.array([0.51, 0.50, 0.49]),
    )
    assert crossing.gamma == pytest.approx(1.56)
    assert crossing.left_index == 0
    assert crossing.right_index == 1
    assert crossing.fraction == pytest.approx(1.0)


def test_crossing_outside_window_is_explicit():
    with pytest.raises(ValueError, match="window_extension_required"):
        linear_crossing(
            np.array([1.55, 1.56, 1.57]),
            np.array([0.4, 0.41, 0.42]),
            np.array([0.5, 0.51, 0.52]),
        )


def test_primary_drift_and_chi_rules():
    lengths = np.array([32.0, 64.0, 128.0])
    values = 1.56 + 0.8 / lengths
    fit = fit_crossing_drift(lengths, values, form="power")
    assert fit.intercept == pytest.approx(1.56)
    assert fit.form == "power"

    converged = crossing_chi_status({128: 1.5605, 256: 1.5602, 384: 1.5601})
    assert converged.converged
    assert converged.next_chi is None
    unresolved = crossing_chi_status({128: 1.5610, 256: 1.5605, 384: 1.5601})
    assert not unresolved.converged
    assert unresolved.next_chi == 512
