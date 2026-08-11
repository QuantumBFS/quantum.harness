"""Period-averaged correlations and coherent-harmonic decomposition."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .operators import ComplexMatrix


@dataclass(frozen=True)
class DeltaCorrelationPeak:
    harmonic: int
    frequency: float
    correlation_weight: float


@dataclass(frozen=True)
class CorrelationResult:
    delays: NDArray[np.float64]
    total: NDArray[np.complex128]
    connected: NDArray[np.complex128]
    coherent: NDArray[np.float64]
    delta_peaks: tuple[DeltaCorrelationPeak, ...]
    method: str
    metadata: dict[str, float | str]


def coherent_decomposition(
    one_point: NDArray[np.float64],
    drive_frequency: float,
    delays: NDArray[np.float64],
    threshold: float = 1e-12,
) -> tuple[NDArray[np.float64], tuple[DeltaCorrelationPeak, ...]]:
    """Compute period-averaged factorized correlation from one micromotion period."""
    if one_point.ndim != 1 or len(one_point) < 2:
        raise ValueError("one_point must contain one sampled drive period")
    coefficients = np.fft.fft(one_point) / len(one_point)
    coherent = np.full_like(delays, abs(coefficients[0]) ** 2, dtype=np.float64)
    peaks: list[DeltaCorrelationPeak] = []
    if abs(coefficients[0]) ** 2 >= threshold:
        peaks.append(DeltaCorrelationPeak(0, 0.0, float(abs(coefficients[0]) ** 2)))
    maximum = len(one_point) // 2
    for harmonic in range(1, maximum + 1):
        weight = float(2 * abs(coefficients[harmonic]) ** 2)
        if weight >= threshold:
            frequency = harmonic * drive_frequency
            coherent += weight * np.cos(frequency * delays)
            peaks.append(DeltaCorrelationPeak(harmonic, frequency, weight))
    return coherent, tuple(peaks)


def unitary_period_correlation(
    step_propagators: tuple[ComplexMatrix, ...],
    phase_densities: NDArray[np.complex128],
    operator: ComplexMatrix,
    dt: float,
    delay_steps: int,
    drive_frequency: float,
    method: str = "closed_unitary",
) -> CorrelationResult:
    """Compute Cbar(tau) by exact finite-system operator insertions.

    This routine is valid for closed dynamics. Using open-system reduced
    propagators would constitute a quantum-regression approximation and must
    carry a different method label.
    """
    period_steps = len(step_propagators)
    if phase_densities.shape[0] != period_steps:
        raise ValueError("one phase density is required per step in a period")
    total = np.zeros(delay_steps + 1, dtype=np.complex128)
    one_point = np.real(
        np.einsum("ij,tji->t", operator, phase_densities, optimize=True)
    )
    for phase in range(period_steps):
        inserted = operator @ phase_densities[phase]
        propagation = np.eye(operator.shape[0], dtype=np.complex128)
        total[0] += np.trace(operator @ inserted)
        for delay in range(1, delay_steps + 1):
            piece = step_propagators[(phase + delay - 1) % period_steps]
            propagation = piece @ propagation
            evolved = propagation @ inserted @ propagation.conj().T
            total[delay] += np.trace(operator @ evolved)
    total /= period_steps
    delays = np.arange(delay_steps + 1, dtype=np.float64) * dt
    coherent, peaks = coherent_decomposition(one_point, drive_frequency, delays)
    return CorrelationResult(
        delays,
        total,
        total - coherent,
        coherent,
        peaks,
        method,
        {"period_steps": float(period_steps), "dt": dt},
    )


def superoperator_period_correlation(
    step_maps: NDArray[np.complex128],
    phase_densities: NDArray[np.complex128],
    operator: ComplexMatrix,
    dt: float,
    delay_steps: int,
    drive_frequency: float,
    method: str = "floquet_markov_qr",
) -> CorrelationResult:
    """Two-time correlation using a periodic Markovian dynamical map.

    This is the quantum regression theorem and is only used for the explicitly
    labeled Markovian backend.
    """
    period_steps = len(step_maps)
    if phase_densities.shape[0] != period_steps:
        raise ValueError("one phase density is required per step in a period")
    dimension = operator.shape[0]
    total = np.zeros(delay_steps + 1, dtype=np.complex128)
    one_point = np.real(
        np.einsum("ij,tji->t", operator, phase_densities, optimize=True)
    )
    measurement = operator.T.reshape(dimension**2, order="F")
    for phase in range(period_steps):
        inserted = (operator @ phase_densities[phase]).reshape(
            dimension**2, order="F"
        )
        vector = inserted
        total[0] += measurement @ vector
        for delay in range(1, delay_steps + 1):
            vector = step_maps[(phase + delay - 1) % period_steps] @ vector
            total[delay] += measurement @ vector
    total /= period_steps
    delays = np.arange(delay_steps + 1, dtype=np.float64) * dt
    coherent, peaks = coherent_decomposition(one_point, drive_frequency, delays)
    return CorrelationResult(
        delays,
        total,
        total - coherent,
        coherent,
        peaks,
        method,
        {"period_steps": float(period_steps), "dt": dt},
    )
