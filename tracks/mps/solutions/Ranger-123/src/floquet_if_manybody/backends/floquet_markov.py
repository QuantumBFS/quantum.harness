"""Secular Floquet-Markov population solver."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from ..bath import bose_occupation, ohmic_spectral_density
from ..config import BathConfig
from ..floquet import FloquetSolution, micromotion, solve_floquet
from ..operators import ComplexMatrix
from .base import OpenSystemResult


@dataclass(frozen=True)
class FloquetRates:
    matrix: np.ndarray
    fourier_elements: np.ndarray


def _bath_rate(frequency: float, bath: BathConfig) -> float:
    if abs(frequency) < 1e-14:
        return 0.0
    positive = abs(frequency)
    density = float(ohmic_spectral_density(positive, bath))
    occupation = bose_occupation(positive, bath.temperature)
    return 2 * np.pi * density * (occupation + (1 if frequency > 0 else 0))


class FloquetMarkovBackend:
    method = "floquet_markov"

    def rates(
        self,
        solution: FloquetSolution,
        coupling: ComplexMatrix,
        bath: BathConfig,
        harmonic_cutoff: int,
    ) -> FloquetRates:
        cumulative = micromotion(solution)[:-1]
        steps = len(cumulative)
        omega_d = 2 * np.pi / solution.period
        times = np.arange(steps) * solution.period / steps
        dimension = coupling.shape[0]
        harmonics = np.arange(-harmonic_cutoff, harmonic_cutoff + 1)
        elements = np.zeros(
            (len(harmonics), dimension, dimension), dtype=np.complex128
        )
        for time, propagator in zip(times, cumulative, strict=True):
            periodic_modes = (
                propagator
                @ solution.modes
                @ np.diag(np.exp(1j * solution.quasienergies * time))
            )
            instantaneous = periodic_modes.conj().T @ coupling @ periodic_modes
            elements += (
                np.exp(-1j * harmonics[:, None, None] * omega_d * time)
                * instantaneous[None, :, :]
                / steps
            )

        rates = np.zeros((dimension, dimension), dtype=float)
        for target in range(dimension):
            for source in range(dimension):
                if target == source:
                    continue
                for h_index, harmonic in enumerate(harmonics):
                    emitted = (
                        solution.quasienergies[source]
                        - solution.quasienergies[target]
                        + harmonic * omega_d
                    )
                    rates[target, source] += _bath_rate(emitted, bath) * abs(
                        elements[h_index, target, source]
                    ) ** 2
        for source in range(dimension):
            rates[source, source] = -np.sum(rates[:, source])
        return FloquetRates(rates, elements)

    def run(
        self,
        hamiltonian: Callable[[float], ComplexMatrix],
        coupling: ComplexMatrix,
        bath: BathConfig,
        period: float,
        steps: int,
        harmonic_cutoff: int,
    ) -> OpenSystemResult:
        solution = solve_floquet(hamiltonian, period, steps)
        rate_data = self.rates(solution, coupling, bath, harmonic_cutoff)
        matrix = rate_data.matrix.copy()
        rhs = np.zeros(matrix.shape[0])
        matrix[-1, :] = 1
        rhs[-1] = 1
        populations, *_ = np.linalg.lstsq(matrix, rhs, rcond=None)
        populations = np.real_if_close(populations).real
        populations = np.clip(populations, 0, None)
        populations /= populations.sum()
        dimension = coupling.shape[0]
        identity = np.eye(dimension, dtype=np.complex128)
        omega_d = 2 * np.pi / period
        harmonics = np.arange(-harmonic_cutoff, harmonic_cutoff + 1)
        cumulative = micromotion(solution)[:-1]
        dt = period / steps
        step_maps: list[ComplexMatrix] = []
        for index, propagator in enumerate(cumulative):
            time = index * dt
            modes = (
                propagator
                @ solution.modes
                @ np.diag(np.exp(1j * solution.quasienergies * time))
            )
            h = hamiltonian((index + 0.5) * dt)
            liouvillian = -1j * (
                np.kron(identity, h) - np.kron(h.T, identity)
            )
            for target in range(dimension):
                for source in range(dimension):
                    if target == source:
                        continue
                    basis_jump = np.outer(modes[:, target], modes[:, source].conj())
                    for harmonic_index, harmonic in enumerate(harmonics):
                        emitted = (
                            solution.quasienergies[source]
                            - solution.quasienergies[target]
                            + harmonic * omega_d
                        )
                        gamma = _bath_rate(emitted, bath)
                        amplitude = rate_data.fourier_elements[
                            harmonic_index, target, source
                        ]
                        if gamma == 0 or abs(amplitude) < 1e-14:
                            continue
                        jump = np.sqrt(gamma) * amplitude * basis_jump
                        product = jump.conj().T @ jump
                        liouvillian += (
                            np.kron(jump.conj(), jump)
                            - 0.5 * np.kron(identity, product)
                            - 0.5 * np.kron(product.T, identity)
                        )
            step_maps.append(expm(liouvillian * dt))

        period_map = np.eye(dimension**2, dtype=np.complex128)
        for step_map in step_maps:
            period_map = step_map @ period_map
        values, vectors = np.linalg.eig(period_map)
        steady_index = int(np.argmin(abs(values - 1)))
        steady_vector = vectors[:, steady_index]
        steady_density = steady_vector.reshape((dimension, dimension), order="F")
        steady_density = (steady_density + steady_density.conj().T) / 2
        steady_density /= np.trace(steady_density)
        densities = [steady_density]
        vector = steady_density.reshape(dimension**2, order="F")
        for step_map in step_maps:
            vector = step_map @ vector
            density = vector.reshape((dimension, dimension), order="F")
            density = (density + density.conj().T) / 2
            density /= np.trace(density)
            densities.append(density)
            vector = density.reshape(dimension**2, order="F")
        rate_residual = float(np.linalg.norm(rate_data.matrix @ populations))
        map_residual = float(
            np.linalg.norm(
                period_map @ steady_density.reshape(dimension**2, order="F")
                - steady_density.reshape(dimension**2, order="F")
            )
        )
        return OpenSystemResult(
            self.method,
            np.asarray(densities),
            np.linspace(0, period, steps + 1),
            map_residual < 1e-8,
            {
                "rate_residual": rate_residual,
                "period_map_residual": map_residual,
                "trace_error": float(
                    max(abs(np.trace(density) - 1) for density in densities)
                ),
                "minimum_population": float(
                    min(np.min(np.linalg.eigvalsh(density)) for density in densities)
                ),
            },
            {
                "approximation": "Born-Markov, Floquet and full secular approximations",
                "harmonic_cutoff": harmonic_cutoff,
                "populations": populations.tolist(),
            },
            np.asarray(step_maps),
        )
