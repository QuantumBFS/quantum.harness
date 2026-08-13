"""Exact stable-band tail certificate for the gauge-fixed seed-61 pair.

The certificate compares the fourth and third exterior representations.
For a word ``w``, strict positivity of ``Lambda^3(w)`` identifies its
Perron root with the product of the three largest eigenvalue moduli.  Hence

``|lambda_4(w)| = rho(Lambda^4(w)) / rho(Lambda^3(w))``.

Fixed weighted one-norms reduce the right-hand side by a factor smaller
than one on every ten-letter block.  Exact residue bounds then prove
``|lambda_4(w)| < 1`` for every word of length at least 24.  This controls
only the stable two-dimensional spectral band; it is not by itself a proof
that ``det(I + w)`` is positive.
"""

from __future__ import annotations

from functools import lru_cache
from fractions import Fraction
from itertools import combinations
from typing import TypeAlias


Matrix: TypeAlias = tuple[tuple[int, ...], ...]
Word: TypeAlias = tuple[int, ...]

SCALE = 768
BLOCK_LENGTH = 10

# SCALE times the positive gauge of the exact seed-61 atom.
_ATOM: Matrix = (
    (768, 288, 0, 0, 0),
    (0, 768, 192, 0, 0),
    (0, 0, 768, 832, 0),
    (0, 0, 0, 768, 88),
    (616, 231, 0, 0, 768),
)

# Rationalized positive weights.  A common scalar is immaterial.
GRADE4_WEIGHTS = (545184, 1853704, 1809811, 822488, 664742)
GRADE3_WEIGHTS = (
    892037,
    831964,
    595034,
    1329636,
    938155,
    788316,
    986631,
    1041039,
    1971566,
    1137182,
)


def _identity(dimension: int) -> Matrix:
    return tuple(
        tuple(int(row == column) for column in range(dimension))
        for row in range(dimension)
    )


def _transpose(matrix: Matrix) -> Matrix:
    return tuple(tuple(column) for column in zip(*matrix, strict=True))


def _matmul(left: Matrix, right: Matrix) -> Matrix:
    columns = _transpose(right)
    return tuple(
        tuple(
            sum(a * b for a, b in zip(row, column, strict=True))
            for column in columns
        )
        for row in left
    )


def _determinant(matrix: Matrix) -> int:
    dimension = len(matrix)
    if dimension == 0:
        return 1
    if dimension == 1:
        return matrix[0][0]
    return sum(
        (-1 if column & 1 else 1)
        * matrix[0][column]
        * _determinant(
            tuple(
                tuple(entry for index, entry in enumerate(row) if index != column)
                for row in matrix[1:]
            )
        )
        for column in range(dimension)
    )


def _compound(matrix: Matrix, grade: int) -> Matrix:
    basis = tuple(combinations(range(len(matrix)), grade))
    return tuple(
        tuple(
            _determinant(
                tuple(
                    tuple(matrix[row][column] for column in columns)
                    for row in rows
                )
            )
            for columns in basis
        )
        for rows in basis
    )


def _weighted_upper(
    matrix: Matrix,
    weights: tuple[int, ...],
    *,
    denominator: int,
) -> Fraction:
    column_values = (
        Fraction(
            sum(weights[row] * abs(matrix[row][column]) for row in range(len(matrix))),
            weights[column],
        )
        for column in range(len(matrix))
    )
    return max(column_values) / denominator


def _weighted_lower(
    matrix: Matrix,
    weights: tuple[int, ...],
    *,
    denominator: int,
) -> Fraction:
    column_values = (
        Fraction(
            sum(weights[row] * matrix[row][column] for row in range(len(matrix))),
            weights[column],
        )
        for column in range(len(matrix))
    )
    return min(column_values) / denominator


