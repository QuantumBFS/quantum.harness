from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from floquet_if_manybody.adaptive import (
    AdaptiveSchedule,
    UniformAdaptiveSchedule,
    run_adaptive,
    run_uniform_adaptive,
    run_uniform_compression_audit,
)
from floquet_if_manybody.convergence import ConvergenceCache, fingerprint
from floquet_if_manybody.n3_heat import N3HeatPoint


def _fake_runner(counter: dict[str, int]):
    def run(point: N3HeatPoint, cache: ConvergenceCache | None) -> dict[str, Any]:
        key = fingerprint(asdict(point), "fake")
        if cache is not None and cache.contains(key):
            return cache.load(key)
        counter["calls"] += 1
        error = (
            (1 / point.steps_per_period) ** 2
            + np.exp(-point.memory_steps)
            + point.epsrel
        )
        grid = np.linspace(0, 1, 9)
        payload: dict[str, Any] = {
            "fingerprint": key,
            "complete": True,
            "converged": True,
            "diagnostics": {
                "phase_residual": 1e-5,
                "trace_error": 1e-8,
                "minimum_density_eigenvalue": 0.0,
                "connected_tail_amplitude": 1e-4,
            },
            "phase_state": {"real": [1 - error, error], "imag": [0.0, 0.0]},
            "correlation": {
                "delay": grid.tolist(),
                "connected": {
                    "real": (np.exp(-grid) + error).tolist(),
                    "imag": np.zeros_like(grid).tolist(),
                },
            },
            "frequency": grid.tolist(),
            "continuous": (grid * (1 + error)).tolist(),
        }
        if cache is not None:
            cache.store(key, payload)
            return cache.load(key)
        return payload

    return run


def test_adaptive_refines_all_controls_and_resumes(tmp_path: Path) -> None:
    counter = {"calls": 0}
    runner = _fake_runner(counter)
    cache = ConvergenceCache(tmp_path)
    point = N3HeatPoint(
        steps_per_period=4,
        memory_steps=1,
        epsrel=0.1,
        steady_periods=1,
        delay_periods=1,
        frequency_points=9,
    )
    schedule = AdaptiveSchedule(
        memory_steps=(1, 3, 6),
        steps_per_period=(4, 8, 16),
        epsrel=(0.1, 0.01, 0.001),
        state_threshold=0.1,
        correlation_threshold=0.1,
        heat_threshold=0.1,
    )
    result = run_adaptive(point, schedule, runner, cache)
    assert result.converged
    assert result.final_point.memory_steps >= 3
    assert result.final_point.steps_per_period >= 8
    assert result.final_point.epsrel <= 0.01
    assert result.final_point.memory_steps >= 12
    assert {record.parameter for record in result.evidence} == {
        "memory_steps",
        "steps_per_period",
        "epsrel",
    }
    first_calls = counter["calls"]
    resumed = run_adaptive(point, schedule, runner, cache)
    assert resumed.converged
    assert counter["calls"] == first_calls


def test_adaptive_reports_resource_ceiling() -> None:
    counter = {"calls": 0}
    point = N3HeatPoint(
        steps_per_period=4,
        memory_steps=1,
        epsrel=0.1,
        steady_periods=1,
        delay_periods=1,
        frequency_points=9,
    )
    schedule = AdaptiveSchedule(
        memory_steps=(1, 2),
        steps_per_period=(4, 8),
        epsrel=(0.1, 0.05),
        state_threshold=1e-12,
        correlation_threshold=1e-12,
        heat_threshold=1e-12,
    )
    result = run_adaptive(point, schedule, _fake_runner(counter), None)
    assert not result.converged
    assert result.status == "resource_ceiling"
    assert result.failed_parameter == "memory_steps"


