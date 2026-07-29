import numpy as np

from chiral_graviton.angular_momentum import l2_operator
from chiral_graviton.basis import FockBasis, SphereSystem
from chiral_graviton.ed import neutral_gap, solve_fixed_l
from chiral_graviton.hamiltonian import build_hamiltonian, relative_hermiticity_error
from chiral_graviton.interactions import pair_matrix_elements, v1_pseudopotentials


def test_v1_hamiltonian_is_hermitian_and_rotationally_invariant():
    system = SphereSystem.from_electron_count(4)
    basis = FockBasis(system, 0)
    table = pair_matrix_elements(system.two_q, v1_pseudopotentials(system.two_q))
    hamiltonian = build_hamiltonian(basis, table)
    assert relative_hermiticity_error(hamiltonian) < 1e-13
    l2 = l2_operator(basis)
    commutator = hamiltonian @ l2 - l2 @ hamiltonian
    assert np.linalg.norm(commutator.toarray()) < 1e-10


def test_laughlin_v1_ground_state_is_zero_energy_l0():
    system = SphereSystem.from_electron_count(4)
    state = solve_fixed_l(system, total_l=0, interaction="v1")
    assert abs(state.energy) < 1e-11
    assert abs(state.l2_expectation) < 1e-10
    assert state.residual_norm < 1e-9


def test_coulomb_graviton_gap_is_positive_and_spin_two():
    result = neutral_gap(SphereSystem.from_electron_count(3), interaction="coulomb")
    assert result.gap > 0.0
    np.testing.assert_allclose(result.l2_excited, 6.0, atol=1e-9)
    assert result.residual_l0 < 1e-8
    assert result.residual_l2 < 1e-8
