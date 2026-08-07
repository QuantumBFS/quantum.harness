"""Reduced-run tests for the spectral-silence production artifact."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from run_spectral_silence_v2 import run


EXTERNAL_PHYSICAL = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "physical_ensemble_v1.npz"
)


@pytest.mark.skipif(
    not EXTERNAL_PHYSICAL.exists(),
    reason=(
        "activates with production arrays listed in release_manifest_v1.json"
    ),
)
def test_reduced_spectral_silence_runner(tmp_path):
    output_json = tmp_path / "spectral_silence_v2.json"
    output_npz = tmp_path / "spectral_silence_v2.npz"
    result = run(
        output_json,
        output_npz,
        samples_per_g=64,
        spectral_samples=64,
        quadrature_order=128,
        rank_form_factor_samples=64,
    )
    assert result["checks"]["exact_energy_silence"]
    assert result["checks"]["structured_control_full_rank"]
    assert result["checks"]["structured_control_multiplets"]
    assert result["checks"]["fixed_projector_invariance"]
    assert result["checks"]["spectral_axis_resolved"]
    assert result["checks"]["atom_plateau_theorem"]
    assert result["all_checks_pass"]
    loaded = json.loads(output_json.read_text(encoding="utf-8"))
    assert loaded["sample_counts"]["per_positive_g"] == 64
    arrays = np.load(output_npz, allow_pickle=False)
    assert arrays["structured_spectra"].shape == (24, 50)
    assert arrays["g_spectra"].shape == (7, 64, 50)
    assert arrays["energy_spectra_alpha"].shape == (8, 64, 50)
    assert arrays["rank_reference_connected_full"].shape[0] == 7