def test_uniform_adaptive_refines_compression_timestep_and_phase() -> None:
    calls: list[tuple[float, int, int | None]] = []

    def runner(
        point: N3HeatPoint, cache: ConvergenceCache | None
    ) -> dict[str, Any]:
        del cache
        calls.append((point.epsrel, point.steps_per_period, point.phase_samples))
        error = point.epsrel + 1 / point.steps_per_period**2 + 0.02 / (
            point.phase_samples or point.steps_per_period
        )
        grid = np.linspace(0, 1, 9)
        return {
            "fingerprint": fingerprint(asdict(point), "uniform-fake"),
            "complete": True,
            "converged": True,
            "diagnostics": {
                "phase_residual": 1e-5,
                "fixed_point_residual": 1e-5,
                "trace_error": 1e-8,
                "hermiticity_error": 1e-8,
                "minimum_density_eigenvalue": 0.0,
                "connected_tail_amplitude": 1e-4,
                "bond_dimension": int(5 - np.log10(point.epsrel)),
            },
            "phase_state": {"real": [1 - error, error], "imag": [0.0, 0.0]},
            "correlation": {
                "delay": grid.tolist(),
                "connected": {
                    "real": (np.exp(-grid) + error).tolist(),
                    "imag": np.zeros_like(grid).tolist(),
                },
            },
            "frequency": grid.tolist(),
            "continuous": (grid * (1 + error)).tolist(),
        }

    point = N3HeatPoint(
        backend="uniform_tempo",
        steps_per_period=12,
        phase_samples=3,
        epsrel=1e-3,
        delay_periods=1,
        frequency_points=9,
    )
    schedule = UniformAdaptiveSchedule(
        steps_per_period=(12, 18),
        tolerances=(1e-3, 1e-4),
        phase_samples=(3, 6),
        state_threshold=0.1,
        correlation_threshold=0.1,
        heat_threshold=0.1,
    )
    result = run_uniform_adaptive(point, schedule, runner, None)
    assert result.converged
    assert result.final_point.steps_per_period == 18
    assert result.final_point.epsrel == 1e-4
    assert result.final_point.phase_samples == 6
    assert {record.parameter for record in result.evidence} == {
        "epsrel",
        "steps_per_period",
        "phase_samples",
    }
    assert [record.parameter for record in result.evidence] == [
        "epsrel",
        "epsrel",
        "steps_per_period",
        "phase_samples",
    ]
    assert all(record.refined_bond_dimension is not None for record in result.evidence)
    assert calls == [
        (1e-3, 12, 3),
        (1e-4, 12, 3),
        (1e-3, 18, 3),
        (1e-4, 18, 3),
        (1e-4, 18, 6),
    ]


def test_uniform_schedule_requires_common_phase_divisors() -> None:
    with np.testing.assert_raises_regex(ValueError, "phase_samples"):
        UniformAdaptiveSchedule(
            steps_per_period=(60, 90),
            tolerances=(1e-6, 3e-7),
            phase_samples=(3, 8),
        )


def test_uniform_adaptive_skips_compression_unstable_coarse_grid() -> None:
    def runner(
        point: N3HeatPoint, cache: ConvergenceCache | None
    ) -> dict[str, Any]:
        del cache
        compression_scale = 10.0 if point.steps_per_period == 12 else 0.01
        error = (
            compression_scale * point.epsrel
            + 1 / point.steps_per_period**2
            + 0.001 / (point.phase_samples or 3)
        )
        grid = np.linspace(0, 1, 9)
        return {
            "fingerprint": fingerprint(asdict(point), "uniform-skip-fake"),
            "complete": True,
            "converged": True,
            "diagnostics": {
                "phase_residual": 1e-5,
                "fixed_point_residual": 1e-5,
                "trace_error": 1e-8,
                "hermiticity_error": 1e-8,
                "minimum_density_eigenvalue": 0.0,
                "connected_tail_amplitude": 1e-4,
                "bond_dimension": 10,
            },
            "phase_state": {"real": [1 - error, error], "imag": [0.0, 0.0]},
            "correlation": {
                "delay": grid.tolist(),
                "connected": {
                    "real": (np.exp(-grid) + error).tolist(),
                    "imag": np.zeros_like(grid).tolist(),
                },
            },
            "frequency": grid.tolist(),
            "continuous": (grid * (1 + error)).tolist(),
        }

    point = N3HeatPoint(
        backend="uniform_tempo",
        steps_per_period=12,
        phase_samples=3,
        epsrel=0.1,
        delay_periods=1,
        frequency_points=9,
    )
    result = run_uniform_adaptive(
        point,
        UniformAdaptiveSchedule(
            steps_per_period=(12, 18, 24),
            tolerances=(0.1, 0.01),
            phase_samples=(3, 6),
            state_threshold=0.1,
            correlation_threshold=0.1,
            heat_threshold=0.1,
        ),
        runner,
        None,
    )
    assert result.converged
    assert result.final_point.steps_per_period == 24
    assert any(
        item.parameter == "epsrel"
        and item.coarse_steps_per_period == 12
        and not item.passed
        for item in result.evidence
    )
    assert any(
        item.parameter == "steps_per_period"
        and item.coarse_steps_per_period == 18
        and item.refined_steps_per_period == 24
        and item.passed
        for item in result.evidence
    )


def test_uniform_compression_audit_never_claims_full_convergence() -> None:
    point = N3HeatPoint(
        backend="uniform_tempo",
        steps_per_period=12,
        phase_samples=3,
        epsrel=1e-3,
        delay_periods=1,
        frequency_points=9,
    )
    result = run_uniform_compression_audit(
        point,
        UniformAdaptiveSchedule(
            steps_per_period=(12, 18),
            tolerances=(1e-3, 1e-4),
            phase_samples=(3, 6),
            state_threshold=0.1,
            correlation_threshold=0.1,
            heat_threshold=0.1,
        ),
        _fake_runner({"calls": 0}),
        None,
    )
    assert not result.converged
    assert result.status == "resource_ceiling"
    assert result.failed_parameter == "steps_per_period"
    assert len(result.evidence) == 1
    assert result.evidence[0].parameter == "epsrel"
    assert result.evidence[0].passed
