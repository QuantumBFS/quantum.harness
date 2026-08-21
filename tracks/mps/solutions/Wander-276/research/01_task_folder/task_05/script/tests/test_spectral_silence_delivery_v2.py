from __future__ import annotations

import importlib
from pathlib import Path

import pytest


verifier = importlib.import_module(
    "verify_spectral_silence_article_v2"
)
EXTERNAL_SPECTRAL = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "spectral_silence_v2.npz"
)


@pytest.mark.skipif(
    not EXTERNAL_SPECTRAL.exists(),
    reason=(
        "activates with production arrays listed in release_manifest_v1.json"
    ),
)
def test_registered_spectral_silence_delivery_passes(
    tmp_path: Path,
) -> None:
    audit = verifier.run(tmp_path / "audit.json")
    assert audit["all_checks_pass"]
    assert audit["pdf"]["title"] == (
        "Spectral Silence and Geometric Chaos in an Exactly Degenerate "
        "Topological Manifold"
    )
    assert 10 <= audit["pdf"]["pages"] <= 15
    assert len(audit["rendered_pages"]) == audit["pdf"]["pages"]
    assert audit["supported_conclusion"] == {
        "energy_connected_sff": 0.0,
        "physical_jacobi_tau_onset": 0.25,
        "geometric_local_onset": 0.20000000298023224,
        "geometric_ramp_onset": 0.4000000059604645,
        "number_variance_compatibility_extent": 1.0,
        "D800_connected_plateau": 0.7,
    }
    assert audit["registered_scale"] == {
        "physical_matrices": 20_000,
        "physical_test_matrices": 4_000,
        "structured_momenta": 24,
        "structured_orbits": 12,
        "geometric_interpolation_matrices": 28_000,
        "spectral_interpolation_matrices": 32_000,
        "haar_matrices": 10_000,
        "root_matrices": 8_750,
        "maximum_rank": 800,
        "bootstrap_replicates": 10_000,
    }
