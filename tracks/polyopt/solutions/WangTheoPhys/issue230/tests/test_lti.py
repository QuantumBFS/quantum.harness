import pytest

from xxzcert.lti import solve_lti


@pytest.fixture(scope="module")
def xxx_values():
    return [solve_lti(1.0, n) for n in (2, 3, 4)]


def test_lti_level_two_is_singlet_bound(xxx_values):
    assert abs(xxx_values[0].raw_lower + 0.75) < 1e-7


def test_lti_small_levels_are_monotone(xxx_values):
    values = [candidate.raw_lower for candidate in xxx_values]
    assert values[0] <= values[1] + 1e-7
    assert values[1] <= values[2] + 1e-7


def test_lti_xxx_values_are_below_exact(xxx_values):
    exact = 0.25 - __import__("math").log(2)
    assert all(candidate.raw_lower <= exact + 1e-7 for candidate in xxx_values)


def test_candidate_residuals_are_small(xxx_values):
    for candidate in xxx_values:
        assert candidate.trace_residual < 1e-7
        assert candidate.lti_residual < 1e-7
        assert candidate.min_eigenvalue > -1e-7


def test_invalid_level_rejected():
    with pytest.raises(ValueError):
        solve_lti(1.0, 1)
