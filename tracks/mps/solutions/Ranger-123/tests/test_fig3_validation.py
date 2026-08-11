from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _module():
    path = Path(__file__).parents[1] / "scripts" / "run_fig3_validation.py"
    spec = importlib.util.spec_from_file_location("run_fig3_validation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_names_match_published_archive() -> None:
    module = _module()
    assert "ω_d_1.5" in module._reference_name(1.5)
    assert module.REFERENCE_FREQUENCY.shape == (3000,)
    assert np.isclose(module.REFERENCE_FREQUENCY[-1], 15.0)


def test_comparison_metrics_separate_shape_and_amplitude() -> None:
    module = _module()
    reference = np.exp(-module.REFERENCE_FREQUENCY)
    metrics = module.comparison_metrics(reference, 2 * reference)
    assert np.isclose(metrics["continuous_relative_l1"], 0.5)
    assert np.isclose(metrics["normalized_shape_relative_l1"], 0.0)
    assert np.isclose(metrics["integrated_magnitude_ratio"], 2.0)


def test_plot_summary_writes_both_publication_formats(tmp_path: Path) -> None:
    module = _module()
    curve = np.exp(-module.REFERENCE_FREQUENCY)
    results = []
    for drive_frequency in (1.0, 1.5, 2.0):
        results.append(
            {
                "model": {"drive_frequency": drive_frequency},
                "frequency": module.REFERENCE_FREQUENCY.tolist(),
                "reference_continuous": curve.tolist(),
                "continuous": curve.tolist(),
                "delta_peaks": [
                    {"frequency": drive_frequency, "harmonic": 1, "weight": 1.0}
                ],
                "metrics": {"normalized_shape_relative_l1": 0.0},
            }
        )
    stem = tmp_path / "summary"
    module.plot_summary(results, stem)
    assert stem.with_suffix(".png").stat().st_size > 0
    assert stem.with_suffix(".pdf").stat().st_size > 0
