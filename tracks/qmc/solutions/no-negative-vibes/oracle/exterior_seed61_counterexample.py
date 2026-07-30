"""Exact length-150 counterexample for the seed-61 determinant claim.

The gauge-fixed atom is stored as ``A = 768 B``.  For the frozen word
``w`` of length ``L``, integer multiplication gives

``W = M / 768**L`` and
``det(I + W) = det(M + 768**L I) / 768**(5L)``.

The acceptance gate is only the sign of that integer determinant.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import TypeAlias

from .exterior_seed61_spectral_tail import audit_seed61_stable_band_tail


Matrix: TypeAlias = tuple[tuple[int, ...], ...]

SCALE = 768
WORD = (
    "000000110010101100101011010101100101010101100101100101011001010100110100"
    "110011010101001010101010110101010010110010101101010011010011010011010010"
    "100000"
)
WORD_SHA256 = "e36ea7ebf0c2038acc3f2a2e0cc97c5fed4a497c8fc9aafa12b61fb24ff4d072"
NUMERATOR_SHA256 = "3ac8e5c102e147edfda33c646a43b1bef3118977f234f7c6a61996e056d69bfe"
NUMERATOR_DIGITS = 2223

_ATOM: Matrix = (
    (768, 288, 0, 0, 0),
    (0, 768, 192, 0, 0),
    (0, 0, 768, 832, 0),
    (0, 0, 0, 768, 88),
    (616, 231, 0, 0, 768),
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


@lru_cache(maxsize=1)
def audit_seed61_exact_counterexample() -> dict[str, object]:
    """Replay the frozen word and return its exact negative determinant."""

    if len(WORD) != 150 or set(WORD) != {"0", "1"}:
        raise ArithmeticError("the frozen seed-61 word changed")
    word_sha256 = hashlib.sha256(WORD.encode("ascii")).hexdigest()
    if word_sha256 != WORD_SHA256:
        raise ArithmeticError("the frozen seed-61 word hash changed")

    atoms = (_ATOM, _transpose(_ATOM))
    product = _identity(5)
    for symbol in WORD:
        product = _matmul(product, atoms[int(symbol)])

    word_scale = SCALE ** len(WORD)
    shifted = tuple(
        tuple(
            product[row][column] + (word_scale if row == column else 0)
            for column in range(5)
        )
        for row in range(5)
    )
    numerator = _determinant(shifted)
    numerator_sha256 = hashlib.sha256(str(numerator).encode("ascii")).hexdigest()
    numerator_digits = len(str(abs(numerator)))
    if (
        numerator >= 0
        or numerator_sha256 != NUMERATOR_SHA256
        or numerator_digits != NUMERATOR_DIGITS
    ):
        raise ArithmeticError("the exact seed-61 determinant witness changed")

    stable_tail = audit_seed61_stable_band_tail()
    if len(WORD) < int(stable_tail["tail_length"]):
        raise ArithmeticError("the counterexample left the certified stable tail")

    denominator = SCALE ** (5 * len(WORD))
    return {
        "candidate": "exact5-shear-loop-pair-seed-61",
        "status": "exact-negative-counterexample",
        "word": {
            "bits": WORD,
            "length": len(WORD),
            "sha256": word_sha256,
        },
        "determinant": {
            "formula": "det(M + 768^L I) / 768^(5L)",
            "numerator": numerator,
            "numerator_digits": numerator_digits,
            "numerator_sha256": numerator_sha256,
            "denominator": denominator,
            "sign": -1,
        },
        "interpretation": {
            "stable_tail_length": stable_tail["tail_length"],
            "stable_pair_factor_positive": True,
            "top_pair_factor_negative": True,
            "candidate_survives_arbitrary_depth": False,
        },
    }


__all__ = [
    "NUMERATOR_DIGITS",
    "NUMERATOR_SHA256",
    "SCALE",
    "WORD",
    "WORD_SHA256",
    "audit_seed61_exact_counterexample",
]
