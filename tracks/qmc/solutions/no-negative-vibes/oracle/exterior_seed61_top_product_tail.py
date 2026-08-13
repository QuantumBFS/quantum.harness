"""Exact top-pair product certificate for the gauge-fixed seed-61 pair.

For a sufficiently long word ``w``, positivity of ``w`` and
``Lambda^3(w)`` identifies their Perron roots as

``rho(w) = lambda_1`` and
``rho(Lambda^3(w)) = lambda_1 lambda_2 lambda_3``.

Fixed weighted one-norm and positive-cone conorm bounds therefore prove
``lambda_2 lambda_3 > 1`` from length 18 onward.  Combined with the
independent stable-band certificate, this also proves positivity of the
top quadratic factor whenever ``tr(w) - rho(w) >= 0`` from length 24.
"""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache

from oracle.exterior_seed61_spectral_tail import (
    SCALE,
    Matrix,
    Word,
    _ATOM,
    _compound,
    _identity,
    _matmul,
    _transpose,
    _weighted_lower,
    _weighted_upper,
    audit_seed61_stable_band_tail,
)


BLOCK_LENGTH = 5

# Rationalized positive weights.  A common scalar is immaterial.
GRADE1_WEIGHTS = (555238, 644059, 2025872, 2010441, 686581)
GRADE3_WEIGHTS = (
    915676,
    787059,
    569210,
    1342330,
    926592,
    859950,
    1005198,
    1005675,
    1938371,
    1163083,
)


def top_factor_lower_bound(
    *,
    trace_minus_perron: Fraction,
    top_pair_product: Fraction,
    stable_radius: Fraction,
) -> Fraction:
    """Return the exact signed-branch lower bound for the top factor.

    If ``A = tr(w)-rho(w)``, ``p=lambda_2 lambda_3`` and
    ``theta=|lambda_4|``, spectral ordering gives

    ``(1+lambda_2)(1+lambda_3) >= 1+p+A-2 theta``.

    The certified branch has ``A>=0``, ``p>1`` and ``0<=theta<1``.
    """

    if trace_minus_perron < 0:
        raise ValueError("the signed branch requires tr(w)-rho(w) >= 0")
    if top_pair_product <= 1:
        raise ValueError("the top-pair certificate requires p > 1")
    if stable_radius < 0 or stable_radius >= 1:
        raise ValueError("the stable-band certificate requires 0 <= theta < 1")
    return (
        1
        + top_pair_product
        + trace_minus_perron
        - 2 * stable_radius
    )


@lru_cache(maxsize=1)
def audit_seed61_top_product_tail() -> dict[str, object]:
    """Enumerate the exact five-block top-pair product certificate."""

    atom_t = _transpose(_ATOM)
    grade3 = _compound(_ATOM, 3)
    grade3_t = _transpose(grade3)
    if any(entry < 0 for row in grade3 for entry in row):
        raise ArithmeticError("the gauge-fixed grade-3 atom is not nonnegative")

    upper: list[Fraction | None] = [None] * (BLOCK_LENGTH + 1)
    lower: list[Fraction | None] = [None] * (BLOCK_LENGTH + 1)
    upper_words: list[Word] = [()] * (BLOCK_LENGTH + 1)
    lower_words: list[Word] = [()] * (BLOCK_LENGTH + 1)

    def visit(word: Word, one_particle_word: Matrix, grade3_word: Matrix) -> None:
        depth = len(word)
        upper_value = _weighted_upper(
            one_particle_word,
            GRADE1_WEIGHTS,
            denominator=SCALE**depth,
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

        if depth == BLOCK_LENGTH:
            return
        for symbol, atom1, atom3 in (
            (0, _ATOM, grade3),
            (1, atom_t, grade3_t),
        ):
            visit(
                word + (symbol,),
                _matmul(one_particle_word, atom1),
                _matmul(grade3_word, atom3),
            )

    visit((), _identity(5), _identity(10))

    exact_upper = tuple(value for value in upper if value is not None)
    exact_lower = tuple(value for value in lower if value is not None)
    if len(exact_upper) != BLOCK_LENGTH + 1 or len(exact_lower) != BLOCK_LENGTH + 1:
        raise ArithmeticError("the exact block enumeration is incomplete")

    block_ratio = exact_upper[BLOCK_LENGTH] / exact_lower[BLOCK_LENGTH]
    if block_ratio >= 1:
        raise ArithmeticError("the five-block exterior ratio is not contracting")

    residue_bounds: list[dict[str, object]] = []
    for residue in range(BLOCK_LENGTH):
        residue_factor = exact_upper[residue] / exact_lower[residue]
        blocks = 1
        while residue_factor * block_ratio**blocks >= 1:
            blocks += 1
        residue_bounds.append(
            {
                "residue": residue,
                "residue_factor": residue_factor,
                "blocks_required": blocks,
                "first_certified_length": BLOCK_LENGTH * blocks + residue,
                "strict": residue_factor * block_ratio**blocks < 1,
            }
        )

    # For each residue, the preceding same-residue length is the last one not
    # covered by this block estimate.  One plus their maximum is a contiguous
    # all-length cutoff.
    tail_length = 1 + max(
        int(entry["first_certified_length"]) - BLOCK_LENGTH
        for entry in residue_bounds
    )
    stable = audit_seed61_stable_band_tail()
    stable_tail_length = int(stable["tail_length"])

    return {
        "block_length": BLOCK_LENGTH,
        "grade1_weights": GRADE1_WEIGHTS,
        "grade3_weights": GRADE3_WEIGHTS,
        "block_upper": exact_upper[BLOCK_LENGTH],
        "block_lower": exact_lower[BLOCK_LENGTH],
        "block_ratio": block_ratio,
        "upper_word": upper_words[BLOCK_LENGTH],
        "lower_word": lower_words[BLOCK_LENGTH],
        "residue_bounds": tuple(residue_bounds),
        "tail_length": tail_length,
        "stable_band_tail_length": stable_tail_length,
        "nonnegative_trace_branch_tail_length": max(
            tail_length,
            stable_tail_length,
        ),
    }


__all__ = [
    "BLOCK_LENGTH",
    "GRADE1_WEIGHTS",
    "GRADE3_WEIGHTS",
    "audit_seed61_top_product_tail",
    "top_factor_lower_bound",
]
