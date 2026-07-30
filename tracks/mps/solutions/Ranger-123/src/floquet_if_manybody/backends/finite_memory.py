"""Brute-force augmented-density-tensor influence-functional backend.

This is a transparent finite-memory QUAPI implementation for few-level
validation. Its cost is O((d^2)^(K+1)); it intentionally refuses unsafe sizes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

import numpy as np
from scipy.linalg import expm

from ..config import BathConfig
from ..influence import InfluenceCoefficients, discretize_influence
from ..operators import ComplexMatrix
from .base import OpenSystemResult


def _trace_from_vector(vector: np.ndarray, dimension: int) -> complex:
    return complex(sum(vector[index * dimension + index] for index in range(dimension)))


class FiniteMemoryBackend:
    """Finite-memory path sum in the coupling-operator eigenbasis."""

    method = "finite_memory_if"

    def __init__(self, max_augmented_elements: int = 2_000_000):
        self.max_augmented_elements = max_augmented_elements

    @staticmethod
    def _influence_table(
        eigenvalues: np.ndarray, coefficients: InfluenceCoefficients, depth: int
    ) -> np.ndarray:
        dimension = len(eigenvalues)
        q = dimension**2
        pairs = [(plus, minus) for plus in range(dimension) for minus in range(dimension)]
        shape = (q,) * (depth + 1)
        table = np.ones(shape, dtype=np.complex128)
        for new_index, (new_plus, new_minus) in enumerate(pairs):
            delta = eigenvalues[new_plus] - eigenvalues[new_minus]
            for indices in np.ndindex(*(q,) * depth):
                exponent = 0.0j
                for lag, history_index in enumerate(indices, start=1):
                    old_plus, old_minus = pairs[history_index]
                    eta = coefficients.values[lag]
                    exponent -= delta * (
                        eta * eigenvalues[old_plus] - eta.conjugate() * eigenvalues[old_minus]
                    )
                eta0 = coefficients.values[0]
                exponent -= delta * (
                    eta0 * eigenvalues[new_plus]
                    - eta0.conjugate() * eigenvalues[new_minus]
                )
                table[(new_index, *indices)] = np.exp(exponent)
        return table

    def run(
        self,
        hamiltonian: Callable[[float], ComplexMatrix],
        coupling: ComplexMatrix,
        initial_density: ComplexMatrix,
        bath: BathConfig,
        dt: float,
        steps: int,
        memory_steps: int,
    ) -> OpenSystemResult:
        if steps < 1:
            raise ValueError("steps must be positive")
        eigenvalues, basis = np.linalg.eigh(coupling)
        dimension = coupling.shape[0]
        q = dimension**2
        augmented_size = q ** (memory_steps + 1)
        if augmented_size > self.max_augmented_elements:
            raise ValueError(
                f"augmented tensor requires {augmented_size} elements; "
                f"limit is {self.max_augmented_elements}"
            )
        coefficients = discretize_influence(bath, dt, memory_steps)
        rho = basis.conj().T @ initial_density @ basis
        augmented = rho.reshape(q).copy()
        histories = 1
        output = [initial_density.copy()]
        maximum_trace_error = 0.0
        minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(initial_density)))

        for step in range(steps):
            midpoint = (step + 0.5) * dt
            transformed_h = basis.conj().T @ hamiltonian(midpoint) @ basis
            unitary = expm(-1j * transformed_h * dt)
            propagator = np.einsum("ac,bd->abcd", unitary, unitary.conj()).reshape(q, q)
            active_depth = min(histories, memory_steps)
            table = self._influence_table(eigenvalues, coefficients, active_depth)
            transition_shape = (q, q) + (1,) * (active_depth - 1)
            expanded = propagator.reshape(transition_shape) * augmented[np.newaxis, ...] * table
            if histories >= memory_steps:
                augmented = expanded.sum(axis=-1)
            else:
                augmented = expanded
                histories += 1
            reduced = augmented
            while reduced.ndim > 1:
                reduced = reduced.sum(axis=-1)
            trace = _trace_from_vector(reduced, dimension)
            maximum_trace_error = max(maximum_trace_error, abs(trace - 1))
            if abs(trace) > 1e-14:
                augmented /= trace
                reduced /= trace
            rho_s = reduced.reshape(dimension, dimension)
            rho_lab = basis @ rho_s @ basis.conj().T
            rho_lab = (rho_lab + rho_lab.conj().T) / 2
            minimum_eigenvalue = min(minimum_eigenvalue, float(np.min(np.linalg.eigvalsh(rho_lab))))
            output.append(rho_lab)

        diagnostics = {
            "trace_error": maximum_trace_error,
            "minimum_density_eigenvalue": minimum_eigenvalue,
            "quadrature_error": coefficients.quadrature_error,
            "correlation_tail_bound": coefficients.tail_bound,
        }
        converged = maximum_trace_error < 1e-8 and minimum_eigenvalue > -1e-6
        return OpenSystemResult(
            self.method,
            np.asarray(output),
            np.asarray(np.arange(steps + 1) * dt, dtype=np.float64),
            converged,
            diagnostics,
            {
                "bath": asdict(bath),
                "dt": dt,
                "memory_steps": memory_steps,
                "approximation": "finite timestep and hard memory cutoff",
            },
        )
