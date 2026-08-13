"""Fast numerical early-stop screen for the general oddcycle matrix."""

from __future__ import annotations

from itertools import combinations
from math import isfinite

import numpy as np


SCHEMA = "symmetric-oddcycle-discovery-v1"
_GRADE4_GAUGE = np.diag([1.0, 1.0, 1.0, -1.0, 1.0])


def oddcycle_matrix(p: float, q: float, r: float) -> np.ndarray:
    """Return the five-dimensional ``B(p,q,r)`` discovery atom."""

    values = tuple(float(value) for value in (p, q, r))
    if not all(isfinite(value) for value in values):
        raise ValueError("p, q, and r must be finite")
    p_value, q_value, r_value = values
    return np.array(
        [
            [0.0, 0.0, 2.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 2.0, 0.0, p_value, 0.0],
            [0.0, 0.0, 0.0, 1.0, q_value],
            [0.0, 0.0, -r_value, 0.0, 1.0],
        ],
        dtype=float,
    )


def compound_matrix(matrix: np.ndarray, grade: int) -> np.ndarray:
    """Return a numerical exterior-power matrix in lexicographic basis."""

    exact = np.asarray(matrix, dtype=float)
    if exact.ndim != 2 or exact.shape[0] != exact.shape[1]:
        raise ValueError("matrix must be square")
    dimension = exact.shape[0]
    if not isinstance(grade, int) or isinstance(grade, bool):
        raise TypeError("grade must be an integer")
    if not 0 <= grade <= dimension:
        raise ValueError("grade is outside the exterior algebra")
    index_sets = tuple(combinations(range(dimension), grade))
    result = np.empty((len(index_sets), len(index_sets)), dtype=float)
    for row, outputs in enumerate(index_sets):
        for column, inputs in enumerate(index_sets):
            result[row, column] = np.linalg.det(
                exact[np.ix_(outputs, inputs)]
            )
    return result


def _advance(
    level: np.ndarray,
    atoms: tuple[np.ndarray, np.ndarray],
) -> np.ndarray:
    return np.concatenate((atoms[0] @ level, atoms[1] @ level), axis=0)


def _advance_words(words: list[str]) -> list[str]:
    return [word + "0" for word in words] + [
        word + "1" for word in words
    ]


def _failure(
    result: dict[str, object],
    stage: str,
    reason: str,
) -> dict[str, object]:
    result["status"] = "failed"
    result["failure_stage"] = stage
    result["failure_reason"] = reason
    return result


