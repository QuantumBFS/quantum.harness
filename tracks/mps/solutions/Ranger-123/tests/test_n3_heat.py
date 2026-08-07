from __future__ import annotations

import numpy as np
from numpy.testing import assert_allclose

import floquet_if_manybody.n3_heat as n3_heat_module
from floquet_if_manybody.backends.uniform_tempo import UniformTempoResult
from floquet_if_manybody.correlations import CorrelationResult
from floquet_if_manybody.n3_heat import (
    N3HeatPoint,
    compare_sector_spectra,
    prepare_n3_sector,
    run_n3_heat_point,
)


def test_odd_point_is_j_independent_before_backend() -> None:
    a = prepare_n3_sector(N3HeatPoint(j=0.25, sector="odd"))
    b = prepare_n3_sector(N3HeatPoint(j=1.0, sector="odd"))
    assert_allclose(a.h0, b.h0, atol=1e-13)
    assert_allclose(a.coupling, b.coupling, atol=1e-13)
    assert a.dimension == 2


def test_default_drive_tracks_sector_bright_gap() -> None:
    even = prepare_n3_sector(N3HeatPoint(j=0.5, sector="even"))
    odd = prepare_n3_sector(N3HeatPoint(j=0.5, sector="odd"))
    assert_allclose(even.bright_gap, 0.4450418679126287, rtol=1e-10)
    assert_allclose(even.model.drive_frequency, even.bright_gap)
    assert_allclose(odd.bright_gap, 1.0, atol=1e-13)
    assert_allclose(odd.model.drive_frequency, 1.0, atol=1e-13)


def test_n3_per_spin_drive_projection_differs_from_bounded_bath() -> None:
    prepared = prepare_n3_sector(
        N3HeatPoint(
            j=0.5,
            sector="even",
            drive_normalization="per_spin",
        )
    )
    assert_allclose(prepared.drive, 3 * prepared.coupling)


def test_derived_drive_frequency_is_stable_at_cache_precision() -> None:
    prepared = prepare_n3_sector(N3HeatPoint(j=0.5, sector="even"))
    assert prepared.bright_gap == 0.44504186791263


def test_drive_ratio_and_counterterm_are_explicit() -> None:
    prepared = prepare_n3_sector(
        N3HeatPoint(
            j=0.5,
            sector="even",
            drive_ratio=1.25,
            alpha=0.1,
            cutoff=2.5,
            counterterm=True,
        )
    )
    assert_allclose(prepared.model.drive_frequency, 1.25 * prepared.bright_gap)
    assert prepared.model.counterterm_strength == 0.25


def test_phase_sample_count_must_divide_period_steps() -> None:
    with np.testing.assert_raises_regex(ValueError, "phase_samples"):
        N3HeatPoint(steps_per_period=12, phase_samples=5)


def test_uniform_backend_controls_are_explicit() -> None:
    point = N3HeatPoint(
        backend="uniform_tempo",
        steps_per_period=60,
        phase_samples=3,
        epsrel=1e-7,
        uniform_auto_nc=False,
        uniform_memory_cutoff=500,
        uniform_low_rank_svd=True,
        uniform_truncation="abs",
        uniform_cap_rank=400,
        uniform_max_rank=800,
    )
    assert point.backend == "uniform_tempo"
    assert point.uniform_memory_cutoff == 500
    assert point.uniform_truncation == "abs"


def test_backend_label_is_validated() -> None:
    with np.testing.assert_raises_regex(ValueError, "backend"):
        N3HeatPoint(backend="unknown")  # type: ignore[arg-type]


def test_uniform_backend_routes_through_existing_heat_transform(monkeypatch) -> None:
    class FakeUniformBackend:
        def __init__(self, **kwargs) -> None:
            assert kwargs["tensor_cache_directory"] is None

        def run_periodic(
            self,
            h0,
            coupling,
            model,
            bath,
            controls,
            *,
            drive_operator=None,
        ):
            assert h0.shape == (6, 6)
            assert coupling.shape == (6, 6)
            assert_allclose(drive_operator, coupling)
            assert controls.steps_per_period == 4
            assert controls.phase_samples == 2
            delays = np.linspace(0.0, model.period, 5)
            total = np.linspace(0.1, 0.01, 5).astype(complex)
            correlation = CorrelationResult(
                delays,
                total,
                total.copy(),
                np.zeros(5),
                (),
                "uniform_tempo_floquet_multitime",
                {"dt": model.period / 4},
            )
            return UniformTempoResult(
                "uniform_tempo_floquet_multitime",
                np.eye(6, dtype=complex) / 6,
                np.repeat((np.eye(6, dtype=complex) / 6)[None, ...], 2, axis=0),
                correlation,
                {
                    "trace_error": 1e-8,
                    "hermiticity_error": 1e-8,
                    "minimum_density_eigenvalue": 1 / 6,
                    "fixed_point_residual": 1e-8,
                    "floquet_transfer_residual": 1e-8,
                },
                {
                    "dt": model.period / 4,
                    "period_steps": 4,
                    "phase_samples": 2,
                    "bond_dimension": 3,
                    "tolerance": controls.tolerance,
                    "julia_version": "1.12.6",
                    "uniform_tempo_revision": "b76a018",
                    "manifest_sha256": "a" * 64,
                },
            )

    monkeypatch.setattr(
        n3_heat_module,
        "UniformTempoBackend",
        FakeUniformBackend,
    )
    result = run_n3_heat_point(
        N3HeatPoint(
            backend="uniform_tempo",
            steps_per_period=4,
            phase_samples=2,
            delay_periods=1,
            epsrel=1e-4,
            frequency_points=9,
        ),
        commit="test",
    )
    assert result["converged"]
    assert result["method"] == "uniform_tempo_floquet_multitime"
    assert result["diagnostics"]["bond_dimension"] == 3
    assert len(result["continuous"]) == 9


def test_compare_sector_spectra_requires_matching_grids() -> None:
    even = {
        "frequency": [0.0, 1.0, 2.0],
        "continuous": [0.0, 2.0, 0.0],
    }
    odd = {
        "frequency": [0.0, 1.0, 2.0],
        "continuous": [0.0, 1.0, 0.0],
    }
    comparison = compare_sector_spectra(even, odd)
    assert comparison["maximum_absolute_difference"] == 1.0
    assert np.isclose(comparison["normalized_l1_difference"], 1.0)
