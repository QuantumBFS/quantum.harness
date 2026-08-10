import math

import numpy as np

from xxzcert.rg_relaxation import (
    alternating_neel_mps,
    dimer_cat_mps,
    mps_flow_maps,
    optimize_uniform_mps,
    solve_rg_lti,
    uniform_mps_energy,
)


def test_mps_flow_compatibility_at_three_sites():
    tensor = alternating_neel_mps()
    w2, left, right = mps_flow_maps(tensor)
    physical = 2
    w3_left = left @ np.kron(np.eye(physical), w2)
    w3_right = right @ np.kron(w2, np.eye(physical))
    assert np.allclose(w3_left, w3_right)


def test_unnormalized_rational_flow_is_exactly_compatible_numerically():
    tensor = np.array(
        [
            [[1, 2], [0, -1]],
            [[2, 0], [1, 1]],
        ],
        dtype=np.complex128,
    )
    w2, left, right = mps_flow_maps(tensor, normalize=False)
    physical = 2
    assert np.array_equal(
        left @ np.kron(np.eye(physical), w2),
        right @ np.kron(w2, np.eye(physical)),
    )


def test_rg_relaxation_is_below_bethe_and_primal_feasible():
    candidate = solve_rg_lti(1.0, alternating_neel_mps(), depth=4)
    assert candidate.raw_lower <= 0.25 - math.log(2) + 1e-6
    assert candidate.max_equality_residual < 1e-6
    assert candidate.minimum_primal_eigenvalue > -1e-6
    assert abs(candidate.dual_objective - candidate.raw_lower) < 1e-5
    assert candidate.dual_stationarity_residual < 1e-5


def test_rg_depth_is_monotone_for_fixed_maps():
    level4 = solve_rg_lti(1.0, alternating_neel_mps(), depth=4)
    level5 = solve_rg_lti(1.0, alternating_neel_mps(), depth=5)
    assert level5.raw_lower >= level4.raw_lower - 1e-6
    assert level5.raw_lower <= 0.25 - math.log(2) + 1e-6


def test_optimized_uniform_mps_improves_neel_energy():
    assert abs(uniform_mps_energy(dimer_cat_mps(), 1.0) + 0.375) < 1e-10
    tensor = optimize_uniform_mps(1.0, bond_dimension=3, restarts=1)
    energy = uniform_mps_energy(tensor, 1.0)
    assert energy <= -0.375 + 1e-8
    assert energy >= 0.25 - math.log(2) - 1e-8
