"""Exact obstruction to a two-invariant oddcycle chamber theorem.

Diagonal similarity reduces the sparse oddcycle atom to

    B(D,T) = [[0,0,D,0,0],
              [1,0,0,0,0],
              [0,1,0,1,0],
              [0,0,0,1,1],
              [0,0,T,0,1]].

Here ``D`` and ``T`` are the two directed-cycle products.  The attractive
chamber ``D > 0`` and ``-D < T < 0`` is not sign-free as a whole.
"""

from __future__ import annotations

import sympy as sp


CHAMBER_COUNTEREXAMPLE_WORD = "00100110011"


def canonical_oddcycle_matrix(D: int, T: int) -> sp.ImmutableMatrix:
    """Return the exact canonical representative with cycle invariants D,T."""

    if D <= 0 or not -D < T < 0:
        raise ValueError("expected D > 0 and -D < T < 0")
    return sp.ImmutableMatrix(
        [
            [0, 0, D, 0, 0],
            [1, 0, 0, 0, 0],
            [0, 1, 0, 1, 0],
            [0, 0, 0, 1, 1],
            [0, 0, T, 0, 1],
        ]
    )


def exact_chamber_counterexample() -> dict[str, object]:
    """Replay a negative determinant strictly inside the proposed chamber."""

    D, T = 10, -9
    matrix = canonical_oddcycle_matrix(D, T)
    atoms = (matrix, matrix.T)
    word_matrix = sp.eye(5)
    for symbol in CHAMBER_COUNTEREXAMPLE_WORD:
        word_matrix = atoms[int(symbol)] * word_matrix
    determinant = int((sp.eye(5) + word_matrix).det())
    return {
        "D": D,
        "T": T,
        "inside_open_chamber": D > 0 and -D < T < 0,
        "word": CHAMBER_COUNTEREXAMPLE_WORD,
        "determinant": determinant,
    }


__all__ = [
    "CHAMBER_COUNTEREXAMPLE_WORD",
    "canonical_oddcycle_matrix",
    "exact_chamber_counterexample",
]
