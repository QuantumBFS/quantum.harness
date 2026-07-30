"""Export exact-rational odd-hole certificate for C5.

Certificate structure:
  beta(C5) <= norm(Z) + 2*lambda
where Q = Z + lambda*C_h is strictly positive definite (exact LDL),
lambda = 3/4 is the rational odd-hole multiplier, and C_h encodes
the odd-hole inequality sum_i <A_i>^2 <= 2 for the pentagon.

Uses the complete degree-2 square-free basis (16x16 moment matrix).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import cvxpy as cp
import numpy as np

try:
    from .problem import EDGES, ODD_HOLE_BOUND, PROBLEM_ID, VERTICES
except ImportError:
    from problem import EDGES, ODD_HOLE_BOUND, PROBLEM_ID, VERTICES

sys.stdout.reconfigure(encoding="utf-8")


def _canonical_word(word, edges):
    items = list(word)
    sign = 1
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor - 1] > items[cursor]:
            if tuple(sorted((items[cursor - 1], items[cursor]))) in edges:
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


def _entry_label(left, right, n, edges):
    counts = [0] * n
    for index in left + right:
        counts[index] += 1
    sign, mask = _canonical_word(tuple(reversed(left)) + right, edges)
    vertices = tuple(i for i in range(n) if mask & (1 << i))
    adjoint_sign, _ = _canonical_word(tuple(reversed(vertices)), edges)
    if adjoint_sign < 0:
        return sign, None
    if mask and mask & (mask - 1) == 0:
        counts[mask.bit_length() - 1] += 1
        mask = 0
    return sign, (tuple(counts), mask)


def _build_model():
    n = len(VERTICES)
    basis = tuple(
        subset
        for size in range(3)
        for subset in combinations(range(n), size)
    )
    groups = defaultdict(list)
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col], n, EDGES)
            if label is not None:
                groups[label].append((row, col, sign))
    labels = tuple(groups)
    matrices = []
    for label in labels:
        matrix = np.zeros((len(basis), len(basis)))
        for row, col, sign in groups[label]:
            matrix[row, col] = sign
            matrix[col, row] = sign
        matrices.append(matrix)
    basis_index = {word: i for i, word in enumerate(basis)}
    objective = np.zeros((len(basis), len(basis)))
    for v in VERTICES:
        objective[basis_index[(v,)], basis_index[(v,)]] = 1.0
    coefficients = np.array([np.sum(objective * m) for m in matrices])
    normalization = labels.index(((0,) * n, 0))
    # Odd-hole matrix C_h
    C_h = np.zeros((len(basis), len(basis)))
    for v in VERTICES:
        C_h[basis_index[(v,)], basis_index[(v,)]] = 1.0
    Ch_contraction = np.array([np.sum(m * C_h) for m in matrices])
    return {
        "basis": basis,
        "groups": groups,
        "labels": labels,
        "matrices": matrices,
        "coefficients": coefficients,
        "normalization": normalization,
        "C_h": C_h,
        "Ch_contraction": Ch_contraction,
    }


def _solve_and_rationalize(model, eps, denom, lam_frac):
    n = len(VERTICES)
    size = len(model["basis"])
    matrices = model["matrices"]
    coefficients = model["coefficients"]
    normalization = model["normalization"]
    C_h = model["C_h"]
    Ch_contraction = model["Ch_contraction"]
    lam_float = float(lam_frac)

    Z = cp.Variable((size, size), symmetric=True)
    margin = cp.Variable()
    Q_var = Z + lam_float * C_h
    constraints = [
        Q_var - margin * np.eye(size) >> 0,
        cp.sum(cp.multiply(matrices[normalization], Z)) <= 0.5 + eps,
    ]
    constraints.extend(
        cp.sum(cp.multiply(matrices[i], Z)) == -coefficients[i]
        for i in range(len(matrices))
        if i != normalization
    )
    prob = cp.Problem(cp.Maximize(margin), constraints)
    prob.solve(
        solver="CLARABEL",
        tol_gap_abs=1e-12,
        tol_gap_rel=1e-12,
        tol_feas=1e-12,
        max_iter=5000,
    )
    if margin.value is None or margin.value <= 0:
        raise RuntimeError(f"No positive margin at eps={eps}")

    Zval = np.array(Z.value, dtype=float)
    Qval = Zval + lam_float * C_h

    # Rationalize Q
    rational_Q = [
        [Fraction(round(float(Qval[r, c]) * denom), denom) for c in range(size)]
        for r in range(size)
    ]
    for r in range(size):
        for c in range(r):
            rational_Q[r][c] = rational_Q[c][r]

    # Exact targets for Q: <B_l, Q> = -coeff_l + lam*<B_l, C_h>
    labels = model["labels"]
    groups = model["groups"]
    exact_targets = []
    for l in range(len(labels)):
        t = Fraction(-int(round(coefficients[l]))) + lam_frac * Fraction(
            int(round(Ch_contraction[l]))
        )
        exact_targets.append(t)
    eps_frac = Fraction(round(eps * denom), denom)
    norm_target = (
        Fraction(1, 2)
        + eps_frac
        + lam_frac * Fraction(int(round(Ch_contraction[normalization])))
    )
    exact_targets[normalization] = norm_target

    # Affine corrections
    for idx, label in enumerate(labels):
        members = groups[label]
        current = sum(
            sign * (rational_Q[row][col] if row == col else 2 * rational_Q[row][col])
            for row, col, sign in members
        )
        row, col, sign = min(members, key=lambda item: 0 if item[0] == item[1] else 1)
        coeff = Fraction(sign if row == col else 2 * sign)
        rational_Q[row][col] += (exact_targets[idx] - current) / coeff
        rational_Q[col][row] = rational_Q[row][col]

    return rational_Q, float(margin.value)


def _exact_ldl(matrix):
    size = len(matrix)
    lower = [[Fraction(int(r == c)) for c in range(size)] for r in range(size)]
    diagonal = []
    for k in range(size):
        pivot = matrix[k][k] - sum(
            lower[k][j] ** 2 * diagonal[j] for j in range(k)
        )
        if pivot <= 0:
            raise ValueError(f"Q not positive definite at pivot {k}: {pivot}")
        diagonal.append(pivot)
        for i in range(k + 1, size):
            lower[i][k] = (
                matrix[i][k]
                - sum(lower[i][j] * lower[k][j] * diagonal[j] for j in range(k))
            ) / pivot
    return diagonal


def _fraction_text(value):
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def export(
    exact_output: Path,
    eps: float = 1e-8,
    denom: int = 10**10,
    lam_frac: Fraction = Fraction(3, 4),
):
    model = _build_model()
    rational_Q, margin = _solve_and_rationalize(model, eps, denom, lam_frac)
    pivots = _exact_ldl(rational_Q)

    # Compute certificate bound
    labels = model["labels"]
    groups = model["groups"]
    normalization = model["normalization"]
    Ch_contraction = model["Ch_contraction"]
    norm_Q = sum(
        sign * (rational_Q[row][col] if row == col else 2 * rational_Q[row][col])
        for row, col, sign in groups[labels[normalization]]
    )
    norm_Z = norm_Q - lam_frac * Fraction(int(round(Ch_contraction[normalization])))
    cert_bound = norm_Z + ODD_HOLE_BOUND * lam_frac

    payload = {
        "schema_version": 1,
        "problem_id": PROBLEM_ID,
        "certificate_type": "exact-rational-odd-hole-sohs",
        "graph": {
            "vertex_count": len(VERTICES),
            "edges": [list(e) for e in sorted(EDGES)],
        },
        "basis": [list(w) for w in model["basis"]],
        "objective": "sum_i <A_i>^2",
        "odd_hole": {
            "vertices": list(VERTICES),
            "bound": ODD_HOLE_BOUND,
            "lambda": _fraction_text(lam_frac),
        },
        "upper_bound": {
            "fraction": _fraction_text(cert_bound),
            "decimal": float(cert_bound),
        },
        "proof_identity": (
            "For every feasible moment matrix M: "
            "trace(Q*M) >= 0 (Q is PD) and "
            "odd-hole inequality sum_i x_i <= 2 holds. "
            "Combined: objective <= norm(Z) + 2*lambda = upper_bound."
        ),
        "Q_matrix": [
            [_fraction_text(v) for v in row] for row in rational_Q
        ],
        "exact_checks": {
            "affine_constraints": True,
            "ldl_positive_pivots": len(pivots),
            "minimum_ldl_pivot": _fraction_text(min(pivots)),
            "rounding_denominator": denom,
        },
        "numeric_provenance": {
            "solver": "Clarabel via CVXPY",
            "interior_margin": margin,
            "hierarchy_order": 2,
            "eps": eps,
        },
    }
    exact_output.parent.mkdir(parents=True, exist_ok=True)
    exact_output.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return payload


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("certificates/c5_oddhole_certificate.json"),
    )
    parser.add_argument("--eps", type=float, default=1e-8)
    parser.add_argument("--denom", type=int, default=10**10)
    args = parser.parse_args()
    payload = export(args.output, args.eps, args.denom)
    print(
        json.dumps(
            {
                "upper_bound": payload["upper_bound"],
                "exact_checks": payload["exact_checks"],
                "output": str(args.output),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
