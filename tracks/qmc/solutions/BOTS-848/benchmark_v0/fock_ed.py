from __future__ import annotations

import itertools
import math
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=None)
def full_basis(n_electrons: int, two_q: int) -> tuple[int, ...]:
    """Return all occupation-bitset Slater determinants."""

    states = []
    for occupied in itertools.combinations(range(two_q + 1), n_electrons):
        state = 0
        for orbital in occupied:
            state |= 1 << orbital
        states.append(state)
    return tuple(states)


def total_m(state: int, *, two_q: int) -> float:
    """Total z angular momentum of an occupation bitset."""

    total_m2 = sum(
        -two_q + 2 * orbital
        for orbital in range(two_q + 1)
        if state & (1 << orbital)
    )
    return total_m2 / 2.0


def fixed_m_basis(
    n_electrons: int,
    two_q: int,
    target_m: float,
) -> tuple[int, ...]:
    """Return determinants with the requested total magnetic quantum number."""

    target_m2 = round(2.0 * target_m)
    if not math.isclose(2.0 * target_m, target_m2, abs_tol=1.0e-12):
        raise ValueError("target_m must be an integer or half-integer")
    return tuple(
        state
        for state in full_basis(n_electrons, two_q)
        if round(2.0 * total_m(state, two_q=two_q)) == target_m2
    )


def apply_annihilation(state: int, orbital: int) -> tuple[int, int] | None:
    """Apply a fermion annihilation operator to an occupation bitset."""

    mask = 1 << orbital
    if not state & mask:
        return None
    lower_occupancy = (state & (mask - 1)).bit_count()
    sign = -1 if lower_occupancy % 2 else 1
    return state ^ mask, sign


def apply_creation(state: int, orbital: int) -> tuple[int, int] | None:
    """Apply a fermion creation operator to an occupation bitset."""

    mask = 1 << orbital
    if state & mask:
        return None
    lower_occupancy = (state & (mask - 1)).bit_count()
    sign = -1 if lower_occupancy % 2 else 1
    return state | mask, sign


def apply_two_body(
    state: int,
    *,
    a: int,
    b: int,
    c: int,
    d: int,
) -> tuple[int, int] | None:
    """Apply ``c_a^dagger c_b^dagger c_d c_c`` to ``state``."""

    sign = 1
    current = state
    for operation, orbital in (
        (apply_annihilation, c),
        (apply_annihilation, d),
        (apply_creation, b),
        (apply_creation, a),
    ):
        result = operation(current, orbital)
        if result is None:
            return None
        current, step_sign = result
        sign *= step_sign
    return current, sign


def hamiltonian_matrix(
    basis: tuple[int, ...],
    pairs: tuple[tuple[int, int], ...],
    pair_matrix: np.ndarray,
) -> np.ndarray:
    """Build the two-body Hamiltonian in a supplied determinant basis."""

    state_to_index = {state: index for index, state in enumerate(basis)}
    hamiltonian = np.zeros((len(basis), len(basis)), dtype=np.complex128)
    for source_index, source in enumerate(basis):
        for source_pair_index, (c, d) in enumerate(pairs):
            if not (source & (1 << c) and source & (1 << d)):
                continue
            for target_pair_index, (a, b) in enumerate(pairs):
                matrix_element = pair_matrix[target_pair_index, source_pair_index]
                if abs(matrix_element) < 1.0e-15:
                    continue
                applied = apply_two_body(source, a=a, b=b, c=c, d=d)
                if applied is None:
                    continue
                target, sign = applied
                row = state_to_index.get(target)
                if row is not None:
                    hamiltonian[row, source_index] += sign * matrix_element
    return hamiltonian


def l_plus_matrix(
    source_basis: tuple[int, ...],
    target_basis: tuple[int, ...],
    *,
    two_q: int,
) -> np.ndarray:
    """Matrix of the total angular-momentum raising operator."""

    target_index = {state: index for index, state in enumerate(target_basis)}
    matrix = np.zeros((len(target_basis), len(source_basis)), dtype=float)
    for column, source in enumerate(source_basis):
        for orbital in range(two_q):
            if not source & (1 << orbital):
                continue
            annihilated = apply_annihilation(source, orbital)
            if annihilated is None:
                continue
            intermediate, sign_1 = annihilated
            created = apply_creation(intermediate, orbital + 1)
            if created is None:
                continue
            target, sign_2 = created
            row = target_index.get(target)
            if row is not None:
                coefficient = math.sqrt((two_q - orbital) * (orbital + 1))
                matrix[row, column] += sign_1 * sign_2 * coefficient
    return matrix


def l_squared_matrix(
    basis: tuple[int, ...],
    *,
    two_q: int,
    target_m: float,
) -> np.ndarray:
    """Construct ``L_- L_+ + M(M+1)`` in a fixed-M basis."""

    n_electrons = basis[0].bit_count() if basis else 0
    raised_basis = fixed_m_basis(n_electrons, two_q, target_m + 1.0)
    l_plus = l_plus_matrix(basis, raised_basis, two_q=two_q)
    return l_plus.T @ l_plus + target_m * (target_m + 1.0) * np.eye(len(basis))
