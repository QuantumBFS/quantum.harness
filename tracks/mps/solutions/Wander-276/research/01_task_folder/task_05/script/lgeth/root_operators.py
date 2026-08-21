"""Exact monomial one-body blocks and accessibility complexes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .combinatorics import RootPartition, root_descendant_partition


@dataclass(frozen=True)
class AccessibilityComplex:
    """Two-tangent root-space accessibility complex."""

    N: int
    n: int
    k: int
    r: int
    D: int
    K1: int
    Pi1: int
    partition: RootPartition
    response_v: np.ndarray
    response_w: np.ndarray
    primitive_v: np.ndarray
    primitive_w: np.ndarray
    stacked_response: np.ndarray
    syzygy: np.ndarray


def onebody_block(
    states: tuple[tuple[int, ...], ...],
    source_indices: tuple[int, ...],
    target_indices: tuple[int, ...],
    tangent: np.ndarray,
) -> np.ndarray:
    """Return an exact monomial-basis block of a one-body representation."""

    matrix = np.asarray(tangent)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("tangent must be square")
    if not np.issubdtype(matrix.dtype, np.integer):
        raise ValueError("tangent must have integer entries")
    n_flux = matrix.shape[0]
    if any(len(state) != n_flux for state in states):
        raise ValueError("state orbital count disagrees with tangent")
    index_by_state = {state: index for index, state in enumerate(states)}
    target_row = {
        int(basis_index): row
        for row, basis_index in enumerate(target_indices)
    }
    block = np.zeros(
        (len(target_indices), len(source_indices)),
        dtype=np.int64,
    )
    for column, basis_index in enumerate(source_indices):
        state = states[int(basis_index)]
        for source, population in enumerate(state):
            if population == 0:
                continue
            for destination in range(n_flux):
                if destination == source:
                    continue
                updated = list(state)
                updated[source] -= 1
                updated[destination] += 1
                target_index = index_by_state[tuple(updated)]
                row = target_row.get(target_index)
                if row is not None:
                    block[row, column] += (
                        int(population)
                        * int(matrix[destination, source])
                    )
    return block


def accessibility_complex(
    n_particles: int,
    n_flux: int,
    tangent_v: np.ndarray,
    tangent_w: np.ndarray,
    k: int = 1,
    r: int = 2,
) -> AccessibilityComplex:
    """Construct ``P -> E+E -> Pi`` for two integer one-body tangents."""

    partition = root_descendant_partition(
        n_particles,
        n_flux,
        q=1,
        k=k,
        r=r,
    )
    response_v = onebody_block(
        partition.states,
        partition.zero_modes,
        partition.descendant_external,
        tangent_v,
    )
    response_w = onebody_block(
        partition.states,
        partition.zero_modes,
        partition.descendant_external,
        tangent_w,
    )
    primitive_v = onebody_block(
        partition.states,
        partition.descendant_external,
        partition.primitive,
        tangent_v,
    )
    primitive_w = onebody_block(
        partition.states,
        partition.descendant_external,
        partition.primitive,
        tangent_w,
    )
    stacked_response = np.concatenate(
        [response_v, response_w],
        axis=0,
    )
    syzygy = np.concatenate(
        [-primitive_w, primitive_v],
        axis=1,
    )
    return AccessibilityComplex(
        N=int(n_particles),
        n=int(n_flux),
        k=int(k),
        r=int(r),
        D=len(partition.zero_modes),
        K1=len(partition.descendant_external),
        Pi1=len(partition.primitive),
        partition=partition,
        response_v=response_v,
        response_w=response_w,
        primitive_v=primitive_v,
        primitive_w=primitive_w,
        stacked_response=stacked_response,
        syzygy=syzygy,
    )
