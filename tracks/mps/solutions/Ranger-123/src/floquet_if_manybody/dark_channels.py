"""Harmonic-resolved Floquet transition and dark-channel diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .floquet import FloquetSolution, micromotion
from .operators import ComplexMatrix


@dataclass(frozen=True)
class FloquetTransition:
    source: int
    target: int
    harmonic: int
    emitted_frequency: float
    amplitude: complex
    weight: float


@dataclass(frozen=True)
class DarkCandidate:
    transition: FloquetTransition
    relative_weight: float


def periodic_modes(solution: FloquetSolution) -> NDArray[np.complex128]:
    cumulative = micromotion(solution)[:-1]
    dt = solution.period / len(cumulative)
    values = []
    for index, propagator in enumerate(cumulative):
        time = index * dt
        values.append(
            propagator
            @ solution.modes
            @ np.diag(np.exp(1j * solution.quasienergies * time))
        )
    return np.asarray(values)


def floquet_matrix_elements(
    solution: FloquetSolution,
    operator: ComplexMatrix,
    harmonic_cutoff: int,
    threshold: float = 0.0,
) -> tuple[FloquetTransition, ...]:
    """Return S_ab^(m) under the project's Fourier convention."""
    if harmonic_cutoff < 0:
        raise ValueError("harmonic_cutoff must be nonnegative")
    modes = periodic_modes(solution)
    samples = len(modes)
    omega_d = 2 * np.pi / solution.period
    instantaneous = np.einsum(
        "tai,ab,tbj->tij", modes.conj(), operator, modes, optimize=True
    )
    records: list[FloquetTransition] = []
    for harmonic in range(-harmonic_cutoff, harmonic_cutoff + 1):
        phase = np.exp(-1j * harmonic * omega_d * np.arange(samples) * solution.period / samples)
        fourier = np.einsum("t,tij->ij", phase, instantaneous) / samples
        for target in range(fourier.shape[0]):
            for source in range(fourier.shape[1]):
                amplitude = complex(fourier[target, source])
                weight = float(abs(amplitude) ** 2)
                if weight >= threshold:
                    records.append(
                        FloquetTransition(
                            source=source,
                            target=target,
                            harmonic=harmonic,
                            emitted_frequency=float(
                                solution.quasienergies[source]
                                - solution.quasienergies[target]
                                + harmonic * omega_d
                            ),
                            amplitude=amplitude,
                            weight=weight,
                        )
                    )
    return tuple(records)


def harmonic_sum_rule(
    solution: FloquetSolution,
    operator: ComplexMatrix,
    harmonic_cutoff: int,
) -> float:
    """Return maximum relative Parseval residual over mode pairs."""
    modes = periodic_modes(solution)
    instantaneous = np.einsum(
        "tai,ab,tbj->tij", modes.conj(), operator, modes, optimize=True
    )
    direct = np.mean(abs(instantaneous) ** 2, axis=0)
    records = floquet_matrix_elements(solution, operator, harmonic_cutoff)
    summed = np.zeros_like(direct, dtype=float)
    for record in records:
        summed[record.target, record.source] += record.weight
    return float(np.max(abs(summed - direct) / (direct + 1e-15)))


def period_variance(
    phase_densities: NDArray[np.complex128], operator: ComplexMatrix
) -> float:
    first = np.einsum("ij,tji->t", operator, phase_densities, optimize=True)
    second = np.einsum(
        "ij,tji->t", operator @ operator, phase_densities, optimize=True
    )
    return float(np.real(np.mean(second - first * first)))


def dark_candidates(
    transitions: tuple[FloquetTransition, ...],
    relative_threshold: float = 1e-4,
) -> tuple[DarkCandidate, ...]:
    if not 0 <= relative_threshold <= 1:
        raise ValueError("relative_threshold must lie in [0, 1]")
    if not transitions:
        return ()
    maximum = max(record.weight for record in transitions)
    if maximum == 0:
        return tuple(DarkCandidate(record, 0.0) for record in transitions)
    return tuple(
        DarkCandidate(record, record.weight / maximum)
        for record in transitions
        if record.weight / maximum <= relative_threshold
    )
