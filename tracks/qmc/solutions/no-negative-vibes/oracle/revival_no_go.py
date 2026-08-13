"""No-go certificates found by reappraising archived positive semigroups."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class AdjointClosureCounterexample:
    """Two legal generators whose Hermitian adjoint word is negative."""

    generators: tuple[np.ndarray, np.ndarray]
    atoms: tuple[np.ndarray, np.ndarray]
    product: np.ndarray
    determinant_weight: float
    minimum_singular_value: float


def permutation_matrix(permutation: Sequence[int]) -> np.ndarray:
    """Return the matrix mapping column ``j`` to row ``permutation[j]``."""

    values = tuple(int(value) for value in permutation)
    if sorted(values) != list(range(len(values))):
        raise ValueError("permutation must contain every mode exactly once")
    matrix = np.zeros((len(values), len(values)))
    matrix[np.asarray(values), np.arange(len(values))] = 1.0
    return matrix


def fock_permutation_action(
    permutation: Sequence[int],
    state: int,
) -> tuple[int, int]:
    """Return target occupation bitstring and fermionic permutation sign."""

    values = tuple(int(value) for value in permutation)
    if sorted(values) != list(range(len(values))):
        raise ValueError("permutation must contain every mode exactly once")
    if not 0 <= state < (1 << len(values)):
        raise ValueError("state is outside the Fock basis")
    occupied_targets = [
        values[source]
        for source in range(len(values))
        if (state >> source) & 1
    ]
    inversions = sum(
        occupied_targets[left] > occupied_targets[right]
        for left in range(len(occupied_targets))
        for right in range(left + 1, len(occupied_targets))
    )
    target = sum(1 << mode for mode in occupied_targets)
    return target, (-1 if inversions % 2 else 1)


def common_fock_permutation_gauge(
    permutations: Sequence[Sequence[int]],
) -> np.ndarray:
    """Gauge a family of signed Fock permutations to nonnegative matrices.

    A contradiction is a negative stabilizer loop.  For a permutation group
    of odd order no such loop exists: a stabilizer sign is a homomorphism
    from an odd-order group to ``{+/-1}``, hence is trivial.
    """

    family = tuple(tuple(int(value) for value in item) for item in permutations)
    if not family:
        raise ValueError("at least one permutation is required")
    modes = len(family[0])
    if any(len(item) != modes for item in family):
        raise ValueError("all permutations must have the same size")
    for item in family:
        permutation_matrix(item)

    dimension = 1 << modes
    phases = np.zeros(dimension, dtype=np.int8)
    for root in range(dimension):
        if phases[root] != 0:
            continue
        phases[root] = 1
        queue: deque[int] = deque([root])
        while queue:
            state = queue.popleft()
            for permutation in family:
                target, sign = fock_permutation_action(permutation, state)
                expected = phases[state] * sign
                if phases[target] == 0:
                    phases[target] = expected
                    queue.append(target)
                elif phases[target] != expected:
                    raise ValueError(
                        "signed Fock action has a negative stabilizer loop"
                    )
    return phases


def diagonal_sign_transform(matrix: np.ndarray, gauge: np.ndarray) -> np.ndarray:
    """Return ``S matrix S`` for diagonal ``S=diag(gauge)``."""

    candidate = np.asarray(matrix)
    signs = np.asarray(gauge)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError("matrix must be square")
    if signs.shape != (candidate.shape[0],):
        raise ValueError("gauge dimension must match matrix")
    return signs[:, None] * candidate * signs[None, :]


def fixed_linf_adjoint_counterexample(
    *,
    shear: float = 3.0,
    metric_ratio: float = 8.0,
) -> AdjointClosureCounterexample:
    """Return a depth-two failure of Hermitianizing fixed-linf atoms.

    Both generators saturate the same weighted logarithmic infinity-norm
    bound for metric ``(metric_ratio, 1)``.  The negative word uses the
    first atom and the transpose of the opposite-shear atom.
    """

    if shear <= 0.0 or metric_ratio <= 1.0:
        raise ValueError("require positive shear and metric_ratio > 1")
    damping = shear / metric_ratio
    positive_generator = np.asarray([[-damping, shear], [0.0, 0.0]])
    negative_generator = np.asarray([[-damping, -shear], [0.0, 0.0]])
    contraction = math.exp(-damping)
    propagated_shear = metric_ratio * (1.0 - contraction)
    positive_atom = np.asarray(
        [[contraction, propagated_shear], [0.0, 1.0]]
    )
    negative_atom = np.asarray(
        [[contraction, -propagated_shear], [0.0, 1.0]]
    )
    product_matrix = positive_atom @ negative_atom.T
    shifted = np.eye(2) + product_matrix
    return AdjointClosureCounterexample(
        generators=(positive_generator, negative_generator),
        atoms=(positive_atom, negative_atom),
        product=product_matrix,
        determinant_weight=float(np.linalg.det(shifted)),
        minimum_singular_value=float(
            np.linalg.svd(shifted, compute_uv=False)[-1]
        ),
    )


def reciprocal_parabolic_adjoint_counterexample(
    *,
    shear: float = 3.0,
) -> AdjointClosureCounterexample:
    """Return the exact ``4-shear**2`` reciprocal adjoint failure."""

    if shear <= 0.0:
        raise ValueError("shear must be positive")
    positive_generator = np.asarray([[0.0, shear], [0.0, 0.0]])
    negative_generator = np.asarray([[0.0, -shear], [0.0, 0.0]])
    positive_atom = np.eye(2) + positive_generator
    negative_atom = np.eye(2) + negative_generator
    product_matrix = positive_atom @ negative_atom.T
    shifted = np.eye(2) + product_matrix
    return AdjointClosureCounterexample(
        generators=(positive_generator, negative_generator),
        atoms=(positive_atom, negative_atom),
        product=product_matrix,
        determinant_weight=float(np.linalg.det(shifted)),
        minimum_singular_value=float(
            np.linalg.svd(shifted, compute_uv=False)[-1]
        ),
    )
