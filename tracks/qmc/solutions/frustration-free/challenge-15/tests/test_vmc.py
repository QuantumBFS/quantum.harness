from __future__ import annotations

from math import comb, pi

import numpy as np
import pytest

from challenge15.fermions import DeterminantBasis
from challenge15.oracle import solve_target_sectors
from challenge15.spec import SphereSpec
from challenge15.vmc import (
    SamplerConfig,
    SamplingDiagnostics,
    SphereMetropolis,
    coulomb_value,
    energy_and_score_gradient,
    su2_rotation,
)


def _random_spinors(particles: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(particles, 2)) + 1j * rng.normal(
        size=(particles, 2)
    )
    return spinors / np.linalg.norm(spinors, axis=1, keepdims=True)


def test_chord_coulomb_uses_sphere_radius_sqrt_q():
    spec = SphereSpec(2)
    separated = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.complex128)

    value = coulomb_value(separated, spec)

    assert value == pytest.approx(1.0 / (2.0 * np.sqrt(spec.q)))


def test_chord_coulomb_is_rigid_rotation_invariant():
    spec = SphereSpec(4)
    spinors = _random_spinors(spec.particles, 7)
    rotation = su2_rotation(np.asarray([1.0, -2.0, 0.5]), 0.73)

    rotated = spinors @ rotation.T

    assert coulomb_value(rotated, spec) == pytest.approx(
        coulomb_value(spinors, spec), rel=2e-14
    )


def test_chord_coulomb_returns_infinity_without_warning_at_exact_collision():
    spec = SphereSpec(2)
    collided = np.asarray([[1.0, 0.0], [1.0, 0.0]], dtype=np.complex128)

    with np.errstate(all="raise"):
        value = coulomb_value(collided, spec)

    assert value == np.inf


def test_chord_coulomb_near_collision_is_large_and_finite():
    spec = SphereSpec(2)
    epsilon = 1e-6
    nearby = np.asarray(
        [[1.0, 0.0], [np.sqrt(1.0 - epsilon**2), epsilon]],
        dtype=np.complex128,
    )

    value = coulomb_value(nearby, spec)

    assert np.isfinite(value)
    assert value > 1e5


def test_score_covariance_is_zero_for_constant_energy():
    scores = np.array([1 + 2j, 3 - 1j, -2 + 0.5j])
    values = np.full(3, 7.0)

    energy, gradient = energy_and_score_gradient(values, scores)

    assert energy == pytest.approx(7.0)
    np.testing.assert_allclose(gradient, 0.0, atol=1e-14)


def test_score_covariance_conjugates_complex_scores():
    values = np.asarray([1.0, 2.0, 5.0])
    scores = np.asarray(
        [[1.0 + 2.0j, -0.5j], [2.0 - 1.0j, 3.0], [-1.0 + 0.25j, 1.5j]]
    )

    _, gradient = energy_and_score_gradient(values, scores)
    expected = 2.0 * np.real(
        len(values)
        / (len(values) - 1)
        * (
            np.mean(np.conjugate(scores) * values[:, None], axis=0)
            - np.mean(np.conjugate(scores), axis=0) * np.mean(values)
        )
    )

    np.testing.assert_allclose(gradient, expected, atol=1e-14)


@pytest.mark.parametrize(
    "values,scores,message",
    [
        (np.asarray([1.0, 2.0]), np.asarray(1.0 + 0.0j), "at least one-dimensional"),
        (np.asarray([1.0, 2.0]), np.ones(3), "same sample axis"),
        (np.asarray([1.0, np.inf]), np.ones(2), "finite"),
        (np.asarray([1.0, 2.0]), np.asarray([1.0, np.nan]), "finite"),
    ],
)
def test_score_covariance_rejects_invalid_arrays(values, scores, message):
    with pytest.raises(ValueError, match=message):
        energy_and_score_gradient(values, scores)


def test_su2_rotation_is_unitary_with_unit_determinant_and_reversible():
    axis = np.asarray([0.2, -0.4, 1.3])
    rotation = su2_rotation(axis, 0.91)
    inverse = su2_rotation(axis, -0.91)

    np.testing.assert_allclose(rotation.conj().T @ rotation, np.eye(2), atol=2e-15)
    assert np.linalg.det(rotation) == pytest.approx(1.0, abs=2e-15)
    np.testing.assert_allclose(inverse, rotation.conj().T, atol=2e-15)


