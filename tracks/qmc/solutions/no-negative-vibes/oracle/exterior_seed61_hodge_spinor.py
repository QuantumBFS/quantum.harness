"""Exact Hodge/spinor diagnostics for the fixed seed-61 atom.

The full exterior algebra splits into its even and odd chiral spinors,
each of dimension 16.  Top-wedge pairing identifies the odd block with
the dual of the even block.  This module checks that structure exactly and
records sharp obstructions to the two most direct positivity proposals:

* an orthant in the Hodge self/anti-self basis;
* a particle-hole/Jordan--Wigner signed-permutation orthant.

It does not claim a no-go for every nonpolyhedral cone coupling all grades.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations

import sympy as sp

from .exterior_candidates import candidate_card, exact_atoms_from_card


def _subsets(dimension: int, grades: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(
        subset
        for grade in grades
        for subset in combinations(range(dimension), grade)
    )


def _compound(matrix: sp.MatrixBase, grade: int) -> sp.ImmutableMatrix:
    indices = tuple(combinations(range(matrix.rows), grade))
    return sp.ImmutableMatrix(
        [
            [
                matrix.extract(rows, columns).det()
                for columns in indices
            ]
            for rows in indices
        ]
    )


def _grade_sum(matrix: sp.MatrixBase, grades: tuple[int, ...]) -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(
        sp.diag(*(_compound(matrix, grade) for grade in grades))
    )


def _top_wedge_pairing(dimension: int) -> sp.ImmutableMatrix:
    even = _subsets(dimension, tuple(range(0, dimension + 1, 2)))
    odd = _subsets(dimension, tuple(range(1, dimension + 1, 2)))
    pairing = sp.zeros(len(even), len(odd))
    universe = set(range(dimension))
    for row, left in enumerate(even):
        complement = universe.difference(left)
        for column, right in enumerate(odd):
            if set(right) != complement:
                continue
            inversions = sum(i > j for i in left for j in right)
            pairing[row, column] = -1 if inversions % 2 else 1
    return sp.ImmutableMatrix(pairing)


def _self_anti_hodge_matrix(matrix: sp.MatrixBase) -> tuple[
    sp.ImmutableMatrix,
    sp.ImmutableMatrix,
    sp.ImmutableMatrix,
]:
    dimension = matrix.rows
    even_grades = tuple(range(0, dimension + 1, 2))
    odd_grades = tuple(range(1, dimension + 1, 2))
    even = _grade_sum(matrix, even_grades)
    odd = _grade_sum(matrix, odd_grades)
    hodge = _top_wedge_pairing(dimension)
    dual_odd = sp.ImmutableMatrix(hodge * odd * hodge.T)
    same = sp.ImmutableMatrix((even + dual_odd) / 2)
    cross = sp.ImmutableMatrix((even - dual_odd) / 2)
    transformed = sp.ImmutableMatrix(
        sp.Matrix.vstack(
            sp.Matrix.hstack(same, cross),
            sp.Matrix.hstack(cross, same),
        )
    )
    return transformed, even, odd


def _label(subset: tuple[int, ...]) -> str:
    return "".join(str(index) for index in subset) if subset else "empty"


def _reciprocal_sign_conflict(
    matrix: sp.MatrixBase,
    labels: tuple[str, ...],
) -> dict[str, str] | None:
    for left in range(matrix.rows):
        for right in range(left + 1, matrix.cols):
            forward = matrix[left, right]
            reverse = matrix[right, left]
            if forward * reverse < 0:
                return {
                    "left": labels[left],
                    "right": labels[right],
                    "forward": str(forward),
                    "reverse": str(reverse),
                }
    return None


@lru_cache(maxsize=1)
def seed61_hodge_spinor_obstruction() -> dict[str, object]:
    """Return exact witnesses closing the simplest Hodge/spinor cones."""

    atoms = exact_atoms_from_card(
        candidate_card(template="exact5-shear-loop-pair", seed=61)
    )
    primary, transpose = atoms
    if transpose != primary.T or primary.det() != 1:
        raise ArithmeticError("seed 61 is no longer a determinant-one transpose pair")

    dimension = primary.rows
    even_subsets = _subsets(dimension, (0, 2, 4))
    all_subsets = _subsets(dimension, tuple(range(dimension + 1)))
    hodge = _top_wedge_pairing(dimension)
    transformed, even, odd = _self_anti_hodge_matrix(primary)
    transpose_transformed, _, _ = _self_anti_hodge_matrix(transpose)

    mukai_identity = even.T * hodge * odd
    if mukai_identity != hodge:
        raise ArithmeticError("top-wedge pairing identity failed")
    if hodge * hodge.T != sp.eye(hodge.rows):
        raise ArithmeticError("Hodge complement is not a signed permutation")

    self_anti_labels = tuple(
        f"{sign}:{_label(subset)}"
        for sign in ("+", "-")
        for subset in even_subsets
    )
    fock = _grade_sum(primary, tuple(range(dimension + 1)))
    fock_labels = tuple(
        f"k{len(subset)}:{_label(subset)}"
        for subset in all_subsets
    )

    word = primary**7
    grade_traces = tuple(
        sp.trace(_compound(word, grade))
        for grade in range(dimension + 1)
    )
    pair_1_4 = sp.factor(grade_traces[1] + grade_traces[4])
    pair_2_3 = sp.factor(grade_traces[2] + grade_traces[3])
    full_fock = sp.factor(sum(grade_traces))
    if pair_1_4 >= 0 or pair_2_3 <= 0 or full_fock <= 0:
        raise ArithmeticError("the exact power-seven sign witness changed")

    # In coordinates (x, H y), the Mukai form is [[0,I],[I,0]].
    # The self/anti change gives diag(I_16,-I_16), hence split inertia.
    return {
        "candidate": "exact5-shear-loop-pair-seed-61",
        "status": "exact-structured-cone-obstruction",
        "mukai": {
            "identity": "E.T * H * O = H",
            "identity_replay": True,
            "hodge_is_signed_permutation": True,
            "inertia": [hodge.rows, hodge.rows],
        },
        "self_anti_hodge": {
            "block_formula": "1/2 [[E+E^-T,E-E^-T],[E-E^-T,E+E^-T]]",
            "transpose_partner_replay": transpose_transformed == transformed.T,
            "negative_entries": sum(1 for entry in transformed if entry < 0),
            "reciprocal_sign_conflict": _reciprocal_sign_conflict(
                transformed,
                self_anti_labels,
            ),
        },
        "particle_hole_signed_basis": {
            "scope": (
                "Every particle-hole/Jordan-Wigner basis change is a signed "
                "permutation of occupation states."
            ),
            "negative_entries": sum(1 for entry in fock if entry < 0),
            "reciprocal_sign_conflict": _reciprocal_sign_conflict(
                fock,
                fock_labels,
            ),
        },
        "paired_trace_witness": {
            "word": "B^7",
            "power": 7,
            "grade_traces": [str(value) for value in grade_traces],
            "pair_1_4": str(pair_1_4),
            "pair_2_3": str(pair_2_3),
            "full_fock": str(full_fock),
        },
        "scope": (
            "This closes the natural Mukai quadratic cone, the self/anti "
            "Hodge orthant, every particle-hole signed orthant, and a "
            "separate trace-positive cone on grades (1,4).  It does not "
            "exclude a cone coupling the (1,4) and (2,3) pairs."
        ),
    }


__all__ = ["seed61_hodge_spinor_obstruction"]
