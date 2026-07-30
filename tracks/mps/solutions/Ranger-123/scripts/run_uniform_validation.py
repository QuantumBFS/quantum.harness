#!/usr/bin/env python3
"""Generate runtime validation records for the pinned UniformTEMPO backend."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from floquet_if_manybody.backends.uniform_tempo import (
    UNIFORM_TEMPO_REVISION,
    UniformTempoBackend,
    UniformTempoControls,
)
from floquet_if_manybody.config import BathConfig, ModelConfig
from floquet_if_manybody.convergence import (
    ConvergenceCache,
    atomic_write_result,
    curve_residual,
    state_residual,
)
from floquet_if_manybody.heat_current import heat_current_spectrum
from floquet_if_manybody.n3_heat import N3HeatPoint, prepare_n3_sector, run_n3_heat_point
from floquet_if_manybody.operators import pauli


def _complex_values(values: NDArray[np.complex128]) -> dict[str, Any]:
    return {
        "real": np.real(values).astype(float).tolist(),
        "imag": np.imag(values).astype(float).tolist(),
    }


def _complex_array(value: dict[str, Any]) -> NDArray[np.complex128]:
    return cast(
        NDArray[np.complex128],
        np.asarray(value["real"], dtype=float) + 1j * np.asarray(value["imag"], dtype=float),
    )


def single_spin_record(cache_directory: Path) -> dict[str, Any]:
    model = ModelConfig(
        n=1,
        j=0.0,
        omega=1.0,
        drive_amplitude=0.2,
        drive_frequency=1.0,
    )
    bath = BathConfig(alpha=0.05, cutoff=2.5, temperature=0.0)
    controls = UniformTempoControls(
        steps_per_period=60,
        tolerance=1e-6,
        phase_samples=3,
        delay_periods=6,
        low_rank_svd=True,
        truncation="abs",
        cap_rank=5_000,
        max_rank=10_000,
    )
    run = UniformTempoBackend(
        tensor_cache_directory=cache_directory / "process_tensors"
    ).run_periodic(0.5 * pauli("x"), pauli("z"), model, bath, controls)
    frequency = np.linspace(0.0, 3.0, 401)
    heat = heat_current_spectrum(run.correlation, bath, frequency)
    diagnostics = {
        **run.diagnostics,
        **run.metadata,
        "connected_tail_amplitude": float(abs(run.correlation.connected[-1])),
    }
    accepted = bool(
        diagnostics["fixed_point_residual"] <= 1e-3
        and diagnostics["trace_error"] <= 5e-3
        and diagnostics["hermiticity_error"] <= 5e-3
        and diagnostics["minimum_density_eigenvalue"] >= -5e-3
        and diagnostics["connected_tail_amplitude"] <= 5e-2
    )
    return {
        "method": "uniform_tempo_single_spin_runtime_validation",
        "converged": accepted,
        "uniform_tempo_revision": UNIFORM_TEMPO_REVISION,
        "model": asdict(model),
        "bath": asdict(bath),
        "controls": asdict(controls),
        "diagnostics": diagnostics,
        "phase_state": _complex_values(run.floquet_state),
        "frequency": heat.frequencies.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(item) for item in heat.delta_peaks],
    }


def cross_backend_record(cache_directory: Path) -> dict[str, Any]:
    common = dict(
        j=0.25,
        sector="odd",
        steps_per_period=60,
        phase_samples=3,
        delay_periods=1,
        frequency_points=401,
    )
    uniform_point = N3HeatPoint(
        **common,
        backend="uniform_tempo",
        epsrel=1e-6,
        uniform_low_rank_svd=True,
        uniform_truncation="abs",
        uniform_cap_rank=5_000,
        uniform_max_rank=10_000,
    )
    oqupy_point = N3HeatPoint(
        **common,
        backend="oqupy",
        memory_steps=3,
        epsrel=1e-5,
        steady_periods=20,
    )
    cache = ConvergenceCache(cache_directory)
    uniform = run_n3_heat_point(uniform_point, cache)
    oqupy = run_n3_heat_point(oqupy_point, cache, commit="oqupy-cross-validation-v1")
    uniform_grid = np.asarray(uniform["frequency"], dtype=float)
    oqupy_grid = np.asarray(oqupy["frequency"], dtype=float)
    uniform_delay = np.asarray(uniform["correlation"]["delay"], dtype=float)
    oqupy_delay = np.asarray(oqupy["correlation"]["delay"], dtype=float)
    metrics = {
        "phase_state_frobenius": state_residual(
            _complex_array(oqupy["phase_state"]),
            _complex_array(uniform["phase_state"]),
        ),
        "connected_correlation_relative_l1": curve_residual(
            oqupy_delay,
            _complex_array(oqupy["correlation"]["connected"]),
            uniform_delay,
            _complex_array(uniform["correlation"]["connected"]),
        ),
        "continuous_heat_relative_l1": curve_residual(
            oqupy_grid,
            np.asarray(oqupy["continuous"], dtype=float),
            uniform_grid,
            np.asarray(uniform["continuous"], dtype=float),
        ),
    }
    reference = prepare_n3_sector(uniform_point)
    target = prepare_n3_sector(N3HeatPoint(**{**asdict(uniform_point), "j": 1.0}))
    return {
        "method": "coarse_uniform_tempo_vs_oqupy_cross_validation",
        "complete": True,
        "converged": bool(
            uniform.get("complete")
            and oqupy.get("complete")
            and all(np.isfinite(value) for value in metrics.values())
        ),
        "interpretation": ("independent coarse-backend diagnostic; not a convergence refinement"),
        "uniform_fingerprint": uniform["fingerprint"],
        "oqupy_fingerprint": oqupy["fingerprint"],
        "projected_odd_j_invariance": {
            "h0_frobenius_residual": float(np.linalg.norm(reference.h0 - target.h0)),
            "coupling_frobenius_residual": float(
                np.linalg.norm(reference.coupling - target.coupling)
            ),
        },
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/validation"))
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("results/cache/uniform_tempo"),
    )
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    single = single_spin_record(arguments.cache)
    atomic_write_result(
        arguments.output / "uniform_tempo_single_spin.json",
        single,
    )
    cross = cross_backend_record(arguments.cache)
    atomic_write_result(
        arguments.output / "uniform_tempo_oqupy_crosscheck.json",
        cross,
    )
    return 0 if single["converged"] and cross["converged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