def test_sampler_mixes_local_and_rigid_moves_and_freezes_adaptation():
    spec = SphereSpec(3)
    config = SamplerConfig(
        burn_in=120,
        samples=80,
        thinning=2,
        chains=2,
        local_step=0.8,
        rigid_step=0.5,
        rigid_probability=0.3,
        adapt_interval=20,
        seed=18,
    )
    sampler = SphereMetropolis(lambda _z: 0.0j, spec, config)

    diagnostics = sampler.run()

    assert diagnostics.samples.shape == (2, 80, 3, 2)
    np.testing.assert_allclose(
        np.linalg.norm(diagnostics.samples, axis=-1), 1.0, atol=2e-14
    )
    assert diagnostics.local_proposals > 0
    assert diagnostics.rigid_proposals > 0
    assert (
        diagnostics.local_proposals + diagnostics.rigid_proposals
        == config.chains * config.samples * config.thinning
    )
    assert diagnostics.pilot_proposals == config.burn_in
    assert diagnostics.warmup_proposals == config.chains * config.burn_in
    assert diagnostics.adaptation_updates == config.burn_in // config.adapt_interval
    assert diagnostics.widths_frozen
    assert 0.0 <= diagnostics.acceptance_rate <= 1.0
    assert 0.0 <= diagnostics.pilot_acceptance_rate <= 1.0
    assert 0.0 <= diagnostics.warmup_acceptance_rate <= 1.0
    assert np.isfinite(diagnostics.final_local_step)
    assert np.isfinite(diagnostics.final_rigid_step)


def test_pilot_is_discarded_before_fresh_independent_production_chains():
    spec = SphereSpec(2)
    config = SamplerConfig(
        burn_in=10,
        samples=2,
        thinning=1,
        chains=3,
        adapt_interval=5,
        seed=118,
    )
    evaluations = []

    def recording_log_amplitude(spinors):
        evaluations.append(spinors.copy())
        return 0.0j

    SphereMetropolis(recording_log_amplitude, spec, config).run()
    pilot_initial = evaluations[0]
    production_initials = evaluations[config.burn_in + 1 : config.burn_in + 4]

    assert len(production_initials) == config.chains
    assert all(not np.allclose(state, pilot_initial) for state in production_initials)
    assert all(
        not np.allclose(production_initials[i], production_initials[j])
        for i in range(config.chains)
        for j in range(i)
    )


def test_uniform_amplitude_samples_product_sphere_measure():
    spec = SphereSpec(2)
    diagnostics = SphereMetropolis(
        lambda _z: 0.0j,
        spec,
        SamplerConfig(
            burn_in=400,
            samples=1200,
            thinning=2,
            chains=4,
            local_step=1.0,
            rigid_probability=0.15,
            seed=29,
        ),
    ).run()

    z_coordinate = (
        np.abs(diagnostics.samples[..., 0]) ** 2
        - np.abs(diagnostics.samples[..., 1]) ** 2
    )
    assert abs(float(np.mean(z_coordinate))) < 0.06
    assert float(np.var(z_coordinate)) == pytest.approx(1.0 / 3.0, abs=0.045)


def test_measurement_phase_does_not_adapt_widths():
    spec = SphereSpec(2)
    short = SamplerConfig(
        burn_in=100,
        samples=20,
        chains=1,
        adapt_interval=10,
        seed=44,
    )
    long = SamplerConfig(
        burn_in=100,
        samples=200,
        chains=1,
        adapt_interval=10,
        seed=44,
    )

    short_result = SphereMetropolis(lambda _z: 0.0j, spec, short).run()
    long_result = SphereMetropolis(lambda _z: 0.0j, spec, long).run()

    assert short_result.final_local_step == long_result.final_local_step
    assert short_result.final_rigid_step == long_result.final_rigid_step
    assert short_result.adaptation_updates == long_result.adaptation_updates


def test_diagnostics_are_autocorrelation_aware_and_report_split_rhat():
    rng = np.random.default_rng(71)
    chains = np.empty((4, 2000))
    innovations = rng.normal(size=chains.shape)
    chains[:, 0] = innovations[:, 0]
    for draw in range(1, chains.shape[1]):
        chains[:, draw] = 0.9 * chains[:, draw - 1] + innovations[:, draw]

    diagnostics = SamplingDiagnostics.from_chains(chains)

    assert diagnostics.integrated_autocorrelation_time > 5.0
    assert diagnostics.effective_sample_size < chains.size / 5.0
    assert diagnostics.effective_sample_size > 0
    assert diagnostics.split_rhat == pytest.approx(1.0, abs=0.04)
    assert diagnostics.autocorrelation_converged
    assert diagnostics.autocorrelation_method == "fft_sokal_window"
    assert diagnostics.autocorrelation_window >= 5
    assert not hasattr(diagnostics, "block_size")
    assert diagnostics.standard_error > 0
    assert diagnostics.bare_potential_estimator_variance == pytest.approx(
        np.var(chains, ddof=1)
    )
    assert not hasattr(diagnostics, "hamiltonian_variance")


