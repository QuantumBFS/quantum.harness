"""Sparse assembly of antisymmetric two-body tensors between determinant bases."""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations
from math import comb

import numpy as np
from scipy import sparse

from challenge15.fermions import (
    DeterminantBasis,
    apply_annihilation,
    apply_creation,
)
from challenge15.spec import SphereSpec


def assemble_two_body(
    domain: DeterminantBasis,
    codomain: DeterminantBasis,
    tensor: np.ndarray,
) -> sparse.csr_matrix:
    """Assemble ``(1/2) A_abcd c†_a c†_b c_d c_c`` between two bases."""

    array, component_shift = _validated_tensor(domain, codomain, tensor)
    target_pairs_by_two_m = _orbital_pairs_by_two_m(domain.spec.particles)
    compact_full_basis = (
        component_shift == 0
        and _is_unrestricted_full_basis(domain)
        and _is_unrestricted_full_basis(codomain)
    )
    capacity = (
        _legal_transition_capacity(domain)
        if compact_full_basis
        else _exact_transition_capacity(
            domain,
            codomain,
            array,
            component_shift,
            target_pairs_by_two_m,
        )
    )
    rows = np.empty(capacity, dtype=np.int64)
    columns = np.empty(capacity, dtype=np.int64)
    data = np.empty(capacity, dtype=np.result_type(array.dtype, np.float64))
    used = 0

    for transition in _iter_transitions(
        domain,
        codomain,
        array,
        component_shift,
        target_pairs_by_two_m,
    ):
        row, column, element = transition
        rows[used] = row
        columns[used] = column
        data[used] = element
        used += 1

    if not compact_full_basis:
        assert used == capacity
    matrix = sparse.csr_matrix(
        (data[:used], (rows[:used], columns[:used])),
        shape=(codomain.dimension, domain.dimension),
    )
    matrix.sum_duplicates()
    matrix.eliminate_zeros()
    return matrix


def _validated_tensor(
    domain: DeterminantBasis,
    codomain: DeterminantBasis,
    tensor: np.ndarray,
) -> tuple[np.ndarray, int]:
    if domain.spec != codomain.spec:
        raise ValueError("domain and codomain must have equal SphereSpec")

    count = domain.spec.orbital_count
    array = np.asarray(tensor)
    if array.shape != (count, count, count, count):
        raise ValueError("tensor shape must be (orbital_count,) repeated four times")

    shifts = _nonzero_component_shifts(domain.spec, array)
    if len(shifts) > 1:
        raise ValueError("nonzero tensor entries must imply one sector shift")
    component_shift = next(iter(shifts), 0)

    domain_two_m = domain.total_two_m
    codomain_two_m = codomain.total_two_m
    if (domain_two_m is None) != (codomain_two_m is None):
        raise ValueError("domain and codomain must use compatible sectors")
    if domain_two_m is None:
        if component_shift != 0:
            raise ValueError("full-basis assembly requires a scalar sector shift")
    elif shifts and codomain_two_m - domain_two_m != component_shift:
        raise ValueError("tensor component does not match the basis sector shift")
    return array, component_shift


def _nonzero_component_shifts(spec: SphereSpec, tensor: np.ndarray) -> set[int]:
    shifts: set[int] = set()
    for a, b, c, d in np.argwhere(tensor != 0):
        shifts.add(
            spec.two_m_values[int(a)]
            + spec.two_m_values[int(b)]
            - spec.two_m_values[int(c)]
            - spec.two_m_values[int(d)]
        )
        if len(shifts) > 1:
            break
    return shifts


def _iter_transitions(
    domain: DeterminantBasis,
    codomain: DeterminantBasis,
    tensor: np.ndarray,
    component_shift: int,
    target_pairs_by_two_m: dict[int, tuple[tuple[int, int, int], ...]],
):
    count = domain.spec.orbital_count
    for column, state in enumerate(domain.states):
        occupied = tuple(index for index in range(count) if state & (1 << index))
        for c, d in combinations(occupied, 2):
            after_c = apply_annihilation(state, c)
            assert after_c is not None
            after_d = apply_annihilation(after_c.state, d)
            assert after_d is not None
            source_two_m = domain.spec.two_m_values[c] + domain.spec.two_m_values[d]
            target_two_m = source_two_m + component_shift
            for a, b, pair_mask in target_pairs_by_two_m.get(target_two_m, ()):
                if after_d.state & pair_mask:
                    continue
                element = 2.0 * tensor[a, b, c, d]
                if element == 0.0:
                    continue
                after_b = apply_creation(after_d.state, b)
                assert after_b is not None
                after_a = apply_creation(after_b.state, a)
                assert after_a is not None
                row = codomain.state_index.get(after_a.state)
                if row is None:
                    continue
                yield (
                    row,
                    column,
                    element
                    * after_c.sign
                    * after_d.sign
                    * after_b.sign
                    * after_a.sign,
                )


def _exact_transition_capacity(
    domain: DeterminantBasis,
    codomain: DeterminantBasis,
    tensor: np.ndarray,
    component_shift: int,
    target_pairs_by_two_m: dict[int, tuple[tuple[int, int, int], ...]],
) -> int:
    return sum(
        1
        for _ in _iter_transitions(
            domain,
            codomain,
            tensor,
            component_shift,
            target_pairs_by_two_m,
        )
    )


def _legal_transition_capacity(basis: DeterminantBasis) -> int:
    """Count M-preserving legal pair substitutions for scalar assembly."""

    target_pairs_by_two_m = _orbital_pairs_by_two_m(basis.spec.particles)
    if _is_unrestricted_full_basis(basis):
        count = basis.spec.orbital_count
        particles = basis.spec.particles
        capacity = 0
        for pairs in target_pairs_by_two_m.values():
            for _, _, source_mask in pairs:
                for _, _, target_mask in pairs:
                    union_size = (source_mask | target_mask).bit_count()
                    capacity += comb(count - union_size, particles - 2)
        return capacity

    capacity = 0
    for state in basis.states:
        occupied = tuple(
            index
            for index in range(basis.spec.orbital_count)
            if state & (1 << index)
        )
        for c, d in combinations(occupied, 2):
            remaining = state ^ (1 << c) ^ (1 << d)
            source_two_m = basis.spec.two_m_values[c] + basis.spec.two_m_values[d]
            capacity += sum(
                not bool(remaining & pair_mask)
                for _, _, pair_mask in target_pairs_by_two_m[source_two_m]
            )
    return capacity


@lru_cache(maxsize=None)
def _orbital_pairs_by_two_m(
    particles: int,
) -> dict[int, tuple[tuple[int, int, int], ...]]:
    spec = SphereSpec(particles)
    grouped: dict[int, list[tuple[int, int, int]]] = {}
    for a, b in combinations(range(spec.orbital_count), 2):
        two_m = spec.two_m_values[a] + spec.two_m_values[b]
        grouped.setdefault(two_m, []).append((a, b, (1 << a) | (1 << b)))
    return {two_m: tuple(pairs) for two_m, pairs in grouped.items()}


def _is_unrestricted_full_basis(basis: DeterminantBasis) -> bool:
    if basis.total_two_m is not None or basis.dimension != basis.spec.full_dimension:
        return False
    return basis.states == DeterminantBasis.full(basis.spec).states
