from __future__ import annotations

import numpy as np

from route_d_plus.coordinate import (
    evaluate_pair_polynomial,
    laughlin_pair_polynomial,
    lll_interpolation_rule,
    scalar_laughlin_amplitudes,
    scalar_tower_amplitudes,
)
from route_d_plus.lll import monopole_orbitals, sphere_quadrature, spinor
from route_d_plus.mother import gmp_quadrupole_tower, laughlin_amplitude
from route_d_plus.scalar import (
    FockSpace,
    one_body_fock_matrix,
    scalar_generator_pair,
    slater_matrix,
)
from route_d_plus.tensor import canonical_tensor


def fixed_spinors(n_particles: int) -> np.ndarray:
    theta = np.linspace(0.31, 2.63, n_particles)
    phi = np.array([0.17, 1.41, 3.02, 5.11])[:n_particles]
    u, v = spinor(theta, phi)
    return np.column_stack((u, v))


def reconstructed_mother(
    space: FockSpace,
    two_q: int,
) -> np.ndarray:
    rng = np.random.default_rng(60_848)
    x = rng.uniform(-1.0, 1.0, size=(4 * space.dimension, 3))
    theta = np.arccos(x)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=theta.shape)
    u, v = spinor(theta, phi)
    batches = np.stack((u, v), axis=-1)
    basis = slater_matrix(two_q, space, batches)
    values = np.array([laughlin_amplitude(item) for item in batches])
    coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
    return coefficients


def test_pair_polynomial_reconstructs_laughlin_exactly() -> None:
    configuration = fixed_spinors(4)
    coefficients = laughlin_pair_polynomial(configuration, 1, 3)
    reconstructed = evaluate_pair_polynomial(
        coefficients, configuration[1], configuration[3]
    )
    expected = laughlin_amplitude(configuration)
    assert abs(reconstructed - expected) / abs(expected) < 1.0e-12


def test_coordinate_pair_backend_matches_fock_backend() -> None:
    configuration = fixed_spinors(3)
    space = FockSpace.build(7, 3)
    mother = reconstructed_mother(space, 6)
    basis = slater_matrix(6, space, configuration[None, ...])[0]
    coordinate = scalar_laughlin_amplitudes(configuration)
    coordinate_ratios = coordinate[1:] / coordinate[0]
    fock_ratios = []
    for ell in (2, 3, 4):
        dressed = scalar_generator_pair(space, 6, ell) @ mother
        fock_ratios.append((basis @ dressed) / (basis @ mother))
    assert np.max(np.abs(coordinate_ratios - fock_ratios)) < 1.0e-11


def test_lll_interpolation_reconstructs_all_orbitals() -> None:
    nodes, inverse = lll_interpolation_rule(9)
    values = monopole_orbitals(9, nodes[:, 0], nodes[:, 1])
    assert np.max(np.abs(inverse @ values - np.eye(10))) < 1.0e-12


def test_scalar_tower_mother_channel_matches_quadrature_proof() -> None:
    configuration = fixed_spinors(3)
    coordinate = scalar_tower_amplitudes(configuration)[:, 0]
    proof = gmp_quadrupole_tower(
        configuration,
        sphere_quadrature(6),
        two_q=6,
    )
    scale = max(float(np.max(np.abs(proof))), 1.0e-30)
    assert np.max(np.abs(coordinate - proof)) / scale < 1.0e-10


def test_scalar_tower_channels_match_commuting_fock_actions() -> None:
    configuration = fixed_spinors(3)
    space = FockSpace.build(7, 3)
    mother = reconstructed_mother(space, 6)
    basis = slater_matrix(6, space, configuration[None, ...])[0]
    coordinate = scalar_tower_amplitudes(configuration)
    reference = np.empty_like(coordinate)
    states = [mother] + [
        scalar_generator_pair(space, 6, ell) @ mother
        for ell in (2, 3, 4)
    ]
    for component, m in enumerate(range(-2, 3)):
        density = one_body_fock_matrix(
            space, canonical_tensor(6, 2, m)
        )
        for channel, state in enumerate(states):
            reference[component, channel] = basis @ density @ state
    scale = max(float(np.max(np.abs(reference))), 1.0e-30)
    assert np.max(np.abs(coordinate - reference)) / scale < 1.0e-10
