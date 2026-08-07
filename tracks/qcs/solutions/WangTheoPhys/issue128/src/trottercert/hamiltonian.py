from __future__ import annotations

from fractions import Fraction

from .algebra import PauliString, PauliSum
from .lattice import SquareLattice


def heisenberg_bond(u: int, v: int) -> PauliSum:
    result = PauliSum.zero()
    for op in ("X", "Y", "Z"):
        result += PauliSum.term(PauliString({u: op, v: op}), Fraction(1, 4))
    return result


def fragment_from_bonds(bonds: tuple[tuple[int, int], ...]) -> PauliSum:
    result = PauliSum.zero()
    for u, v in bonds:
        result += heisenberg_bond(u, v)
    return result


def four_matching_fragments(lattice: SquareLattice) -> tuple[PauliSum, ...]:
    return tuple(fragment_from_bonds(group) for group in lattice.four_matchings())


def full_heisenberg_hamiltonian(lattice: SquareLattice) -> PauliSum:
    return fragment_from_bonds(lattice.bonds())
