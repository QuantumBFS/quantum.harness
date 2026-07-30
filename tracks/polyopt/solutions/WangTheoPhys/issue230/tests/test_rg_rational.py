from fractions import Fraction

import numpy as np

from xxzcert.rg_rational import (
    make_rg_dual_barrier_witness,
    make_rg_u1_conic_witness,
    make_rg_dual_witness,
    reconstruct_rg_dual_slacks,
    verify_rg_dual_witness,
)
from xxzcert.rg_relaxation import alternating_neel_mps, dimer_cat_mps


def test_exact_rg_dual_repair_for_neel_flow():
    witness, candidate = make_rg_dual_witness(
        Fraction(1), alternating_neel_mps(), depth=4, dual_scale=10**6
    )
    assert verify_rg_dual_witness(Fraction(1), witness)
    assert witness.energy_density_lower <= Fraction.from_float(candidate.raw_lower)
    assert len(reconstruct_rg_dual_slacks(Fraction(1), witness)) == 2


def test_rg_witness_tampering_is_rejected():
    witness, _ = make_rg_dual_witness(
        Fraction(1), alternating_neel_mps(), depth=4, dual_scale=10**6
    )
    broken = type(witness)(
        **{
            **witness.__dict__,
            "y_numerator": witness.y_numerator - 100,
        }
    )
    assert not verify_rg_dual_witness(Fraction(1), broken)


def test_exact_rg_dual_supports_bond_dimension_three():
    witness, candidate = make_rg_dual_witness(
        Fraction(1),
        dimer_cat_mps(),
        depth=4,
        tensor_scale=10**4,
        dual_scale=10**7,
    )
    assert witness.bond_dimension == 3
    assert verify_rg_dual_witness(Fraction(1), witness)
    assert (
        witness.energy_density_lower
        <= Fraction.from_float(candidate.raw_lower)
    )


def test_matrix_free_rg_dual_is_exactly_repaired():
    witness, candidate = make_rg_dual_barrier_witness(
        Fraction(1),
        alternating_neel_mps(),
        depth=4,
        tensor_scale=10**4,
        dual_scale=10**7,
        use_symmetry=True,
    )
    assert verify_rg_dual_witness(Fraction(1), witness)
    assert (
        abs(
            candidate.raw_lower
            - float(witness.energy_density_lower)
        )
        < 2e-4
    )


def test_u1_conic_rg_dual_is_exactly_repaired():
    witness, candidate = make_rg_u1_conic_witness(
        Fraction(1),
        alternating_neel_mps(),
        depth=4,
        tensor_scale=10**4,
        dual_scale=10**7,
    )
    assert verify_rg_dual_witness(Fraction(1), witness)
    assert witness.energy_density_lower <= Fraction.from_float(
        candidate.raw_lower
    )
