"""Independent exact verifier for the exported graph-33 rational dual."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

try:
    from .problem import EDGES, PROBLEM_ID, VERTICES
except ImportError:  # Direct script execution.
    from problem import EDGES, PROBLEM_ID, VERTICES

PREFIX = "GRAPH33_EXACT_DUAL_RESULT="


def _canonical_word(word: tuple[int, ...]) -> tuple[int, int]:
    items = list(word)
    sign = 1
    for position in range(1, len(items)):
        cursor = position
        while cursor and items[cursor - 1] > items[cursor]:
            if tuple(sorted((items[cursor - 1], items[cursor]))) in EDGES:
                sign = -sign
            items[cursor - 1], items[cursor] = items[cursor], items[cursor - 1]
            cursor -= 1
    reduced: list[int] = []
    for item in items:
        if reduced and reduced[-1] == item:
            reduced.pop()
        else:
            reduced.append(item)
    return sign, sum(1 << item for item in reduced)


def _entry_label(
    left: tuple[int, ...], right: tuple[int, ...]
) -> tuple[int, tuple[tuple[int, ...], int] | None]:
    counts = [0] * len(VERTICES)
    for index in left + right:
        counts[index] += 1
    sign, mask = _canonical_word(tuple(reversed(left)) + right)
    vertices = tuple(
        index for index in VERTICES if mask & (1 << index)
    )
    adjoint_sign, _ = _canonical_word(tuple(reversed(vertices)))
    if adjoint_sign < 0:
        return sign, None
    if mask and mask & (mask - 1) == 0:
        counts[mask.bit_length() - 1] += 1
        mask = 0
    return sign, (tuple(counts), mask)


def _parse_fraction(value: object) -> Fraction:
    if not isinstance(value, str):
        raise TypeError("all exact matrix entries must be rational strings")
    return Fraction(value)


def _ldl_positive(matrix: list[list[Fraction]]) -> list[Fraction]:
    size = len(matrix)
    lower = [
        [Fraction(int(row == col)) for col in range(size)] for row in range(size)
    ]
    diagonal: list[Fraction] = []
    for row in range(size):
        pivot = matrix[row][row] - sum(
            lower[row][index] ** 2 * diagonal[index] for index in range(row)
        )
        if pivot <= 0:
            raise ValueError(f"non-positive exact LDL pivot {row}: {pivot}")
        diagonal.append(pivot)
        for target_row in range(row + 1, size):
            lower[target_row][row] = (
                matrix[target_row][row]
                - sum(
                    lower[target_row][index]
                    * lower[row][index]
                    * diagonal[index]
                    for index in range(row)
                )
            ) / pivot
    return diagonal


def verify(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("problem_id") != PROBLEM_ID:
        raise ValueError("wrong problem_id")
    graph = payload.get("graph", {})
    if graph.get("vertex_count") != len(VERTICES):
        raise ValueError("wrong vertex count")
    if {tuple(edge) for edge in graph.get("edges", [])} != EDGES:
        raise ValueError("certificate graph differs from immutable graph 33")

    basis = tuple(tuple(word) for word in payload["basis"])
    if len(set(basis)) != len(basis) or () not in basis:
        raise ValueError("basis must be unique and include the empty word")
    required = {
        subset
        for degree in range(3)
        for subset in combinations(VERTICES, degree)
    }
    if not required.issubset(basis):
        raise ValueError("basis is missing a required degree-2 word")
    if any(
        tuple(sorted(word)) != word
        or len(set(word)) != len(word)
        or any(vertex not in VERTICES for vertex in word)
        for word in basis
    ):
        raise ValueError("basis contains an invalid word")

    raw_matrix = payload["dual_matrix"]
    if len(raw_matrix) != len(basis) or any(
        len(row) != len(basis) for row in raw_matrix
    ):
        raise ValueError("dual matrix shape does not match basis")
    matrix = [[_parse_fraction(value) for value in row] for row in raw_matrix]
    if any(
        matrix[row][col] != matrix[col][row]
        for row in range(len(basis))
        for col in range(row)
    ):
        raise ValueError("dual matrix is not exactly symmetric")

    groups: dict[object, list[tuple[int, int, int]]] = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col])
            if label is not None:
                groups[label].append((row, col, sign))
    normalization = ((0,) * len(VERTICES), 0)
    basis_index = {word: index for index, word in enumerate(basis)}
    upper = Fraction(payload["upper_bound"]["fraction"])
    checked = 0
    for label, members in groups.items():
        contraction = sum(
            sign * (matrix[row][col] if row == col else 2 * matrix[row][col])
            for row, col, sign in members
        )
        objective_coefficient = sum(
            sign
            for row, col, sign in members
            if row == col
            and row in {basis_index[(vertex,)] for vertex in VERTICES}
        )
        expected = upper if label == normalization else -objective_coefficient
        if contraction != expected:
            raise ValueError(
                f"dual affine identity failed for label {label}: "
                f"{contraction} != {expected}"
            )
        checked += 1
    pivots = _ldl_positive(matrix)
    return {
        "valid": True,
        "problem_id": PROBLEM_ID,
        "upper_bound_fraction": str(upper),
        "upper_bound": float(upper),
        "matrix_size": len(matrix),
        "affine_constraints_checked": checked,
        "positive_ldl_pivots": len(pivots),
        "minimum_ldl_pivot": str(min(pivots)),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_dual_certificate.py CERTIFICATE.json", file=sys.stderr)
        return 2
    try:
        result = verify(Path(sys.argv[1]))
    except Exception as exc:
        result = {"valid": False, "error": f"{type(exc).__name__}: {exc}"}
    print(PREFIX + json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
