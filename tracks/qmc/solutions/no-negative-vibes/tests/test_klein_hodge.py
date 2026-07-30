from __future__ import annotations

import pytest
import sympy as sp

from oracle.fock_basis import one_body_operator, parity_indices
from oracle.klein_hodge import (
    embed_contiguous_even_gate,
    is_orthogonal_exact,
    klein_hodge_gate,
    klein_seed_one_body,
    overlap_klein_circuit,
    plucker_quadric,
)


def _is_metzler(matrix: sp.MatrixBase) -> bool:
    return all(
        sp.simplify(matrix[i, j]) >= 0
        for i in range(matrix.rows)
        for j in range(matrix.cols)
        if i != j
    )


def test_klein_gate_is_exact_orthogonal_and_number_sector_preserving() -> None:
    gate = klein_hodge_gate()
    assert gate.shape == (16, 16)
    assert isinstance(gate, sp.ImmutableSparseMatrix)
    assert is_orthogonal_exact(gate)
    for left in range(16):
        for right in range(16):
            if left.bit_count() != right.bit_count():
                assert gate[left, right] == 0


def test_klein_gate_uses_the_fixed_row_basis_and_identity_elsewhere() -> None:
    gate = klein_hodge_gate()
    two_particle = (3, 5, 9, 6, 10, 12)
    inverse_sqrt_two = 1 / sp.sqrt(2)
    expected_block = sp.ImmutableSparseMatrix(
        [
            [inverse_sqrt_two, 0, 0, 0, 0, inverse_sqrt_two],
            [inverse_sqrt_two, 0, 0, 0, 0, -inverse_sqrt_two],
            [0, inverse_sqrt_two, 0, 0, -inverse_sqrt_two, 0],
            [0, inverse_sqrt_two, 0, 0, inverse_sqrt_two, 0],
            [0, 0, inverse_sqrt_two, inverse_sqrt_two, 0, 0],
            [0, 0, inverse_sqrt_two, -inverse_sqrt_two, 0, 0],
        ]
    )
    outside = tuple(state for state in range(16) if state not in two_particle)

    assert gate.extract(two_particle, two_particle) == expected_block
    assert gate.extract(outside, outside) == sp.eye(len(outside))
    assert gate.extract(two_particle, outside) == sp.zeros(6, len(outside))
    assert gate.extract(outside, two_particle) == sp.zeros(len(outside), 6)


def test_klein_transform_is_not_induced_by_one_particle_basis_change() -> None:
    gate = klein_hodge_gate()
    two_particle = (3, 5, 9, 6, 10, 12)
    transformed_e12 = gate.extract(two_particle, two_particle).T * sp.eye(6)[:, 0]
    assert sp.simplify(plucker_quadric(transformed_e12)) != 0


def test_exact_four_mode_seed_is_metzler_in_both_parities() -> None:
    gate = klein_hodge_gate()
    seed = klein_seed_one_body()
    assert isinstance(seed, sp.ImmutableMatrix)
    assert seed == sp.ImmutableMatrix(
        [
            [3, 1, 0, 1],
            [1, 0, 2, 0],
            [0, 2, 0, 2],
            [1, 0, 2, 0],
        ]
    )

    transformed = sp.simplify(gate * one_body_operator(seed) * gate.T)
    even, odd = parity_indices(4)
    assert _is_metzler(transformed.extract(even, even))
    assert _is_metzler(transformed.extract(odd, odd))


def test_plucker_quadric_uses_the_fixed_bivector_coordinate_order() -> None:
    coordinates = sp.ImmutableMatrix([2, 3, 5, 7, 11, 13])
    assert plucker_quadric(coordinates) == 28


def test_overlap_circuit_is_one_fixed_six_mode_orthogonal_gate() -> None:
    gate = overlap_klein_circuit()
    assert gate.shape == (64, 64)
    assert isinstance(gate, sp.ImmutableSparseMatrix)
    assert is_orthogonal_exact(gate)

    left = embed_contiguous_even_gate(klein_hodge_gate(), start=0, total_modes=6)
    right = embed_contiguous_even_gate(klein_hodge_gate(), start=2, total_modes=6)
    assert gate == right * left


def test_contiguous_embedding_uses_low_bit_mode_order_independently() -> None:
    embedded = embed_contiguous_even_gate(
        klein_hodge_gate(), start=1, total_modes=6
    )

    assert isinstance(embedded, sp.ImmutableSparseMatrix)
    assert embedded[0b100111, 0b111001] == 1 / sp.sqrt(2)
    assert embedded[0b000111, 0b011001] == 1 / sp.sqrt(2)
    assert embedded[0b100110, 0b111001] == 0


def test_embedding_rejects_non_even_gates_and_out_of_range_blocks() -> None:
    parity_mixing_gate = sp.ImmutableSparseMatrix([[0, 1], [1, 0]])
    with pytest.raises(ValueError, match="preserve local fermion parity"):
        embed_contiguous_even_gate(parity_mixing_gate, start=0, total_modes=1)

    with pytest.raises(ValueError, match="sorted contiguous block"):
        embed_contiguous_even_gate(klein_hodge_gate(), start=3, total_modes=6)
