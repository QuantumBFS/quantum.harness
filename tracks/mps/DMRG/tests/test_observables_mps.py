from __future__ import annotations

import numpy as np

from vmcrg_ref.autocorrelation import autocorrelation_summary
from vmcrg_ref.observables import patch_distribution_distances


def test_patch_distribution_distances_uniform_identity() -> None:
    counts = np.full(512, 3, dtype=np.int64)
    distances = patch_distribution_distances(counts)
    assert distances["total_variation"] == 0.0
    assert distances["jensen_shannon"] == 0.0
    assert distances["kl_smoothed"] == 0.0


def test_patch_distribution_distances_detect_point_mass() -> None:
    counts = np.zeros(512, dtype=np.int64)
    counts[0] = 100
    distances = patch_distribution_distances(counts)
    assert 0.99 < distances["total_variation"] < 1.0
    assert distances["jensen_shannon"] > 0.0
    assert distances["kl_smoothed"] > 0.0


def test_autocorrelation_summary_reports_ess_per_second() -> None:
    rng = np.random.default_rng(20260890)
    values = np.empty(5000, dtype=np.float64)
    values[0] = rng.normal()
    for index in range(1, values.size):
        values[index] = 0.8 * values[index - 1] + rng.normal(scale=0.6)
    summary = autocorrelation_summary(values, elapsed_seconds=2.0)
    assert summary["tau_int"] > 1.0
    assert 0.0 < summary["ess"] < values.size
    assert summary["ess_per_second"] == summary["ess"] / 2.0
    assert summary["window_rule"] == "sokal_c5_with_initial_positive_fallback"
