"""Local orthogonal-contraction Hamiltonians revived from the norm route."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.linalg import expm

from oracle.semigroup_model_factory import (
    HermitianSemigroupModel,
    hermitian_semigroup_model,
)


@dataclass(frozen=True)
class StoquasticCycleAudit:
    """Occupation-graph result for diagonal ``+/-1`` sign gauges."""

    gauge_exists: bool
    frustrated_cycle: tuple[int, ...] | None
    cycle_matrix_elements: tuple[float, ...]
    component_sizes: tuple[int, ...]
    component_particle_numbers: tuple[tuple[int, ...], ...]


_INTEGER_GENERATORS = (
    np.asarray(
        [
            [0, 1, -1, -1],
            [-1, 0, 1, 0],
            [1, -1, 0, -1],
            [1, 0, 1, 0],
        ],
        dtype=float,
    ),
    np.asarray(
        [
            [0, -1, -1, 1],
            [1, 0, 1, -1],
            [1, -1, 0, -1],
            [-1, 1, 1, 0],
        ],
        dtype=float,
    ),
)


def orthogonal_plaquette_generators(
    *,
    scale: float = 0.6,
) -> tuple[np.ndarray, np.ndarray]:
    """Return two explicit noncommuting real skew generators."""

    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale must be positive and finite")
    return tuple(scale * item for item in _INTEGER_GENERATORS)  # type: ignore[return-value]


def orthogonal_plaquette_atoms(
    *,
    scale: float = 0.6,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the corresponding two ``SO(4)`` one-particle vertices."""

    return tuple(
        expm(generator)
        for generator in orthogonal_plaquette_generators(scale=scale)
    )  # type: ignore[return-value]


def build_orthogonal_plaquette_model(
    *,
    scale: float = 0.6,
    coefficients: Sequence[float] = (1.0, 0.8),
) -> HermitianSemigroupModel:
    """Build the four-mode interacting Hamiltonian anchor."""

    return hermitian_semigroup_model(
        orthogonal_plaquette_atoms(scale=scale),
        coefficients,
    )


def embed_orthogonal_plaquette_atoms(
    *,
    modes: int,
    plaquettes: Sequence[Sequence[int]],
    scale: float = 0.6,
) -> tuple[np.ndarray, ...]:
    """Embed the two local ``SO(4)`` vertices on each four-mode plaquette."""

    if modes < 4:
        raise ValueError("at least four modes are required")
    local_atoms = orthogonal_plaquette_atoms(scale=scale)
    embedded: list[np.ndarray] = []
    for plaquette in plaquettes:
        support = tuple(int(mode) for mode in plaquette)
        if len(support) != 4 or len(set(support)) != 4:
            raise ValueError("each plaquette must contain four distinct modes")
        if any(not 0 <= mode < modes for mode in support):
            raise ValueError("plaquette mode is outside the lattice")
        for atom in local_atoms:
            full = np.eye(modes)
            full[np.ix_(support, support)] = atom
            embedded.append(full)
    if not embedded:
        raise ValueError("at least one plaquette is required")
    return tuple(embedded)


def stoquastic_cycle_audit(
    hamiltonian: np.ndarray,
    *,
    tolerance: float = 1e-12,
) -> StoquasticCycleAudit:
    """Find a frustrated sign cycle or return a valid diagonal gauge."""

    matrix = np.asarray(hamiltonian, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("hamiltonian must be square")
    dimension = matrix.shape[0]
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(dimension)]
    for left in range(dimension):
        for right in range(left + 1, dimension):
            if abs(matrix[left, right]) <= tolerance:
                continue
            required = -1 if matrix[left, right] > 0.0 else 1
            adjacency[left].append((right, required))
            adjacency[right].append((left, required))

    phases = np.zeros(dimension, dtype=np.int8)
    parents = np.full(dimension, -1, dtype=int)
    components: list[tuple[int, ...]] = []
    conflict: tuple[int, int] | None = None
    for root in range(dimension):
        if phases[root] != 0:
            continue
        phases[root] = 1
        queue: deque[int] = deque([root])
        component: list[int] = []
        while queue:
            state = queue.popleft()
            component.append(state)
            for target, required in adjacency[state]:
                expected = phases[state] * required
                if phases[target] == 0:
                    phases[target] = expected
                    parents[target] = state
                    queue.append(target)
                elif phases[target] != expected and conflict is None:
                    conflict = (state, target)
        components.append(tuple(component))

    cycle: tuple[int, ...] | None = None
    elements: tuple[float, ...] = ()
    if conflict is not None:
        left, right = conflict
        left_path: list[int] = []
        cursor = left
        while cursor != -1:
            left_path.append(cursor)
            cursor = int(parents[cursor])
        right_path: list[int] = []
        cursor = right
        while cursor != -1:
            right_path.append(cursor)
            cursor = int(parents[cursor])
        left_positions = {
            state: index for index, state in enumerate(left_path)
        }
        common = next(state for state in right_path if state in left_positions)
        open_cycle = (
            left_path[: left_positions[common] + 1]
            + list(reversed(right_path[: right_path.index(common)]))
        )
        cycle = tuple(open_cycle + [left])
        elements = tuple(
            float(matrix[cycle[index], cycle[index + 1]])
            for index in range(len(cycle) - 1)
        )

    ordered_components = sorted(components, key=lambda item: (len(item), item))
    return StoquasticCycleAudit(
        gauge_exists=conflict is None,
        frustrated_cycle=cycle,
        cycle_matrix_elements=elements,
        component_sizes=tuple(len(item) for item in ordered_components),
        component_particle_numbers=tuple(
            tuple(sorted({state.bit_count() for state in item}))
            for item in ordered_components
        ),
    )
