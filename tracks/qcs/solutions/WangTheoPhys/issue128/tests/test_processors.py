import numpy as np

from trottercert.algebra import QComplex, commutator, to_dense
from trottercert.formulas import leading_effective_error, strang_stages
from trottercert.hamiltonian import (
    four_matching_fragments,
    full_heisenberg_hamiltonian,
    heisenberg_bond,
)
from trottercert.lattice import SquareLattice
from trottercert.processors import (
    global_chirality_color_basis,
    processor_images,
    solve_processor_obstruction,
    spin_chirality,
)


def test_spin_chirality_convention_and_hermiticity() -> None:
    chi = spin_chirality(0, 1, 2)
    lhs = commutator(heisenberg_bond(0, 1), heisenberg_bond(1, 2))
    assert lhs == chi.scale(QComplex(0, -1))
    assert chi.is_hermitian()
    assert np.allclose(to_dense(chi, 3), to_dense(chi, 3).conj().T)


def test_global_color_chirality_basis_and_images_are_hermitian() -> None:
    lattice = SquareLattice(4)
    labeled = global_chirality_color_basis(lattice)
    assert len(labeled) == 6
    assert all(operator.is_hermitian() for _, operator in labeled)
    images = processor_images(
        full_heisenberg_hamiltonian(lattice),
        [operator for _, operator in labeled],
    )
    assert all(image.is_hermitian() for image in images)


def test_projection_reconstructs_target_plus_residual() -> None:
    lattice = SquareLattice(4)
    labeled = global_chirality_color_basis(lattice)
    images = processor_images(
        full_heisenberg_hamiltonian(lattice),
        [operator for _, operator in labeled],
    )
    target = images[0].scale(2) - images[2]
    result = solve_processor_obstruction(target, images)
    assert result.exact_solution
    assert not result.residual
