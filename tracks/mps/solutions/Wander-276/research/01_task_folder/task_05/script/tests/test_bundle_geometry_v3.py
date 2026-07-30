"""Tests for task-local closed-surface non-Abelian bundle geometry."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.linalg import expm

from lgeth.bundle_geometry import (
    analyze_ambient_frame_mesh,
    apply_bosonic_fock_lift,
    manybody_frame_overlap,
    polar_unitary,
    random_local_gauge,
    sorted_wilson_eigenphases,
)
from lgeth.lattice import BosonBasis


def _seeded_unitary(dimension: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(dimension, dimension))
    matrix = matrix + 1j * rng.normal(size=matrix.shape)
    unitary, _ = np.linalg.qr(matrix)
    return unitary


def _qiwuzhang_lower_band_mesh(mesh: int, mass: float) -> np.ndarray:
    frames = np.empty((mesh, mesh, 2, 1), dtype=complex)
    momenta = 2.0 * np.pi * np.arange(mesh) / mesh
    for ix, kx in enumerate(momenta):
        for iy, ky in enumerate(momenta):
            hamiltonian = np.array(
                [
                    [
                        mass + np.cos(kx) + np.cos(ky),
                        np.sin(kx) - 1j * np.sin(ky),
                    ],
                    [
                        np.sin(kx) + 1j * np.sin(ky),
                        -mass - np.cos(kx) - np.cos(ky),
                    ],
                ],
                dtype=complex,
            )
            _, vectors = np.linalg.eigh(hamiltonian)
            frames[ix, iy, :, 0] = vectors[:, 0]
    return frames


def _synthetic_rank_three_bundle(mesh: int) -> np.ndarray:
    rng = np.random.default_rng(5)
    generators = []
    for _ in range(2):
        matrix = rng.normal(size=(6, 6))
        matrix = matrix + 1j * rng.normal(size=matrix.shape)
        matrix = 0.5 * (matrix + matrix.conj().T)
        generators.append(matrix / np.linalg.norm(matrix))
    base = _seeded_unitary(6, seed=6)[:, :3]
    frames = np.empty((mesh, mesh, 6, 3), dtype=complex)
    angles = 2 * np.pi * np.arange(mesh) / mesh
    for ix, theta_x in enumerate(angles):
        for iy, theta_y in enumerate(angles):
            unitary = expm(0.4j * np.sin(theta_x) * generators[0])
            unitary = unitary @ expm(
                0.3j * np.sin(theta_y) * generators[1]
            )
            frames[ix, iy] = unitary @ base
    return frames


def test_one_particle_fock_lift_equals_single_particle_overlap() -> None:
    basis = BosonBasis(n_orbitals=4, n_particles=1)
    overlap = _seeded_unitary(4, seed=1)
    frames = np.eye(4, dtype=complex)
    basis_to_orbital = np.zeros((4, 4), dtype=complex)
    for basis_index, state in enumerate(basis.states):
        basis_to_orbital[state.index(1), basis_index] = 1.0
    np.testing.assert_allclose(
        apply_bosonic_fock_lift(basis, overlap, frames),
        basis_to_orbital.conj().T @ overlap @ basis_to_orbital,
        atol=1e-12,
    )


def test_identity_orbital_overlap_reduces_to_coefficient_overlap() -> None:
    basis = BosonBasis(n_orbitals=4, n_particles=2)
    left = _seeded_unitary(basis.dimension, seed=2)[:, :3]
    right = _seeded_unitary(basis.dimension, seed=3)[:, :3]
    orbitals = _seeded_unitary(6, seed=4)[:, :4]
    observed = manybody_frame_overlap(
        basis,
        left,
        right,
        orbitals,
        orbitals,
    )
    np.testing.assert_allclose(
        observed,
        left.conj().T @ right,
        atol=1e-12,
    )


def test_polar_link_is_unitary_and_retains_singular_values() -> None:
    rng = np.random.default_rng(7)
    matrix = rng.normal(size=(6, 6))
    matrix = matrix + 1j * rng.normal(size=matrix.shape)
    unitary, values = polar_unitary(matrix)
    np.testing.assert_allclose(
        unitary.conj().T @ unitary,
        np.eye(6),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        values,
        np.linalg.svd(matrix, compute_uv=False),
    )


def test_rank_one_qwz_bundle_has_unit_chern_number() -> None:
    frames = _qiwuzhang_lower_band_mesh(mesh=20, mass=-1.0)
    result = analyze_ambient_frame_mesh(frames)
    assert abs(round(result.chern_determinant)) == 1
    assert abs(
        result.chern_determinant - result.chern_trace_log
    ) < 1e-10


def test_bundle_outputs_are_invariant_under_local_ud_gauges() -> None:
    bundle = _synthetic_rank_three_bundle(mesh=5)
    original = analyze_ambient_frame_mesh(bundle)
    transformed = analyze_ambient_frame_mesh(
        random_local_gauge(bundle, seed=8)
    )
    assert transformed.chern_determinant == pytest.approx(
        original.chern_determinant,
        abs=1e-10,
    )
    np.testing.assert_allclose(
        np.exp(1j * sorted_wilson_eigenphases(transformed)),
        np.exp(1j * sorted_wilson_eigenphases(original)),
        atol=1e-9,
    )