def screen_oddcycle_parameters(
    p: float,
    q: float,
    r: float,
    *,
    short_depth: int = 10,
    determinant_tolerance: float = 1.0e-10,
    entry_tolerance: float = 1.0e-12,
    ratio_tolerance: float = 1.0e-12,
    tail_start: int = 6,
) -> dict[str, object]:
    """Run the fixed-proof exterior gates and stop at the first failure."""

    if (
        not isinstance(short_depth, int)
        or isinstance(short_depth, bool)
        or short_depth < 1
    ):
        raise ValueError("short_depth must be a positive integer")
    if (
        not isinstance(tail_start, int)
        or isinstance(tail_start, bool)
        or tail_start < 1
    ):
        raise ValueError("tail_start must be a positive integer")
    if min(determinant_tolerance, entry_tolerance, ratio_tolerance) < 0.0:
        raise ValueError("tolerances must be nonnegative")

    matrix = oddcycle_matrix(p, q, r)
    atoms = (matrix, matrix.T)
    result: dict[str, object] = {
        "schema": SCHEMA,
        "method": "float64-exterior-early-stop",
        "parameters": {"p": float(p), "q": float(q), "r": float(r)},
        "status": "running",
        "failure_stage": None,
    }

    level = np.eye(5, dtype=float)[None, :, :]
    words = [""]
    minimum = np.inf
    witness = ""
    witness_depth = 0
    word_count = 0
    for depth in range(1, short_depth + 1):
        level = _advance(level, atoms)
        words = _advance_words(words)
        determinants = np.linalg.det(level + np.eye(5, dtype=float))
        if not np.all(np.isfinite(determinants)):
            result["short_words"] = {
                "passed": False,
                "max_depth": short_depth,
                "max_depth_reached": depth,
                "word_count": word_count + len(words),
                "minimum_determinant": float("nan"),
                "witness": "",
                "witness_depth": depth,
            }
            return _failure(
                result,
                "short-word-determinant",
                "a determinant was non-finite",
            )
        local_index = int(np.argmin(determinants))
        local_minimum = float(determinants[local_index])
        word_count += len(words)
        if local_minimum < minimum:
            minimum = local_minimum
            witness = words[local_index]
            witness_depth = depth
        if local_minimum <= determinant_tolerance:
            result["short_words"] = {
                "passed": False,
                "max_depth": short_depth,
                "max_depth_reached": depth,
                "word_count": word_count,
                "minimum_determinant": minimum,
                "witness": witness,
                "witness_depth": witness_depth,
            }
            return _failure(
                result,
                "short-word-determinant",
                "a short-word determinant is not strictly positive",
            )
    result["short_words"] = {
        "passed": True,
        "max_depth": short_depth,
        "max_depth_reached": short_depth,
        "word_count": word_count,
        "minimum_determinant": minimum,
        "witness": witness,
        "witness_depth": witness_depth,
    }

    grade3 = compound_matrix(matrix, 3)
    grade4 = _GRADE4_GAUGE @ compound_matrix(matrix, 4) @ _GRADE4_GAUGE
    grade3_atoms = (grade3, grade3.T)
    grade4_atoms = (grade4, grade4.T)
    grade4_minimum = float(
        min(np.min(atom) for atom in grade4_atoms)
    )
    grade4_passed = grade4_minimum >= -entry_tolerance
    result["grade4_atom_gate"] = {
        "passed": grade4_passed,
        "minimum_entry": grade4_minimum,
        "tolerance": entry_tolerance,
    }
    if not grade4_passed:
        return _failure(
            result,
            "grade4-atom-nonnegative",
            "the fixed sign gauge leaves a negative grade-four entry",
        )

    level3 = np.eye(10, dtype=float)[None, :, :]
    level4 = np.eye(5, dtype=float)[None, :, :]
    words = [""]
    remainder_maximum = 10.0
    remainder_witness = ""
    remainder_witness_depth = 0
    remainder_word_count = 1
    block_maximum = np.inf
    block_witness = ""
    for depth in range(1, 14):
        level3 = _advance(level3, grade3_atoms)
        level4 = _advance(level4, grade4_atoms)
        words = _advance_words(words)
        numerator = np.einsum("bij,bij->b", level3, level3)
        denominator = np.square(level4[:, 0, 0])
        ratios = np.full(numerator.shape, np.inf, dtype=float)
        np.divide(
            numerator,
            denominator,
            out=ratios,
            where=denominator > entry_tolerance**2,
        )
        local_index = int(np.argmax(ratios))
        local_maximum = float(ratios[local_index])
        if depth <= 12:
            remainder_word_count += len(words)
            if local_maximum > remainder_maximum:
                remainder_maximum = local_maximum
                remainder_witness = words[local_index]
                remainder_witness_depth = depth
            if remainder_maximum > 10.0 + ratio_tolerance:
                result["grade34_short_remainder"] = {
                    "passed": False,
                    "max_depth": 12,
                    "max_depth_reached": depth,
                    "word_count": remainder_word_count,
                    "maximum_ratio": remainder_maximum,
                    "required_upper_bound": 10.0,
                    "witness": remainder_witness,
                    "witness_depth": remainder_witness_depth,
                }
                return _failure(
                    result,
                    "grade34-short-remainder",
                    "the short-remainder ratio exceeds 10",
                )
        else:
            block_maximum = local_maximum
            block_witness = words[local_index]

    result["grade34_short_remainder"] = {
        "passed": True,
        "max_depth": 12,
        "max_depth_reached": 12,
        "word_count": remainder_word_count,
        "maximum_ratio": remainder_maximum,
        "required_upper_bound": 10.0,
        "witness": remainder_witness,
        "witness_depth": remainder_witness_depth,
    }
    block_passed = block_maximum < 0.01 - ratio_tolerance
    result["grade34_block"] = {
        "passed": block_passed,
        "length": 13,
        "word_count": 8192,
        "maximum_ratio": block_maximum,
        "required_strict_upper_bound": 0.01,
        "witness": block_witness,
    }
    if not block_passed:
        return _failure(
            result,
            "grade34-13-block",
            "the 13-block grade-three/four ratio is not below 1/100",
        )

    grade2_atoms = tuple(compound_matrix(atom, 2) for atom in atoms)
    grade1_squared_norm = float(
        max(np.linalg.norm(atom, ord=2) ** 2 for atom in atoms)
    )
    grade2_squared_norm = float(
        max(np.linalg.norm(atom, ord=2) ** 2 for atom in grade2_atoms)
    )
    determinant_growth = float(
        min(abs(np.linalg.det(atom)) for atom in atoms)
    )
    grade1_growth_ratio = (
        np.sqrt(grade1_squared_norm) / determinant_growth
        if determinant_growth > 0.0
        else np.inf
    )
    grade2_growth_ratio = (
        np.sqrt(grade2_squared_norm) / determinant_growth
        if determinant_growth > 0.0
        else np.inf
    )
    grade1_bound = 5.0 * grade1_squared_norm ** (tail_start / 2.0)
    grade2_bound = 10.0 * grade2_squared_norm ** (tail_start / 2.0)
    determinant_sector = determinant_growth**tail_start
    strict_margin = determinant_sector - grade1_bound - grade2_bound
    tail_passed = (
        grade1_growth_ratio < 1.0
        and grade2_growth_ratio < 1.0
        and strict_margin > determinant_tolerance
    )
    result["low_sector_norm_tail"] = {
        "passed": tail_passed,
        "tail_start": tail_start,
        "grade1_squared_spectral_norm": grade1_squared_norm,
        "grade2_squared_spectral_norm": grade2_squared_norm,
        "determinant_growth": determinant_growth,
        "grade1_growth_ratio": grade1_growth_ratio,
        "grade2_growth_ratio": grade2_growth_ratio,
        "grade1_bound_at_tail_start": grade1_bound,
        "grade2_bound_at_tail_start": grade2_bound,
        "determinant_sector_at_tail_start": determinant_sector,
        "strict_margin_at_tail_start": strict_margin,
    }
    if not tail_passed:
        return _failure(
            result,
            "low-sector-norm-tail",
            "grade-one/two norm growth does not stay below grade five",
        )

    result["status"] = "passed-all-gates"
    result["failure_stage"] = None
    result["failure_reason"] = None
    return result


__all__ = [
    "SCHEMA",
    "compound_matrix",
    "oddcycle_matrix",
    "screen_oddcycle_parameters",
]
