"""Exact minimal novelty filters for the oddcycle interval alphabet.

The checks here deliberately separate exact exclusions from mechanisms that
still require a Majorana- or generator-level classification.  They use the
fixed member ``B(1)``: one obstructed member is enough to rule out a common
similarity reduction of the complete interval alphabet.
"""

from __future__ import annotations

from math import isqrt

import sympy as sp

from .symmetric_oddcycle_cones import fixed_candidate_matrix


_ALGEBRA_WITNESS_WORDS = (
    "",
    "0",
    "1",
    "00",
    "01",
    "10",
    "11",
    "000",
    "001",
    "010",
    "011",
    "100",
    "101",
    "110",
    "111",
    "0000",
    "0001",
    "0010",
    "0011",
    "0100",
    "0101",
    "0110",
    "0111",
    "1011",
    "00001",
)


def _word_matrix(word: str) -> sp.ImmutableMatrix:
    matrix = fixed_candidate_matrix()
    atoms = (matrix, matrix.T)
    product = sp.eye(matrix.rows)
    for symbol in word:
        if symbol not in {"0", "1"}:
            raise ValueError("word must contain only 0 and 1")
        product = atoms[int(symbol)] * product
    return sp.ImmutableMatrix(product)


def _commutant_constraint_matrix(
    atoms: tuple[sp.ImmutableMatrix, ...],
) -> sp.ImmutableMatrix:
    dimension = atoms[0].rows
    rows = []
    for atom in atoms:
        for output_row in range(dimension):
            for output_column in range(dimension):
                row = [0] * (dimension * dimension)
                for index in range(dimension):
                    row[output_row * dimension + index] += atom[
                        index, output_column
                    ]
                    row[index * dimension + output_column] -= atom[
                        output_row, index
                    ]
                rows.append(row)
    return sp.ImmutableMatrix(rows)


def _bilinear_invariance_constraint_matrix(
    atoms: tuple[sp.ImmutableMatrix, ...],
) -> sp.ImmutableMatrix:
    dimension = atoms[0].rows
    rows = []
    for atom in atoms:
        for output_row in range(dimension):
            for output_column in range(dimension):
                row = [0] * (dimension * dimension)
                for left in range(dimension):
                    for right in range(dimension):
                        row[left * dimension + right] += (
                            atom[left, output_row]
                            * atom[right, output_column]
                        )
                row[output_row * dimension + output_column] -= 1
                rows.append(row)
    return sp.ImmutableMatrix(rows)


def exact_oddcycle_novelty_filter() -> dict[str, object]:
    """Return exact exclusions and explicitly unresolved known-class checks."""

    matrix = fixed_candidate_matrix()
    atoms = (matrix, matrix.T)
    dimension = matrix.rows
    determinant = int(matrix.det())
    characteristic = matrix.charpoly().as_poly()

    commutant_constraints = _commutant_constraint_matrix(atoms)
    bilinear_constraints = _bilinear_invariance_constraint_matrix(atoms)
    commutant_nullity = dimension**2 - commutant_constraints.rank()
    bilinear_invariant_nullity = dimension**2 - bilinear_constraints.rank()

    algebra_columns = tuple(
        sp.ImmutableMatrix(dimension**2, 1, list(_word_matrix(word)))
        for word in _ALGEBRA_WITNESS_WORDS
    )
    algebra_witness = sp.ImmutableMatrix.hstack(*algebra_columns)
    algebra_rank = algebra_witness.rank()

    negative_cycle_product = int(
        matrix[4, 2] * matrix[3, 4] * matrix[2, 3]
    )
    one_letter_weight = int((sp.eye(dimension) + matrix).det())
    square_root = isqrt(one_letter_weight)

    return {
        "candidate": "symmetric-oddcycle-interval-family",
        "fixed_member": "B(1)",
        "dimension": dimension,
        "determinant": determinant,
        "characteristic_coefficients": tuple(
            int(coefficient) for coefficient in characteristic.all_coeffs()
        ),
        "positive_real_root_count": int(
            characteristic.count_roots(0, sp.oo)
        ),
        "negative_real_root_count": int(
            characteristic.count_roots(-sp.oo, 0)
        ),
        "square_free_characteristic": (
            sp.gcd(characteristic, characteristic.diff()).degree() == 0
        ),
        "one_letter_weight": one_letter_weight,
        "one_letter_weight_is_integer_square": (
            square_root * square_root == one_letter_weight
        ),
        "split_orthogonal": {
            "status": "excluded-exactly",
            "reason": "det(B)=8 and no common nonzero invariant bilinear form",
            "orthogonal_determinant_square": determinant * determinant,
            "common_bilinear_invariant_nullity": bilinear_invariant_nullity,
        },
        "standard_kramers": {
            "status": "excluded-exactly-on-five-dimensional-one-particle-space",
            "reason": (
                "odd dimension and scalar common commutant forbid T^2=-I"
            ),
            "odd_dimension": dimension % 2 == 1,
            "common_commutant_nullity": commutant_nullity,
        },
        "obvious_similarity_reductions": {
            "status": "excluded-for-listed-reductions",
            "generated_algebra_rank": algebra_rank,
            "full_matrix_algebra_dimension": dimension**2,
            "witness_word_count": len(_ALGEBRA_WITNESS_WORDS),
            "maximum_witness_length": max(
                len(word) for word in _ALGEBRA_WITNESS_WORDS
            ),
            "negative_directed_cycle_product": negative_cycle_product,
            "consequences": (
                "no simultaneous invariant block decomposition",
                "no fixed non-scalar commuting linear symmetry",
                "no diagonal sign/positive scaling gauge to nonnegative atoms",
                "not simultaneously similar to totally nonnegative atoms",
            ),
        },
        "broader_semigroup_majorana": {
            "status": "not-excluded-by-this-minimal-filter",
            "open_checks": (
                "Wei-2024 contraction inequalities after the 10-Majorana lift",
                "Majorana reflection positivity after a fixed complex basis",
                "irreducible cone-preserving semigroup equivalences",
                "literature equivalence to a known fermion-bag or loop class",
            ),
        },
    }


__all__ = ["exact_oddcycle_novelty_filter"]
