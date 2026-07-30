from __future__ import annotations

import numpy as np

from route_d_plus.vmc import (
    block_estimate,
    center_whiten_channels,
    channel_weight,
    correlated_sr_optimize,
    delayed_acceptance_chain,
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


def test_center_whiten_channels_preserves_mother_and_reduces_rank() -> None:
    channels = np.array(
        [
            [2.0, 3.0, 5.0, 7.0],
            [1.0, -2.0, 4.0, 3.0],
        ],
        dtype=np.complex128,
    )
    mean = np.array([0.5, -0.25, 0.75])
    whitening = np.array([[1.0, 2.0, 0.0], [0.0, -1.0, 1.0]])
    transformed = center_whiten_channels(channels, mean, whitening)
    centered = channels[:, 1:] - channels[:, :1] * mean
    assert transformed.shape == (2, 3)
    assert np.max(np.abs(transformed[:, 0] - channels[:, 0])) == 0.0
    assert np.max(
        np.abs(transformed[:, 1:] - centered @ whitening.T)
    ) == 0.0


def test_correlated_sr_reduces_fixed_sample_energy() -> None:
    rng = np.random.default_rng(75)
    samples = 2048
    channels = np.column_stack(
        (
            np.ones(samples),
            rng.normal(size=samples),
            rng.normal(size=samples),
        )
    ).astype(np.complex128)
    energy = (
        1.0
        + 0.4 * channels[:, 1].real
        - 0.25 * channels[:, 2].real
    )
    trace = correlated_sr_optimize(
        channels,
        energy,
        np.array([1.0e-3 + 2.0e-4j, -1.0e-3j]),
        updates=12,
    )
    assert trace.energies[-1] < trace.energies[0]
    assert np.min(trace.effective_sample_sizes) > 0.5 * samples


def test_block_diagnostics_distinguish_correlated_chains() -> None:
    rng = np.random.default_rng(76)
    chains = np.empty((4, 512))
    noise = rng.normal(size=chains.shape)
    chains[:, 0] = noise[:, 0]
    for index in range(1, chains.shape[1]):
        chains[:, index] = 0.85 * chains[:, index - 1] + noise[:, index]
    diagnostics = block_estimate(chains, block_size=32)
    assert diagnostics["standard_error"] > 0.0
    assert diagnostics["integrated_autocorrelation_time"] > 1.0
    assert diagnostics["effective_sample_size"] < chains.size
    assert 0.9 < diagnostics["r_hat"] < 1.1


def test_delayed_acceptance_retains_rejections_and_invariants() -> None:
    def mother(configuration: np.ndarray) -> np.ndarray:
        z_sum = np.sum(spinors_to_vectors(configuration)[:, 2])
        return np.array([np.exp(0.15 * z_sum)], dtype=np.complex128)

    def full(configuration: np.ndarray) -> np.ndarray:
        base = mother(configuration)[0]
        z_sum = np.sum(spinors_to_vectors(configuration)[:, 2])
        return np.array([base, z_sum * base], dtype=np.complex128)

    result = delayed_acceptance_chain(
        mother,
        full,
        n_particles=3,
        coefficients=np.array([0.35 + 0.1j]),
        seed=77,
        sample_steps=32,
        proposal_sweeps=2,
        delta_max=0.4,
        global_rotation_interval=0,
    )
    assert result.samples.shape == (32, 3, 2)
    assert result.channel_values.shape == (32, 2)
    assert 0.0 < result.correction_acceptance <= 1.0
    assert 0.0 < result.mother_acceptance < 1.0
    assert result.proposed_mother_moves == 32 * 2 * 3
