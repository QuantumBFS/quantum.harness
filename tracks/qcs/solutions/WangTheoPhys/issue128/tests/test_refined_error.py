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
from trottercert.local_commutators import CoordinateRegistry
from trottercert.refined_error import (
    HEISENBERG_BOND_PAULI_L1_GROWTH,
    canonicalize_symplectic_unit_cell,
    certified_d4_cell_coefficients,
    certified_leading_e5_cell_l1,
    defect_tail_site_bound,
    symplectic_pauli_from_coordinates,
)
from trottercert.rigorous_fourth import fourth_order_suzuki_interval_stages


def test_defect_tail_decreases_with_steps() -> None:
    stages, _ = fourth_order_suzuki_interval_stages(4, decimal_digits=8)
    assert defect_tail_site_bound(stages, 200) < defect_tail_site_bound(stages, 100)


def test_grouped_d4_override_must_tighten_the_existing_constant() -> None:
    from trottercert.refined_error import (
        build_refined_fourth_order_constants,
        evaluate_refined_fourth_order_bound,
    )

    constants = build_refined_fourth_order_constants(
        decimal_digits=8,
        quantization_digits=8,
    )
    tightened = constants.d4_site / 2
    original = evaluate_refined_fourth_order_bound(constants, 144, 116)
    grouped = evaluate_refined_fourth_order_bound(
        constants,
        144,
        116,
        d4_site_override=tightened,
    )
    assert grouped.degree_four_contribution == (
        original.degree_four_contribution / 2
    )
    with pytest.raises(ValueError, match="nonnegative"):
        evaluate_refined_fourth_order_bound(
            constants,
            144,
            116,
            d4_site_override=Fraction(-1),
        )
    with pytest.raises(ValueError, match="cannot exceed"):
        evaluate_refined_fourth_order_bound(
            constants,
            144,
            116,
            d4_site_override=constants.d4_site + 1,
        )


def test_colored_unit_cell_canonicalization_merges_translates() -> None:
    registry = CoordinateRegistry()
    left = symplectic_pauli_from_coordinates(
        registry,
        ((0, 0, "X"), (1, 0, "X")),
    )
    right = symplectic_pauli_from_coordinates(
        registry,
        ((2, 0, "X"), (3, 0, "X")),
    )
    assert canonicalize_symplectic_unit_cell(registry, left) == (
        canonicalize_symplectic_unit_cell(registry, right)
    )


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
def test_canonical_d4_coefficients_are_valid_and_tighter() -> None:
    stages, _ = fourth_order_suzuki_interval_stages(
        4,
        decimal_digits=12,
    )
    coefficients = certified_d4_cell_coefficients(
        stages,
        quantization_digits=18,
    )
    assert coefficients
    assert all(
        interval.lower <= interval.upper
        for interval in coefficients.values()
    )
    assert sum(
        (interval.abs_upper() for interval in coefficients.values()),
        Fraction(),
    ) <= 5 * certified_leading_e5_cell_l1(
        stages,
        quantization_digits=18,
    )


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


@pytest.mark.slow
def test_grouped_d4_bound_crosses_global_fourfold_target() -> None:
    from trottercert.anticommuting import (
        certify_anticommuting_partition,
        discover_anticommuting_partition,
    )
    from trottercert.refined_error import (
        build_refined_fourth_order_constants,
        evaluate_refined_fourth_order_bound,
    )

    stages, _ = fourth_order_suzuki_interval_stages(
        4,
        decimal_digits=12,
    )
    coefficients = certified_d4_cell_coefficients(
        stages,
        quantization_digits=18,
    )
    groups = discover_anticommuting_partition(
        coefficients,
        max_group_size=10,
    )
    certificate = certify_anticommuting_partition(
        coefficients,
        groups,
    )
    constants = build_refined_fourth_order_constants()
    d4_site = certificate.bound / 4
    accepted = evaluate_refined_fourth_order_bound(
        constants,
        144,
        97,
        d4_site_override=d4_site,
    )
    rejected = evaluate_refined_fourth_order_bound(
        constants,
        144,
        96,
        d4_site_override=d4_site,
    )
    assert len(certificate.paulis) == 75_324
    assert len(certificate.groups) == 7_576
    assert accepted.global_error_bound <= Fraction(1, 10**6)
    assert rejected.global_error_bound > Fraction(1, 10**6)
