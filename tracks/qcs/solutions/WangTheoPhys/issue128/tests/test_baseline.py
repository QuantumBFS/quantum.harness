from fractions import Fraction

from trottercert.baseline import (
    pauli_l1_second_order_constant,
    strang_commutator_operators,
)
from trottercert.hamiltonian import four_matching_fragments
from trottercert.lattice import SquareLattice


def test_baseline_blocks_are_hermitian() -> None:
    fragments = four_matching_fragments(SquareLattice(4))
    blocks = strang_commutator_operators(fragments)
    assert len(blocks) == 3
    assert all(block.repeated_fragment.is_hermitian() for block in blocks)
    assert all(block.repeated_tail.is_hermitian() for block in blocks)


def test_pauli_l1_baseline_l4() -> None:
    fragments = four_matching_fragments(SquareLattice(4))
    constant = pauli_l1_second_order_constant(fragments)
    assert constant == Fraction(21, 8) * 16


def test_symbolic_aggregate_coefficients_are_real_l4() -> None:
    fragments = four_matching_fragments(SquareLattice(4))
    for block in strang_commutator_operators(fragments):
        for operator in (block.repeated_fragment, block.repeated_tail):
            assert operator.is_hermitian()
            assert all(coefficient.imag == 0 for coefficient in operator.terms.values())
