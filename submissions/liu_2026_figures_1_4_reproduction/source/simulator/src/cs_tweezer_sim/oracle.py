"""Privileged validator-only access to simulator truth."""

from __future__ import annotations

import itertools

import numpy as np
import qutip as qt

from .contracts import ExperimentProgram
from .backend import PhysicsBackend, SimulationContext


class TruthOracle:
    """Exact diagnostics that must never be passed to an online controller."""

    def __init__(self, backend: PhysicsBackend):
        self._backend = backend

    def final_density_matrix(
        self,
        program: ExperimentProgram,
        *,
        context: SimulationContext | None = None,
    ) -> np.ndarray:
        snapshot = self._backend.simulate(program, context=context)
        state = snapshot.state
        density = qt.ket2dm(state) if state.isket else state
        return np.asarray(density.full(), dtype=complex)

    def outcome_probabilities(
        self,
        program: ExperimentProgram,
        *,
        context: SimulationContext | None = None,
    ) -> dict[str, float]:
        snapshot = self._backend.simulate(program, context=context)
        return self._backend.outcome_probabilities(snapshot.state)

    def outcome_probabilities_from_local_levels(
        self,
        program: ExperimentProgram,
        levels: tuple[str, ...],
        *,
        context: SimulationContext | None = None,
    ) -> dict[str, float]:
        """Validator-only evolution from non-computational physical levels."""

        initial = self._backend.local_level_product_state(levels)
        snapshot = self._backend.simulate(
            program,
            initial_state=initial,
            ignore_prepare=True,
            context=context,
        )
        return self._backend.outcome_probabilities(snapshot.state)

    def computational_map(
        self,
        program: ExperimentProgram,
        *,
        context: SimulationContext | None = None,
    ) -> np.ndarray:
        """Project a coherent program onto the computational subspace.

        Preparation operations are ignored so that the same user-level gate
        program can be evaluated on every computational input.
        """

        bitstrings = tuple(
            "".join(bits)
            for bits in itertools.product(("0", "1"), repeat=self._backend.n_atoms)
        )
        projected = np.zeros((len(bitstrings), len(bitstrings)), dtype=complex)
        for column, bits in enumerate(bitstrings):
            initial = self._backend.computational_basis_state(bits)
            snapshot = self._backend.simulate(
                program,
                initial_state=initial,
                ignore_prepare=True,
                context=context,
            )
            projected[:, column] = self._backend.computational_amplitudes(
                snapshot.state
            )
        return projected

    @staticmethod
    def process_overlap(target: np.ndarray, actual: np.ndarray) -> float:
        """Return the leakage-sensitive squared normalized trace overlap."""

        if target.shape != actual.shape or target.ndim != 2:
            raise ValueError("target and actual maps must be square and shape-matched")
        dimension = target.shape[0]
        return float(abs(np.trace(target.conj().T @ actual)) ** 2 / dimension**2)
