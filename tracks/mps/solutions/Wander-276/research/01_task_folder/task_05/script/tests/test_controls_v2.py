"""Causal-control tests for spectral and geometric chaos channels."""

from __future__ import annotations

import numpy as np

from lgeth.channels import (
    build_physical_channel_cache,
    cached_channel,
)
from lgeth.controls import (
    fixed_projector_spectral_ensemble,
    fourier_tangent_pairs,
    scrambled_tangent_pair,
)
from lgeth.jacobi import normalized_curvature


def test_fourier_pairs_cover_all_nonzero_momenta_without_fake_phase_samples():
    pairs = fourier_tangent_pairs(5)
    assert len(pairs) == 24
    assert {(pair.kx, pair.ky) for pair in pairs} == {
        (kx, ky)
        for ky in range(5)
        for kx in range(5)
        if (kx, ky) != (0, 0)
    }
    assert len({pair.orbit_key for pair in pairs}) == 12
    assert all(abs(pair.v.mean()) < 1e-14 for pair in pairs)
    assert all(abs(pair.w.mean()) < 1e-14 for pair in pairs)
    assert all(abs(np.linalg.norm(pair.v) - 1.0) < 1e-14 for pair in pairs)
    assert all(abs(np.linalg.norm(pair.w) - 1.0) < 1e-14 for pair in pairs)


def test_scrambling_endpoints_are_exact():
    pair = fourier_tangent_pairs(5)[0]
    random_v = np.arange(25.0) - 12.0
    random_w = np.roll(random_v, 3)
    gram = np.eye(25)
    v0, w0 = scrambled_tangent_pair(
        pair,
        random_v,
        random_w,
        0.0,
        gram,
    )
    v1, w1 = scrambled_tangent_pair(
        pair,
        random_v,
        random_w,
        1.0,
        gram,
    )
    centered_v = random_v - random_v.mean()
    centered_w = random_w - random_w.mean()
    assert abs(abs(v0 @ pair.v) - 1.0) < 1e-12
    assert abs(abs(w0 @ pair.w) - 1.0) < 1e-12
    assert (
        abs(
            abs(v1 @ centered_v)
            / np.linalg.norm(centered_v)
            - 1.0
        )
        < 1e-12
    )
    assert (
        abs(
            abs(w1 @ centered_w)
            / np.linalg.norm(centered_w)
            - 1.0
        )
        < 1e-12
    )


def test_fixed_projector_changes_energy_not_geometry():
    control = fixed_projector_spectral_ensemble(
        dimension=50,
        samples=256,
        alphas=np.array([0.0, 1.0]),
        seed=19,
        reference_curvature_spectrum=np.linspace(-0.9, 0.9, 50),
    )
    assert (
        control.mean_gap_ratio[-1]
        > control.mean_gap_ratio[0] + 0.12
    )
    assert np.max(control.projector_distance) < 1e-13
    assert np.max(control.curvature_spectrum_error) < 1e-14
    assert control.energy_spectra.shape == (2, 256, 50)


def test_physical_fourier_controls_are_full_rank_but_multiplet_structured():
    cache = build_physical_channel_cache()
    unique_counts = []
    for pair in fourier_tangent_pairs(5):
        channel_v = cached_channel(pair.v, cache)
        channel_w = cached_channel(pair.w, cache)
        normalized = normalized_curvature(
            channel_v,
            channel_w,
            rtol=1e-10,
        )
        spectrum = np.linalg.eigvalsh(normalized.omega)
        assert normalized.rank == cache.rank == 50
        unique_counts.append(
            np.unique(np.round(spectrum, 10)).size
        )
    assert max(unique_counts) <= 10
