from fractions import Fraction

from trottercert.algebra import PauliString, PauliSum, QComplex
from trottercert.lattice import SquareLattice
from trottercert.orbits import canonical_translation, translation_orbits


def test_wrapped_bond_gets_contiguous_representative() -> None:
    lattice = SquareLattice(4)
    pauli = PauliString({lattice.site(0, 0): "X", lattice.site(3, 0): "X"})
    representative, members = canonical_translation(pauli, lattice)
    assert max(x for x, _, _ in representative) == 1
    assert len(members) == lattice.n_sites


def test_translation_invariant_orbit_decomposition() -> None:
    lattice = SquareLattice(4)
    seed = PauliString({lattice.site(0, 0): "X", lattice.site(1, 0): "X"})
    _, members = canonical_translation(seed, lattice)
    operator = PauliSum({member: 2 for member in members})
    orbits = translation_orbits(operator, lattice)
    assert len(orbits) == 1
    assert len(orbits[0].members) == lattice.n_sites


def test_noninvariant_operator_is_rejected() -> None:
    lattice = SquareLattice(4)
    operator = PauliSum.term(PauliString({0: "X"}))
    try:
        translation_orbits(operator, lattice)
    except ValueError as error:
        assert "not translation invariant" in str(error)
    else:
        raise AssertionError("expected a translation-invariance error")


def test_colored_two_by_two_unit_cell_orbit() -> None:
    lattice = SquareLattice(4)
    seed = PauliString({lattice.site(0, 0): "X"})
    _, members = canonical_translation(seed, lattice, (2, 2))
    operator = PauliSum({member: 1 for member in members})
    orbits = translation_orbits(operator, lattice, unit_cell=(2, 2))
    assert len(orbits) == 1
    assert len(orbits[0].members) == lattice.n_sites // 4


def test_unit_cell_phase_is_preserved() -> None:
    lattice = SquareLattice(4)
    even = PauliString({lattice.site(0, 0): "X"})
    odd = PauliString({lattice.site(1, 0): "X"})
    even_rep, _ = canonical_translation(even, lattice, (2, 2))
    odd_rep, _ = canonical_translation(odd, lattice, (2, 2))
    assert even_rep != odd_rep
    assert even_rep == ((0, 0, "X"),)
    assert odd_rep == ((1, 0, "X"),)


def test_finite_size_stabilizer_scales_density_coefficient() -> None:
    lattice = SquareLattice(4)
    pauli = PauliString(
        {
            lattice.site(0, 0): "X",
            lattice.site(2, 0): "X",
        }
    )
    _, members = canonical_translation(pauli, lattice, (2, 2))
    operator = PauliSum({member: 3 for member in members})
    orbit = translation_orbits(operator, lattice, unit_cell=(2, 2))[0]
    assert orbit.stabilizer == 2
    assert orbit.coefficient == QComplex(Fraction(3, 2))
