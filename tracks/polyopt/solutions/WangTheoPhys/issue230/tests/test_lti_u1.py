import math

from xxzcert.lti import solve_lti
from xxzcert.lti_u1 import sector_basis, solve_u1_lti


def test_sector_basis_partitions_hilbert_space():
    assert sum(len(sector_basis(6, ones)) for ones in range(7)) == 64


def test_u1_lti_matches_dense_small_level():
    dense = solve_lti(1.0, 4)
    blocked = solve_u1_lti(1.0, 4)
    assert abs(dense.raw_lower - blocked.raw_lower) < 2e-7
    assert blocked.raw_lower <= 0.25 - math.log(2) + 1e-7
    assert blocked.max_equality_residual < 1e-7
    assert blocked.minimum_primal_eigenvalue > -1e-7
