from __future__ import annotations

import numpy as np
import pytest

from benchmark_v0.fock_ed import fixed_m_basis, hamiltonian_matrix, l_squared_matrix
from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)
from benchmark_v0.projected_nqs import (
    angular_momentum_subspace,
    finite_rotation_residual,
    generate_l2_tower,
    particle_swap_residual,
    projected_ritz_state,
    shared_random_features,
    tower_ladder_residual,
    vmc_energy,
)


@pytest.fixture(scope="module")
def m0_problem() -> dict[str, object]:
    basis = fixed_m_basis(6, 15, 0.0)
    integrals = coulomb_integrals(15)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    hamiltonian = (hamiltonian + hamiltonian.T.conj()) / 2.0
    l_squared = l_squared_matrix(basis, two_q=15, target_m=0.0)
    return {
        "basis": basis,
        "hamiltonian": hamiltonian,
        "l_squared": l_squared,
        "pairs": pairs,
        "pair_matrix": pair_matrix,
    }


@pytest.mark.parametrize(("target_l", "expected_rank"), [(0, 6), (2, 11)])
def test_angular_momentum_subspace_is_exact_projector(
    m0_problem: dict[str, object], target_l: int, expected_rank: int
) -> None:
    subspace = angular_momentum_subspace(
        m0_problem["basis"],
        two_q=15,
        target_m=0.0,
        target_l=target_l,
    )
    target = target_l * (target_l + 1.0)

    assert subspace.shape == (338, expected_rank)
    np.testing.assert_allclose(subspace.T.conj() @ subspace, np.eye(expected_rank), atol=1e-12)
    np.testing.assert_allclose(
        m0_problem["l_squared"] @ subspace,
        target * subspace,
        atol=2e-11,
    )


def test_shared_random_feature_trunk_is_seeded_and_shared(
    m0_problem: dict[str, object],
) -> None:
    features_1 = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    features_2 = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )

    assert features_1.shape == (338, 129)
    np.testing.assert_array_equal(features_1, features_2)
    np.testing.assert_array_equal(features_1[:, 0], np.ones(338))


@pytest.mark.parametrize("target_l", [0, 2])
def test_projected_neural_head_reaches_ed_variational_minimum(
    m0_problem: dict[str, object], target_l: int
) -> None:
    features = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    subspace = angular_momentum_subspace(
        m0_problem["basis"],
        two_q=15,
        target_m=0.0,
        target_l=target_l,
    )
    result = projected_ritz_state(
        m0_problem["hamiltonian"], features, subspace
    )
    exact_energy = np.linalg.eigvalsh(
        subspace.T.conj() @ m0_problem["hamiltonian"] @ subspace
    )[0]

    assert result.projected_rank == subspace.shape[1]
    assert result.energy >= exact_energy - 2e-12
    assert result.energy == pytest.approx(exact_energy, abs=2e-11)
    np.testing.assert_allclose(
        subspace @ (subspace.T.conj() @ result.coefficients),
        result.coefficients,
        atol=2e-11,
    )


def test_l2_head_generates_normalized_fivefold_tower(
    m0_problem: dict[str, object],
) -> None:
    features = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    subspace = angular_momentum_subspace(
        m0_problem["basis"], two_q=15, target_m=0.0, target_l=2
    )
    m0_state = projected_ritz_state(
        m0_problem["hamiltonian"], features, subspace
    )

    tower = generate_l2_tower(
        m0_state.coefficients,
        n_electrons=6,
        two_q=15,
    )

    assert list(tower) == [-2, -1, 0, 1, 2]
    for magnetic_number, component in tower.items():
        assert component.magnetic_number == magnetic_number
        assert len(component.basis) == len(component.coefficients)
        assert np.linalg.norm(component.coefficients) == pytest.approx(1.0)
        l_squared = l_squared_matrix(
            component.basis,
            two_q=15,
            target_m=float(magnetic_number),
        )
        expectation = component.coefficients.conj() @ l_squared @ component.coefficients
        variance = (
            component.coefficients.conj()
            @ l_squared
            @ l_squared
            @ component.coefficients
            - expectation**2
        )
        assert float(np.real(expectation)) == pytest.approx(6.0, abs=2e-11)
        assert abs(variance) < 2e-10


def test_l2_tower_has_ladder_closure_and_degenerate_energy(
    m0_problem: dict[str, object],
) -> None:
    features = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    subspace = angular_momentum_subspace(
        m0_problem["basis"], two_q=15, target_m=0.0, target_l=2
    )
    state = projected_ritz_state(m0_problem["hamiltonian"], features, subspace)
    tower = generate_l2_tower(state.coefficients, n_electrons=6, two_q=15)

    energies = []
    for component in tower.values():
        hamiltonian = hamiltonian_matrix(
            component.basis,
            m0_problem["pairs"],
            m0_problem["pair_matrix"],
        )
        energies.append(
            float(
                np.real(
                    component.coefficients.conj()
                    @ hamiltonian
                    @ component.coefficients
                )
            )
        )

    assert max(energies) - min(energies) < 2e-11
    assert tower_ladder_residual(tower, two_q=15, target_l=2) < 2e-11


def test_independent_determinant_vmc_reports_error_and_ess(
    m0_problem: dict[str, object],
) -> None:
    features = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    subspace = angular_momentum_subspace(
        m0_problem["basis"], two_q=15, target_m=0.0, target_l=0
    )
    state = projected_ritz_state(m0_problem["hamiltonian"], features, subspace)

    estimate = vmc_energy(
        state.coefficients,
        m0_problem["hamiltonian"],
        n_samples=20_000,
        seed=849,
        numerical_floor=1.0e-12,
    )

    assert estimate.sampling == "independent categorical determinant samples"
    assert estimate.effective_sample_size == 20_000
    assert estimate.standard_error >= 0.0
    assert estimate.total_uncertainty >= 1.0e-12
    assert estimate.mean == pytest.approx(state.energy, abs=5 * estimate.total_uncertainty)


def test_continuous_lll_wavefunctions_change_sign_under_particle_swap(
    m0_problem: dict[str, object],
) -> None:
    features = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    l0_subspace = angular_momentum_subspace(
        m0_problem["basis"], two_q=15, target_m=0.0, target_l=0
    )
    l2_subspace = angular_momentum_subspace(
        m0_problem["basis"], two_q=15, target_m=0.0, target_l=2
    )
    ground = projected_ritz_state(
        m0_problem["hamiltonian"], features, l0_subspace
    )
    excited = projected_ritz_state(
        m0_problem["hamiltonian"], features, l2_subspace
    )
    tower = generate_l2_tower(excited.coefficients, n_electrons=6, two_q=15)

    assert (
        particle_swap_residual(
            m0_problem["basis"], ground.coefficients, two_q=15, seed=850
        )
        < 2e-11
    )
    assert max(
        particle_swap_residual(
            component.basis,
            component.coefficients,
            two_q=15,
            seed=851 + magnetic_number,
        )
        for magnetic_number, component in tower.items()
    ) < 2e-11


def test_l2_tower_transforms_under_finite_random_so3_rotation(
    m0_problem: dict[str, object],
) -> None:
    features = shared_random_features(
        m0_problem["basis"], n_orbitals=16, width=128, seed=848
    )
    subspace = angular_momentum_subspace(
        m0_problem["basis"], two_q=15, target_m=0.0, target_l=2
    )
    state = projected_ritz_state(m0_problem["hamiltonian"], features, subspace)
    tower = generate_l2_tower(state.coefficients, n_electrons=6, two_q=15)

    assert finite_rotation_residual(tower, two_q=15, seed=852) < 2e-10
