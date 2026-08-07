"""Probe seed 61 as a positive two-letter rational series.

For the transpose-paired atoms ``B_0, B_1 = B_0.T`` define

``f(w) = det(I + B_w) = Tr Gamma(B_w)``.

This module keeps two logically separate gates:

* an exact Hankel/nonnegative-rank audit through total word length eight;
* a numerical closure test for the two canonical exact NMF gauges.  The
  closure test uses the one-symbol-shifted Hankel blocks (length nine).

Failure of the canonical gauges is not a no-go for a larger positive
realization.  A reported arbitrary-word hit would require a rationalized
nonnegative realization and exact replay, which this discovery probe does
not manufacture from a finite-depth fit.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from itertools import product

import numpy as np
import sympy as sp
from scipy.optimize import nnls

from .exterior_candidates import candidate_card, exact_atoms_from_card


DEFAULT_PRIMES = (2_147_483_647, 2_147_483_629)


def binary_words_upto(depth: int) -> tuple[tuple[int, ...], ...]:
    """Return binary words in length/lexicographic order."""

    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
        raise ValueError("depth must be a nonnegative integer")
    return tuple(
        word
        for length in range(depth + 1)
        for word in product((0, 1), repeat=length)
    )


def transpose_reversal_word(word: Sequence[int]) -> tuple[int, ...]:
    """Return the word induced by transposition when ``B_1 = B_0.T``."""

    checked = tuple(word)
    if any(
        not isinstance(symbol, int)
        or isinstance(symbol, bool)
        or symbol not in (0, 1)
        for symbol in checked
    ):
        raise ValueError("word entries must be 0 or 1")
    return tuple(1 - symbol for symbol in reversed(checked))


def exact_determinant_weight(
    atoms: Sequence[sp.MatrixBase],
    word: Sequence[int],
) -> sp.Rational:
    """Evaluate ``det(I + B_w)`` with exact rational arithmetic."""

    checked = tuple(sp.ImmutableMatrix(atom) for atom in atoms)
    if len(checked) != 2:
        raise ValueError("exactly two atoms are required")
    dimension = checked[0].rows
    if dimension < 1 or any(atom.shape != (dimension, dimension) for atom in checked):
        raise ValueError("atoms must have one common nonempty square shape")
    branch_word = tuple(word)
    if any(
        not isinstance(symbol, int)
        or isinstance(symbol, bool)
        or symbol not in (0, 1)
        for symbol in branch_word
    ):
        raise ValueError("word entries must be 0 or 1")

    matrix = sp.eye(dimension)
    for symbol in branch_word:
        matrix *= checked[symbol]
    value = sp.factor(sp.det(sp.eye(dimension) + matrix))
    if not bool(value.is_rational):
        raise ArithmeticError("the exact determinant weight is not rational")
    return sp.Rational(value)


def exact_hankel(
    atoms: Sequence[sp.MatrixBase],
    prefixes: Sequence[Sequence[int]],
    suffixes: Sequence[Sequence[int]],
    *,
    middle: Sequence[int] = (),
    cache: dict[tuple[int, ...], sp.Rational] | None = None,
) -> sp.ImmutableMatrix:
    """Build ``H[u,v] = f(u middle v)`` exactly."""

    prefix_words = tuple(tuple(word) for word in prefixes)
    suffix_words = tuple(tuple(word) for word in suffixes)
    middle_word = tuple(middle)
    memo = {} if cache is None else cache

    def weight(word: tuple[int, ...]) -> sp.Rational:
        if word not in memo:
            memo[word] = exact_determinant_weight(atoms, word)
        return memo[word]

    return sp.ImmutableMatrix(
        [
            [
                weight(prefix + middle_word + suffix)
                for suffix in suffix_words
            ]
            for prefix in prefix_words
        ]
    )


def rank_mod_prime(matrix: sp.MatrixBase, prime: int) -> int:
    """Return the matrix rank over ``F_prime`` by explicit elimination."""

    if (
        not isinstance(prime, int)
        or isinstance(prime, bool)
        or prime <= 2
        or not sp.isprime(prime)
    ):
        raise ValueError("prime must be an odd prime")
    rows = [
        [
            int(sp.Rational(value).p)
            * pow(int(sp.Rational(value).q), -1, prime)
            % prime
            for value in matrix.row(row)
        ]
        for row in range(matrix.rows)
    ]

    rank = 0
    for column in range(matrix.cols):
        pivot = next(
            (
                row
                for row in range(rank, matrix.rows)
                if rows[row][column]
            ),
            None,
        )
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        inverse = pow(rows[rank][column], -1, prime)
        rows[rank] = [entry * inverse % prime for entry in rows[rank]]
        for row in range(matrix.rows):
            if row == rank or rows[row][column] == 0:
                continue
            factor = rows[row][column]
            rows[row] = [
                (left - factor * right) % prime
                for left, right in zip(rows[row], rows[rank], strict=True)
            ]
        rank += 1
        if rank == min(matrix.rows, matrix.cols):
            break
    return rank


def canonical_positive_closure_gate(
    hankel: np.ndarray,
    shifted: np.ndarray,
    *,
    factorization: str = "identity-left",
    tolerance: float = 1.0e-8,
) -> dict[str, float | int | str]:
    """Test one canonical exact-NMF gauge for a positive transition.

    ``identity-left`` means ``H = I H`` and hence ``P H = H_shift``.
    ``identity-right`` means ``H = H I`` and hence ``H P = H_shift``.
    When ``H`` is nonsingular the transition is unique.  NNLS measures the
    distance to the nearest nonnegative transition in the selected gauge.
    """

    matrix = np.asarray(hankel, dtype=float)
    target = np.asarray(shifted, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("hankel must be square")
    if target.shape != matrix.shape:
        raise ValueError("shifted must have the same shape as hankel")
    if factorization not in {"identity-left", "identity-right"}:
        raise ValueError("unknown canonical NMF factorization")
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(target)):
        raise ValueError("matrices must be finite")
    if np.any(matrix < 0.0):
        raise ValueError("the canonical NMF gate requires a nonnegative Hankel")

    row_scale = np.maximum(np.max(np.abs(matrix), axis=1), 1.0)
    equilibrated = matrix / row_scale[:, None]
    column_scale = np.maximum(np.max(np.abs(equilibrated), axis=0), 1.0e-300)
    equilibrated /= column_scale[None, :]
    target_equilibrated = (
        target / row_scale[:, None] / column_scale[None, :]
    )

    if factorization == "identity-left":
        transition = np.linalg.solve(
            equilibrated.T,
            target_equilibrated.T,
        ).T
        reconstructed = transition @ equilibrated
        positive_transition = np.vstack(
            [
                nnls(equilibrated.T, row, maxiter=10_000)[0]
                for row in target_equilibrated
            ]
        )
        positive_reconstruction = positive_transition @ equilibrated
    else:
        transition = np.linalg.solve(equilibrated, target_equilibrated)
        reconstructed = equilibrated @ transition
        positive_transition = np.column_stack(
            [
                nnls(
                    equilibrated,
                    target_equilibrated[:, column],
                    maxiter=10_000,
                )[0]
                for column in range(target_equilibrated.shape[1])
            ]
        )
        positive_reconstruction = equilibrated @ positive_transition
    residual = float(
        np.linalg.norm(reconstructed - target_equilibrated)
        / max(np.linalg.norm(target_equilibrated), 1.0e-300)
    )
    negative_entries = int(np.count_nonzero(transition < -tolerance))

    nnls_residual = float(
        np.linalg.norm(positive_reconstruction - target_equilibrated)
        / max(np.linalg.norm(target_equilibrated), 1.0e-300)
    )
    return {
        "status": (
            "canonical-positive-closure"
            if negative_entries == 0 and nnls_residual <= tolerance
            else "canonical-positive-closure-failed"
        ),
        "condition_number_equilibrated": float(
            np.linalg.cond(equilibrated)
        ),
        "factorization": factorization,
        "minimum_transition_entry": float(np.min(transition)),
        "negative_transition_entries": negative_entries,
        "unconstrained_relative_residual": residual,
        "nnls_relative_residual": nnls_residual,
    }


def audit_seed61_positive_realization(
    *,
    max_depth: int = 4,
    primes: Sequence[int] = DEFAULT_PRIMES,
    tolerance: float = 1.0e-8,
) -> dict[str, object]:
    """Run the depth-eight Hankel and canonical positive-closure audit."""

    if max_depth > 4:
        raise ValueError("this lightweight audit is capped at depth four")
    atoms = exact_atoms_from_card(
        candidate_card(template="exact5-shear-loop-pair", seed=61)
    )
    if atoms[1] != atoms[0].T:
        raise ArithmeticError("seed 61 is no longer transpose paired")

    memo: dict[tuple[int, ...], sp.Rational] = {}
    profile: list[dict[str, object]] = []
    final_hankel: sp.ImmutableMatrix | None = None
    final_words: tuple[tuple[int, ...], ...] = ()
    for depth in range(max_depth + 1):
        words = binary_words_upto(depth)
        hankel = exact_hankel(atoms, words, words, cache=memo)
        modular_ranks = [rank_mod_prime(hankel, prime) for prime in primes]
        full_rank = max(modular_ranks) == min(hankel.shape)
        entrywise_nonnegative = all(entry >= 0 for entry in hankel)
        profile.append(
            {
                "depth": depth,
                "shape": list(hankel.shape),
                "maximum_word_length": 2 * depth,
                "modular_ranks": modular_ranks,
                "full_rational_rank_certified": full_rank,
                "entrywise_nonnegative": entrywise_nonnegative,
                "nonnegative_rank": (
                    hankel.rows
                    if full_rank
                    and hankel.rows == hankel.cols
                    and entrywise_nonnegative
                    else None
                ),
            }
        )
        final_hankel = hankel
        final_words = words

    assert final_hankel is not None
    checked_words = binary_words_upto(2 * max_depth)
    symmetry_ok = all(
        exact_determinant_weight(atoms, word)
        == exact_determinant_weight(
            atoms,
            transpose_reversal_word(word),
        )
        for word in checked_words
    )
    minimum_weight = min(
        exact_determinant_weight(atoms, word) for word in checked_words
    )

    hankel_float = np.asarray(final_hankel.tolist(), dtype=float)
    closure = []
    for symbol in (0, 1):
        shifted = exact_hankel(
            atoms,
            final_words,
            final_words,
            middle=(symbol,),
            cache=memo,
        )
        shifted_float = np.asarray(shifted.tolist(), dtype=float)
        for factorization in ("identity-left", "identity-right"):
            result = canonical_positive_closure_gate(
                hankel_float,
                shifted_float,
                factorization=factorization,
                tolerance=tolerance,
            )
            result["symbol"] = symbol
            closure.append(result)

    canonical_hit = all(
        result["status"] == "canonical-positive-closure"
        for result in closure
    )
    return {
        "candidate": "exact5-shear-loop-pair-seed-61",
        "series": "f(w)=det(I+B_w)=Tr Gamma(B_w)",
        "hankel_profile": profile,
        "transpose_reversal_symmetry": symmetry_ok,
        "minimum_weight_through_depth": str(minimum_weight),
        "maximum_weight_length": 2 * max_depth,
        "shifted_gate_maximum_weight_length": 2 * max_depth + 1,
        "canonical_closure": closure,
        "status": (
            "canonical-positive-realization-hit"
            if canonical_hit
            else "no-canonical-positive-realization"
        ),
        "scope": (
            "The Hankel ranks are exact.  The closure failure applies only "
            "to the two canonical full-rank NMF gauges, not to every "
            "higher-dimensional positive dilation."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--tolerance", type=float, default=1.0e-8)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = audit_seed61_positive_realization(
        max_depth=args.max_depth,
        tolerance=args.tolerance,
    )
    print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "audit_seed61_positive_realization",
    "binary_words_upto",
    "canonical_positive_closure_gate",
    "exact_determinant_weight",
    "exact_hankel",
    "rank_mod_prime",
    "transpose_reversal_word",
]
