import numpy as np
from fractions import Fraction

from xxzcert.lti_su2 import (
    lift_su2_dual_to_u1,
    solve_su2_lti,
    su2_multiplicity_bases,
)
from xxzcert.lti_u1 import solve_u1_lti
from xxzcert.lti_u1_rational import (
    make_u1_lti_dual_witness,
    verify_u1_lti_dual_witness,
)


def test_su2_bases_are_orthonormal_and_complete():
    sites = 6
    twice_js, bases = su2_multiplicity_bases(sites)
    dimensions = []
    for twice_j, sectors in zip(twice_js, bases, strict=True):
        available = [basis for basis in sectors if basis is not None]
        dimensions.append(available[0].shape[1])
        for basis in available:
            assert np.allclose(basis.T @ basis, np.eye(basis.shape[1]))
        assert len(available) == twice_j + 1
    assert sum((twice_j + 1) * multiplicity for twice_j, multiplicity in zip(twice_js, dimensions, strict=True)) == 2**sites


def test_su2_lti_matches_u1_small_level():
    ordinary = solve_u1_lti(1.0, 5)
    symmetric = solve_su2_lti(
        5,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    assert abs(ordinary.raw_lower - symmetric.raw_lower) < 2e-6
    assert symmetric.max_equality_residual < 1e-6


def test_su2_lti_matches_u1_at_next_nontrivial_level():
    ordinary = solve_u1_lti(1.0, 7)
    symmetric = solve_su2_lti(
        7,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    assert abs(ordinary.raw_lower - symmetric.raw_lower) < 3e-6


def test_su2_dual_lifts_to_exactly_verifiable_u1_witness():
    symmetric = solve_su2_lti(
        5,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    lifted = lift_su2_dual_to_u1(symmetric)
    witness = make_u1_lti_dual_witness(
        Fraction(1), lifted, scale=10**8
    )
    assert verify_u1_lti_dual_witness(Fraction(1), witness)
    assert float(witness.energy_density_lower) <= symmetric.raw_lower
    assert symmetric.raw_lower - float(witness.energy_density_lower) < 1e-5
