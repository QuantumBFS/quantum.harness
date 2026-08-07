"""Reproducible baseline experiments used by the report."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from .backends.finite_memory import FiniteMemoryBackend
from .backends.floquet_markov import FloquetMarkovBackend
from .config import BathConfig, ModelConfig, Normalization
from .correlations import superoperator_period_correlation
from .heat_current import heat_current_spectrum
from .models import coupling_operator, ising_hamiltonian
from .spectra import diagonalize, transitions
from .symmetry import n2_sectors, n3_reflection_sectors, project


def n2_bright_sweep(
    j_values: np.ndarray,
    omega: float = 1.0,
    normalization: Normalization = "bounded",
) -> dict[str, object]:
    _, triplet = n2_sectors()
    records = []
    maximum_residual = 0.0
    for j in j_values:
        cfg = ModelConfig(n=2, j=float(j), omega=omega, normalization=normalization)
        h = project(ising_hamiltonian(cfg), triplet)
        s = project(coupling_operator(cfg), triplet)
        spectrum = diagonalize(h)
        items = transitions(spectrum, spectrum, s, threshold=1e-10)
        low = next(item for item in items if item.source == 0 and item.frequency > 0)
        high = next(item for item in items if item.source == 1 and item.target == 2)
        energy = float(np.sqrt(j**2 + omega**2))
        analytic = {
            "gap_low": energy - float(j),
            "gap_high": energy + float(j),
            "weight_low": 2 * cfg.eta**2 * (1 + float(j) / energy),
            "weight_high": 2 * cfg.eta**2 * (1 - float(j) / energy),
        }
        numerical = {
            "gap_low": low.frequency,
            "gap_high": high.frequency,
            "weight_low": low.weight,
            "weight_high": high.weight,
        }
        maximum_residual = max(
            maximum_residual,
            max(abs(numerical[key] - analytic[key]) for key in analytic),
        )
        records.append(
            {
                "j": float(j),
                **numerical,
                **{f"analytic_{key}": value for key, value in analytic.items()},
            }
        )
    return {
        "method": "exact_diagonalization",
        "converged": maximum_residual < 1e-10,
        "diagnostics": {"maximum_analytic_residual": maximum_residual},
        "data": records,
    }


def n3_sector_sweep(
    j_values: np.ndarray,
    omega: float = 1.0,
    normalization: Normalization = "bounded",
) -> dict[str, object]:
    odd, even = n3_reflection_sectors()
    records = []
    odd_gap_spread = 0.0
    odd_gaps = []
    for j in j_values:
        cfg = ModelConfig(n=3, j=float(j), omega=omega, normalization=normalization)
        full_h = ising_hamiltonian(cfg)
        full_s = coupling_operator(cfg)
        even_spectrum = diagonalize(project(full_h, even))
        odd_spectrum = diagonalize(project(full_h, odd))
        odd_gap = float(odd_spectrum.energies[1] - odd_spectrum.energies[0])
        odd_gaps.append(odd_gap)
        even_operator = project(full_s, even)
        bright = sorted(
            [
                item
                for item in transitions(even_spectrum, even_spectrum, even_operator, 1e-10)
                if item.source == 0 and item.frequency > 0
            ],
            key=lambda item: item.frequency,
        )
        primary = bright[0]
        records.append(
            {
                "j": float(j),
                "odd_gap": odd_gap,
                "primary_even_gap": primary.frequency,
                "primary_even_weight": primary.weight,
                "cat_ratio": (
                    primary.frequency * 4 * float(j) ** 2 / omega**3 if j > 0 else None
                ),
            }
        )
    odd_gap_spread = float(np.ptp(odd_gaps))
    return {
        "method": "exact_diagonalization",
        "converged": odd_gap_spread < 1e-10,
        "diagnostics": {"odd_gap_spread": odd_gap_spread},
        "data": records,
    }


def backend_comparison(
    alphas: list[float],
    j: float = 0.5,
    omega: float = 1.0,
    drive_amplitude: float = 0.2,
    steps_per_period: int = 48,
    periods: int = 100,
) -> dict[str, object]:
    """Compare two explicitly approximate backends for the N=2 triplet."""
    _, triplet = n2_sectors()
    gap = float(np.sqrt(j**2 + omega**2) - j)
    cfg = ModelConfig(
        n=2,
        j=j,
        omega=omega,
        drive_amplitude=drive_amplitude,
        drive_frequency=gap,
    )
    h0 = project(ising_hamiltonian(cfg), triplet)
    s = project(coupling_operator(cfg), triplet)

    def hamiltonian(time: float) -> np.ndarray:
        return np.asarray(
            h0 + cfg.drive_amplitude * np.cos(cfg.drive_frequency * time) * s,
            dtype=np.complex128,
        )

    ground = diagonalize(h0).states[:, 0]
    rho0 = np.outer(ground, ground.conj())
    dt = cfg.period / steps_per_period
    records = []
    for alpha in alphas:
        bath = BathConfig(alpha=alpha)
        markov = FloquetMarkovBackend().run(
            hamiltonian, s, bath, cfg.period, steps_per_period, 4
        )
        memory = FiniteMemoryBackend().run(
            hamiltonian,
            s,
            rho0,
            bath,
            dt,
            steps_per_period * periods,
            1,
        )
        memory_phase_residual = float(
            np.linalg.norm(
                memory.density_matrices[-1]
                - memory.density_matrices[-1 - steps_per_period]
            )
        )
        trace_distance = float(
            0.5
            * np.sum(
                np.abs(
                    np.linalg.eigvalsh(
                        memory.density_matrices[-1] - markov.density_matrices[0]
                    )
                )
            )
        )
        records.append(
            {
                "alpha": alpha,
                "trace_distance": trace_distance,
                "finite_memory_phase_residual": memory_phase_residual,
                "finite_memory_trace_error": memory.diagnostics["trace_error"],
                "finite_memory_min_eigenvalue": memory.diagnostics[
                    "minimum_density_eigenvalue"
                ],
                "markov_rate_residual": markov.diagnostics["rate_residual"],
            }
        )
    converged = all(
        record["finite_memory_phase_residual"] < 5e-3
        and record["finite_memory_min_eigenvalue"] > -1e-5
        for record in records
    )
    return {
        "method": "finite_memory_if_vs_floquet_markov",
        "converged": converged,
        "diagnostics": {
            "memory_steps": 1,
            "steps_per_period": steps_per_period,
            "periods": periods,
            "warning": (
                "This is an approximation-to-approximation comparison, "
                "not an exact Floquet-IF error map."
            ),
        },
        "model": asdict(cfg),
        "data": records,
    }


def n2_markov_heat_spectrum(
    j: float = 0.5,
    omega: float = 1.0,
    alpha: float = 0.05,
    drive_amplitude: float = 0.2,
    steps_per_period: int = 96,
    correlation_periods: int = 16,
) -> dict[str, object]:
    """Generate the explicitly approximate N=2 Floquet-Markov heat spectrum."""
    _, triplet = n2_sectors()
    gap = float(np.sqrt(j**2 + omega**2) - j)
    cfg = ModelConfig(
        n=2,
        j=j,
        omega=omega,
        drive_amplitude=drive_amplitude,
        drive_frequency=gap,
    )
    h0 = project(ising_hamiltonian(cfg), triplet)
    coupling = project(coupling_operator(cfg), triplet)

    def hamiltonian(time: float) -> np.ndarray:
        return np.asarray(
            h0 + drive_amplitude * np.cos(cfg.drive_frequency * time) * coupling,
            dtype=np.complex128,
        )

    bath = BathConfig(alpha=alpha)
    markov = FloquetMarkovBackend().run(
        hamiltonian,
        coupling,
        bath,
        cfg.period,
        steps_per_period,
        5,
    )
    if markov.step_maps is None:
        raise RuntimeError("Floquet-Markov backend did not return step maps")
    correlation = superoperator_period_correlation(
        markov.step_maps,
        markov.density_matrices[:-1],
        coupling,
        cfg.period / steps_per_period,
        steps_per_period * correlation_periods,
        cfg.drive_frequency,
    )
    frequencies = np.linspace(0, 3.0, 601)
    heat = heat_current_spectrum(correlation, bath, frequencies)
    records = [
        {"frequency": float(frequency), "continuous": float(value)}
        for frequency, value in zip(heat.frequencies, heat.continuous, strict=True)
    ]
    return {
        "method": heat.method,
        "converged": markov.converged,
        "diagnostics": {
            **markov.diagnostics,
            **heat.metadata,
            "continuous_tail_amplitude": float(abs(correlation.connected[-1])),
        },
        "model": asdict(cfg),
        "bath": asdict(bath),
        "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
        "data": records,
    }
