import numpy as np

from chiral_graviton.basis import SphereSystem
from chiral_graviton.ed import neutral_gap
from chiral_graviton.nqs import SharedProjectedMLP


def test_projected_nqs_has_exact_l0_and_l2():
    model = SharedProjectedMLP.build(
        SphereSystem.from_electron_count(3), "v1", hidden_width=8, seed=17
    )
    assert model.equivariance_error(model.initial_parameters) < 1e-10
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
