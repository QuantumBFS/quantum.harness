from __future__ import annotations

import numpy as np

from route_d_plus.vmc import (
    channel_weight,
    coulomb_potential,
    energy_gradient_metric,
    geodesic_proposal,
    linear_log_derivatives,
    multiplet_log_derivatives,
    random_configuration,
    random_global_rotation,
    spinors_to_vectors,
    sr_update,
)


def test_geodesic_proposal_stays_on_sphere() -> None:
    rng = np.random.default_rng(71)
    configuration = random_configuration(rng, 6)
    proposed = geodesic_proposal(configuration, 2, 0.37, rng)
    assert np.max(
        np.abs(np.linalg.norm(spinors_to_vectors(proposed), axis=1) - 1.0)
    ) < 1.0e-14
    assert np.max(np.abs(proposed[:2] - configuration[:2])) == 0.0


def test_coulomb_estimator_is_rotation_and_exchange_invariant() -> None:
    rng = np.random.default_rng(72)
    configuration = random_configuration(rng, 6)
    expected = coulomb_potential(configuration, 15)[0]
    rotated = random_global_rotation(configuration, rng)
    swapped = configuration.copy()
    swapped[[1, 4]] = swapped[[4, 1]]
    assert abs(coulomb_potential(rotated, 15)[0] - expected) < 1.0e-13
    assert abs(coulomb_potential(swapped, 15)[0] - expected) < 1.0e-13


def test_multiplet_weight_and_derivative_are_unitary_invariant() -> None:
    rng = np.random.default_rng(73)
    channels = rng.normal(size=(5, 4)) + 1.0j * rng.normal(size=(5, 4))
    coefficients = np.array([0.03 + 0.01j, -0.02j, 0.015 - 0.01j])
    unitary, _ = np.linalg.qr(
        rng.normal(size=(5, 5)) + 1.0j * rng.normal(size=(5, 5))
    )
    rotated = unitary @ channels
    assert abs(
        channel_weight(rotated, coefficients)
        - channel_weight(channels, coefficients)
    ) < 1.0e-12
    original_derivative = multiplet_log_derivatives(
        channels[None, ...], coefficients
    )
    rotated_derivative = multiplet_log_derivatives(
        rotated[None, ...], coefficients
    )
    assert np.max(
        np.abs(original_derivative - rotated_derivative)
    ) < 1.0e-12


def test_real_parameter_log_derivatives_match_finite_difference() -> None:
    channels = np.array(
        [[1.2 + 0.3j, 0.2 - 0.1j, -0.4j, 0.1 + 0.5j]]
    )
    coefficients = np.array([0.03 + 0.01j, -0.02j, 0.015 - 0.01j])
    derivatives = linear_log_derivatives(channels, coefficients)[0]
    epsilon = 1.0e-7
    base = channels[0, 0] + channels[0, 1:] @ coefficients
    numerical = []
    for index in range(coefficients.size):
        shifted = coefficients.copy()
        shifted[index] += epsilon
        value = channels[0, 0] + channels[0, 1:] @ shifted
        numerical.append((np.log(value) - np.log(base)) / epsilon)
    for index in range(coefficients.size):
        shifted = coefficients.copy()
        shifted[index] += 1.0j * epsilon
        value = channels[0, 0] + channels[0, 1:] @ shifted
        numerical.append((np.log(value) - np.log(base)) / epsilon)
    assert np.max(np.abs(derivatives - numerical)) < 1.0e-7


def test_sr_step_decreases_linearized_objective_with_trust_region() -> None:
    rng = np.random.default_rng(74)
    derivatives = rng.normal(size=(256, 6)) + 1.0j * rng.normal(
        size=(256, 6)
    )
    energy = rng.normal(size=256)
    _, gradient, metric = energy_gradient_metric(energy, derivatives)
    step = sr_update(
        metric,
        gradient,
        learning_rate=0.2,
        diagonal_shift=1.0e-2,
        trust_radius=0.05,
    )
    assert float(gradient @ step) < 0.0
    assert float(step @ metric @ step) <= 0.05**2 * (1.0 + 1.0e-12)
