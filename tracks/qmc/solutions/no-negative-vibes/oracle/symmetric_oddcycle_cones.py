"""Exact cone certificates for the fixed symmetric-oddcycle candidate.

The candidate studied here is

    B = [[0, 0, 2, 0, 0],
         [2, 0, 0, 0, 0],
         [0, 2, 0, 1, 0],
         [0, 0, 0, 1, 1],
         [0, 0,-1, 0, 1]].

Only exact rational replay is exposed.  Numerical optimization was used to
discover the stored transforms, but it is not part of verification.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import sympy as sp

from .exterior_exact5_full_fock_cone import combined_grade_lift
from .exterior_exact5_shared_cone import exact_compound_matrix


SCHEMA = "symmetric-oddcycle-simplicial-certificate-v1"


def fixed_candidate_matrix() -> sp.ImmutableMatrix:
    """Return the exact fixed matrix ``B(2, 1)``."""

    return sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, 1, 0],
            [0, 0, 0, 1, 1],
            [0, 0, -1, 0, 1],
        ]
    )


def symbolic_grade4_positive_atoms() -> tuple[sp.ImmutableMatrix, ...]:
    """Return the sign-gauged grade-four atoms for positive symbols ``x,y``."""

    x, y = sp.symbols("x y", positive=True)
    atom = sp.ImmutableMatrix(
        [
            [x**3, x**3 * y, 0, x**2 * y**2, 0],
            [0, x**3, 0, x**2 * y, 0],
            [0, 0, 0, x**2, 0],
            [0, 0, 0, 0, x**2],
            [x**2 * y, x**2 * y**2, x**2, x * y**3, 0],
        ]
    )
    return atom, sp.ImmutableMatrix(atom.T)


def exact_grade4_formula_replay() -> bool:
    """Replay the symbolic ``D wedge^4(B) D >= 0`` identity exactly."""

    x, y = sp.symbols("x y", positive=True)
    matrix = sp.ImmutableMatrix(
        [
            [0, 0, x, 0, 0],
            [x, 0, 0, 0, 0],
            [0, x, 0, y, 0],
            [0, 0, 0, 1, y],
            [0, 0, -y, 0, 1],
        ]
    )
    diagonal = sp.diag(1, 1, 1, -1, 1)
    expected = symbolic_grade4_positive_atoms()
    actual = tuple(
        sp.ImmutableMatrix(
            diagonal * exact_compound_matrix(atom, 4) * diagonal
        )
        for atom in (matrix, matrix.T)
    )
    return actual == expected


def load_certificate(path: str | Path) -> dict[str, object]:
    """Load one compact rational transform certificate."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("certificate root must be an object")
    return payload


def _rational_matrix(
    payload: Sequence[Sequence[Mapping[str, object]]],
) -> sp.ImmutableMatrix:
    rows = []
    for row in payload:
        rows.append(
            [
                sp.Rational(int(entry["numerator"]), int(entry["denominator"]))
                for entry in row
            ]
        )
    return sp.ImmutableMatrix(rows)


