"""Reusable reflection-resolved N=3 PT-TEMPO heat-current points."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import trapezoid

from .backends.pt_tempo import PtTempoBackend
from .backends.uniform_tempo import UniformTempoBackend, UniformTempoControls
from .config import BathConfig, DriveNormalization, ModelConfig, Normalization
from .convergence import ConvergenceCache, fingerprint
from .heat_current import heat_current_spectrum
from .models import coupling_operator, drive_operator, ising_hamiltonian
from .operators import ComplexMatrix
from .spectra import diagonalize, transitions
from .symmetry import Sector, n3_reflection_sectors, project


@dataclass(frozen=True)
class N3HeatPoint:
    """Complete physical and numerical controls for one N=3 calculation."""

    j: float = 0.5
    sector: Literal["even", "odd"] = "even"
    backend: Literal["oqupy", "uniform_tempo"] = "oqupy"
    omega: float = 1.0
    drive_amplitude: float = 0.2
    drive_ratio: float = 1.0
    drive_frequency: float | None = None
    normalization: Normalization = "bounded"
    drive_normalization: DriveNormalization = "coupling"
    counterterm: bool = False
    alpha: float = 0.1
    cutoff: float = 2.5
    temperature: float = 0.0
    steps_per_period: int = 12
    steady_periods: int = 30
    delay_periods: int = 3
    memory_steps: int = 3
    epsrel: float = 1e-5
    frequency_max: float = 3.0
    frequency_points: int = 401
    phase_samples: int | None = None
    uniform_auto_nc: bool = True
    uniform_memory_cutoff: int = 100_000
    uniform_low_rank_svd: bool = False
    uniform_truncation: Literal["rel", "abs"] = "rel"
    uniform_cap_rank: int = 100_000
    uniform_max_rank: int = 100_000

    def __post_init__(self) -> None:
        if self.sector not in ("even", "odd"):
            raise ValueError("sector must be 'even' or 'odd'")
        if self.backend not in ("oqupy", "uniform_tempo"):
            raise ValueError("backend must be 'oqupy' or 'uniform_tempo'")
        if self.drive_ratio <= 0:
            raise ValueError("drive_ratio must be positive")
        if self.steps_per_period < 2 or self.steady_periods < 1:
            raise ValueError("insufficient time discretization")
        if self.delay_periods < 1 or self.memory_steps < 1:
            raise ValueError("delay and memory controls must be positive")
        if not 0 < self.epsrel < 1:
            raise ValueError("epsrel must lie between zero and one")
        if self.frequency_max <= 0 or self.frequency_points < 2:
            raise ValueError("invalid frequency grid")
        if self.phase_samples is not None and (
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
class PreparedN3:
    point: N3HeatPoint
    model: ModelConfig
    bath: BathConfig
    sector: Sector
    h0: ComplexMatrix
    coupling: ComplexMatrix
    drive: ComplexMatrix
    bright_gap: float

    @property
    def dimension(self) -> int:
        return int(self.h0.shape[0])


def _primary_bright_gap(
    hamiltonian: ComplexMatrix, coupling: ComplexMatrix
) -> float:
    spectrum = diagonalize(hamiltonian)
    records = transitions(spectrum, spectrum, coupling)
    candidates = [
        record.frequency
        for record in records
        if record.source == 0 and record.frequency > 1e-12
    ]
    if not candidates:
        raise ValueError("sector has no bright transition from its ground state")
    # Hermitian eigensolvers may differ in the last one or two binary digits.
    # Canonicalizing a derived control prevents scientifically identical jobs
    # from receiving different content-addressed cache keys.
    return float(f"{min(candidates):.14g}")


def prepare_n3_sector(point: N3HeatPoint) -> PreparedN3:
    """Project the model exactly and select its primary bright resonance."""
    provisional = ModelConfig(
        n=3,
        j=point.j,
        omega=point.omega,
        drive_amplitude=point.drive_amplitude,
        drive_frequency=point.omega,
        normalization=point.normalization,
        drive_normalization=point.drive_normalization,
        counterterm=point.counterterm,
        counterterm_strength=(
            point.alpha * point.cutoff if point.counterterm else 0.0
        ),
    )
    odd, even = n3_reflection_sectors()
    sector = even if point.sector == "even" else odd
    h0 = project(ising_hamiltonian(provisional), sector)
    coupling = project(coupling_operator(provisional), sector)
    drive = project(drive_operator(provisional), sector)
    bright_gap = _primary_bright_gap(h0, coupling)
    drive_frequency = (
        point.drive_frequency
        if point.drive_frequency is not None
        else point.drive_ratio * bright_gap
    )
    model = ModelConfig(
        n=3,
        j=point.j,
        omega=point.omega,
        drive_amplitude=point.drive_amplitude,
        drive_frequency=drive_frequency,
        normalization=point.normalization,
        drive_normalization=point.drive_normalization,
        counterterm=point.counterterm,
        counterterm_strength=provisional.counterterm_strength,
    )
    bath = BathConfig(point.alpha, point.cutoff, point.temperature)
    return PreparedN3(point, model, bath, sector, h0, coupling, drive, bright_gap)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _complex_values(values: NDArray[np.complex128]) -> dict[str, list[float]]:
    return {
        "real": np.real(values).astype(float).tolist(),
        "imag": np.imag(values).astype(float).tolist(),
    }


def run_n3_heat_point(
    point: N3HeatPoint,
    cache: ConvergenceCache | None = None,
    *,
    commit: str | None = None,
) -> dict[str, Any]:
    """Run or restore one complete PT-TEMPO steady/correlation/heat pipeline."""
    prepared = prepare_n3_sector(point)
    revision = _git_commit() if commit is None else commit
    key = fingerprint(
        {
            "experiment": f"n3_{point.backend}_heat",
            "point": asdict(point),
            "model": asdict(prepared.model),
            "bath": asdict(prepared.bath),
        },
        revision,
    )
    model_hash = fingerprint(
        {
            "model": asdict(prepared.model),
            "bath": asdict(prepared.bath),
            "sector": point.sector,
        },
        "scientific-model-v1",
    )
    projected_model_hash = fingerprint(
        {
            "h0": _complex_values(prepared.h0),
            "coupling": _complex_values(prepared.coupling),
            "drive": _complex_values(prepared.drive),
            "drive_amplitude": prepared.model.drive_amplitude,
            "drive_frequency": prepared.model.drive_frequency,
            "bath": asdict(prepared.bath),
        },
        "projected-open-system-v1",
    )
    if cache is not None and cache.contains(key):
        return cache.load(key)

    model = prepared.model
    if point.backend == "uniform_tempo":
        phase_samples = (
            point.steps_per_period
            if point.phase_samples is None
            else point.phase_samples
        )
        controls = UniformTempoControls(
            steps_per_period=point.steps_per_period,
            tolerance=point.epsrel,
            phase_samples=phase_samples,
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
            model,
            prepared.bath,
            controls,
            drive_operator=prepared.drive,
        )
        correlation = uniform_run.correlation
        frequencies = np.linspace(
            0.0,
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
            "phase_samples": phase_samples,
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
            "sector": point.sector,
            "model": asdict(model),
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
        }
        uniform_payload["fingerprint"] = key
        if cache is not None:
            cache.store(key, uniform_payload)
            return cache.load(key)
        return {"complete": True, **uniform_payload}

    def hamiltonian(time: float) -> ComplexMatrix:
        return np.asarray(
            prepared.h0
            + model.drive_amplitude
            * np.cos(model.drive_frequency * time)
            * prepared.drive,
            dtype=np.complex128,
        )

    ground = diagonalize(prepared.h0).states[:, 0]
    initial = np.outer(ground, ground.conj())
    dt = model.period / point.steps_per_period
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
    phase_states = states[phase_start : phase_start + point.steps_per_period]
    phase_residual = float(
        np.linalg.norm(phase_state - states[phase_start - point.steps_per_period])
    )
    correlation = backend.period_averaged_correlation(
        run,
        prepared.coupling,
        phase_start,
        point.steps_per_period,
        delay_steps,
        model.drive_frequency,
        (
            None
            if point.phase_samples is None
            else list(
                range(
                    0,
                    point.steps_per_period,
                    point.steps_per_period // point.phase_samples,
                )
            )
        ),
    )
    frequencies = np.linspace(0.0, point.frequency_max, point.frequency_points)
    heat = heat_current_spectrum(correlation, prepared.bath, frequencies)
    connected_tail = float(abs(correlation.connected[-1]))
    payload: dict[str, Any] = {
        "method": "pt_tempo_multitime",
        "sector": point.sector,
        "model": asdict(model),
        "model_hash": model_hash,
        "projected_model_hash": projected_model_hash,
        "bath": asdict(prepared.bath),
        "point": asdict(point),
        "bright_gap": prepared.bright_gap,
        "dimension": prepared.dimension,
        "source_commit": revision,
        "converged": bool(
            run.result.converged
            and phase_residual < 1e-3
            and connected_tail < 5e-2
        ),
        "diagnostics": {
            **run.result.diagnostics,
            "phase_residual": phase_residual,
            "connected_tail_amplitude": connected_tail,
            "dt": dt,
            "tau_max": float(correlation.delays[-1]),
            "memory_steps": point.memory_steps,
            "epsrel": point.epsrel,
            "phase_samples": (
                point.steps_per_period
                if point.phase_samples is None
                else point.phase_samples
            ),
        },
        "phase_state": _complex_values(phase_state),
        "phase_states": _complex_values(phase_states),
        "correlation": {
            "delay": correlation.delays.tolist(),
            "total": _complex_values(correlation.total),
            "connected": _complex_values(correlation.connected),
            "coherent": correlation.coherent.tolist(),
        },
        "frequency": heat.frequencies.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
    }
    payload["fingerprint"] = key
    if cache is not None:
        cache.store(key, payload)
        return cache.load(key)
    return {"complete": True, **payload}


def compare_sector_spectra(
    even: dict[str, Any], odd: dict[str, Any]
) -> dict[str, float]:
    """Return direct differences without interpolating either spectrum."""
    even_grid = np.asarray(even["frequency"], dtype=float)
    odd_grid = np.asarray(odd["frequency"], dtype=float)
    if even_grid.shape != odd_grid.shape or not np.allclose(even_grid, odd_grid):
        raise ValueError("sector frequency grids do not match")
    even_heat = np.asarray(even["continuous"], dtype=float)
    odd_heat = np.asarray(odd["continuous"], dtype=float)
    difference = even_heat - odd_heat
    denominator = float(trapezoid(abs(odd_heat), odd_grid)) + 1e-15
    return {
        "maximum_absolute_difference": float(np.max(abs(difference))),
        "normalized_l1_difference": float(
            trapezoid(abs(difference), even_grid) / denominator
        ),
    }
