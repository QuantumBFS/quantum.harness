from __future__ import annotations

import sympy as sp


_TWO_PARTICLE_STATES = (0b0011, 0b0101, 0b1001, 0b0110, 0b1010, 0b1100)


def _mode_count(dimension: int) -> int:
    if dimension <= 1 or dimension & (dimension - 1):
        raise ValueError("gate dimension must be a power of two greater than one")
    return dimension.bit_length() - 1


def _preserves_local_parity(gate: sp.MatrixBase, modes: int) -> bool:
    for left in range(1 << modes):
        for right in range(1 << modes):
            if (left.bit_count() - right.bit_count()) % 2:
                if sp.simplify(gate[left, right]) != 0:
                    return False
    return True


def klein_hodge_gate() -> sp.ImmutableSparseMatrix:
    inverse_sqrt_two = 1 / sp.sqrt(2)
    two_particle_block = sp.ImmutableSparseMatrix(
        [
            [inverse_sqrt_two, 0, 0, 0, 0, inverse_sqrt_two],
            [inverse_sqrt_two, 0, 0, 0, 0, -inverse_sqrt_two],
            [0, inverse_sqrt_two, 0, 0, -inverse_sqrt_two, 0],
            [0, inverse_sqrt_two, 0, 0, inverse_sqrt_two, 0],
            [0, 0, inverse_sqrt_two, inverse_sqrt_two, 0, 0],
            [0, 0, inverse_sqrt_two, -inverse_sqrt_two, 0, 0],
        ]
    )
    gate = sp.eye(16)
    for row, target_state in enumerate(_TWO_PARTICLE_STATES):
        for column, source_state in enumerate(_TWO_PARTICLE_STATES):
            gate[target_state, source_state] = two_particle_block[row, column]
    return sp.ImmutableSparseMatrix(gate)


def embed_contiguous_even_gate(
    gate: sp.MatrixBase, *, start: int, total_modes: int
) -> sp.ImmutableSparseMatrix:
    if gate.rows != gate.cols:
        raise ValueError("gate must be square")
    local_modes = _mode_count(gate.rows)
    if not isinstance(start, int) or not isinstance(total_modes, int):
        raise TypeError("start and total_modes must be integers")
    if total_modes <= 0 or start < 0 or start + local_modes > total_modes:
        raise ValueError("gate must occupy a sorted contiguous block within total_modes")
    if not _preserves_local_parity(gate, local_modes):
        raise ValueError("gate must preserve local fermion parity")

    lower_identity = sp.ImmutableSparseMatrix(sp.eye(1 << start))
    upper_modes = total_modes - start - local_modes
    upper_identity = sp.ImmutableSparseMatrix(sp.eye(1 << upper_modes))
    embedded = sp.kronecker_product(upper_identity, gate, lower_identity)
    return sp.ImmutableSparseMatrix(embedded)


def overlap_klein_circuit() -> sp.ImmutableSparseMatrix:
    local_gate = klein_hodge_gate()
    left = embed_contiguous_even_gate(local_gate, start=0, total_modes=6)
    right = embed_contiguous_even_gate(local_gate, start=2, total_modes=6)
    return sp.ImmutableSparseMatrix(right * left)


def klein_seed_one_body() -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(
        [
            [3, 1, 0, 1],
            [1, 0, 2, 0],
            [0, 2, 0, 2],
            [1, 0, 2, 0],
        ]
    )


def plucker_quadric(two_particle_coordinates: sp.MatrixBase) -> sp.Expr:
    if two_particle_coordinates.shape not in ((6, 1), (1, 6)):
        raise ValueError("two-particle coordinates must be a six-component vector")
    p12, p13, p14, p23, p24, p34 = list(two_particle_coordinates)
    return sp.simplify(p12 * p34 - p13 * p24 + p14 * p23)


def is_orthogonal_exact(matrix: sp.MatrixBase) -> bool:
    if matrix.rows != matrix.cols:
        return False
    residual = matrix * matrix.T - sp.eye(matrix.rows)
    return all(sp.simplify(entry) == 0 for entry in residual)
