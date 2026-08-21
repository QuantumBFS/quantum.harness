"""Inference tests for the spectral-silence expansion."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from run_spectral_silence_statistics_v2 import (
    registered_compatibility_extent,
    registered_compatibility_onset,
    run,
)


EXTERNAL_SPECTRAL = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "spectral_silence_v2.npz"
)


def test_registered_crossover_requires_all_later_nonplateau_points():
    grid = np.array([0.2, 0.4, 0.6, 0.8])
    lower = np.array([0.1, -0.1, -0.1, -0.1])
    upper = np.array([0.2, 0.1, 0.1, 0.1])
    assert (
        registered_compatibility_onset(
            grid,
            lower,
            upper,
            minimum=0.2,
            maximum=0.8,
        )
        == 0.4
    )


def test_unresolved_crossover_is_explicit():
    assert (
        registered_compatibility_onset(
            np.array([0.2, 0.4]),
            np.array([0.1, 0.1]),
            np.array([0.2, 0.2]),
            minimum=0.2,
            maximum=0.4,
        )
        is None
    )


def test_compatibility_extent_stops_before_first_resolved_deviation():
    extent = registered_compatibility_extent(
        np.array([0.5, 1.0, 1.5, 2.0]),
        np.array([-0.1, -0.1, 0.05, 0.1]),
        np.array([0.1, 0.1, 0.15, 0.2]),
        minimum=0.5,
        maximum=2.0,
    )
    assert extent == 1.0


@pytest.mark.skipif(
    not EXTERNAL_SPECTRAL.exists(),
    reason=(
        "activates with production arrays listed in release_manifest_v1.json"
    ),
)
def test_production_statistics_artifact(tmp_path):
    output_json = tmp_path / "statistics.json"
    output_npz = tmp_path / "statistics.npz"
    result = run(
        output_json,
        output_npz,
        bootstrap_replicates=500,
    )
    assert result["checks"]["structured_control_rejects_jacobi"]
    assert result["checks"]["physical_has_registered_jacobi_window"]
    assert result["checks"]["spectral_axis_confidence_separated"]
    assert result["all_checks_pass"]
    loaded = json.loads(output_json.read_text(encoding="utf-8"))
    assert loaded["bootstrap_replicates"] == 500
    arrays = np.load(output_npz, allow_pickle=False)
    assert arrays["g_form_mean"].shape[0] == 7
    assert arrays["energy_gap_ratio_mean"].shape[0] == 8
