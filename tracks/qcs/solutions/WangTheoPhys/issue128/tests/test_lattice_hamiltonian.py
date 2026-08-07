from fractions import Fraction

import numpy as np

from trottercert.algebra import commutator, to_dense
from trottercert.hamiltonian import (
    four_matching_fragments,
    full_heisenberg_hamiltonian,
    heisenberg_bond,
)
from trottercert.lattice import SquareLattice


def test_periodic_square_bond_and_matching_counts() -> None:
    for length in (4, 6):
        lattice = SquareLattice(length)
        matchings = lattice.four_matchings()
        assert len(lattice.bonds()) == 2 * length * length
        assert all(len(group) == length * length // 2 for group in matchings)
        assert set().union(*(set(group) for group in matchings)) == set(lattice.bonds())
        for group in matchings:
            flattened = [site for bond in group for site in bond]
            assert len(flattened) == len(set(flattened))


def test_matching_fragments_reconstruct_hamiltonian() -> None:
    lattice = SquareLattice(4)
    total = sum(four_matching_fragments(lattice)[1:], four_matching_fragments(lattice)[0])
    assert total == full_heisenberg_hamiltonian(lattice)


def test_heisenberg_bond_spectrum() -> None:
    values = np.linalg.eigvalsh(to_dense(heisenberg_bond(0, 1), 2))
    assert np.allclose(values, [-0.75, 0.25, 0.25, 0.25])


def test_overlapping_bond_double_commutator_identity() -> None:
    h12 = heisenberg_bond(0, 1)
    h23 = heisenberg_bond(1, 2)
    h13 = heisenberg_bond(0, 2)
    lhs = commutator(h12, commutator(h12, h23))
    rhs = (h23 - h13).scale(Fraction(1, 2))
    assert lhs == rhs
    assert np.allclose(to_dense(lhs, 3), to_dense(rhs, 3))
