import numpy as np
import pytest
from fractions import Fraction

from xxzcert.lti_su2_reflection import (
    lift_su2_reflection_dual_to_u1,
    solve_su2_reflection_lti,
    su2_reflection_bases,
)
from xxzcert.lti_u1 import solve_u1_lti
from xxzcert.lti_u1_rational import (
    make_u1_lti_dual_witness,
    verify_u1_lti_dual_witness,
)


def test_joint_bases_diagonalize_reflection():
    twice_js, blocks = su2_reflection_bases(7)
    assert len(twice_js) == len(blocks)
    for block in blocks:
        transform = np.hstack((block.even, block.odd))
        assert np.allclose(
            transform.T @ transform, np.eye(transform.shape[1])
        )
        assert (
            transform.shape[0]
            == block.even.shape[1] + block.odd.shape[1]
        )
        diagonal = transform.T @ block.reflection @ transform
        expected = np.diag(
            np.r_[
                np.ones(block.even.shape[1]),
                -np.ones(block.odd.shape[1]),
            ]
        )
        assert np.allclose(diagonal, expected, atol=1e-9)


@pytest.mark.parametrize("level", [5, 7])
def test_joint_relaxation_matches_u1(level):
    ordinary = solve_u1_lti(1.0, level)
    joint = solve_su2_reflection_lti(
        level,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    assert abs(ordinary.raw_lower - joint.raw_lower) < 4e-6
    assert joint.max_equality_residual < 1e-6
    assert joint.minimum_block_eigenvalue > -1e-5


def test_joint_dual_lifts_to_exact_u1_witness():
    candidate = solve_su2_reflection_lti(
        7,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    lifted = lift_su2_reflection_dual_to_u1(candidate)
    witness = make_u1_lti_dual_witness(
        Fraction(1), lifted, scale=10**8
    )
    assert verify_u1_lti_dual_witness(Fraction(1), witness)
    assert (
        abs(float(witness.energy_density_lower) - candidate.raw_lower)
        < 1e-5
    )
