"""Reusable interacting-triplet N=2 PT-TEMPO heat-current points."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np

from .backends.pt_tempo import PtTempoBackend
from .backends.uniform_tempo import UniformTempoBackend, UniformTempoControls
from .config import BathConfig, ModelConfig, Normalization
from .convergence import ConvergenceCache, fingerprint
from .heat_current import heat_current_spectrum
from .models import coupling_operator, ising_hamiltonian
from .operators import ComplexMatrix
from .spectra import diagonalize, transitions
from .symmetry import n2_sectors, project


@dataclass(frozen=True)
class N2HeatPoint:
    j: float = 0.5
    backend: Literal["oqupy", "uniform_tempo"] = "oqupy"
    omega: float = 1.0
    drive_amplitude: float = 0.2
    drive_ratio: float = 1.0
    drive_frequency: float | None = None
    normalization: Normalization = "bounded"
    counterterm: bool = False
    alpha: float = 0.1
    cutoff: float = 2.5
    temperature: float = 0.0
    steps_per_period: int = 16
    steady_periods: int = 20
    delay_periods: int = 4
    memory_steps: int = 4
    epsrel: float = 1e-5
    frequency_max: float = 3.0
    frequency_points: int = 401
    phase_samples: int = 4
    uniform_auto_nc: bool = True
    uniform_memory_cutoff: int = 100_000
    uniform_low_rank_svd: bool = False
    uniform_truncation: Literal["rel", "abs"] = "rel"
    uniform_cap_rank: int = 100_000
    uniform_max_rank: int = 100_000

    def __post_init__(self) -> None:
        if self.backend not in ("oqupy", "uniform_tempo"):
            raise ValueError("backend must be 'oqupy' or 'uniform_tempo'")
        if self.drive_ratio <= 0 or self.steps_per_period < 2:
            raise ValueError("invalid drive or timestep controls")
        if self.steady_periods < 1 or self.delay_periods < 1:
            raise ValueError("period counts must be positive")
        if self.memory_steps < 1 or not 0 < self.epsrel < 1:
            raise ValueError("invalid process-tensor controls")
        if (
            self.phase_samples < 2
            or self.phase_samples > self.steps_per_period
            or self.steps_per_period % self.phase_samples != 0
        ):
            raise ValueError("phase_samples must divide steps_per_period")
        if self.uniform_memory_cutoff < 1:
            raise ValueError("uniform_memory_cutoff must be positive")
        if self.uniform_truncation not in ("rel", "abs"):
            raise ValueError("uniform_truncation must be 'rel' or 'abs'")
        if (
            self.uniform_cap_rank < 1
            or self.uniform_max_rank < self.uniform_cap_rank
        ):
            raise ValueError("invalid uniform rank limits")


@dataclass(frozen=True)
class PreparedN2:
    point: N2HeatPoint
    model: ModelConfig
    bath: BathConfig
    h0: ComplexMatrix
    coupling: ComplexMatrix
    bright_gap: float

    @property
    def dimension(self) -> int:
        return int(self.h0.shape[0])


def _bright_gap(hamiltonian: ComplexMatrix, coupling: ComplexMatrix) -> float:
    spectrum = diagonalize(hamiltonian)
    candidates = [
        item.frequency
        for item in transitions(spectrum, spectrum, coupling)
        if item.source == 0 and item.frequency > 1e-12
    ]
    return float(f"{min(candidates):.14g}")


def prepare_n2_triplet(point: N2HeatPoint) -> PreparedN2:
    provisional = ModelConfig(
        n=2,
        j=point.j,
        omega=point.omega,
        drive_amplitude=point.drive_amplitude,
        drive_frequency=point.omega,
        normalization=point.normalization,
        counterterm=point.counterterm,
        counterterm_strength=(
            point.alpha * point.cutoff if point.counterterm else 0.0
        ),
    )
    _, triplet = n2_sectors()
    h0 = project(ising_hamiltonian(provisional), triplet)
    coupling = project(coupling_operator(provisional), triplet)
    gap = _bright_gap(h0, coupling)
    frequency = (
        point.drive_frequency
        if point.drive_frequency is not None
        else point.drive_ratio * gap
    )
    model = ModelConfig(
        n=2,
        j=point.j,
        omega=point.omega,
        drive_amplitude=point.drive_amplitude,
        drive_frequency=frequency,
        normalization=point.normalization,
        counterterm=point.counterterm,
        counterterm_strength=provisional.counterterm_strength,
    )
    return PreparedN2(
        point,
        model,
        BathConfig(point.alpha, point.cutoff, point.temperature),
        h0,
        coupling,
        gap,
    )


def _complex_values(values: np.ndarray[Any, np.dtype[np.complex128]]) -> dict[str, Any]:
    return {
        "real": np.real(values).astype(float).tolist(),
        "imag": np.imag(values).astype(float).tolist(),
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_n2_heat_point(
    point: N2HeatPoint,
    cache: ConvergenceCache | None = None,
    *,
    commit: str | None = None,
) -> dict[str, Any]:
    prepared = prepare_n2_triplet(point)
    revision = _git_commit() if commit is None else commit
    key = fingerprint(
        {
            "experiment": f"n2_triplet_{point.backend}_heat",
            "point": asdict(point),
            "model": asdict(prepared.model),
            "bath": asdict(prepared.bath),
        },
        revision,
    )
    if cache is not None and cache.contains(key):
        return cache.load(key)
    model_hash = fingerprint(
        {
            "model": asdict(prepared.model),
            "bath": asdict(prepared.bath),
            "sector": "triplet",
        },
        "scientific-model-v1",
    )
    projected_model_hash = fingerprint(
        {
            "h0": _complex_values(prepared.h0),
            "coupling": _complex_values(prepared.coupling),
            "drive_amplitude": prepared.model.drive_amplitude,
            "drive_frequency": prepared.model.drive_frequency,
            "bath": asdict(prepared.bath),
        },
        "projected-open-system-v1",
    )
    if point.backend == "uniform_tempo":
        controls = UniformTempoControls(
            steps_per_period=point.steps_per_period,
            tolerance=point.epsrel,
            phase_samples=point.phase_samples,
            delay_periods=point.delay_periods,
            auto_nc=point.uniform_auto_nc,
            memory_cutoff=point.uniform_memory_cutoff,
            low_rank_svd=point.uniform_low_rank_svd,
            truncation=point.uniform_truncation,
            cap_rank=point.uniform_cap_rank,
            max_rank=point.uniform_max_rank,
        )
        uniform_run = UniformTempoBackend(
            tensor_cache_directory=(
                None if cache is None else cache.directory / "process_tensors"
            )
        ).run_periodic(
            prepared.h0,
            prepared.coupling,
            prepared.model,
            prepared.bath,
            controls,
        )
        correlation = uniform_run.correlation
        frequencies = np.linspace(
            0,
            point.frequency_max,
            point.frequency_points,
        )
        heat = heat_current_spectrum(correlation, prepared.bath, frequencies)
        connected_tail = float(abs(correlation.connected[-1]))
        diagnostics = {
            **uniform_run.diagnostics,
            **uniform_run.metadata,
            "phase_residual": uniform_run.diagnostics["fixed_point_residual"],
            "connected_tail_amplitude": connected_tail,
            "tau_max": float(correlation.delays[-1]),
            "epsrel": point.epsrel,
            "phase_samples": point.phase_samples,
        }
        physical = bool(
            uniform_run.diagnostics["trace_error"] <= 5e-3
            and uniform_run.diagnostics["hermiticity_error"] <= 5e-3
            and uniform_run.diagnostics["minimum_density_eigenvalue"] >= -5e-3
            and uniform_run.diagnostics["fixed_point_residual"] <= 1e-3
            and connected_tail <= 5e-2
        )
        uniform_payload: dict[str, Any] = {
            "method": uniform_run.method,
            "sector": "triplet",
            "model": asdict(prepared.model),
            "model_hash": model_hash,
            "projected_model_hash": projected_model_hash,
            "bath": asdict(prepared.bath),
            "point": asdict(point),
            "bright_gap": prepared.bright_gap,
            "dimension": prepared.dimension,
            "source_commit": revision,
            "converged": physical,
            "diagnostics": diagnostics,
            "phase_state": _complex_values(uniform_run.floquet_state),
            "phase_states": _complex_values(uniform_run.phase_states),
            "correlation": {
                "delay": correlation.delays.tolist(),
                "total": _complex_values(correlation.total),
                "connected": _complex_values(correlation.connected),
                "coherent": correlation.coherent.tolist(),
            },
            "frequency": heat.frequencies.tolist(),
            "continuous": heat.continuous.tolist(),
            "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
            "fingerprint": key,
        }
        if cache is not None:
            cache.store(key, uniform_payload)
            return cache.load(key)
        return {"complete": True, **uniform_payload}

    def hamiltonian(time: float) -> ComplexMatrix:
        return np.asarray(
            prepared.h0
            + prepared.model.drive_amplitude
            * np.cos(prepared.model.drive_frequency * time)
            * prepared.coupling,
            dtype=np.complex128,
        )

    ground = diagonalize(prepared.h0).states[:, 0]
    initial = np.outer(ground, ground.conj())
    dt = prepared.model.period / point.steps_per_period
    phase_start = point.steady_periods * point.steps_per_period
    delay_steps = point.delay_periods * point.steps_per_period
    total_steps = phase_start + point.steps_per_period + delay_steps
    backend = PtTempoBackend()
    run = backend.run(
        hamiltonian,
        prepared.coupling,
        initial,
        prepared.bath,
        dt,
        total_steps,
        point.memory_steps,
        point.epsrel,
    )
    states = run.result.density_matrices
    phase_state = states[phase_start]
    phase_residual = float(
        np.linalg.norm(phase_state - states[phase_start - point.steps_per_period])
    )
    offsets = list(
        range(0, point.steps_per_period, point.steps_per_period // point.phase_samples)
    )
    correlation = backend.period_averaged_correlation(
        run,
        prepared.coupling,
        phase_start,
        point.steps_per_period,
        delay_steps,
        prepared.model.drive_frequency,
        offsets,
    )
    frequencies = np.linspace(0, point.frequency_max, point.frequency_points)
    heat = heat_current_spectrum(correlation, prepared.bath, frequencies)
    diagnostics = {
        **run.result.diagnostics,
        "phase_residual": phase_residual,
        "connected_tail_amplitude": float(abs(correlation.connected[-1])),
        "dt": dt,
        "tau_max": float(correlation.delays[-1]),
        "memory_steps": point.memory_steps,
        "epsrel": point.epsrel,
        "phase_samples": point.phase_samples,
    }
    payload: dict[str, Any] = {
        "method": "pt_tempo_multitime",
        "sector": "triplet",
        "model": asdict(prepared.model),
        "model_hash": model_hash,
        "projected_model_hash": projected_model_hash,
        "bath": asdict(prepared.bath),
        "point": asdict(point),
        "bright_gap": prepared.bright_gap,
        "dimension": prepared.dimension,
        "source_commit": revision,
        "converged": bool(
            run.result.converged
            and phase_residual < 2e-3
            and float(diagnostics["connected_tail_amplitude"]) < 5e-2
        ),
        "diagnostics": diagnostics,
        "phase_state": _complex_values(phase_state),
        "phase_states": _complex_values(
            states[phase_start : phase_start + point.steps_per_period]
        ),
        "correlation": {
            "delay": correlation.delays.tolist(),
            "total": _complex_values(correlation.total),
            "connected": _complex_values(correlation.connected),
            "coherent": correlation.coherent.tolist(),
        },
        "frequency": heat.frequencies.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
        "fingerprint": key,
    }
    if cache is not None:
        cache.store(key, payload)
        return cache.load(key)
    return {"complete": True, **payload}