@lru_cache(maxsize=1)
def audit_seed61_stable_band_tail() -> dict[str, object]:
    """Enumerate and return the exact ten-block stable-band certificate."""

    atom_t = _transpose(_ATOM)
    grade3 = _compound(_ATOM, 3)
    grade4 = _compound(_ATOM, 4)
    grade3_t = _transpose(grade3)
    grade4_t = _transpose(grade4)
    if any(entry < 0 for row in grade3 for entry in row):
        raise ArithmeticError("the gauge-fixed grade-3 atom is not nonnegative")

    upper: list[Fraction | None] = [None] * (BLOCK_LENGTH + 1)
    lower: list[Fraction | None] = [None] * (BLOCK_LENGTH + 1)
    upper_words: list[Word] = [()] * (BLOCK_LENGTH + 1)
    lower_words: list[Word] = [()] * (BLOCK_LENGTH + 1)
    one_particle_positive = [True] * (BLOCK_LENGTH + 1)
    grade3_positive = [True] * (BLOCK_LENGTH + 1)

    def visit(
        word: Word,
        one_particle_word: Matrix | None,
        grade3_word: Matrix,
        grade4_word: Matrix,
    ) -> None:
        depth = len(word)
        upper_value = _weighted_upper(
            grade4_word,
            GRADE4_WEIGHTS,
            denominator=SCALE ** (4 * depth),
        )
        lower_value = _weighted_lower(
            grade3_word,
            GRADE3_WEIGHTS,
            denominator=SCALE ** (3 * depth),
        )
        if upper[depth] is None or upper_value > upper[depth]:
            upper[depth] = upper_value
            upper_words[depth] = word
        if lower[depth] is None or lower_value < lower[depth]:
            lower[depth] = lower_value
            lower_words[depth] = word

        grade3_positive[depth] &= all(
            entry > 0 for row in grade3_word for entry in row
        )
        if one_particle_word is not None:
            one_particle_positive[depth] &= all(
                entry > 0 for row in one_particle_word for entry in row
            )

        if depth == BLOCK_LENGTH:
            return
        for symbol, atom1, atom3, atom4 in (
            (0, _ATOM, grade3, grade4),
            (1, atom_t, grade3_t, grade4_t),
        ):
            visit(
                word + (symbol,),
                (
                    _matmul(one_particle_word, atom1)
                    if one_particle_word is not None and depth < 4
                    else None
                ),
                _matmul(grade3_word, atom3),
                _matmul(grade4_word, atom4),
            )

    visit((), _identity(5), _identity(10), _identity(5))

    exact_upper = tuple(value for value in upper if value is not None)
    exact_lower = tuple(value for value in lower if value is not None)
    if len(exact_upper) != BLOCK_LENGTH + 1 or len(exact_lower) != BLOCK_LENGTH + 1:
        raise ArithmeticError("the exact block enumeration is incomplete")
    one_particle_depth = next(
        depth
        for depth in range(1, 5)
        if one_particle_positive[depth]
    )
    grade3_depth = next(
        depth
        for depth in range(1, BLOCK_LENGTH + 1)
        if grade3_positive[depth]
    )

    block_ratio = exact_upper[BLOCK_LENGTH] / exact_lower[BLOCK_LENGTH]
    if block_ratio >= 1:
        raise ArithmeticError("the ten-block exterior ratio is not contracting")

    residue_bounds: list[dict[str, object]] = []
    for residue in range(BLOCK_LENGTH):
        residue_factor = exact_upper[residue] / exact_lower[residue]
        blocks = 1
        while residue_factor * block_ratio**blocks >= 1:
            blocks += 1
        strict = residue_factor * block_ratio**blocks < 1
        residue_bounds.append(
            {
                "residue": residue,
                "residue_factor": residue_factor,
                "blocks_required": blocks,
                "first_certified_length": BLOCK_LENGTH * blocks + residue,
                "strict": strict,
            }
        )

    return {
        "block_length": BLOCK_LENGTH,
        "grade4_weights": GRADE4_WEIGHTS,
        "grade3_weights": GRADE3_WEIGHTS,
        "block_upper": exact_upper[BLOCK_LENGTH],
        "block_lower": exact_lower[BLOCK_LENGTH],
        "block_ratio": block_ratio,
        "upper_word": upper_words[BLOCK_LENGTH],
        "lower_word": lower_words[BLOCK_LENGTH],
        "one_particle_strict_depth": one_particle_depth,
        "grade3_strict_depth": grade3_depth,
        "residue_bounds": tuple(residue_bounds),
        "tail_length": max(
            int(entry["first_certified_length"]) for entry in residue_bounds
        ),
    }


__all__ = [
    "BLOCK_LENGTH",
    "GRADE3_WEIGHTS",
    "GRADE4_WEIGHTS",
    "audit_seed61_stable_band_tail",
]
