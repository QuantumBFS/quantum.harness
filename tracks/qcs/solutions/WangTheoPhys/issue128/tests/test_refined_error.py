from fractions import Fraction
from itertools import product

import pytest

from trottercert.algebra import (
    PauliString,
    PauliSum,
    commutator,
    pauli_strings_commute,
)
from trottercert.hamiltonian import heisenberg_bond
from trottercert.refined_error import (
    HEISENBERG_BOND_PAULI_L1_GROWTH,
    defect_tail_site_bound,
)
from trottercert.rigorous_fourth import fourth_order_suzuki_interval_stages


def test_defect_tail_decreases_with_steps() -> None:
    stages, _ = fourth_order_suzuki_interval_stages(4, decimal_digits=8)
    assert defect_tail_site_bound(stages, 200) < defect_tail_site_bound(stages, 100)


def test_heisenberg_bond_pauli_l1_growth_constant_is_exact() -> None:
    bond_axes = tuple(
        PauliString({0: axis, 1: axis})
        for axis in ("X", "Y", "Z")
    )
    observed = []
    anticommuting_counts = []
    for left, right in product(("I", "X", "Y", "Z"), repeat=2):
        pauli = PauliString({0: left, 1: right})
        anticommuting_counts.append(
            sum(
                not pauli_strings_commute(axis, pauli)
                for axis in bond_axes
            )
        )
        operator = PauliSum.term(pauli, Fraction(1))
        observed.append(
            commutator(
                heisenberg_bond(0, 1),
                operator,
            ).exact_axis_l1()
        )
    assert set(anticommuting_counts) <= {0, 2}
    assert max(observed) == HEISENBERG_BOND_PAULI_L1_GROWTH == 1


@pytest.mark.slow
def test_refined_bound_crosses_global_twofold_target() -> None:
    from trottercert.refined_error import (
        build_refined_fourth_order_constants,
        evaluate_refined_fourth_order_bound,
    )

    constants = build_refined_fourth_order_constants()
    bound = evaluate_refined_fourth_order_bound(constants, 144, 116)
    previous = evaluate_refined_fourth_order_bound(constants, 144, 115)
    assert bound.global_error_bound <= Fraction(1, 10**6)
    assert previous.global_error_bound > Fraction(1, 10**6)