def verify_compact_certificate(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Verify ``S^-1 A_i S >= 0`` exactly for the declared grade sum."""

    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected certificate schema")
    matrix_payload = payload.get("matrix")
    grades_payload = payload.get("grades")
    transform_payload = payload.get("transform")
    if not isinstance(matrix_payload, Sequence):
        raise ValueError("matrix payload is missing")
    if not isinstance(grades_payload, Sequence):
        raise ValueError("grades payload is missing")
    if not isinstance(transform_payload, Sequence):
        raise ValueError("transform payload is missing")

    matrix = sp.ImmutableMatrix(matrix_payload)
    if matrix != fixed_candidate_matrix():
        raise ValueError("certificate targets a different matrix")
    grades = tuple(int(grade) for grade in grades_payload)
    transform = _rational_matrix(transform_payload)
    matrices = tuple(
        combined_grade_lift(atom, grades) for atom in (matrix, matrix.T)
    )
    if transform.shape != matrices[0].shape or transform.det() == 0:
        raise ValueError("certificate transform is not invertible")

    inverse = transform.inv()
    transformed = tuple(
        sp.ImmutableMatrix(inverse * atom * transform) for atom in matrices
    )
    minimum = min(entry for atom in transformed for entry in atom)
    if minimum < 0:
        raise ValueError("certificate has a negative transformed entry")
    if transformed[1] != sp.ImmutableMatrix(
        inverse * matrices[1] * transform
    ):
        raise RuntimeError("transpose-atom replay failed")
    return {
        "status": "exact-certificate",
        "grades": grades,
        "dimension": matrices[0].rows,
        "minimum_entry": minimum,
        "trace_compatible": True,
    }


def exact_chi23_obstruction() -> dict[str, int]:
    """Return the exact grade-(2,3) obstruction at ``W=B^7``."""

    matrix = fixed_candidate_matrix() ** 7
    chi2 = int(sp.trace(exact_compound_matrix(matrix, 2)))
    chi3 = int(sp.trace(exact_compound_matrix(matrix, 3)))
    return {"chi2": chi2, "chi3": chi3, "sum": chi2 + chi3}


def _principal_minor(
    matrix: sp.MatrixBase,
    indices: tuple[int, ...],
) -> sp.Expr:
    return matrix.extract(indices, indices).det()


def _word_matrix(word: str) -> sp.ImmutableMatrix:
    matrix = fixed_candidate_matrix()
    atoms = (matrix, matrix.T)
    product = sp.eye(matrix.rows)
    for symbol in word:
        if symbol not in {"0", "1"}:
            raise ValueError("word must contain only 0 and 1")
        product = atoms[int(symbol)] * product
    return sp.ImmutableMatrix(product)


def exact_complementary_sector_audit() -> dict[str, object]:
    """Replay exact identities and obstructions for the remaining sector sum.

    For every invertible five-by-five matrix ``W``, Jacobi's complementary
    minor identity gives ``chi3(W) = det(W) * chi2(W.inv())``.  The returned
    examples show why individual complementary minor pairs cannot supply a
    positive proof.
    """

    matrix = fixed_candidate_matrix()
    minor_examples = []
    for label, word, index_sets in (
        ("B", "0", ((0, 1),)),
        ("B^2", "00", ((0, 3), (1, 4))),
    ):
        word_matrix = _word_matrix(word)
        for indices in index_sets:
            complement = tuple(
                index for index in range(matrix.rows) if index not in indices
            )
            left = _principal_minor(word_matrix, indices)
            right = _principal_minor(word_matrix, complement)
            minor_examples.append(
                {
                    "matrix": label,
                    "indices": indices,
                    "complement": complement,
                    "left": int(left),
                    "right": int(right),
                    "sum": int(left + right),
                }
            )

    word = "0001010101"
    mixed = _word_matrix(word)
    mixed_chi2 = int(sp.trace(exact_compound_matrix(mixed, 2)))
    mixed_chi3 = int(sp.trace(exact_compound_matrix(mixed, 3)))
    mixed_det = int(mixed.det())

    pure_values = {}
    for power in (7, 10):
        pure = matrix**power
        chi2 = int(sp.trace(exact_compound_matrix(pure, 2)))
        chi3 = int(sp.trace(exact_compound_matrix(pure, 3)))
        determinant = int(pure.det())
        pure_values[power] = {
            "chi2": chi2,
            "chi3": chi3,
            "determinant": determinant,
            "F": 1 + chi2 + chi3 + determinant,
        }

    jacobi_checks = {}
    for label, word_matrix in (
        ("mixed", mixed),
        ("B^7", matrix**7),
        ("B^10", matrix**10),
    ):
        determinant = word_matrix.det()
        chi3 = sp.trace(exact_compound_matrix(word_matrix, 3))
        inverse_chi2 = sp.trace(
            exact_compound_matrix(word_matrix.inv(), 2)
        )
        jacobi_checks[label] = bool(
            sp.simplify(chi3 - determinant * inverse_chi2) == 0
        )

    return {
        "identity": "chi3(W)=det(W)*chi2(W^-1)",
        "determinant_per_letter": int(matrix.det()),
        "jacobi_checks": jacobi_checks,
        "negative_complementary_minor_pairs": minor_examples,
        "mixed_word": {
            "word": word,
            "chi2": mixed_chi2,
            "chi3": mixed_chi3,
            "determinant": mixed_det,
            "F": 1 + mixed_chi2 + mixed_chi3 + mixed_det,
        },
        "pure_power_values": pure_values,
    }


def exact_invariant_chamber_obstruction() -> dict[str, object]:
    """Disprove positivity from the signs ``D>0`` and ``-D<T<0`` alone."""

    z = sp.symbols("z", real=True)
    matrix = sp.Matrix(fixed_candidate_matrix())
    matrix[4, 2] = -z
    word_matrix = matrix**4
    polynomial = sp.Poly(
        1
        + sp.trace(exact_compound_matrix(word_matrix, 2))
        + sp.trace(exact_compound_matrix(word_matrix, 3))
        + word_matrix.det(),
        z,
    )
    return {
        "positive_cycle_invariant": 8,
        "negative_cycle_invariant": "-z",
        "coefficients_descending": tuple(
            int(coefficient) for coefficient in polynomial.all_coeffs()
        ),
        "F_at_z3": int(polynomial.eval(3)),
        "F_at_z4": int(polynomial.eval(4)),
        "z3_inside_chamber": 0 < 3 < 8,
        "z4_inside_chamber": 0 < 4 < 8,
    }


__all__ = [
    "SCHEMA",
    "exact_chi23_obstruction",
    "exact_complementary_sector_audit",
    "exact_grade4_formula_replay",
    "exact_invariant_chamber_obstruction",
    "fixed_candidate_matrix",
    "load_certificate",
    "symbolic_grade4_positive_atoms",
    "verify_compact_certificate",
]
