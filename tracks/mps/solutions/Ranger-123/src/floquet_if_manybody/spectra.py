"""Hermitian spectra and symmetry-resolved bright transitions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .operators import ComplexMatrix


@dataclass(frozen=True)
class Spectrum:
    energies: NDArray[np.float64]
    states: ComplexMatrix


@dataclass(frozen=True)
class Transition:
    source: int
    target: int
    frequency: float
    weight: float
    amplitude: complex


def diagonalize(hamiltonian: ComplexMatrix) -> Spectrum:
    if not np.allclose(hamiltonian, hamiltonian.conj().T, atol=1e-12):
        raise ValueError("hamiltonian must be Hermitian")
    energies, states = np.linalg.eigh(hamiltonian)
    for column in range(states.shape[1]):
        pivot = int(np.argmax(np.abs(states[:, column])))
        phase = np.angle(states[pivot, column])
        states[:, column] *= np.exp(-1j * phase)
    return Spectrum(energies.astype(np.float64), states)


def transitions(
    source: Spectrum,
    target: Spectrum,
    operator: ComplexMatrix,
    threshold: float = 1e-12,
) -> list[Transition]:
    if operator.shape != (target.states.shape[0], source.states.shape[0]):
        raise ValueError("transition operator has incompatible dimensions")
    matrix = target.states.conj().T @ operator @ source.states
    out: list[Transition] = []
    for target_index in range(len(target.energies)):
        for source_index in range(len(source.energies)):
            amplitude = matrix[target_index, source_index]
            weight = float(abs(amplitude) ** 2)
            if weight >= threshold:
                out.append(
                    Transition(
                        source_index,
                        target_index,
                        float(target.energies[target_index] - source.energies[source_index]),
                        weight,
                        complex(amplitude),
                    )
                )
    return out


def ground_bright_transitions(
    ground_sector: Spectrum,
    opposite_sector: Spectrum,
    cross_operator: ComplexMatrix,
    threshold: float = 1e-12,
) -> list[Transition]:
    candidates = transitions(ground_sector, opposite_sector, cross_operator, threshold)
    return sorted(
        [item for item in candidates if item.source == 0 and item.frequency > 0],
        key=lambda item: item.frequency,
    )
