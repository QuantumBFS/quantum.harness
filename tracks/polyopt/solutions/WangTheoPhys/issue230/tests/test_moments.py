import math

import pytest

from xxzcert.moments import solve_moment_relaxation


def test_ti_moment_relaxation_is_below_xxx_exact():
    candidate = solve_moment_relaxation(1.0, radius=2)
    assert candidate.raw_lower <= 0.25 - math.log(2) + 1e-7
    assert candidate.min_moment_eigenvalue > -1e-6


def test_stationarity_never_weakens_lower_bound():
    base = solve_moment_relaxation(1.0, radius=3, max_weight=1)
    enhanced = solve_moment_relaxation(
        1.0, radius=3, stationarity_radius=1, max_weight=1
    )
    assert enhanced.raw_lower >= base.raw_lower - 1e-7
    assert enhanced.raw_lower <= 0.25 - math.log(2) + 1e-6


def test_ground_optimality_psd_never_weakens_lower_bound():
    base = solve_moment_relaxation(1.0, radius=2)
    enhanced = solve_moment_relaxation(
        1.0, radius=2, optimality_radius=1
    )
    assert enhanced.raw_lower >= base.raw_lower - 1e-7
    assert enhanced.raw_lower <= 0.25 - math.log(2) + 1e-6


def test_moment_problem_reports_compression_metadata():
    candidate = solve_moment_relaxation(0.0, radius=2)
    assert candidate.moment_dimension == 16
    assert candidate.variable_count > 0


def test_invalid_radius_rejected():
    with pytest.raises(ValueError):
        solve_moment_relaxation(1.0, radius=1)
