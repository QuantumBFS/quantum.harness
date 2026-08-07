"""Tests for physical closed twist-torus bundle checkpoints."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lgeth.twist_bundle import (
    build_twist_bundle,
    load_twist_bundle,
    save_twist_bundle,
)


@pytest.fixture(scope="module")
def reduced_bundle():
    return build_twist_bundle(N=3, n_flux=8, rank=16, mesh=3)


def test_reduced_twist_bundle_has_exact_kernel_and_open_gap(
    reduced_bundle,
) -> None:
    bundle = reduced_bundle
    assert bundle.coefficient_frames.shape[:2] == (3, 3)
    assert bundle.coefficient_frames.shape[-1] == 16
    assert np.max(bundle.kernel_bandwidth) < 1e-9
    assert np.min(bundle.external_gap) > 0.0
    assert bundle.geometry.minimum_overlap_singular_value > 0.0
    assert bundle.observed_rank_min == bundle.observed_rank_max == 16


def test_checkpoint_round_trip_preserves_frames_and_geometry(
    reduced_bundle,
    tmp_path: Path,
) -> None:
    metadata = tmp_path / "bundle.json"
    save_twist_bundle(reduced_bundle, metadata)
    loaded = load_twist_bundle(
        metadata,
        expected_N=3,
        expected_n_flux=8,
        expected_rank=16,
        expected_mesh=3,
    )
    np.testing.assert_allclose(
        loaded.coefficient_frames,
        reduced_bundle.coefficient_frames,
    )
    np.testing.assert_allclose(
        loaded.orbital_frames,
        reduced_bundle.orbital_frames,
    )
    assert loaded.geometry.chern_determinant == pytest.approx(
        reduced_bundle.geometry.chern_determinant,
        abs=1e-12,
    )


def test_checkpoint_rejects_mesh_mismatch(
    reduced_bundle,
    tmp_path: Path,
) -> None:
    metadata = tmp_path / "bundle.json"
    save_twist_bundle(reduced_bundle, metadata)
    with pytest.raises(ValueError, match="checkpoint identity"):
        load_twist_bundle(
            metadata,
            expected_N=3,
            expected_n_flux=8,
            expected_rank=16,
            expected_mesh=4,
        )
