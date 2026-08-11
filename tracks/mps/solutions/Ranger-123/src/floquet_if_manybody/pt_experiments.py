"""Long-running PT-TEMPO baselines kept separate from fast CI experiments."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from .backends.pt_tempo import PtTempoBackend
from .config import BathConfig, ModelConfig
from .heat_current import heat_current_spectrum
from .models import coupling_operator, ising_hamiltonian
from .spectra import diagonalize
from .symmetry import Sector, n2_sectors, n3_reflection_sectors, project


def _projected_model(config: ModelConfig, sector: Sector) -> tuple[np.ndarray, np.ndarray]:
    return (
        project(ising_hamiltonian(config), sector),
        project(coupling_operator(config), sector),
    )


def n2_pt_tempo_heat() -> dict[str, object]:
    """Non-Markovian N=2 heat spectrum with an explicit memory comparison."""
    j = 0.5
    gap = float(np.sqrt(1 + j**2) - j)
    model = ModelConfig(
        n=2,
        j=j,
        drive_amplitude=0.2,
        drive_frequency=gap,
    )
    bath = BathConfig(alpha=0.1, cutoff=2.5)
    _, triplet = n2_sectors()
    h0, coupling = _projected_model(model, triplet)

    def hamiltonian(time: float) -> np.ndarray:
        return np.asarray(
            h0
            + model.drive_amplitude
            * np.cos(model.drive_frequency * time)
            * coupling,
            dtype=np.complex128,
        )

    ground = diagonalize(h0).states[:, 0]
    initial = np.outer(ground, ground.conj())
    period_steps = 16
    steady_periods = 10
    delay_periods = 4
    total_periods = steady_periods + 1 + delay_periods
    dt = model.period / period_steps
    backend = PtTempoBackend()
    reference = backend.run(
        hamiltonian,
        coupling,
        initial,
        bath,
        dt,
        total_periods * period_steps,
        memory_steps=5,
        epsrel=1e-5,
    )
    shorter_memory = backend.run(
        hamiltonian,
        coupling,
        initial,
        bath,
        dt,
        steady_periods * period_steps,
        memory_steps=4,
        epsrel=1e-5,
    )
    phase_start = steady_periods * period_steps
    phase_residual = float(
        np.linalg.norm(
            reference.result.density_matrices[phase_start]
            - reference.result.density_matrices[phase_start - period_steps]
        )
    )
    memory_residual = float(
        np.linalg.norm(
            reference.result.density_matrices[phase_start]
            - shorter_memory.result.density_matrices[-1]
        )
    )
    correlation = backend.period_averaged_correlation(
        reference,
        coupling,
        phase_start,
        period_steps,
        delay_periods * period_steps,
        model.drive_frequency,
    )
    frequencies = np.linspace(0, 3, 401)
    heat = heat_current_spectrum(correlation, bath, frequencies)
    tail = float(abs(correlation.connected[-1]))
    converged = (
        reference.result.converged
        and phase_residual < 1e-3
        and memory_residual < 5e-2
        and tail < 5e-2
    )
    return {
        "method": "pt_tempo_multitime",
        "converged": converged,
        "diagnostics": {
            **reference.result.diagnostics,
            "phase_residual": phase_residual,
            "memory_k4_to_k5_residual": memory_residual,
            "connected_tail_amplitude": tail,
            "tau_max": float(correlation.delays[-1]),
            "dt": dt,
            "memory_steps": 5,
            "epsrel": 1e-5,
        },
        "model": asdict(model),
        "bath": asdict(bath),
        "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
        "data": [
            {"frequency": float(frequency), "continuous": float(current)}
            for frequency, current in zip(
                heat.frequencies, heat.continuous, strict=True
            )
        ],
    }


def n3_pt_tempo_dynamics() -> dict[str, object]:
    """N=3 reflection-even non-Markovian periodic-state convergence baseline."""
    model = ModelConfig(
        n=3,
        j=0.5,
        drive_amplitude=0.2,
        drive_frequency=0.4450418679126287,
    )
    bath = BathConfig(alpha=0.1, cutoff=2.5)
    _, even = n3_reflection_sectors()
    h0, coupling = _projected_model(model, even)

    def hamiltonian(time: float) -> np.ndarray:
        return np.asarray(
            h0
            + model.drive_amplitude
            * np.cos(model.drive_frequency * time)
            * coupling,
            dtype=np.complex128,
        )

    ground = diagonalize(h0).states[:, 0]
    initial = np.outer(ground, ground.conj())
    period_steps = 12
    periods = 30
    dt = model.period / period_steps
    run = PtTempoBackend().run(
        hamiltonian,
        coupling,
        initial,
        bath,
        dt,
        periods * period_steps,
        memory_steps=3,
        epsrel=1e-5,
    )
    phase_residual = float(
        np.linalg.norm(
            run.result.density_matrices[-1]
            - run.result.density_matrices[-1 - period_steps]
        )
    )
    magnetization = [
        float(np.real(np.trace(coupling @ state)))
        for state in run.result.density_matrices[-1 - period_steps : -1]
    ]
    return {
        "method": "pt_tempo",
        "converged": run.result.converged and phase_residual < 1e-3,
        "diagnostics": {
            **run.result.diagnostics,
            "phase_residual": phase_residual,
            "dt": dt,
            "memory_steps": 3,
            "epsrel": 1e-5,
        },
        "model": asdict(model),
        "bath": asdict(bath),
        "data": [
            {"phase_index": index, "magnetization": value}
            for index, value in enumerate(magnetization)
        ],
    }