def test_autocorrelation_diagnostics_fail_closed_without_reliable_window():
    rng = np.random.default_rng(711)
    chains = np.cumsum(rng.normal(size=(4, 128)), axis=1)

    diagnostics = SamplingDiagnostics.from_chains(chains)

    assert not diagnostics.autocorrelation_converged
    assert np.isnan(diagnostics.standard_error)
    assert np.isnan(diagnostics.effective_sample_size)
    assert diagnostics.autocorrelation_window > 0


def test_split_rhat_detects_nonconverged_independent_chains():
    rng = np.random.default_rng(72)
    chains = rng.normal(size=(4, 1000))
    chains[2:] += 2.5

    diagnostics = SamplingDiagnostics.from_chains(chains)

    assert diagnostics.split_rhat > 1.2


def test_paired_gap_uses_covariance_in_standard_error():
    rng = np.random.default_rng(90)
    common = rng.normal(size=(4, 1800))
    lower = common + 0.25 * rng.normal(size=common.shape)
    upper = common + 1.7 + 0.25 * rng.normal(size=common.shape)

    gap = SamplingDiagnostics.from_paired_gap(lower, upper)
    independent_se = np.sqrt(
        SamplingDiagnostics.from_chains(lower).standard_error**2
        + SamplingDiagnostics.from_chains(upper).standard_error**2
    )

    assert gap.estimate == pytest.approx(1.7, abs=0.03)
    assert gap.paired_covariance > 0.8
    assert gap.standard_error < independent_se / 2.0
    assert gap.split_rhat == pytest.approx(1.0, abs=0.04)


def test_sampler_diagnostics_can_estimate_bare_coulomb_values():
    spec = SphereSpec(3)
    samples = SphereMetropolis(
        lambda _z: 0.0j,
        spec,
        SamplerConfig(burn_in=100, samples=200, chains=3, seed=101),
    ).run()

    diagnostics = samples.for_observable(
        lambda spinors: coulomb_value(spinors, spec)
    )

    assert diagnostics.estimate > 0
    assert diagnostics.standard_error > 0
    assert diagnostics.bare_potential_estimator_variance > 0
    assert diagnostics.effective_sample_size <= 600


@pytest.mark.parametrize("particles,seed", [(3, 1503), (4, 1504)])
def test_coordinate_vmc_matches_exact_small_system_energy_within_two_se(
    particles,
    seed,
):
    spec = SphereSpec(particles)
    oracle = solve_target_sectors(spec)
    sector = oracle.exact_sector(0)
    coefficients = sector.isometry @ sector.eigenvectors[:, 0]
    log_amplitude = _determinant_log_amplitude(spec, coefficients)
    sampled = SphereMetropolis(
        log_amplitude,
        spec,
        SamplerConfig(
            burn_in=1200,
            samples=4000,
            thinning=2,
            chains=4,
            local_step=0.8,
            rigid_probability=0.1,
            seed=seed,
        ),
    ).run()
    bare = sampled.for_observable(lambda z: coulomb_value(z, spec))
    exact_energy = float(sector.eigenvalues[0])

    assert bare.autocorrelation_converged
    assert np.isfinite(bare.standard_error)
    assert bare.standard_error > 0
    assert bare.effective_sample_size >= 1000
    assert bare.split_rhat < 1.01
    assert 0.2 <= sampled.acceptance_rate <= 0.8
    assert abs(bare.estimate - exact_energy) <= 2.0 * bare.standard_error


def _determinant_log_amplitude(spec, coefficients):
    basis = DeterminantBasis.with_two_m(spec, 0)
    occupied = [
        [index for index in range(spec.orbital_count) if state & (1 << index)]
        for state in basis.states
    ]
    powers_u = np.asarray(
        [(spec.two_q + two_m) // 2 for two_m in spec.two_m_values]
    )
    powers_v = spec.two_q - powers_u
    normalizations = np.sqrt(
        (spec.two_q + 1)
        / (4.0 * pi)
        * np.asarray([comb(spec.two_q, int(power)) for power in powers_u])
    )

    def log_amplitude(spinors):
        orbitals = (
            normalizations[None, :]
            * spinors[:, 0, None] ** powers_u[None, :]
            * spinors[:, 1, None] ** powers_v[None, :]
        )
        determinants = np.asarray(
            [np.linalg.det(orbitals[:, columns]) for columns in occupied]
        )
        amplitude = np.dot(determinants, coefficients)
        return np.log(amplitude)

    return log_amplitude
