from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np

from lgeth.jacobi import sample_jacobi_wishart


runner = importlib.import_module("run_rank_scaling_v1")


def test_qr_curvature_matches_metric_normalization() -> None:
    from lgeth.jacobi import normalized_curvature

    rng = np.random.default_rng(20260728500)
    first = rng.normal(size=(7, 9))
    second = rng.normal(size=(7, 9))
    _, qr_spectrum, _ = runner.qr_normalized_curvature(first, second)
    direct = normalized_curvature(first, second)
    np.testing.assert_allclose(
        qr_spectrum,
        np.linalg.eigvalsh(direct.omega),
        atol=1e-10,
        rtol=0.0,
    )


def test_exact_wishart_jacobi_atoms() -> None:
    full, interior, labels = sample_jacobi_wishart(
        8, 6, 4, 20260728501
    )
    assert full.shape == (4, 8)
    assert interior.shape == (4, 4)
    assert np.all(full[:, :2] == -1.0)
    assert np.all(full[:, -2:] == 1.0)
    assert np.all(labels.sum(axis=1) == 4)


def test_reduced_runner_and_explicit_resource_rejection(
    tmp_path: Path,
) -> None:
    result = runner.run(
        tmp_path / "scaling.json",
        tmp_path / "scaling.npz",
        cases=((8, 4),),
    )
    assert result["all_checks_pass"]
    assert result["cases"][0]["D"] == 16
    assert result["cases"][0]["M"] == 80
    rejected = runner.run(
        tmp_path / "rejected.json",
        tmp_path / "rejected.npz",
        cases=((20, 4),),
        response_entry_ceiling=100,
    )
    assert rejected["all_checks_pass"]
    assert rejected["cases"][0]["status"] == "resource_rejected"
