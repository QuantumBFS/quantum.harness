"""Tests for periodic isospectral holonomy deformations and CUE statistics."""

from __future__ import annotations

import numpy as np
import pytest

from lgeth.bundle_geometry import analyze_frame_bundle
from lgeth.holonomy import (
    ambient_unitary,
    cue_wilson_reference,
    deform_orbital_mesh,
    local_generator_pair,
    wilson_statistics,
)
from lgeth.lattice import BosonBasis
from lgeth.twist_bundle import build_twist_bundle


def _nearest_neighbor_support_only(
    matrix: np.ndarray,
    length: int,
) -> bool:
    sites = length * length
    for left in range(sites):
        lx, ly = left % length, left // length
        for right in range(sites):
            if left == right or abs(matrix[left, right]) < 1e-12:
                continue
            rx, ry = right % length, right // length
            dx = min(abs(lx - rx), length - abs(lx - rx))
            dy = min(abs(ly - ry), length - abs(ly - ry))
            if dx + dy != 1:
                return False
    return True


def test_generator_pair_is_hermitian_local_and_noncommuting() -> None:
    gx, gy = local_generator_pair(length=4, seed=41, commuting=False)
    np.testing.assert_allclose(gx, gx.conj().T)
    np.testing.assert_allclose(gy, gy.conj().T)
    assert _nearest_neighbor_support_only(gx, length=4)
    assert _nearest_neighbor_support_only(gy, length=4)
    assert np.linalg.norm(gx @ gy - gy @ gx) > 1e-3


def test_commuting_control_generators_commute() -> None:
    gx, gy = local_generator_pair(length=4, seed=42, commuting=True)
    assert np.linalg.norm(gx @ gy - gy @ gx) < 1e-14


def test_ambient_unitary_is_periodic_and_unitary() -> None:
    generators = local_generator_pair(4, seed=41, commuting=False)
    first = ambient_unitary(0.2, 0.7, 0.8, generators)
    wrapped = ambient_unitary(
        0.2 + 2 * np.pi,
        0.7 - 2 * np.pi,
        0.8,
        generators,
    )
    np.testing.assert_allclose(first, wrapped, atol=1e-12)
    np.testing.assert_allclose(
        first.conj().T @ first,
        np.eye(first.shape[0]),
        atol=1e-12,
    )


def test_periodic_orbit_preserves_gap_and_chern() -> None:
    bundle = build_twist_bundle(N=3, n_flux=8, rank=16, mesh=6)
    deformed_orbitals = deform_orbital_mesh(
        bundle.orbital_frames,
        g=0.7,
        seed=43,
        commuting=False,
    )
    geometry = analyze_frame_bundle(
        bundle.coefficient_frames,
        deformed_orbitals,
        BosonBasis(bundle.n_flux, bundle.N),
    )
    assert geometry.chern_determinant == pytest.approx(
        bundle.geometry.chern_determinant,
        abs=1e-9,
    )
    assert np.min(bundle.external_gap) > 0.0


def test_wilson_statistics_are_common_phase_invariant() -> None:
    bundle = build_twist_bundle(N=3, n_flux=8, rank=16, mesh=3)
    original = wilson_statistics(bundle.geometry)
    shifted_geometry = bundle.geometry
    shifted_x = np.exp(0.37j) * shifted_geometry.wilson_x
    shifted_y = np.exp(-0.29j) * shifted_geometry.wilson_y
    shifted = wilson_statistics(
        shifted_geometry,
        wilson_x=shifted_x,
        wilson_y=shifted_y,
    )
    np.testing.assert_allclose(
        shifted["gap_ratio"],
        original["gap_ratio"],
        atol=1e-12,
    )
    np.testing.assert_allclose(
        shifted["form_factor"],
        original["form_factor"],
        atol=1e-10,
    )


def test_cue_reference_is_seed_reproducible() -> None:
    first = cue_wilson_reference(
        D=8,
        samples=64,
        k_values=np.arange(1, 9),
        seed=51,
    )
    second = cue_wilson_reference(
        D=8,
        samples=64,
        k_values=np.arange(1, 9),
        seed=51,
    )
    np.testing.assert_array_equal(
        first["gap_ratio"],
        second["gap_ratio"],
    )
    np.testing.assert_array_equal(
        first["form_factor"],
        second["form_factor"],
    )
