from fractions import Fraction

from trottercert.baseline import strang_commutator_operators
from trottercert.hamiltonian import four_matching_fragments
from trottercert.lattice import SquareLattice
from trottercert.local_commutators import (
    DyadicLocalDensityEvaluator,
    local_nested_pauli_l1_density,
    matching_partner,
    LocalDensityEvaluator,
    SymplecticDyadicLocalDensityEvaluator,
)


def test_matching_partner_is_an_involution() -> None:
    for color in range(4):
        for coordinate in ((0, 0), (1, 0), (-1, 2), (3, -2)):
            partner = matching_partner(coordinate, color)
            assert matching_partner(partner, color) == coordinate


def test_local_depth_three_density_matches_unaliased_global_l6() -> None:
    lattice = SquareLattice(6)
    fragments = four_matching_fragments(lattice)
    # Compare representative pure nested commutators, not the B_j sums.
    for key in ((0, 0, 1), (2, 3, 0), (1, 2, 3)):
        from trottercert.algebra import commutator

        global_operator = commutator(
            fragments[key[0]],
            commutator(fragments[key[1]], fragments[key[2]]),
        )
        expected_density = global_operator.exact_real_l1() / 9
        assert local_nested_pauli_l1_density(key) == expected_density


def test_suffix_memoized_evaluator_matches_direct() -> None:
    evaluator = LocalDensityEvaluator()
    for key in ((0, 2, 3), (1, 2, 3), (0, 1, 2, 3)):
        assert evaluator.pauli_l1_density(key) == local_nested_pauli_l1_density(key)


def test_dyadic_evaluator_matches_fraction_evaluator() -> None:
    fraction_evaluator = LocalDensityEvaluator()
    dyadic_evaluator = DyadicLocalDensityEvaluator()
    for key in (
        (0,),
        (1, 0),
        (2, 1, 0),
        (3, 2, 1, 0),
        (0, 3, 2, 1, 0),
    ):
        fraction_operator = fraction_evaluator.evaluate(key)
        dyadic_operator = dyadic_evaluator.evaluate(key)
        exponent = dyadic_evaluator.denominator_exponent(key)
        assert set(fraction_operator.terms) == set(dyadic_operator)
        for pauli, coefficient in fraction_operator.terms.items():
            numerator = dyadic_operator[pauli]
            assert coefficient.real == Fraction(numerator[0], 1 << exponent)
            assert coefficient.imag == Fraction(numerator[1], 1 << exponent)
        assert (
            dyadic_evaluator.pauli_l1_density(key)
            == fraction_evaluator.pauli_l1_density(key)
        )


def test_symplectic_evaluator_matches_fraction_evaluator() -> None:
    fraction_evaluator = LocalDensityEvaluator()
    symplectic_evaluator = SymplecticDyadicLocalDensityEvaluator()
    for key in (
        (0,),
        (1, 0),
        (2, 1, 0),
        (3, 2, 1, 0),
        (0, 3, 2, 1, 0),
    ):
        assert (
            symplectic_evaluator.pauli_l1_density(key)
            == fraction_evaluator.pauli_l1_density(key)
        )
