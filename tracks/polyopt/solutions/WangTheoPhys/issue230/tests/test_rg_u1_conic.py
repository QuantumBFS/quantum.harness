import pytest

from xxzcert.rg_relaxation import alternating_neel_mps, solve_rg_lti
from xxzcert.rg_u1_conic import solve_rg_u1_conic


@pytest.mark.parametrize("depth", [4, 5])
def test_u1_conic_matches_unreduced_rg_relaxation(depth):
    tensor = alternating_neel_mps()
    dense = solve_rg_lti(1.0, tensor, depth=depth)
    blocked = solve_rg_u1_conic(1.0, tensor, depth=depth)
    assert blocked.raw_lower == pytest.approx(dense.raw_lower, abs=2e-6)
    assert min(blocked.dual_slack_min_eigenvalues) > -2e-7
    assert blocked.bond_dimension == 2


def test_u1_conic_can_reserve_strict_slack_margin():
    tensor = alternating_neel_mps()
    baseline = solve_rg_u1_conic(1.0, tensor, depth=4)
    strict = solve_rg_u1_conic(
        1.0, tensor, depth=4, slack_margin=1e-5
    )
    assert min(strict.dual_slack_min_eigenvalues) > 9e-6
    assert strict.raw_lower <= baseline.raw_lower + 1e-8


@pytest.mark.parametrize("depth", [4, 5])
def test_native_sector_model_matches_legacy_full_expressions(depth):
    tensor = alternating_neel_mps()
    native = solve_rg_u1_conic(
        1.0, tensor, depth=depth, native_blocks=True
    )
    legacy = solve_rg_u1_conic(
        1.0, tensor, depth=depth, native_blocks=False
    )
    assert native.raw_lower == pytest.approx(
        legacy.raw_lower, abs=2e-7
    )
    assert len(native.equality_duals) == len(legacy.equality_duals)
