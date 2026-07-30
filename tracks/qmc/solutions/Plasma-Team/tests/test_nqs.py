import numpy as np

from chiral_graviton.basis import SphereSystem
from chiral_graviton.ed import neutral_gap
from chiral_graviton.nqs import SharedProjectedMLP


def test_projected_nqs_has_exact_l0_and_l2():
    model = SharedProjectedMLP.build(
        SphereSystem.from_electron_count(3), "v1", hidden_width=8, seed=17
    )
    assert model.irrep_error(model.initial_parameters) < 1e-10
    assert model.scalar_rotation_error(model.initial_parameters) < 1e-10
    assert model.multiplet_rotation_error(model.initial_parameters) < 1e-10
    assert model.estimate(model.initial_parameters, 0).l2_expectation < 1e-10
    np.testing.assert_allclose(
        model.estimate(model.initial_parameters, 2).l2_expectation, 6.0, atol=1e-10
    )


def test_analytic_energy_gradient_matches_finite_difference():
    model = SharedProjectedMLP.build(
        SphereSystem.from_electron_count(3), "v1", hidden_width=4, seed=23
    )
    parameters = model.initial_parameters.copy()
    _, gradient = model.objective_and_gradient(parameters)
    epsilon = 2e-6
    for index in (0, 3, model.parameter_count - 2):
        plus = parameters.copy()
        minus = parameters.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        value_plus = model.objective_and_gradient(plus)[0]
        value_minus = model.objective_and_gradient(minus)[0]
        numeric = (value_plus - value_minus) / (2 * epsilon)
        np.testing.assert_allclose(gradient[index], numeric, rtol=2e-4, atol=2e-6)


def test_nqs_matches_ed_when_projected_sector_is_one_dimensional():
    system = SphereSystem.from_electron_count(3)
    reference = neutral_gap(system, interaction="coulomb")
    model = SharedProjectedMLP.build(system, "coulomb", hidden_width=6, seed=31)
    ground = model.estimate(model.initial_parameters, 0)
    graviton = model.estimate(model.initial_parameters, 2)
    np.testing.assert_allclose(ground.energy, reference.e_l0, atol=1e-10)
    np.testing.assert_allclose(graviton.energy, reference.e_l2, atol=1e-10)


def test_scalar_invariance_detects_l2_contamination():
    """Scalar-error test must reject a state with deliberate L>0 content."""

    from chiral_graviton.rotation_equivariance import scalar_invariance_error

    system = SphereSystem.from_electron_count(3)
    # Build the pure L=0 state for comparison.
    model = SharedProjectedMLP.build(system, "v1", hidden_width=6, seed=31)
    vector_clean = model.vector(model.initial_parameters, 0).copy()
    clean_error = scalar_invariance_error(model.sectors[0].basis, vector_clean)
    assert clean_error < 1e-10  # genuine L=0 state

    # Mix in part of the L=2 sector via orbital permutation to simulate a
    # rotation-broken state that has small L>0 content.
    from chiral_graviton.angular_momentum import angular_momentum_raising
    from chiral_graviton.basis import FockBasis

    # L_+ maps M=0 -> M=1 (two_lz delta = +2).  The L=2 highest-weight
    # sector is at M=2 (two_lz=4), which requires two consecutive raisings.
    lz1_basis = FockBasis(system, two_lz=2)
    raising_01 = angular_momentum_raising(model.sectors[0].basis, lz1_basis)
    raised = raising_01 @ vector_clean
    if np.linalg.norm(raised) > 0:
        raised /= np.linalg.norm(raised)
        # L_- maps back from M=1 -> M=0.
        lowered_back = raising_01.T @ raised
        contaminated = vector_clean + 0.3 * lowered_back
        contaminated /= np.linalg.norm(contaminated)
        contaminated_error = scalar_invariance_error(
            model.sectors[0].basis, contaminated
        )
        # The error should be noticeably larger than the clean case.
        assert contaminated_error > 1e-6


def test_direct_vmc_sampling_is_reproducible_and_has_error_bar():
    system = SphereSystem.from_electron_count(3)
    model = SharedProjectedMLP.build(system, "coulomb", hidden_width=6, seed=31)
    first = model.sample_energy(model.initial_parameters, 2, n_samples=2000, seed=99)
    second = model.sample_energy(model.initial_parameters, 2, n_samples=2000, seed=99)
    assert first == second
    assert first.standard_error >= 0.0
    np.testing.assert_allclose(
        first.mean, model.estimate(model.initial_parameters, 2).energy, atol=1e-12
    )
