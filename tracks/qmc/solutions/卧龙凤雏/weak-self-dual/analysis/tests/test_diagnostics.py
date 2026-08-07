import numpy as np

from analysis.diagnostics import (
    effective_sample_size,
    self_duality_diagnostic,
    width_sampling_diagnostics,
)


def test_effective_sample_size_is_bounded_by_observation_count():
    series = np.array([1.0, -1.0] * 50)
    ess = effective_sample_size(series)
    assert 1.0 <= ess <= len(series)


def test_width_diagnostics_sum_stream_effective_sizes():
    blocks = {6: np.asarray([[1.0, 1.1, 0.9, 1.0], [1.0, 0.9, 1.1, 1.0]])}
    result = width_sampling_diagnostics(blocks)
    assert 1.0 <= result[6]["effective_sample_size"] <= 8.0


def test_equal_vortex_counts_give_zero_self_duality_z():
    electric = {6: np.full((3, 4), 75.0)}
    magnetic = {6: np.full((3, 4), 75.0)}
    faces = {6: np.full((3, 4), 200.0)}
    result = self_duality_diagnostic(electric, magnetic, faces)
    assert result["mean_difference"] == 0.0
    assert result["z_score"] == 0.0
