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


__all__ = [
    "SCHEMA",
    "exact_chi23_obstruction",
    "exact_grade4_formula_replay",
    "fixed_candidate_matrix",
    "load_certificate",
    "symbolic_grade4_positive_atoms",
    "verify_compact_certificate",
]
