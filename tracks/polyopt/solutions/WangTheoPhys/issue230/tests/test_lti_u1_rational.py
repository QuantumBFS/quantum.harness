from fractions import Fraction

from xxzcert.lti_u1 import solve_u1_lti
from xxzcert.lti_u1_rational import (
    make_u1_lti_dual_witness,
    verify_u1_lti_dual_witness,
)


def test_u1_lti_dual_is_exactly_repaired():
    candidate = solve_u1_lti(1.0, 5)
    witness = make_u1_lti_dual_witness(Fraction(1), candidate)
    assert verify_u1_lti_dual_witness(Fraction(1), witness)
    assert float(witness.energy_density_lower) <= candidate.raw_lower
    assert candidate.raw_lower - float(witness.energy_density_lower) < 1e-5


def test_u1_lti_dual_tampering_is_rejected():
    candidate = solve_u1_lti(1.0, 4)
    witness = make_u1_lti_dual_witness(Fraction(1), candidate)
    broken = type(witness)(
        **{**witness.__dict__, "y_numerator": witness.y_numerator - 100}
    )
    assert not verify_u1_lti_dual_witness(Fraction(1), broken)
