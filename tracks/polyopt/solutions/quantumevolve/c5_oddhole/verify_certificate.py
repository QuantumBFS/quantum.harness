"""Independent exact verifier for the C5 odd-hole certificate.

Checks:
1. Graph consistency with immutable C5 definition
2. Basis validity (square-free subsets through degree 2)
3. Q matrix symmetry and rational entries
4. Affine constraints: <B_l, Q> = -coeff_l + lambda*<B_l, C_h>
5. Q is strictly positive definite (all LDL pivots > 0)
6. Certificate bound = norm(Z) + 2*lambda matches claimed upper_bound
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

try:
    from .problem import EDGES, ODD_HOLE_BOUND, PROBLEM_ID, VERTICES
except ImportError:
    from problem import EDGES, ODD_HOLE_BOUND, PROBLEM_ID, VERTICES

PREFIX = "C5_ODDHOLE_CERT_RESULT="


def _canonical_word(word):
    items = list(word)
    sign = 1
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor - 1] > items[cursor]:
            if tuple(sorted((items[cursor - 1], items[cursor]))) in EDGES:
                sign = -sign
            items[cursor - 1], items[cursor] = items[cursor], items[cursor - 1]
            cursor -= 1
    reduced = []
    for item in items:
        if reduced and reduced[-1] == item:
            reduced.pop()
        else:
            reduced.append(item)
    return sign, sum(1 << item for item in reduced)


def _entry_label(left, right):
    n = len(VERTICES)
    counts = [0] * n
    for index in left + right:
        counts[index] += 1
    sign, mask = _canonical_word(tuple(reversed(left)) + right)
    vertices = tuple(i for i in VERTICES if mask & (1 << i))
    adjoint_sign, _ = _canonical_word(tuple(reversed(vertices)))
    if adjoint_sign < 0:
        return sign, None
    if mask and mask & (mask - 1) == 0:
        counts[mask.bit_length() - 1] += 1
        mask = 0
    return sign, (tuple(counts), mask)


def _parse_fraction(value):
    if not isinstance(value, str):
        raise TypeError("all matrix entries must be rational strings")
    return Fraction(value)


def _ldl_positive(matrix):
    size = len(matrix)
    lower = [[Fraction(int(r == c)) for c in range(size)] for r in range(size)]
    diagonal = []
    for k in range(size):
        pivot = matrix[k][k] - sum(
            lower[k][j] ** 2 * diagonal[j] for j in range(k)
        )
        if pivot <= 0:
            raise ValueError(f"non-positive LDL pivot {k}: {pivot}")
        diagonal.append(pivot)
        for i in range(k + 1, size):
            lower[i][k] = (
                matrix[i][k]
                - sum(lower[i][j] * lower[k][j] * diagonal[j] for j in range(k))
            ) / pivot
    return diagonal


def verify(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("problem_id") != PROBLEM_ID:
        raise ValueError("wrong problem_id")
    graph = payload.get("graph", {})
    if graph.get("vertex_count") != len(VERTICES):
        raise ValueError("wrong vertex count")
    if {tuple(e) for e in graph.get("edges", [])} != EDGES:
        raise ValueError("certificate graph differs from immutable C5")

    basis = tuple(tuple(w) for w in payload["basis"])
    n = len(VERTICES)
    required = {
        subset for deg in range(3) for subset in combinations(range(n), deg)
    }
    if set(basis) != required:
        raise ValueError("basis must be exactly the degree-2 square-free subsets")

    # Parse Q matrix
    raw = payload["Q_matrix"]
    size = len(basis)
    if len(raw) != size or any(len(row) != size for row in raw):
        raise ValueError("Q matrix shape mismatch")
    Q = [[_parse_fraction(v) for v in row] for row in raw]
    if any(Q[r][c] != Q[c][r] for r in range(size) for c in range(r)):
        raise ValueError("Q is not exactly symmetric")

    # Build label groups
    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col])
            if label is not None:
                groups[label].append((row, col, sign))

    # Compute coefficients and C_h contractions
    basis_index = {w: i for i, w in enumerate(basis)}
    normalization = ((0,) * n, 0)
    odd_hole = payload["odd_hole"]
    lam = Fraction(odd_hole["lambda"])

    # Objective coefficients: c_l = sum of B_l diagonal at singleton positions
    obj_diags = {basis_index[(v,)] for v in VERTICES}
    # C_h contractions: <B_l, C_h> = sum of B_l entries at singleton diagonals
    for label, members in groups.items():
        contraction_Q = sum(
            sign * (Q[row][col] if row == col else 2 * Q[row][col])
            for row, col, sign in members
        )
        # coeff_l = number of members at singleton diagonal positions
        obj_coeff = sum(
            sign for row, col, sign in members if row == col and row in obj_diags
        )
        # Ch_l = same as obj_coeff (C_h has 1 at singleton diagonals)
        Ch_l = obj_coeff
        expected = Fraction(-obj_coeff) + lam * Fraction(Ch_l)
        if label == normalization:
            # For normalization: expected = norm_Z + lam*Ch_norm
            # We verify the bound separately
            continue
        if contraction_Q != expected:
            raise ValueError(
                f"affine constraint failed for label {label}: "
                f"{contraction_Q} != {expected}"
            )

    # Verify Q is PD
    pivots = _ldl_positive(Q)

    # Verify certificate bound
    norm_members = groups[normalization]
    norm_Q = sum(
        sign * (Q[row][col] if row == col else 2 * Q[row][col])
        for row, col, sign in norm_members
    )
    # Ch_norm = obj_coeff for normalization label
    Ch_norm = sum(
        sign
        for row, col, sign in norm_members
        if row == col and row in obj_diags
    )
    norm_Z = norm_Q - lam * Fraction(Ch_norm)
    cert_bound = norm_Z + ODD_HOLE_BOUND * lam
    claimed = Fraction(payload["upper_bound"]["fraction"])
    if cert_bound != claimed:
        raise ValueError(
            f"certificate bound mismatch: computed {cert_bound} != claimed {claimed}"
        )

    checked = sum(1 for label in groups if label != normalization)
    return {
        "valid": True,
        "problem_id": PROBLEM_ID,
        "upper_bound_fraction": str(claimed),
        "upper_bound": float(claimed),
        "lambda": str(lam),
        "matrix_size": size,
        "affine_constraints_checked": checked,
        "positive_ldl_pivots": len(pivots),
        "minimum_ldl_pivot": str(min(pivots)),
    }


def main():
    if len(sys.argv) != 2:
        print("usage: verify_certificate.py CERTIFICATE.json", file=sys.stderr)
        return 2
    try:
        result = verify(Path(sys.argv[1]))
    except Exception as exc:
        result = {"valid": False, "error": f"{type(exc).__name__}: {exc}"}
    print(PREFIX + json.dumps(result, sort_keys=True), flush=True)
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
