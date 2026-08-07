from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose
from scipy.special import jn_zeros

import floquet_if_manybody.heat_valve as heat_valve_module
from floquet_if_manybody.backends.uniform_tempo import UniformTempoResult
from floquet_if_manybody.convergence import ConvergenceCache
from floquet_if_manybody.correlations import CorrelationResult
from floquet_if_manybody.heat_valve import (
    HeatValvePoint,
    ValveNumerics,
    build_heat_valve_manifest,
    isolated_valve_scan,
    prepare_heat_valve_point,
    run_uniform_valve_point,
)


class FakePoleBackend:
    def __init__(self, **_kwargs: object) -> None:
        pass

    def run_periodic(
        self,
        h0: np.ndarray,
        coupling: np.ndarray,
        model: object,
        _bath: object,
        controls: object,
        *,
        drive_operator: np.ndarray,
    ) -> UniformTempoResult:
        assert_allclose(drive_operator, 3 * coupling)
        dimension = h0.shape[0]
        period = model.period
        dt = period / controls.steps_per_period
        delays = np.arange(controls.delay_steps + 1) * dt
        eigenvalues = np.array(
            [1.0, 0.85, 0.75, 0.65, 0.55, 0.45, 0.4, 0.35],
            dtype=complex,
        )
        residues = np.linspace(0.7, 0.1, 7).astype(complex)
        connected = np.zeros(len(delays), dtype=complex)
        for index, delay in enumerate(delays):
            scaled = delay / period
            if np.isclose(scaled, round(scaled), atol=1e-10):
                order = round(scaled)
                connected[index] = np.sum(residues * eigenvalues[1:] ** order)
        correlation = CorrelationResult(
            delays=delays,
            total=connected,
            connected=connected,
            coherent=np.zeros(len(delays)),
            delta_peaks=(),
            method="uniform_tempo_floquet_multitime",
            metadata={"dt": dt},
        )
        state = np.eye(dimension, dtype=complex) / dimension
        return UniformTempoResult(
            method="uniform_tempo_floquet_multitime",
            floquet_state=state,
            phase_states=np.repeat(
                state[None, ...],
                controls.phase_samples,
                axis=0,
            ),
            correlation=correlation,
            diagnostics={
                "trace_error": 1e-12,
                "hermiticity_error": 1e-12,
                "minimum_density_eigenvalue": 1 / dimension,
                "fixed_point_residual": 1e-12,
                "floquet_transfer_residual": 1e-12,
            },
            metadata={
                "dt": dt,
                "period_steps": controls.steps_per_period,
                "phase_samples": controls.phase_samples,
                "bond_dimension": 2,
                "tolerance": controls.tolerance,
                "julia_version": "1.12.6",
                "uniform_tempo_revision": "test",
                "manifest_sha256": "a" * 64,
                "process_tensor_cache_hit": 0,
                "transfer_dimension": 48,
                "pole_count": 8,
            },
            transfer_eigenvalues=eigenvalues,
            transfer_eigenpair_residuals=np.full(8, 1e-12),
        )


def test_heat_valve_uses_common_physical_drive_for_all_sizes() -> None:
    prepared = [
        prepare_heat_valve_point(HeatValvePoint(n=n, xi=2.2))
        for n in (1, 2, 3)
    ]
    assert_allclose(
        [item.model.drive_amplitude for item in prepared],
        [prepared[0].model.drive_frequency * 2.2 / 2] * 3,
    )
    assert_allclose(
        [
            np.linalg.norm(item.drive) / np.linalg.norm(item.coupling)
            for item in prepared
        ],
        [1, 2, 3],
    )


def test_single_spin_high_frequency_gap_minimum_tracks_first_bessel_zero() -> None:
    xis = np.linspace(2.2, 2.6, 41)
    manifest = isolated_valve_scan(
        HeatValvePoint(
            n=1,
            j=0.0,
            drive_frequency=6.0,
            xi=float(xi),
            floquet_steps=360,
        )
        for xi in xis
    )
    minimum = min(manifest["points"], key=lambda item: item["cat_gap"])
    assert abs(minimum["xi"] - jn_zeros(0, 1)[0]) <= xis[1] - xis[0]


def test_interacting_scan_returns_resolved_cat_diagnostics() -> None:
    manifest = isolated_valve_scan(
        HeatValvePoint(n=n, xi=xi, drive_frequency=3.0, floquet_steps=180)
        for n in (2, 3)
        for xi in (2.2, 2.4, 2.6)
    )
    assert manifest["complete"]
    assert len(manifest["points"]) == 6
    for point in manifest["points"]:
        assert point["cat_overlap"] >= 0.5
        assert point["cat_gap"] >= 0
        assert point["cat_brightness"] >= 0
        assert point["unitarity_residual"] < 1e-10
        assert point["floquet_eigen_residual"] < 1e-10


def test_uniform_valve_point_records_poles_residues_and_fixed_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        heat_valve_module,
        "UniformTempoBackend",
        FakePoleBackend,
    )
    result = run_uniform_valve_point(
        HeatValvePoint(n=3, xi=2.4, drive_frequency=3.0),
        ValveNumerics(
            steps_per_period=60,
            tolerance=1e-6,
            phase_samples=3,
            delay_periods=12,
            pole_count=8,
        ),
        ConvergenceCache(tmp_path),
        source_revision="test",
    )
    assert result["model"]["drive_frequency"] == 3.0
    assert result["bath"]["cutoff"] == 2.5
    assert result["pole_fit"]["reconstruction_residual"] < 0.05
    assert len(result["poles"]) == 7


def test_manifest_selects_minimum_and_two_resolved_flanks() -> None:
    records = []
    for n in (1, 2, 3):
        for xi, gap in ((2.0, 0.2), (2.2, 0.01), (2.4, 0.3)):
            records.append(
                {
                    **asdict(HeatValvePoint(n=n, xi=xi)),
                    "cat_overlap": 0.9,
                    "cat_gap": gap,
                }
            )
    manifest = build_heat_valve_manifest(
        {"complete": True, "points": records}
    )
    assert not manifest["complete"]
    assert [
        point["xi"] for point in manifest["selected_points"]
    ] == [2.0, 2.2, 2.4] * 3
