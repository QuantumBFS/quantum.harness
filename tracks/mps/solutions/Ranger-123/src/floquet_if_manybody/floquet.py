"""Direct finite-dimensional Floquet propagation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import expm

from .operators import ComplexMatrix


@dataclass(frozen=True)
class FloquetSolution:
    propagator: ComplexMatrix
    quasienergies: NDArray[np.float64]
    modes: ComplexMatrix
    period: float
    step_propagators: tuple[ComplexMatrix, ...]
    unitarity_residual: float
    eigen_residual: float


def one_period_propagator(
    hamiltonian: Callable[[float], ComplexMatrix],
    period: float,
    steps: int,
) -> tuple[ComplexMatrix, tuple[ComplexMatrix, ...]]:
    if period <= 0 or steps < 1:
        raise ValueError("period and steps must be positive")
    dt = period / steps
    dimension = hamiltonian(0.0).shape[0]
    total = np.eye(dimension, dtype=np.complex128)
    pieces: list[ComplexMatrix] = []
    for index in range(steps):
        midpoint = (index + 0.5) * dt
        piece = expm(-1j * hamiltonian(midpoint) * dt)
        pieces.append(piece)
        total = piece @ total
    return total, tuple(pieces)


def solve_floquet(
    hamiltonian: Callable[[float], ComplexMatrix],
    period: float,
    steps: int,
) -> FloquetSolution:
    total, pieces = one_period_propagator(hamiltonian, period, steps)
    values, modes = np.linalg.eig(total)
    phases = np.angle(values)
    quasienergies = -phases / period
    order = np.argsort(quasienergies)
    quasienergies = quasienergies[order].astype(np.float64)
    modes = modes[:, order]
    modes /= np.linalg.norm(modes, axis=0)
    identity = np.eye(total.shape[0])
    unitarity = float(np.linalg.norm(total.conj().T @ total - identity))
    residual = float(
        np.linalg.norm(total @ modes - modes * np.exp(-1j * quasienergies * period))
    )
    return FloquetSolution(
        total,
        quasienergies,
        modes,
        period,
        pieces,
        unitarity,
        residual,
    )


def micromotion(solution: FloquetSolution) -> tuple[ComplexMatrix, ...]:
    """Return cumulative propagators at all step boundaries, including t=0."""
    values = [np.eye(solution.propagator.shape[0], dtype=np.complex128)]
    for piece in solution.step_propagators:
        values.append(piece @ values[-1])
    return tuple(values)
